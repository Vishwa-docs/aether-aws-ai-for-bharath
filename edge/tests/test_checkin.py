"""
Tests for the AETHER Daily Check-In Dialogue System (Day 14).
Covers session lifecycle, step parsing, follow-up logic,
wellness scoring, and report generation.
"""
import unittest

from aether.voice.checkin_dialogue import (
    CheckInDialogue,
    CheckInSession,
    CheckInStep,
    DialogueTurn,
    _extract_number,
    _detect_yes_no,
)


class TestCheckInSessionCreation(unittest.TestCase):
    """Test that sessions are created correctly."""

    def setUp(self):
        self.dialogue = CheckInDialogue(use_bedrock=False)

    def test_start_session_returns_session_and_turn(self):
        session, turn = self.dialogue.start_session("R001", "Kamala")
        self.assertIsInstance(session, CheckInSession)
        self.assertIsInstance(turn, DialogueTurn)

    def test_session_has_correct_resident(self):
        session, _ = self.dialogue.start_session("R001", "Kamala")
        self.assertEqual(session.resident_id, "R001")
        self.assertEqual(session.resident_name, "Kamala")

    def test_session_starts_at_greeting(self):
        session, turn = self.dialogue.start_session("R001", "Kamala")
        self.assertEqual(session.current_step, CheckInStep.GREETING)
        self.assertEqual(turn.step, CheckInStep.GREETING)

    def test_greeting_contains_name(self):
        _, turn = self.dialogue.start_session("R001", "Kamala")
        self.assertIn("Kamala", turn.question)

    def test_session_id_is_unique(self):
        s1, _ = self.dialogue.start_session("R001", "Kamala")
        s2, _ = self.dialogue.start_session("R001", "Kamala")
        self.assertNotEqual(s1.session_id, s2.session_id)

    def test_session_has_empty_responses(self):
        session, _ = self.dialogue.start_session("R001", "Kamala")
        self.assertEqual(session.responses, {})

    def test_session_started_at_set(self):
        session, _ = self.dialogue.start_session("R001", "Kamala")
        self.assertGreater(session.started_at, 0)


class TestDialogueStepAdvancement(unittest.TestCase):
    """Test that the dialogue advances through all steps correctly."""

    def setUp(self):
        self.dialogue = CheckInDialogue(use_bedrock=False)
        self.session, _ = self.dialogue.start_session("R001", "Kamala")

    def test_greeting_to_mood(self):
        session, turn = self.dialogue.process_response(self.session, "Yes, let's chat")
        self.assertEqual(session.current_step, CheckInStep.MOOD)
        self.assertEqual(turn.step, CheckInStep.MOOD)

    def test_full_dialogue_flow(self):
        """Walk through every step from GREETING to COMPLETE."""
        session = self.session
        # Acknowledge greeting
        session, turn = self.dialogue.process_response(session, "Sure!")
        self.assertEqual(turn.step, CheckInStep.MOOD)

        # Mood — good
        session, turn = self.dialogue.process_response(session, "I'm feeling good today")
        self.assertEqual(turn.step, CheckInStep.PAIN)

        # Pain — none
        session, turn = self.dialogue.process_response(session, "No pain at all")
        self.assertEqual(turn.step, CheckInStep.SLEEP)

        # Sleep — good
        session, turn = self.dialogue.process_response(session, "Slept really well, about 8 hours")
        self.assertEqual(turn.step, CheckInStep.HYDRATION)

        # Hydration — adequate
        session, turn = self.dialogue.process_response(session, "I had about 6 glasses")
        self.assertEqual(turn.step, CheckInStep.MEALS)

        # Meals — good appetite
        session, turn = self.dialogue.process_response(session, "Ate well, had a big breakfast")
        self.assertEqual(turn.step, CheckInStep.MEDICATION)

        # Medication — taken
        session, turn = self.dialogue.process_response(session, "Yes, I took them all")
        self.assertEqual(turn.step, CheckInStep.ACTIVITY)

        # Activity — active
        session, turn = self.dialogue.process_response(session, "Went for a short walk")
        self.assertEqual(turn.step, CheckInStep.CONCERNS)

        # Concerns — none
        session, turn = self.dialogue.process_response(session, "No, nothing to worry about")
        self.assertEqual(turn.step, CheckInStep.SUMMARY)

        # Summary acknowledgement
        session, turn = self.dialogue.process_response(session, "Thanks")
        self.assertEqual(turn.step, CheckInStep.COMPLETE)

    def test_question_includes_resident_name(self):
        session, turn = self.dialogue.process_response(self.session, "Sure")
        # Mood question should include the name
        self.assertIn("Kamala", turn.question)


