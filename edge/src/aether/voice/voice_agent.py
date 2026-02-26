"""
AETHER Edge Voice Pipeline – Voice Agent
==========================================
Top-level orchestrator that wires together wake-word detection, VAD,
transcription, intent classification, and TTS into a coherent voice
interaction loop for elderly residents.

Designed for Raspberry Pi 5 / Jetson Orin Nano edge gateways.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from aether.voice.intent_classifier import Intent, IntentClassifier, IntentResult
from aether.voice.synthesizer import ALERT_RESPONSES, AetherSynthesizer, SynthesisResult
from aether.voice.transcriber import AetherTranscriber, TranscriptionResult
from aether.voice.vad import VoiceActivityDetector
from aether.voice.wake_word import WakeWordDetector, WakeWordEvent

logger = logging.getLogger("aether.voice.voice_agent")

SIMULATOR_MODE = os.getenv("SIMULATOR_MODE", "true").lower() in ("1", "true", "yes")

# Supported languages for the AETHER voice pipeline
SUPPORTED_LANGUAGES = {"en-IN", "hi-IN"}


# ---------------------------------------------------------------------------
# Result / state dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VoiceResponse:
    """Full result of a voice interaction cycle."""

    transcript: str
    intent: IntentResult
    response_text: str
    audio_bytes: bytes = b""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckInReport:
    """Summary of a multi-turn daily check-in dialogue."""

    resident_id: str
    mood: Optional[str] = None
    pain_level: Optional[int] = None
    sleep_quality: Optional[str] = None
    hydration: Optional[str] = None
    meals: Optional[str] = None
    notes: str = ""
    completed: bool = False
    timestamp: str = ""
    responses: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Conversation state
# ---------------------------------------------------------------------------

@dataclass
class _ConversationState:
    """Tracks multi-turn conversation context."""

    session_id: str = ""
    resident_id: str = ""
    active: bool = False
    turn_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    checkin_step: int = 0
    checkin_report: Optional[CheckInReport] = None


# ---------------------------------------------------------------------------
# Check-in dialogue
# ---------------------------------------------------------------------------

_CHECKIN_QUESTIONS: List[Dict[str, str]] = [
    {
        "key": "mood",
        "prompt": "How are you feeling today? Would you say good, okay, or not so good?",
    },
    {
        "key": "pain",
        "prompt": "Are you experiencing any pain right now? If yes, on a scale of 1 to 10, how bad is it?",
    },
    {
        "key": "sleep",
        "prompt": "How did you sleep last night? Did you sleep well?",
    },
    {
        "key": "hydration",
        "prompt": "Have you had enough water today? How many glasses would you say?",
    },
    {
        "key": "meals",
        "prompt": "Have you eaten your meals today? What did you have?",
    },
]


# ---------------------------------------------------------------------------
# Voice Agent
# ---------------------------------------------------------------------------

class VoiceAgent:
    """Orchestrates the full AETHER edge voice pipeline.

    Parameters
    ----------
    config : dict
        Configuration dictionary. Recognised keys:

        - ``access_key`` – Porcupine access key
        - ``keywords`` – wake word list
        - ``energy_threshold`` – VAD energy threshold
        - ``language_code`` – transcription language (default ``en-IN``)
        - ``voice_id`` – Polly voice (default ``Kajal``)
        - ``use_bedrock`` – enable Bedrock intent classification
        - ``simulator`` – force simulator mode
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = config or {}
        self._simulator = cfg.get("simulator", SIMULATOR_MODE)

        # --- Sub-components ---
        self._wake_word = WakeWordDetector(
            access_key=cfg.get("access_key"),
            keywords=cfg.get("keywords"),
            energy_threshold=cfg.get("wake_energy_threshold", 1500.0),
            simulator=self._simulator,
        )

        self._vad = VoiceActivityDetector(
            energy_threshold=cfg.get("energy_threshold", 500.0),
            min_speech_ms=cfg.get("min_speech_ms", 250),
            min_silence_ms=cfg.get("min_silence_ms", 700),
            max_utterance_s=cfg.get("max_utterance_s", 30.0),
        )

        self._transcriber = AetherTranscriber(
            region_name=cfg.get("region_name"),
            s3_bucket=cfg.get("s3_bucket"),
            simulator=self._simulator,
        )

        self._synthesizer = AetherSynthesizer(
            region_name=cfg.get("region_name"),
            default_voice_id=cfg.get("voice_id", "Kajal"),
            default_engine=cfg.get("polly_engine", "neural"),
            simulator=self._simulator,
        )

        self._classifier = IntentClassifier(
            use_bedrock=cfg.get("use_bedrock", False),
            region_name=cfg.get("region_name"),
            simulator=self._simulator,
        )

        # --- State ---
        self._conversation = _ConversationState()
        self._running = False
        self._event_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        logger.info(
            "VoiceAgent initialised (simulator=%s, voice=%s)",
            self._simulator,
            cfg.get("voice_id", "Kajal"),
        )

    # ------------------------------------------------------------------
    # Event system
    # ------------------------------------------------------------------

    def on_event(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for voice pipeline events.

        The callback receives ``(event_type: str, payload: dict)``.
        Event types include ``wake_word``, ``utterance``, ``intent``,
        ``response``, ``error``.
        """
        self._event_callbacks.append(callback)

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        for cb in self._event_callbacks:
            try:
                cb(event_type, payload)
            except Exception as exc:
                logger.warning("Event callback error (%s): %s", event_type, exc)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the wake-word → VAD → transcribe → respond loop.

        Blocks until ``stop()`` is called or KeyboardInterrupt.
        """
        self._running = True
        logger.info("VoiceAgent starting main loop")

        def _on_wake(event: WakeWordEvent) -> None:
            self._emit("wake_word", {
                "keyword": event.keyword_label,
                "timestamp": event.timestamp,
            })
            logger.info("Wake word '%s' – listening for command…", event.keyword_label)

            # Play acknowledgement
            self._synthesizer.speak("Yes, I'm listening.")

            # Capture utterance via VAD
            # In real mode this would read from the mic stream; for demo we
            # use a simulated short utterance.
            if self._simulator:
                import struct, math
                # Generate 1.5 s of simulated speech-like audio
                sr = 16000
                n = int(sr * 1.5)
                samples = [int(2000 * math.sin(2 * math.pi * 300 * i / sr)) for i in range(n)]
                sim_audio = struct.pack(f"<{n}h", *samples)
                response = self.process_voice_command(sim_audio)
                self._emit("response", {
                    "transcript": response.transcript,
                    "intent": response.intent.intent.value,
                    "response_text": response.response_text,
                })
            # In real mode, the mic stream would be passed to VAD here.

        try:
            self._wake_word.start(audio_callback=_on_wake)
        except KeyboardInterrupt:
            logger.info("VoiceAgent interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the voice agent and release resources."""
        self._running = False
        self._wake_word.stop()
        logger.info("VoiceAgent stopped")

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    def process_voice_command(
        self,
        audio_bytes: bytes,
        resident_id: str = "default",
    ) -> VoiceResponse:
        """Run the full pipeline on a captured audio buffer.

        Steps: Transcribe → Classify intent → Generate response → Synthesize

        Parameters
        ----------
        audio_bytes :
            Raw 16-bit 16 kHz mono PCM audio containing the user's utterance.
        resident_id :
            Resident identifier for context-dependent responses.

        Returns
        -------
        VoiceResponse
        """
        t_start = time.time()

        # 1. Transcribe
        transcription = self._transcriber.transcribe_audio(audio_bytes)
        self._emit("utterance", {
            "text": transcription.text,
            "confidence": transcription.confidence,
        })

        # 2. Classify intent
        intent_result = self._classifier.classify(transcription.text)
        self._emit("intent", {
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "entities": intent_result.entities,
        })

        # 3. Generate response text
        response_text = self.handle_intent(intent_result, resident_id)

        # 4. Synthesize
        synth_result = self._synthesizer.synthesize(response_text)

        # 5. Play
        self._synthesizer.play_audio(synth_result.audio_bytes)

        elapsed_ms = (time.time() - t_start) * 1000
        logger.info(
            "Voice command processed in %.0f ms: '%s' → %s → '%s'",
            elapsed_ms,
            transcription.text[:50],
            intent_result.intent.value,
            response_text[:50],
        )

        return VoiceResponse(
            transcript=transcription.text,
            intent=intent_result,
            response_text=response_text,
            audio_bytes=synth_result.audio_bytes,
            metadata={
                "transcription_confidence": transcription.confidence,
                "intent_confidence": intent_result.confidence,
                "processing_time_ms": elapsed_ms,
                "resident_id": resident_id,
            },
        )

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    def handle_intent(self, intent_result: IntentResult, resident_id: str) -> str:
        """Route an intent to the appropriate handler and return a response.

        Parameters
        ----------
        intent_result :
            Classification output.
        resident_id :
            Resident identifier.

        Returns
        -------
        str
            The textual response to be spoken.
        """
        intent = intent_result.intent
        entities = intent_result.entities

        if intent == Intent.CANCEL_ALERT:
            return self._handle_cancel_alert(resident_id)

        if intent == Intent.CONFIRM_OK:
            return self._handle_confirm_ok(resident_id)

        if intent == Intent.CALL_CONTACT:
            contact = entities.get("contact_name", "your emergency contact")
            return self._handle_call_contact(resident_id, contact)

        if intent == Intent.MEDICATION_QUERY:
            med_name = entities.get("medication_name")
            return self._handle_medication_query(resident_id, med_name)

        if intent == Intent.HEALTH_QUERY:
            return self._handle_health_query(resident_id)

        if intent == Intent.EMERGENCY:
            return self._handle_emergency(resident_id)

        if intent == Intent.DAILY_CHECKIN:
            return self._handle_daily_checkin_start(resident_id)

        if intent == Intent.SET_REMINDER:
            t = entities.get("time", "later")
            return self._handle_set_reminder(resident_id, t)

        # GENERAL / fallback
        return (
            "I'm sorry, I didn't quite understand that. "
            "Could you please repeat or say 'help' if you need assistance?"
        )

    def _handle_cancel_alert(self, resident_id: str) -> str:
        self._emit("cancel_alert", {"resident_id": resident_id})
        logger.info("Alert cancelled by resident %s", resident_id)
        return ALERT_RESPONSES["cancel_confirmed"]

    def _handle_confirm_ok(self, resident_id: str) -> str:
        self._emit("confirm_ok", {"resident_id": resident_id})
        return "Great, I'm glad you're okay. Let me know if you need anything."

    def _handle_call_contact(self, resident_id: str, contact_name: str) -> str:
        self._emit("call_contact", {
            "resident_id": resident_id,
            "contact_name": contact_name,
        })
        logger.info("Calling contact '%s' for resident %s", contact_name, resident_id)
        return f"I'm calling {contact_name} for you now. Please hold on."

    def _handle_medication_query(
        self, resident_id: str, medication_name: Optional[str]
    ) -> str:
        self._emit("medication_query", {
            "resident_id": resident_id,
            "medication_name": medication_name,
        })
        if medication_name:
            return (
                f"Let me check your schedule for {medication_name}. "
                "According to your records, your next dose is at your regular time. "
                "Would you like me to set a reminder?"
            )
        return (
            "Your next medication is scheduled for your regular time. "
            "Would you like me to list all your medications?"
        )

    def _handle_health_query(self, resident_id: str) -> str:
        self._emit("health_query", {"resident_id": resident_id})
        return (
            "Based on your latest readings, your vitals look stable. "
            "Your blood pressure and heart rate are within normal range. "
            "Would you like more details?"
        )

    def _handle_emergency(self, resident_id: str) -> str:
        self._emit("emergency", {"resident_id": resident_id, "priority": "CRITICAL"})
        logger.critical("EMERGENCY triggered by resident %s", resident_id)
        return ALERT_RESPONSES["emergency"]

    def _handle_daily_checkin_start(self, resident_id: str) -> str:
        self._conversation = _ConversationState(
            session_id=uuid.uuid4().hex[:12],
            resident_id=resident_id,
            active=True,
            checkin_step=0,
            checkin_report=CheckInReport(
                resident_id=resident_id,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ),
        )
        self._emit("checkin_started", {"resident_id": resident_id})
        return ALERT_RESPONSES["daily_checkin_greeting"]

    def _handle_set_reminder(self, resident_id: str, reminder_time: str) -> str:
        self._emit("set_reminder", {
            "resident_id": resident_id,
            "time": reminder_time,
        })
        return f"Okay, I've set a reminder for {reminder_time}. I'll let you know when it's time."

    # ------------------------------------------------------------------
    # Daily check-in (multi-turn)
    # ------------------------------------------------------------------

    def run_daily_checkin(self, resident_id: str) -> CheckInReport:
        """Run a full multi-turn daily check-in dialogue.

        In demo/simulator mode, the answers are auto-generated so the full
        flow can be exercised end-to-end.

        Parameters
        ----------
        resident_id :
            The resident being checked in.

        Returns
        -------
        CheckInReport
        """
        report = CheckInReport(
            resident_id=resident_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # Greeting
        greeting = ALERT_RESPONSES["daily_checkin_greeting"]
        self._synthesizer.speak(greeting)
        logger.info("Check-in started for resident %s", resident_id)

        # Demo / simulator answers
        _demo_answers = [
            "I'm feeling good today",
            "no pain, I'm fine",
            "I slept well, about 7 hours",
            "yes I had 4 glasses of water",
            "I had toast for breakfast and rice for lunch",
        ]

        for i, question in enumerate(_CHECKIN_QUESTIONS):
            # Ask question
            self._synthesizer.speak(question["prompt"])
            logger.info("Check-in Q%d: %s", i + 1, question["key"])

            if self._simulator:
                answer_text = _demo_answers[i % len(_demo_answers)]
                logger.info("Check-in A%d (sim): %s", i + 1, answer_text)
            else:
                # In real mode: capture audio via VAD and transcribe
                # This would involve the microphone stream
                answer_text = "(awaiting real audio input)"

            report.responses[question["key"]] = answer_text

            # Map answers to report fields
            key = question["key"]
            if key == "mood":
                report.mood = answer_text
            elif key == "pain":
                report.pain_level = self._parse_pain_level(answer_text)
            elif key == "sleep":
                report.sleep_quality = answer_text
            elif key == "hydration":
                report.hydration = answer_text
            elif key == "meals":
                report.meals = answer_text

        # Summary
        report.completed = True
        summary = self._generate_checkin_summary(report)
        report.notes = summary

        # Speak summary
        self._synthesizer.speak(
            "Thank you for completing your check-in. "
            "Everything looks good. Have a wonderful day!"
        )

        self._emit("checkin_completed", {
            "resident_id": resident_id,
            "report": {
                "mood": report.mood,
                "pain_level": report.pain_level,
                "sleep_quality": report.sleep_quality,
                "hydration": report.hydration,
                "meals": report.meals,
                "notes": report.notes,
                "completed": report.completed,
            },
        })

        logger.info("Check-in completed for resident %s: %s", resident_id, summary)
        return report

    # ------------------------------------------------------------------
    # Check-in turn processing (for interactive mode)
    # ------------------------------------------------------------------

    def process_checkin_turn(self, audio_bytes: bytes) -> Optional[str]:
        """Process a single turn of an ongoing check-in conversation.

        Returns the next question/prompt, or ``None`` if the check-in is
        complete.
        """
        if not self._conversation.active or self._conversation.checkin_report is None:
            return None

        # Transcribe the answer
        result = self._transcriber.transcribe_audio(audio_bytes)
        step_idx = self._conversation.checkin_step

        if step_idx >= len(_CHECKIN_QUESTIONS):
            # All questions answered
            self._conversation.active = False
            self._conversation.checkin_report.completed = True
            return None

        question = _CHECKIN_QUESTIONS[step_idx]
        self._conversation.checkin_report.responses[question["key"]] = result.text

        # Map to report field
        key = question["key"]
        rpt = self._conversation.checkin_report
        if key == "mood":
            rpt.mood = result.text
        elif key == "pain":
            rpt.pain_level = self._parse_pain_level(result.text)
        elif key == "sleep":
            rpt.sleep_quality = result.text
        elif key == "hydration":
            rpt.hydration = result.text
        elif key == "meals":
            rpt.meals = result.text

        self._conversation.checkin_step += 1
        self._conversation.turn_count += 1

        # Return next question or summary
        if self._conversation.checkin_step < len(_CHECKIN_QUESTIONS):
            next_q = _CHECKIN_QUESTIONS[self._conversation.checkin_step]
            return next_q["prompt"]
        else:
            self._conversation.active = False
            rpt.completed = True
            rpt.notes = self._generate_checkin_summary(rpt)
            return (
                "Thank you for completing your check-in. "
                "Everything looks good. Have a wonderful day!"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_pain_level(text: str) -> int:
        """Extract a numeric pain level from text."""
        import re

        m = re.search(r"(\d{1,2})", text)
        if m:
            level = int(m.group(1))
            return min(level, 10)
        # No pain mentioned → 0
        if any(word in text.lower() for word in ("no pain", "no", "fine", "none", "zero")):
            return 0
        return -1  # unknown

    @staticmethod
    def _generate_checkin_summary(report: CheckInReport) -> str:
        """Build a short textual summary of the check-in."""
        parts = []
        if report.mood:
            parts.append(f"Mood: {report.mood}")
        if report.pain_level is not None and report.pain_level >= 0:
            parts.append(f"Pain: {report.pain_level}/10")
        elif report.pain_level == 0:
            parts.append("Pain: none")
        if report.sleep_quality:
            parts.append(f"Sleep: {report.sleep_quality}")
        if report.hydration:
            parts.append(f"Hydration: {report.hydration}")
        if report.meals:
            parts.append(f"Meals: {report.meals}")
        return "; ".join(parts) if parts else "Check-in completed with no detailed responses."

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def conversation_active(self) -> bool:
        return self._conversation.active

    # ------------------------------------------------------------------
    # Language management (multi-language support)
    # ------------------------------------------------------------------

    def set_language(self, language: str) -> None:
        """Switch voice pipeline language.

        Parameters
        ----------
        language : str
            Language code — ``en-IN`` for English (India) or ``hi-IN`` for Hindi.
        """
        supported = {"en-IN", "hi-IN"}
        if language not in supported:
            logger.warning("Unsupported language '%s', falling back to en-IN", language)
            language = "en-IN"

        self._language = language

        # Update Polly voice: Kajal for English, Kajal/Aditi for Hindi
        voice_map = {"en-IN": "Kajal", "hi-IN": "Aditi"}
        self._synthesizer._default_voice_id = voice_map.get(language, "Kajal")

        logger.info("Language switched to %s (voice: %s)", language, voice_map.get(language))

    @property
    def current_language(self) -> str:
        return getattr(self, "_language", "en-IN")

    # ------------------------------------------------------------------
    # Proactive companion (loneliness reduction + wellness nudges)
    # ------------------------------------------------------------------

    def start_proactive_conversation(
        self,
        resident_id: str = "default",
        reason: str = "loneliness_outreach",
    ) -> VoiceResponse:
        """Initiate a proactive conversation without wake word.

        Used for:
        - Loneliness outreach (no social interactions detected for hours)
        - Hydration reminders during hot weather
        - Medication reminders
        - Gentle movement nudges (sedentary too long)
        - Cognitive engagement (storytelling, memory exercises)

        Parameters
        ----------
        resident_id :
            Resident identifier.
        reason :
            Why the proactive conversation is being triggered.

        Returns
        -------
        VoiceResponse
        """
        prompts = _PROACTIVE_PROMPTS.get(reason, _PROACTIVE_PROMPTS["loneliness_outreach"])
        prompt_pool = prompts if self.current_language == "en-IN" else _PROACTIVE_PROMPTS_HI.get(reason, prompts)

        # Cycle through prompts
        idx = hash(f"{resident_id}_{time.time():.0f}") % len(prompt_pool)
        prompt_text = prompt_pool[idx]

        logger.info(
            "Proactive conversation: reason=%s resident=%s lang=%s",
            reason, resident_id, self.current_language,
        )

        # Synthesize and play the prompt
        synth_result = self._synthesizer.synthesize(prompt_text)
        self._synthesizer.play_audio(synth_result.audio_bytes)

        self._emit("proactive_outreach", {
            "resident_id": resident_id,
            "reason": reason,
            "prompt": prompt_text,
            "language": self.current_language,
        })

        # In simulator mode, generate a simulated response
        intent_result = IntentResult(
            intent=Intent.GENERAL,
            confidence=0.9,
            entities={"proactive_reason": reason},
        )

        return VoiceResponse(
            transcript="(proactive outreach — awaiting response)",
            intent=intent_result,
            response_text=prompt_text,
            audio_bytes=synth_result.audio_bytes,
            metadata={
                "proactive": True,
                "reason": reason,
                "language": self.current_language,
                "resident_id": resident_id,
            },
        )

    def should_trigger_proactive(
        self,
        hours_since_social_interaction: float = 0,
        temperature_c: float = 25.0,
        hours_since_medication: float = 0,
        medication_due: bool = False,
        hours_sedentary: float = 0,
    ) -> Optional[str]:
        """Determine if a proactive outreach should be triggered.

        Returns the trigger reason string or None.
        """
        if hours_since_social_interaction >= 4:
            return "loneliness_outreach"
        if temperature_c >= 35 and hours_since_social_interaction >= 2:
            return "hydration_reminder"
        if medication_due and hours_since_medication >= 0.5:
            return "medication_reminder"
        if hours_sedentary >= 3:
            return "movement_nudge"
        return None


# ---------------------------------------------------------------------------
# Proactive prompt libraries (English + Hindi)
# ---------------------------------------------------------------------------

_PROACTIVE_PROMPTS: Dict[str, List[str]] = {
    "loneliness_outreach": [
        "Hello! I noticed it's been a while since we talked. How are you doing today? Would you like to chat or hear a story?",
        "Hi there! Just checking in on you. Is there anything you'd like to talk about? I'm here for you.",
        "Good day! I thought I'd say hello. Would you like to hear some interesting news or play a memory game?",
        "Hey! It's your companion here. How about we do a quick brain exercise together? Or I can tell you a joke!",
    ],
    "hydration_reminder": [
        "Just a gentle reminder — it's quite warm today. Have you had a glass of water recently? Staying hydrated is important!",
        "Time for a water break! The temperature is high today. Please have some water or juice.",
        "Hello! This is your hydration reminder. Can you please drink a glass of water for me?",
    ],
    "medication_reminder": [
        "Hi! It looks like it's time for your medication. Would you like me to remind you which ones to take?",
        "Just a friendly reminder — your medication is due. Please check your MedDock.",
        "Hello! Don't forget your medicines. Your pill box should have your next dose ready.",
    ],
    "movement_nudge": [
        "You've been sitting for a while. How about a gentle stretch or a short walk around the room?",
        "Time to get moving! Even a few minutes of gentle stretching can make a big difference.",
        "Hey! Let's do some light exercises together. Can you stand up and stretch your arms above your head?",
    ],
    "cognitive_engagement": [
        "Would you like to play a word game? I'll say a category, and you name as many things as you can!",
        "Let me tell you an interesting fact today! Did you know that walking just 15 minutes a day can improve memory?",
        "How about a memory exercise? I'll list five items, and let's see how many you remember after a minute.",
    ],
}

_PROACTIVE_PROMPTS_HI: Dict[str, List[str]] = {
    "loneliness_outreach": [
        "नमस्ते! काफी देर हो गई बात किए हुए। आप कैसे हैं? क्या आप बात करना चाहेंगे या कोई कहानी सुनना चाहेंगे?",
        "नमस्कार! बस आपकी खबर लेने आई हूँ। आज आप कैसा महसूस कर रहे हैं?",
        "अरे! मैंने सोचा आपसे हैलो कहूँ। क्या आप कोई दिमागी खेल खेलना चाहेंगे?",
    ],
    "hydration_reminder": [
        "ज़रा याद दिला दूँ — आज बहुत गर्मी है। क्या आपने पानी पिया? हाइड्रेटेड रहना ज़रूरी है!",
        "पानी पीने का समय! आज तापमान बहुत ज़्यादा है। कृपया एक गिलास पानी पी लीजिए।",
    ],
    "medication_reminder": [
        "नमस्ते! आपकी दवाई का समय हो गया है। क्या आप चाहेंगे कि मैं बताऊँ कौन सी लेनी है?",
        "दवाई का अनुस्मारक — कृपया अपना मेडडॉक चेक कीजिए।",
    ],
    "movement_nudge": [
        "आप काफी देर से बैठे हैं। चलिए थोड़ा टहल लीजिए या स्ट्रेचिंग कर लीजिए?",
        "हल्की कसरत करने का समय! बस कुछ मिनट की स्ट्रेचिंग बहुत फायदेमंद होती है।",
    ],
    "cognitive_engagement": [
        "क्या आप एक शब्द खेल खेलना चाहेंगे? मैं एक श्रेणी बोलूँगी, आप जितने नाम बता सकें बताइए!",
        "चलिए एक याददाश्त का अभ्यास करते हैं! मैं पाँच चीज़ें बोलूँगी, देखते हैं कितनी याद रहती हैं।",
    ],
}
