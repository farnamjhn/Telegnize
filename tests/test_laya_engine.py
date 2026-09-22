import unittest
from datetime import datetime
from domain.models.message import Message, ContentType
from infrastructure.decision_engine.laya_engine import LayaDecisionEngine


class TestLayaDecisionEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = LayaDecisionEngine.get_instance()

    def test_predict_simple_english(self):
        questions = {
            "is_greeting": {
                "type": "noul",
                "instructions": "Is this a greeting?"
            }
        }
        res = self.engine.predict("Hello there, good morning!", questions)
        self.assertIn("answers", res)
        self.assertIn("is_greeting", res["answers"])
        answer = res["answers"]["is_greeting"]
        self.assertEqual(answer["type"], "noul")
        self.assertIn("noul", answer)
        self.assertIn("confidence", answer)

    def test_evaluate_message_entity(self):
        msg = Message(
            id=1,
            telegram_msg_id=101,
            sender_id="u1",
            sender_name="Alice",
            reply_to_msg_id=None,
            timestamp=datetime.now(),
            text="I really appreciate your help with this project!",
            content_type=ContentType.TEXT,
        )
        decisions = self.engine.evaluate_message(msg)
        self.assertTrue(len(decisions) > 0)
        tone_dec = next((d for d in decisions if d.question_key == "tone"), None)
        self.assertIsNotNone(tone_dec)
        self.assertEqual(tone_dec.target_type, "message")
        self.assertIn(tone_dec.result_value, ["friendly", "affectionate", "neutral", "casual"])


if __name__ == "__main__":
    unittest.main()