class TestResponseParsing(unittest.TestCase):
    """Test the NLU parsing for each check-in step."""

    def setUp(self):
        self.dialogue = CheckInDialogue(use_bedrock=False)

    # -- Mood --
    def test_parse_mood_good(self):
        session, _ = self.dialogue.start_session("R001", "A")
        session, _ = self.dialogue.process_response(session, "Hi")  # greeting
        session, _ = self.dialogue.process_response(session, "I'm feeling great today")
        mood = session.responses.get("mood", {})
        self.assertEqual(mood["category"], "good")
        self.assertGreater(mood["sentiment"], 0.5)

    def test_parse_mood_bad(self):
        session, _ = self.dialogue.start_session("R001", "A")
        session, _ = self.dialogue.process_response(session, "okay")
        session, _ = self.dialogue.process_response(session, "I feel terrible and sad")
        mood = session.responses.get("mood", {})
        self.assertEqual(mood["category"], "bad")
        self.assertLess(mood["sentiment"], 0.5)

    def test_parse_mood_neutral(self):
        session, _ = self.dialogue.start_session("R001", "A")
        session, _ = self.dialogue.process_response(session, "okay")
        session, _ = self.dialogue.process_response(session, "It's so-so I guess")
        mood = session.responses.get("mood", {})
        self.assertIn(mood["category"], ("fair",))

    # -- Pain --
    def test_parse_pain_with_number(self):
        session, _ = self.dialogue.start_session("R001", "A")
        session, _ = self.dialogue.process_response(session, "yes")
        session, _ = self.dialogue.process_response(session, "fine")  # mood
        session, _ = self.dialogue.process_response(session, "Yes, about a 7 out of 10 in my knee")
        pain = session.responses.get("pain", {})
        self.assertEqual(pain["level"], 7)
        self.assertTrue(pain["has_pain"])
        self.assertIn("knee", pain["locations"])

    def test_parse_pain_none(self):
        session, _ = self.dialogue.start_session("R001", "A")
        session, _ = self.dialogue.process_response(session, "yes")
        session, _ = self.dialogue.process_response(session, "okay")  # mood
        session, _ = self.dialogue.process_response(session, "No pain at all")
        pain = session.responses.get("pain", {})
        self.assertEqual(pain["level"], 0)
        self.assertFalse(pain["has_pain"])

    # -- Sleep --
    def test_parse_sleep_good(self):
        session, _ = self.dialogue.start_session("R001", "A")
        session, _ = self.dialogue.process_response(session, "yes")
        session, _ = self.dialogue.process_response(session, "fine")
        session, _ = self.dialogue.process_response(session, "no pain")
        session, _ = self.dialogue.process_response(session, "Slept really well, deep sleep")
        sleep = session.responses.get("sleep", {})
        self.assertEqual(sleep["quality"], "good")
        self.assertGreater(sleep["score"], 0.5)

    def test_parse_sleep_poor(self):
        session, _ = self.dialogue.start_session("R001", "A")
        session, _ = self.dialogue.process_response(session, "yes")
        session, _ = self.dialogue.process_response(session, "fine")
        session, _ = self.dialogue.process_response(session, "no pain")
        session, _ = self.dialogue.process_response(session, "Terrible night, tossed and turned")
        sleep = session.responses.get("sleep", {})
        self.assertEqual(sleep["quality"], "poor")
        self.assertLess(sleep["score"], 0.5)

    # -- Hydration --
    def test_parse_hydration_adequate(self):
        session = self._advance_to_step(CheckInStep.HYDRATION)
        session, _ = self.dialogue.process_response(session, "About 6 glasses today")
        hydration = session.responses.get("hydration", {})
        self.assertEqual(hydration["glasses"], 6)
        self.assertTrue(hydration["adequate"])

    def test_parse_hydration_low(self):
        session = self._advance_to_step(CheckInStep.HYDRATION)
        session, _ = self.dialogue.process_response(session, "Just one cup")
        hydration = session.responses.get("hydration", {})
        self.assertEqual(hydration["glasses"], 1)
        self.assertFalse(hydration["adequate"])

    # -- Meals --
    def test_parse_meals_good_appetite(self):
        session = self._advance_to_step(CheckInStep.MEALS)
        session, _ = self.dialogue.process_response(session, "Had a big breakfast and ate well")
        meals = session.responses.get("meals", {})
        self.assertEqual(meals["appetite"], "good")

    def test_parse_meals_poor_appetite(self):
        session = self._advance_to_step(CheckInStep.MEALS)
        session, _ = self.dialogue.process_response(session, "I skipped meals, no appetite")
        meals = session.responses.get("meals", {})
        self.assertEqual(meals["appetite"], "poor")

    # -- Medication --
    def test_parse_medication_taken(self):
        session = self._advance_to_step(CheckInStep.MEDICATION)
        session, _ = self.dialogue.process_response(session, "Yes, I took them all")
        med = session.responses.get("medication", {})
        self.assertTrue(med["taken"])

    def test_parse_medication_not_taken(self):
        session = self._advance_to_step(CheckInStep.MEDICATION)
        session, _ = self.dialogue.process_response(session, "No, I forgot")
        med = session.responses.get("medication", {})
        self.assertFalse(med["taken"])

    # -- Helper NLU functions --
    def test_extract_number_digit(self):
        self.assertEqual(_extract_number("about 5 glasses"), 5)

    def test_extract_number_word(self):
        self.assertEqual(_extract_number("three cups"), 3)

    def test_extract_number_none(self):
        self.assertIsNone(_extract_number("lots"))

    def test_detect_yes_no_yes(self):
        self.assertTrue(_detect_yes_no("yes absolutely"))

    def test_detect_yes_no_no(self):
        self.assertFalse(_detect_yes_no("nope not yet"))

    def test_detect_yes_no_ambiguous(self):
        result = _detect_yes_no("some random words")
        self.assertIsNone(result)

    # Helper to advance session to a specific step
    def _advance_to_step(self, target_step: CheckInStep) -> CheckInSession:
        """Advance a session to the target step by providing neutral responses."""
        session, _ = self.dialogue.start_session("R001", "Anita")
        neutral_responses = {
            CheckInStep.GREETING: "Sure",
            CheckInStep.MOOD: "I'm okay",
            CheckInStep.PAIN: "No pain",
            CheckInStep.SLEEP: "Slept fine",
            CheckInStep.HYDRATION: "About 5 glasses",
            CheckInStep.MEALS: "Ate a moderate amount",
            CheckInStep.MEDICATION: "Yes, took them",
            CheckInStep.ACTIVITY: "Did a bit of walking",
            CheckInStep.CONCERNS: "Nothing",
        }
        from aether.voice.checkin_dialogue import _STEP_ORDER
        for step in _STEP_ORDER:
            if step == target_step:
                break
            response = neutral_responses.get(step, "Okay")
            session, _ = self.dialogue.process_response(session, response)
        return session


