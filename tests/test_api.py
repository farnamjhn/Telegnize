import json
import unittest

from fastapi.testclient import TestClient

from application.services.decision_service import DecisionService
from infrastructure.api.app import create_app
from infrastructure.api.dependencies import get_decision_service
from tests.conftest import memory_container
from tests.fakes import FakeDecisionEngine


def export_bytes(messages, **header) -> bytes:
    document = {"name": "Dana", "type": "personal_chat", "id": 555000111, **header}
    document["messages"] = messages
    return json.dumps(document).encode("utf-8")


PERSIAN_EXPORT = export_bytes(
    [
        {
            "id": 1,
            "type": "message",
            "date": "2026-05-27T00:01:00",
            "from": "Farnam",
            "from_id": "user_farnam",
            "text": "سلام، چطوری؟",
        },
        {
            "id": 2,
            "type": "message",
            "date": "2026-05-27T00:02:00",
            "from": "Dana",
            "from_id": "user_dana",
            "reply_to_message_id": 1,
            "text": "سلام قربانت تو چطوری؟",
        },
    ]
)


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.container = memory_container()
        self.engine = FakeDecisionEngine()
        self.app = create_app(self.container)
        # Only the model is faked; everything else is the real object graph.
        self.app.dependency_overrides[get_decision_service] = lambda: DecisionService(
            message_repo=self.container.message_repository,
            decision_repo=self.container.decision_repository,
            engine=self.engine,
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.container.close()


class TestHealth(APITestCase):
    def test_root_identifies_the_service(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["app"], "Telegnize API")

    def test_health_reports_dependencies(self):
        body = self.client.get("/api/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("decision_engine", body)


class TestMessages(APITestCase):
    def post_message(self, **overrides):
        payload = {
            "telegram_msg_id": 501,
            "sender_id": "user_500",
            "sender_name": "Alice",
            "timestamp": "2026-08-23T10:00:00",
            "text": "Is this a question?",
        }
        payload.update(overrides)
        return self.client.post("/api/messages", json=payload)

    def test_create_then_read_back(self):
        response = self.post_message()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["sender_id"], "user_500")
        self.assertEqual(body["text"], "Is this a question?")
        self.assertTrue(body["is_question"])
        self.assertEqual(body["word_count"], 4)
        self.assertEqual(body["language"], "en")
        self.assertEqual(body["normalized_text"], "is this a question?")

        by_id = self.client.get(f"/api/messages/{body['id']}")
        self.assertEqual(by_id.status_code, 200)
        self.assertEqual(by_id.json()["sender_name"], "Alice")

        by_telegram_id = self.client.get("/api/messages/telegram/501")
        self.assertEqual(by_telegram_id.json()["id"], body["id"])

    def test_listing_is_chronological(self):
        self.post_message(telegram_msg_id=1, sender_name="User 1",
                          timestamp="2026-08-23T11:00:00", text="Second message")
        self.post_message(telegram_msg_id=2, sender_name="User 2",
                          timestamp="2026-08-23T10:00:00", text="First message")

        items = self.client.get("/api/messages").json()
        self.assertEqual([item["text"] for item in items],
                         ["First message", "Second message"])

    def test_listing_honours_filters(self):
        self.post_message(telegram_msg_id=1, sender_id="a")
        self.post_message(telegram_msg_id=2, sender_id="b")
        items = self.client.get("/api/messages", params={"sender_id": "a"}).json()
        self.assertEqual(len(items), 1)

    def test_missing_message_is_a_404(self):
        response = self.client.get("/api/messages/4242")
        self.assertEqual(response.status_code, 404)
        self.assertIn("4242", response.json()["detail"])


class TestChatImport(APITestCase):
    def upload(self, payload=PERSIAN_EXPORT, filename="export.json"):
        return self.client.post(
            "/api/chats/upload",
            files={"file": (filename, payload, "application/json")},
        )

    def test_upload_streams_and_reports_what_was_imported(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["total_messages"], 2)
        self.assertEqual(body["chat"]["name"], "export")
        self.assertEqual(body["chat"]["telegram_chat_id"], 555000111)

    def test_non_json_uploads_are_rejected(self):
        self.assertEqual(self.upload(filename="notes.txt").status_code, 400)

    def test_malformed_exports_are_a_400_not_a_500(self):
        response = self.upload(payload=b'{"name": "x", "messages": [')
        self.assertEqual(response.status_code, 400)

    def test_reimporting_the_same_export_does_not_duplicate_messages(self):
        self.upload()
        second = self.upload()
        self.assertEqual(second.json()["chat"]["total_messages"], 2)

    def test_listing_and_deleting_chats(self):
        chat_id = self.upload().json()["chat"]["id"]

        listed = self.client.get("/api/chats").json()
        self.assertIn(chat_id, [chat["id"] for chat in listed])

        self.assertEqual(self.client.get(f"/api/chats/{chat_id}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/chats/{chat_id}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/chats/{chat_id}").status_code, 404)

    def test_importing_a_path_that_does_not_exist_is_a_404(self):
        response = self.client.post(
            "/api/chats/import-local", json={"file_path": "/nope/missing.json"}
        )
        self.assertEqual(response.status_code, 404)


class TestAnalyticsEndpoint(APITestCase):
    def test_analytics_for_an_imported_chat(self):
        chat_id = self.client.post(
            "/api/chats/upload",
            files={"file": ("export.json", PERSIAN_EXPORT, "application/json")},
        ).json()["chat"]["id"]

        body = self.client.get(f"/api/analytics/{chat_id}").json()
        self.assertEqual(body["total_messages"], 2)
        self.assertEqual(len(body["participants"]), 2)
        self.assertIn("fa", body["language_breakdown"])
        self.assertEqual(body["avg_response_time_seconds"], 60.0)

    def test_analytics_for_an_unknown_chat_is_a_404(self):
        self.assertEqual(self.client.get("/api/analytics/9999").status_code, 404)


class TestDecisionEndpoints(APITestCase):
    def given_message(self) -> int:
        return self.client.post(
            "/api/messages",
            json={
                "telegram_msg_id": 77,
                "sender_id": "u1",
                "sender_name": "Alice",
                "timestamp": "2026-08-23T10:00:00",
                "text": "Thank you so much for the assistance!",
            },
        ).json()["id"]

    def test_evaluating_a_message_then_reading_the_cache(self):
        message_id = self.given_message()

        evaluated = self.client.post(f"/api/decisions/messages/{message_id}")
        self.assertEqual(evaluated.status_code, 200)
        keys = {item["question_key"] for item in evaluated.json()}
        self.assertEqual(keys, {"tone", "is_conflict"})

        cached = self.client.get(f"/api/decisions/messages/{message_id}").json()
        self.assertEqual({item["question_key"] for item in cached}, keys)

    def test_evaluating_a_chat_window(self):
        self.given_message()
        response = self.client.post("/api/decisions/chats/1", json={"limit": 5})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(i["target_type"] == "chat" for i in response.json()))

    def test_custom_questions(self):
        response = self.client.post(
            "/api/decisions/custom",
            json={
                "state": "Thank you so much for the assistance!",
                "questions": {
                    "sentiment": {
                        "type": "choice",
                        "instructions": "What is the sentiment?",
                        "criteria": {
                            "positive": "gratitude, praise, appreciation",
                            "negative": "complaint, anger",
                        },
                    }
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("sentiment", response.json()["answers"])

    def test_an_engine_failure_is_a_503(self):
        self.app.dependency_overrides[get_decision_service] = lambda: DecisionService(
            message_repo=self.container.message_repository,
            decision_repo=self.container.decision_repository,
            engine=FakeDecisionEngine(fail_with="checkpoint unavailable"),
        )
        response = self.client.post(f"/api/decisions/messages/{self.given_message()}")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("checkpoint unavailable", response.text)


if __name__ == "__main__":
    unittest.main()
