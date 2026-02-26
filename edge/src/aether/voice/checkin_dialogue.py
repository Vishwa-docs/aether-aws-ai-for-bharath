"""
AETHER Daily Check-In Dialogue System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A multi-turn dialogue manager for daily wellness check-ins with elderly
residents.  Designed to be warm, patient, and respectful — like a caring
companion, not a clinical questionnaire.

Features
--------
* Pre-scripted, elder-friendly questions for each wellness domain
* Time-of-day-aware greetings that reference the resident by name
* Lightweight NLU parsing (mood keywords, number extraction, yes/no, etc.)
* Wellness scoring algorithm (0–100) aggregating all domains
* Follow-up questions when concerning answers are detected
* Optional AWS Bedrock integration for richer AI insights
* Report generation suitable for DynamoDB / timeline storage
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums & data models
# ---------------------------------------------------------------------------

class CheckInStep(Enum):
    GREETING = "greeting"
    MOOD = "mood"
    PAIN = "pain"
    SLEEP = "sleep"
    HYDRATION = "hydration"
    MEALS = "meals"
    MEDICATION = "medication"
    ACTIVITY = "activity"
    CONCERNS = "concerns"
    SUMMARY = "summary"
    COMPLETE = "complete"


# The ordered list of steps (GREETING is the entry point; COMPLETE is terminal)
_STEP_ORDER: list[CheckInStep] = [
    CheckInStep.GREETING,
    CheckInStep.MOOD,
    CheckInStep.PAIN,
    CheckInStep.SLEEP,
    CheckInStep.HYDRATION,
    CheckInStep.MEALS,
    CheckInStep.MEDICATION,
    CheckInStep.ACTIVITY,
    CheckInStep.CONCERNS,
    CheckInStep.SUMMARY,
    CheckInStep.COMPLETE,
]


@dataclass
class CheckInSession:
    """Represents an in-progress or completed check-in session."""
    session_id: str
    resident_id: str
    resident_name: str
    current_step: CheckInStep
    responses: Dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    ai_insights: List[str] = field(default_factory=list)
    follow_ups_asked: List[str] = field(default_factory=list)
    previous_sessions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DialogueTurn:
    """A single dialogue turn presented to the resident."""
    step: CheckInStep
    question: str
    response_type: str  # "free_text", "scale_1_10", "yes_no", "multiple_choice"
    options: List[str] = field(default_factory=list)
    follow_up: Optional[str] = None
    is_follow_up: bool = False


# ---------------------------------------------------------------------------
# Pre-scripted question bank
# ---------------------------------------------------------------------------

_GREETINGS_MORNING = [
    "Good morning, {name}! I hope you had a restful night. Ready for our little chat?",
    "Good morning, {name}. It's lovely to see you today. Shall we do a quick check-in?",
    "Rise and shine, {name}! How about we take a few minutes to see how you're doing?",
]

_GREETINGS_AFTERNOON = [
    "Good afternoon, {name}! How's your day going so far? Let's have a quick check-in.",
    "Hello, {name}! Hope you're having a pleasant afternoon. Time for our daily chat.",
    "Hi there, {name}. Good afternoon! Let's go through a few questions together.",
]

_GREETINGS_EVENING = [
    "Good evening, {name}. Winding down for the day? Let's chat for just a moment.",
    "Hello, {name}! Hope your day was good. Let's do a quick evening check-in.",
    "Good evening, {name}. Before you relax for the night, let's have a little chat.",
]

_QUESTIONS: Dict[CheckInStep, DialogueTurn] = {
    CheckInStep.MOOD: DialogueTurn(
        step=CheckInStep.MOOD,
        question="How are you feeling today, {name}? You can say things like 'pretty good', 'okay', or 'not so great' — whatever feels right.",
        response_type="free_text",
    ),
    CheckInStep.PAIN: DialogueTurn(
        step=CheckInStep.PAIN,
        question="Are you experiencing any pain or discomfort right now? If so, on a scale of 1 to 10 — where 1 is very mild and 10 is severe — how would you rate it?",
        response_type="scale_1_10",
    ),
    CheckInStep.SLEEP: DialogueTurn(
        step=CheckInStep.SLEEP,
        question="How did you sleep last night? Did you sleep well, or was it a rough night?",
        response_type="free_text",
    ),
    CheckInStep.HYDRATION: DialogueTurn(
        step=CheckInStep.HYDRATION,
        question="Have you been drinking enough water today? About how many glasses or cups have you had?",
        response_type="free_text",
    ),
    CheckInStep.MEALS: DialogueTurn(
        step=CheckInStep.MEALS,
        question="What about meals — have you eaten today? How's your appetite been?",
        response_type="free_text",
    ),
    CheckInStep.MEDICATION: DialogueTurn(
        step=CheckInStep.MEDICATION,
        question="Have you taken all your medications today?",
        response_type="yes_no",
    ),
    CheckInStep.ACTIVITY: DialogueTurn(
        step=CheckInStep.ACTIVITY,
        question="Have you been able to move around today — maybe a short walk or some light activity?",
        response_type="free_text",
    ),
    CheckInStep.CONCERNS: DialogueTurn(
        step=CheckInStep.CONCERNS,
        question="Is there anything else on your mind, {name}? Anything you'd like to share or any concerns?",
        response_type="free_text",
    ),
}

# Follow-up questions triggered by concerning answers
_FOLLOW_UPS: Dict[str, Dict[str, DialogueTurn]] = {
    "mood_bad": {
        "key": "mood_follow_up",
        "turn": DialogueTurn(
            step=CheckInStep.MOOD,
            question="I'm sorry to hear that, {name}. Can you tell me a little more about what's bothering you?",
            response_type="free_text",
            is_follow_up=True,
        ),
    },
    "pain_high": {
        "key": "pain_follow_up",
        "turn": DialogueTurn(
            step=CheckInStep.PAIN,
            question="That sounds uncomfortable. Can you tell me where the pain is and what it feels like — sharp, dull, throbbing?",
            response_type="free_text",
            is_follow_up=True,
        ),
    },
    "sleep_poor": {
        "key": "sleep_follow_up",
        "turn": DialogueTurn(
            step=CheckInStep.SLEEP,
            question="I'm sorry you didn't sleep well. Was there anything keeping you up — pain, worries, noise?",
            response_type="free_text",
            is_follow_up=True,
        ),
    },
    "medication_no": {
        "key": "medication_follow_up",
        "turn": DialogueTurn(
            step=CheckInStep.MEDICATION,
            question="That's important to keep track of. Is there a reason you missed them — did you forget, or is something else going on?",
            response_type="free_text",
            is_follow_up=True,
        ),
    },
    "hydration_low": {
        "key": "hydration_follow_up",
        "turn": DialogueTurn(
            step=CheckInStep.HYDRATION,
            question="Staying hydrated is really important. Could you try to have a glass of water now? Is there a reason you haven't been drinking much?",
            response_type="free_text",
            is_follow_up=True,
        ),
    },
    "meals_poor": {
        "key": "meals_follow_up",
        "turn": DialogueTurn(
            step=CheckInStep.MEALS,
            question="Eating well is so important. Is there a reason you haven't been eating much — not feeling hungry, or is something else going on?",
            response_type="free_text",
            is_follow_up=True,
        ),
    },
}

# ---------------------------------------------------------------------------
# NLU helpers
# ---------------------------------------------------------------------------

_POSITIVE_MOOD = re.compile(
    r"\b(good|great|wonderful|fine|happy|fantastic|excellent|well|okay|ok|alright|"
    r"not bad|pretty good|can't complain|doing well|cheerful|bright|blessed|thankful)\b",
    re.IGNORECASE,
)
_NEGATIVE_MOOD = re.compile(
    r"\b(bad|awful|terrible|sad|depressed|anxious|worried|down|lonely|miserable|"
    r"horrible|not good|not great|rough|low|upset|unhappy|frustrated|angry|scared)\b",
    re.IGNORECASE,
)
_NEUTRAL_MOOD = re.compile(
    r"\b(so-so|meh|average|mediocre|same|nothing special|fair|moderate)\b",
    re.IGNORECASE,
)

_NUMBER_WORDS = {
    "zero": 0, "none": 0, "no": 0, "one": 1, "two": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "a couple": 2, "couple": 2,
    "few": 3, "a few": 3, "several": 4, "half a dozen": 6, "a dozen": 12,
}

_YES_PATTERN = re.compile(
    r"\b(yes|yeah|yep|yup|sure|absolutely|of course|certainly|affirmative|"
    r"definitely|indeed|uh-huh|right|correct|took them|taken|did|have)\b",
    re.IGNORECASE,
)
_NO_PATTERN = re.compile(
    r"\b(no|nope|nah|not yet|haven't|didn't|forgot|missed|skip|none)\b",
    re.IGNORECASE,
)

_PAIN_LOCATION = re.compile(
    r"\b(head|back|knee|hip|shoulder|chest|stomach|abdomen|leg|arm|neck|"
    r"joint|ankle|wrist|foot|feet|hand|tooth|teeth|eye|ear)\b",
    re.IGNORECASE,
)
_PAIN_TYPE = re.compile(
    r"\b(sharp|dull|throbbing|aching|burning|stinging|stabbing|cramping|"
    r"tight|pressure|sore|tender|shooting|tingling|numb)\b",
    re.IGNORECASE,
)

_SLEEP_GOOD = re.compile(
    r"\b(well|good|great|fine|solid|deep|sound|peaceful|restful|wonderful|"
    r"slept like a log|slept like a baby|perfectly|8 hours|nine hours|7 hours)\b",
    re.IGNORECASE,
)
_SLEEP_BAD = re.compile(
    r"\b(bad|poor|terrible|awful|rough|tossed|turned|insomnia|couldn't sleep|"
    r"woke up|restless|barely|hardly|nightmare|interrupted|pain kept me)\b",
    re.IGNORECASE,
)


def _extract_number(text: str) -> Optional[int]:
    """Extract a numeric value from text (digit or written number)."""
    # Try digit extraction first
    match = re.search(r"\b(\d{1,2})\b", text)
    if match:
        return int(match.group(1))
    # Try word-based numbers
    text_lower = text.lower()
    for word, val in sorted(_NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
        if word in text_lower:
            return val
    return None


def _detect_yes_no(text: str) -> Optional[bool]:
    """Detect yes/no intent from free text."""
    yes = bool(_YES_PATTERN.search(text))
    no = bool(_NO_PATTERN.search(text))
    if yes and not no:
        return True
    if no and not yes:
        return False
    # Ambiguous — fall back to None
    return None


# ---------------------------------------------------------------------------
# CheckInDialogue — main dialogue manager
# ---------------------------------------------------------------------------

class CheckInDialogue:
    """Multi-turn daily check-in dialogue manager.

    Parameters
    ----------
    use_bedrock : bool
        When True, attempt to call AWS Bedrock (Claude) for dynamic
        follow-up questions and richer AI insights.  Falls back to
        rule-based when the API is unavailable.
    bedrock_model_id : str
        The Bedrock model identifier to invoke.
    """

    def __init__(
        self,
        *,
        use_bedrock: bool = False,
        bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
    ):
        self.use_bedrock = use_bedrock
        self.bedrock_model_id = bedrock_model_id
        self._bedrock_client = None

        if self.use_bedrock:
            try:
                import boto3
                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=os.environ.get("AWS_REGION", "us-east-1"),
                )
                logger.info("Bedrock client initialised for check-in dialogue")
            except Exception as exc:
                logger.warning("Bedrock unavailable, falling back to rules: %s", exc)
                self.use_bedrock = False

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(
        self,
        resident_id: str,
        resident_name: str,
        *,
        previous_sessions: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[CheckInSession, DialogueTurn]:
        """Create a new check-in session and return the greeting turn."""
        session = CheckInSession(
            session_id=str(uuid.uuid4()),
            resident_id=resident_id,
            resident_name=resident_name,
            current_step=CheckInStep.GREETING,
            started_at=time.time(),
            previous_sessions=previous_sessions or [],
        )
        greeting = self._make_greeting(resident_name)
        turn = DialogueTurn(
            step=CheckInStep.GREETING,
            question=greeting,
            response_type="free_text",
        )
        logger.info(
            "Check-in session %s started for resident %s (%s)",
            session.session_id, resident_id, resident_name,
        )
        return session, turn

    def process_response(
        self,
        session: CheckInSession,
        user_response: str,
    ) -> Tuple[CheckInSession, DialogueTurn]:
        """Parse the response for the current step, advance, and return the next turn."""
        step = session.current_step
        parsed = self._parse_step(step, user_response, session.resident_name)
        session.responses[step.value] = parsed

        # Check if a follow-up is warranted
        follow_up_turn = self._check_for_follow_up(step, parsed, session)
        if follow_up_turn is not None:
            return session, follow_up_turn

        # Advance to the next step
        session = self._advance(session)
        next_turn = self._turn_for_step(session.current_step, session)
        return session, next_turn

    # ------------------------------------------------------------------
    # Greeting helpers
    # ------------------------------------------------------------------

    def _make_greeting(self, name: str) -> str:
        hour = datetime.now().hour
        if hour < 12:
            pool = _GREETINGS_MORNING
        elif hour < 17:
            pool = _GREETINGS_AFTERNOON
        else:
            pool = _GREETINGS_EVENING
        # Deterministic-ish selection based on current minute
        idx = datetime.now().minute % len(pool)
        return pool[idx].format(name=name)

    # ------------------------------------------------------------------
    # Step-specific parsers
    # ------------------------------------------------------------------

    def _parse_step(self, step: CheckInStep, text: str, name: str) -> Dict[str, Any]:
        parsers = {
            CheckInStep.GREETING: lambda t: {"acknowledged": True, "raw": t},
            CheckInStep.MOOD: self._parse_mood,
            CheckInStep.PAIN: self._parse_pain,
            CheckInStep.SLEEP: self._parse_sleep,
            CheckInStep.HYDRATION: self._parse_hydration,
            CheckInStep.MEALS: self._parse_meals,
            CheckInStep.MEDICATION: self._parse_medication,
            CheckInStep.ACTIVITY: self._parse_activity,
            CheckInStep.CONCERNS: self._parse_concerns,
            CheckInStep.SUMMARY: lambda t: {"acknowledged": True, "raw": t},
        }
        parser = parsers.get(step, lambda t: {"raw": t})
        result = parser(text)
        result["raw"] = text
        result["timestamp"] = time.time()
        return result

    def _parse_mood(self, text: str) -> Dict[str, Any]:
        """Extract mood category and sentiment score."""
        positive = bool(_POSITIVE_MOOD.search(text))
        negative = bool(_NEGATIVE_MOOD.search(text))
        neutral = bool(_NEUTRAL_MOOD.search(text))

        if positive and not negative:
            category = "good"
            sentiment = 0.8
        elif negative and not positive:
            category = "bad"
            sentiment = 0.2
        elif neutral or (positive and negative):
            category = "fair"
            sentiment = 0.5
        else:
            # Default to fair if we can't parse
            category = "fair"
            sentiment = 0.5

        return {"category": category, "sentiment": sentiment}

    def _parse_pain(self, text: str) -> Dict[str, Any]:
        """Extract pain level (1-10), location, and type."""
        level = _extract_number(text)
        # Check for "no pain" explicitly
        if _detect_yes_no(text) is False or re.search(r"\bno\s+pain\b", text, re.IGNORECASE):
            level = 0

        locations = _PAIN_LOCATION.findall(text)
        pain_types = _PAIN_TYPE.findall(text)

        return {
            "level": level if level is not None else 0,
            "locations": [loc.lower() for loc in locations],
            "pain_types": [pt.lower() for pt in pain_types],
            "has_pain": (level or 0) > 0,
        }

    def _parse_sleep(self, text: str) -> Dict[str, Any]:
        """Extract sleep quality, estimated hours, and interruptions."""
        good = bool(_SLEEP_GOOD.search(text))
        bad = bool(_SLEEP_BAD.search(text))
        hours = _extract_number(text)

        if good and not bad:
            quality = "good"
            score = 0.8
        elif bad and not good:
            quality = "poor"
            score = 0.2
        else:
            quality = "fair"
            score = 0.5

        interruptions = bool(re.search(
            r"\b(woke up|woke|up several times|interrupted|bathroom|restless|tossed)\b",
            text, re.IGNORECASE,
        ))

        return {
            "quality": quality,
            "score": score,
            "hours": hours,
            "interruptions": interruptions,
        }

    def _parse_hydration(self, text: str) -> Dict[str, Any]:
        """Extract glasses/cups count."""
        glasses = _extract_number(text)
        adequate = (glasses or 0) >= 4  # rough threshold

        return {
            "glasses": glasses if glasses is not None else 0,
            "adequate": adequate,
        }

    def _parse_meals(self, text: str) -> Dict[str, Any]:
        """Extract meals consumed and appetite assessment."""
        count = _extract_number(text)
        good_appetite = bool(re.search(
            r"\b(good|great|hungry|hearty|ate well|enjoyed|big)\b", text, re.IGNORECASE
        ))
        poor_appetite = bool(re.search(
            r"\b(poor|bad|not hungry|no appetite|skipped|couldn't eat|nothing|barely)\b",
            text, re.IGNORECASE,
        ))

        if good_appetite and not poor_appetite:
            appetite = "good"
        elif poor_appetite and not good_appetite:
            appetite = "poor"
        else:
            appetite = "moderate"

        return {
            "count": count if count is not None else 0,
            "appetite": appetite,
        }

    def _parse_medication(self, text: str) -> Dict[str, Any]:
        """Detect whether medications were taken."""
        taken = _detect_yes_no(text)
        return {"taken": taken if taken is not None else False}

    def _parse_activity(self, text: str) -> Dict[str, Any]:
        """Parse activity / movement response."""
        active = bool(re.search(
            r"\b(walk|walked|exercise|stretched|gardening|moved|moving|active|"
            r"yoga|tai chi|swim|swam|danced|cycling|stairs|physical therapy)\b",
            text, re.IGNORECASE,
        ))
        sedentary = bool(re.search(
            r"\b(no|not really|stayed in|sat|sitting|haven't|couch|bed|resting|"
            r"didn't move|couldn't)\b",
            text, re.IGNORECASE,
        ))

        if active and not sedentary:
            level = "active"
        elif sedentary and not active:
            level = "sedentary"
        else:
            level = "light"

        return {"level": level, "was_active": active}

    def _parse_concerns(self, text: str) -> Dict[str, Any]:
        """Capture any free-text concerns."""
        has_concerns = not bool(re.search(
            r"\b(no|nothing|nope|all good|that's it|I'm fine|not really)\b",
            text, re.IGNORECASE,
        ))
        return {"has_concerns": has_concerns, "text": text if has_concerns else None}

    # ------------------------------------------------------------------
    # Follow-up logic
    # ------------------------------------------------------------------

    def _check_for_follow_up(
        self,
        step: CheckInStep,
        parsed: Dict[str, Any],
        session: CheckInSession,
    ) -> Optional[DialogueTurn]:
        """Return a follow-up DialogueTurn if the response is concerning."""
        key: Optional[str] = None

        if step == CheckInStep.MOOD and parsed.get("category") == "bad":
            key = "mood_bad"
        elif step == CheckInStep.PAIN and (parsed.get("level", 0) or 0) > 6:
            key = "pain_high"
        elif step == CheckInStep.SLEEP and parsed.get("quality") == "poor":
            key = "sleep_poor"
        elif step == CheckInStep.MEDICATION and parsed.get("taken") is False:
            key = "medication_no"
        elif step == CheckInStep.HYDRATION and (parsed.get("glasses", 0) or 0) < 2:
            key = "hydration_low"
        elif step == CheckInStep.MEALS and parsed.get("appetite") == "poor":
            key = "meals_poor"

        if key is None:
            return None

        # Don't ask the same follow-up twice in one session
        fu_info = _FOLLOW_UPS.get(key)
        if fu_info is None:
            return None
        fu_key = fu_info["key"]
        if fu_key in session.follow_ups_asked:
            return None

        session.follow_ups_asked.append(fu_key)
        turn: DialogueTurn = fu_info["turn"]
        question = turn.question.format(name=session.resident_name)
        return DialogueTurn(
            step=turn.step,
            question=question,
            response_type=turn.response_type,
            is_follow_up=True,
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _advance(self, session: CheckInSession) -> CheckInSession:
        """Move the session to the next step."""
        idx = _STEP_ORDER.index(session.current_step)
        if idx + 1 < len(_STEP_ORDER):
            session.current_step = _STEP_ORDER[idx + 1]
        else:
            session.current_step = CheckInStep.COMPLETE
        return session

    def _turn_for_step(
        self,
        step: CheckInStep,
        session: CheckInSession,
    ) -> DialogueTurn:
        """Build the DialogueTurn for a given step."""
        if step == CheckInStep.SUMMARY:
            summary = self.generate_summary(session)
            session.ai_insights = summary.get("insights", [])
            question = self._build_summary_message(session, summary)
            return DialogueTurn(
                step=CheckInStep.SUMMARY,
                question=question,
                response_type="free_text",
            )

        if step == CheckInStep.COMPLETE:
            session.completed_at = time.time()
            return DialogueTurn(
                step=CheckInStep.COMPLETE,
                question=(
                    f"Thank you so much for chatting with me, {session.resident_name}. "
                    "I've noted everything down. Take care and have a wonderful rest of your day!"
                ),
                response_type="free_text",
            )

        template = _QUESTIONS.get(step)
        if template is None:
            return DialogueTurn(step=step, question="", response_type="free_text")

        question = template.question.format(name=session.resident_name)
        return DialogueTurn(
            step=template.step,
            question=question,
            response_type=template.response_type,
            options=template.options,
        )

    # ------------------------------------------------------------------
    # Summary & scoring
    # ------------------------------------------------------------------

    def generate_summary(self, session: CheckInSession) -> Dict[str, Any]:
        """Generate wellness score, insights, and recommendations."""
        score = self._compute_wellness_score(session)
        insights = self._rule_based_insights(session, score)
        trends = self._detect_trends(session)

        # Attempt Bedrock-powered enrichment
        if self.use_bedrock and self._bedrock_client:
            try:
                ai_insights = self._bedrock_insights(session, score)
                insights.extend(ai_insights)
            except Exception as exc:
                logger.warning("Bedrock insight generation failed: %s", exc)

        return {
            "wellness_score": score,
            "insights": insights,
            "trends": trends,
            "timestamp": time.time(),
        }

    def _compute_wellness_score(self, session: CheckInSession) -> int:
        """Compute an aggregate wellness score (0–100)."""
        scores: Dict[str, float] = {}
        r = session.responses

        # Mood (weight 20)
        mood = r.get("mood", {})
        scores["mood"] = mood.get("sentiment", 0.5) * 20

        # Pain (weight 20) — lower pain = higher score
        pain = r.get("pain", {})
        pain_level = pain.get("level", 0) or 0
        scores["pain"] = max(0, (10 - pain_level) / 10) * 20

        # Sleep (weight 15)
        sleep = r.get("sleep", {})
        scores["sleep"] = sleep.get("score", 0.5) * 15

        # Hydration (weight 10)
        hydration = r.get("hydration", {})
        glasses = hydration.get("glasses", 0) or 0
        scores["hydration"] = min(1.0, glasses / 8) * 10

        # Meals (weight 10)
        meals = r.get("meals", {})
        appetite_map = {"good": 1.0, "moderate": 0.6, "poor": 0.2}
        scores["meals"] = appetite_map.get(meals.get("appetite", "moderate"), 0.6) * 10

        # Medication (weight 15)
        med = r.get("medication", {})
        scores["medication"] = (1.0 if med.get("taken") else 0.0) * 15

        # Activity (weight 10)
        activity = r.get("activity", {})
        activity_map = {"active": 1.0, "light": 0.6, "sedentary": 0.2}
        scores["activity"] = activity_map.get(activity.get("level", "light"), 0.6) * 10

        total = sum(scores.values())
        return max(0, min(100, round(total)))

    def _rule_based_insights(
        self,
        session: CheckInSession,
        wellness_score: int,
    ) -> List[str]:
        """Generate rule-based insights from parsed responses."""
        insights: List[str] = []
        r = session.responses

        if wellness_score >= 80:
            insights.append(f"{session.resident_name} is doing well overall today (score {wellness_score}/100).")
        elif wellness_score >= 50:
            insights.append(f"{session.resident_name} is doing fairly today (score {wellness_score}/100). Some areas need attention.")
        else:
            insights.append(
                f"{session.resident_name} may need extra support today (score {wellness_score}/100). "
                "Several areas of concern were identified."
            )

        # Domain-specific insights
        mood = r.get("mood", {})
        if mood.get("category") == "bad":
            insights.append("Mood is low — consider checking in with care staff about emotional well-being.")

        pain = r.get("pain", {})
        pain_level = pain.get("level", 0) or 0
        if pain_level >= 7:
            locations = ", ".join(pain.get("locations", [])) or "unspecified location"
            insights.append(
                f"Significant pain reported (level {pain_level}/10 at {locations}). "
                "A clinical follow-up is recommended."
            )
        elif pain_level >= 4:
            insights.append(f"Moderate pain reported (level {pain_level}/10). Monitor closely.")

        sleep = r.get("sleep", {})
        if sleep.get("quality") == "poor":
            insights.append("Poor sleep quality reported. Consider reviewing sleep environment or medications.")

        hydration = r.get("hydration", {})
        if (hydration.get("glasses", 0) or 0) < 3:
            insights.append("Low fluid intake today. Encourage hydration.")

        meals = r.get("meals", {})
        if meals.get("appetite") == "poor":
            insights.append("Poor appetite reported. May warrant dietary review.")

        med = r.get("medication", {})
        if not med.get("taken"):
            insights.append("Medications not taken today. Notify care team for follow-up.")

        activity = r.get("activity", {})
        if activity.get("level") == "sedentary":
            insights.append("No physical activity reported today. Encourage gentle movement if safe.")

        concerns = r.get("concerns", {})
        if concerns.get("has_concerns"):
            insights.append(f"Resident expressed additional concerns: \"{concerns.get('text', '')}\"")

        return insights

    def _detect_trends(self, session: CheckInSession) -> Dict[str, Any]:
        """Compare current session with previous sessions to detect trends."""
        trends: Dict[str, Any] = {"available": False}
        prev = session.previous_sessions
        if not prev:
            return trends

        trends["available"] = True
        trends["sessions_compared"] = len(prev)

        # Mood trend
        prev_sentiments = [
            s.get("responses", {}).get("mood", {}).get("sentiment", 0.5)
            for s in prev if "mood" in s.get("responses", {})
        ]
        current_sentiment = session.responses.get("mood", {}).get("sentiment", 0.5)
        if prev_sentiments:
            avg_prev = sum(prev_sentiments) / len(prev_sentiments)
            if current_sentiment < avg_prev - 0.2:
                trends["mood"] = "declining"
            elif current_sentiment > avg_prev + 0.2:
                trends["mood"] = "improving"
            else:
                trends["mood"] = "stable"

        # Pain trend
        prev_pain = [
            s.get("responses", {}).get("pain", {}).get("level", 0) or 0
            for s in prev if "pain" in s.get("responses", {})
        ]
        current_pain = session.responses.get("pain", {}).get("level", 0) or 0
        if prev_pain:
            avg_pain = sum(prev_pain) / len(prev_pain)
            if current_pain > avg_pain + 2:
                trends["pain"] = "worsening"
            elif current_pain < avg_pain - 2:
                trends["pain"] = "improving"
            else:
                trends["pain"] = "stable"

        # Sleep trend
        prev_sleep = [
            s.get("responses", {}).get("sleep", {}).get("score", 0.5)
            for s in prev if "sleep" in s.get("responses", {})
        ]
        current_sleep = session.responses.get("sleep", {}).get("score", 0.5)
        if prev_sleep:
            avg_sleep = sum(prev_sleep) / len(prev_sleep)
            if current_sleep < avg_sleep - 0.2:
                trends["sleep"] = "declining"
            elif current_sleep > avg_sleep + 0.2:
                trends["sleep"] = "improving"
            else:
                trends["sleep"] = "stable"

        # Medication adherence trend
        prev_med = [
            s.get("responses", {}).get("medication", {}).get("taken", False)
            for s in prev if "medication" in s.get("responses", {})
        ]
        if prev_med:
            adherence_rate = sum(1 for t in prev_med if t) / len(prev_med)
            trends["medication_adherence_rate"] = round(adherence_rate, 2)
            current_taken = session.responses.get("medication", {}).get("taken", False)
            if not current_taken and adherence_rate > 0.8:
                trends["medication"] = "unusual_miss"
            elif not current_taken:
                trends["medication"] = "recurring_misses"

        return trends

    def _build_summary_message(
        self,
        session: CheckInSession,
        summary: Dict[str, Any],
    ) -> str:
        """Build a warm, readable summary message for the resident."""
        score = summary["wellness_score"]
        name = session.resident_name

        if score >= 80:
            opener = f"Wonderful, {name}! It sounds like you're having a great day."
        elif score >= 60:
            opener = f"Thank you, {name}. It sounds like things are going reasonably well today."
        elif score >= 40:
            opener = f"Thank you for sharing, {name}. It sounds like today has some challenges."
        else:
            opener = (
                f"Thank you for being open with me, {name}. "
                "I want to make sure the care team knows about some of the things you mentioned."
            )

        # Pick top two actionable insights for the spoken summary
        actionable = [i for i in summary.get("insights", [])[1:] if "recommend" in i.lower() or "encourage" in i.lower() or "notify" in i.lower()]
        note = ""
        if actionable:
            note = " I'll make a note to let the team know about a couple of things so they can help."

        closing = f" Your overall wellness score for today is {score} out of 100.{note} Is there anything else before we wrap up?"
        return opener + closing

    # ------------------------------------------------------------------
    # Bedrock-powered insights
    # ------------------------------------------------------------------

    def _bedrock_insights(
        self,
        session: CheckInSession,
        wellness_score: int,
    ) -> List[str]:
        """Call Bedrock for richer AI insights (optional)."""
        if not self._bedrock_client:
            return []

        prompt = (
            "You are a compassionate geriatric care AI assistant.  Based on the "
            "following daily check-in responses for an elderly resident, provide "
            "2-3 concise, actionable insights for the care team.  Do NOT give "
            "medical diagnoses or prescription advice.\n\n"
            f"Resident: {session.resident_name}\n"
            f"Wellness Score: {wellness_score}/100\n"
            f"Responses:\n{json.dumps(session.responses, indent=2, default=str)}\n\n"
            "Insights:"
        )

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            })
            resp = self._bedrock_client.invoke_model(
                modelId=self.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            result = json.loads(resp["body"].read())
            text = result.get("content", [{}])[0].get("text", "")
            # Split into list of insights
            insights = [
                line.strip().lstrip("•-0123456789.) ")
                for line in text.strip().split("\n")
                if line.strip() and len(line.strip()) > 10
            ]
            return insights[:3]
        except Exception as exc:
            logger.warning("Bedrock invoke failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self, session: CheckInSession) -> Dict[str, Any]:
        """Generate a complete check-in report suitable for DynamoDB / timeline."""
        summary = self.generate_summary(session)
        return {
            "report_id": str(uuid.uuid4()),
            "session_id": session.session_id,
            "resident_id": session.resident_id,
            "resident_name": session.resident_name,
            "type": "daily_checkin",
            "started_at": session.started_at,
            "completed_at": session.completed_at or time.time(),
            "duration_seconds": round(
                (session.completed_at or time.time()) - session.started_at, 1
            ),
            "responses": session.responses,
            "wellness_score": summary["wellness_score"],
            "insights": summary["insights"],
            "trends": summary.get("trends", {}),
            "follow_ups_asked": session.follow_ups_asked,
            "steps_completed": [
                s.value for s in _STEP_ORDER
                if s.value in session.responses
            ],
            "metadata": {
                "bedrock_used": self.use_bedrock,
                "model_id": self.bedrock_model_id if self.use_bedrock else None,
                "version": "1.0.0",
            },
        }