class TestFollowUpQuestions(unittest.TestCase):
    """Test that follow-up questions are triggered by concerning answers."""

    def setUp(self):
        self.dialogue = CheckInDialogue(use_bedrock=False)

    def test_bad_mood_triggers_follow_up(self):
        session, _ = self.dialogue.start_session("R001", "Kamala")
        session, _ = self.dialogue.process_response(session, "Okay")  # greeting
        session, turn = self.dialogue.process_response(session, "I feel terrible and sad")
        # Should get a follow-up about mood, not advance to pain yet
        self.assertTrue(turn.is_follow_up)
        self.assertEqual(turn.step, CheckInStep.MOOD)

    def test_high_pain_triggers_follow_up(self):
        session = self._advance_to_pain()
        session, turn = self.dialogue.process_response(session, "Pain is 8 out of 10 in my back")
        self.assertTrue(turn.is_follow_up)
        self.assertEqual(turn.step, CheckInStep.PAIN)

    def test_poor_sleep_triggers_follow_up(self):
        session = self._advance_to_sleep()
        session, turn = self.dialogue.process_response(session, "Terrible, couldn't sleep at all")
        self.assertTrue(turn.is_follow_up)
        self.assertEqual(turn.step, CheckInStep.SLEEP)

    def test_medication_missed_triggers_follow_up(self):
        session = self._advance_to_medication()
        session, turn = self.dialogue.process_response(session, "No, I forgot")
        self.assertTrue(turn.is_follow_up)
        self.assertEqual(turn.step, CheckInStep.MEDICATION)

    def test_follow_up_not_repeated(self):
        """The same follow-up should not be asked twice in one session."""
        session, _ = self.dialogue.start_session("R001", "Kamala")
        session, _ = self.dialogue.process_response(session, "Okay")
        # First bad mood → follow-up
        session, turn = self.dialogue.process_response(session, "I feel miserable")
        self.assertTrue(turn.is_follow_up)
        # Respond to follow-up → should now advance to PAIN, not ask again
        session, turn = self.dialogue.process_response(session, "Just feeling down")
        self.assertEqual(turn.step, CheckInStep.PAIN)
        self.assertFalse(turn.is_follow_up)

    # Helpers
    def _advance_to_pain(self) -> CheckInSession:
        session, _ = self.dialogue.start_session("R001", "A")
        session, _ = self.dialogue.process_response(session, "Sure")
        session, _ = self.dialogue.process_response(session, "I'm fine")
        return session

    def _advance_to_sleep(self) -> CheckInSession:
        session = self._advance_to_pain()
        session, _ = self.dialogue.process_response(session, "No pain")
        return session

    def _advance_to_medication(self) -> CheckInSession:
        session = self._advance_to_sleep()
        session, _ = self.dialogue.process_response(session, "Slept fine")
        session, _ = self.dialogue.process_response(session, "5 glasses")  # hydration
        session, _ = self.dialogue.process_response(session, "Ate okay")  # meals
        return session


class TestWellnessScore(unittest.TestCase):
    """Test the wellness score computation."""

    def setUp(self):
        self.dialogue = CheckInDialogue(use_bedrock=False)

    def test_perfect_day_high_score(self):
        session = self._make_session_with_responses({
            "mood": {"category": "good", "sentiment": 0.8},
            "pain": {"level": 0, "has_pain": False, "locations": [], "pain_types": []},
            "sleep": {"quality": "good", "score": 0.8},
            "hydration": {"glasses": 8, "adequate": True},
            "meals": {"count": 3, "appetite": "good"},
            "medication": {"taken": True},
            "activity": {"level": "active", "was_active": True},
        })
        summary = self.dialogue.generate_summary(session)
        self.assertGreaterEqual(summary["wellness_score"], 75)

    def test_bad_day_low_score(self):
        session = self._make_session_with_responses({
            "mood": {"category": "bad", "sentiment": 0.2},
            "pain": {"level": 8, "has_pain": True, "locations": ["back"], "pain_types": ["sharp"]},
            "sleep": {"quality": "poor", "score": 0.2},
            "hydration": {"glasses": 1, "adequate": False},
            "meals": {"count": 0, "appetite": "poor"},
            "medication": {"taken": False},
            "activity": {"level": "sedentary", "was_active": False},
        })
        summary = self.dialogue.generate_summary(session)
        self.assertLessEqual(summary["wellness_score"], 30)

    def test_score_is_bounded(self):
        session = self._make_session_with_responses({})
        summary = self.dialogue.generate_summary(session)
        self.assertGreaterEqual(summary["wellness_score"], 0)
        self.assertLessEqual(summary["wellness_score"], 100)

    def test_summary_has_insights(self):
        session = self._make_session_with_responses({
            "mood": {"category": "good", "sentiment": 0.8},
        })
        summary = self.dialogue.generate_summary(session)
        self.assertIsInstance(summary["insights"], list)
        self.assertGreater(len(summary["insights"]), 0)

    def _make_session_with_responses(self, responses):
        session = CheckInSession(
            session_id="test-session",
            resident_id="R001",
            resident_name="Kamala",
            current_step=CheckInStep.SUMMARY,
            responses=responses,
        )
        return session


class TestReportGeneration(unittest.TestCase):
    """Test report generation from completed sessions."""

    def setUp(self):
        self.dialogue = CheckInDialogue(use_bedrock=False)

    def test_report_structure(self):
        session = CheckInSession(
            session_id="test-session",
            resident_id="R001",
            resident_name="Kamala",
            current_step=CheckInStep.COMPLETE,
            responses={
                "mood": {"category": "good", "sentiment": 0.8, "raw": "Good", "timestamp": 1.0},
                "pain": {"level": 0, "has_pain": False, "locations": [], "pain_types": [], "raw": "No", "timestamp": 2.0},
            },
        )
        report = self.dialogue.generate_report(session)
        self.assertIn("report_id", report)
        self.assertIn("session_id", report)
        self.assertIn("resident_id", report)
        self.assertEqual(report["type"], "daily_checkin")
        self.assertIn("wellness_score", report)
        self.assertIn("insights", report)
        self.assertIn("responses", report)

    def test_report_has_metadata(self):
        session = CheckInSession(
            session_id="test-session",
            resident_id="R001",
            resident_name="Kamala",
            current_step=CheckInStep.COMPLETE,
            responses={},
        )
        report = self.dialogue.generate_report(session)
        self.assertIn("metadata", report)
        self.assertFalse(report["metadata"]["bedrock_used"])

    def test_report_wellness_score_matches_summary(self):
        session = CheckInSession(
            session_id="test-session",
            resident_id="R001",
            resident_name="Kamala",
            current_step=CheckInStep.SUMMARY,
            responses={
                "mood": {"category": "good", "sentiment": 0.8},
                "medication": {"taken": True},
            },
        )
        report = self.dialogue.generate_report(session)
        summary = self.dialogue.generate_summary(session)
        self.assertEqual(report["wellness_score"], summary["wellness_score"])

    def test_report_steps_completed(self):
        session = CheckInSession(
            session_id="s",
            resident_id="R001",
            resident_name="K",
            current_step=CheckInStep.COMPLETE,
            responses={
                "greeting": {"acknowledged": True, "raw": "yes", "timestamp": 0},
                "mood": {"category": "good", "sentiment": 0.8, "raw": "good", "timestamp": 0},
            },
        )
        report = self.dialogue.generate_report(session)
        self.assertIn("greeting", report["steps_completed"])
        self.assertIn("mood", report["steps_completed"])


if __name__ == "__main__":
    unittest.main()
