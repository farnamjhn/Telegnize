import json
import unittest
from datetime import datetime

from fastapi.testclient import TestClient

from domain.models.message import ContentType, Message
from domain.models.chat import Chat
from infrastructure.api.controllers import app
from infrastructure.api.dependencies import (
    get_message_repo,
    get_chat_repo,
    get_analytics_service,
    get_ingestion_service,
    get_decision_service,
)
from infrastructure.repository.sqlite_chat_repository import SQLiteChatRepository
from infrastructure.repository.sqlite_message_repository import SQLiteMessageRepository
from application.services.analytics_service import AnalyticsService
from application.services.ingestion_service import IngestionService
from application.services.decision_service import DecisionService


class TestAPIControllers(unittest.TestCase):
    def setUp(self):
        # Use shared in-memory databases for testing
        self.test_message_repo = SQLiteMessageRepository(":memory:")
        self.test_chat_repo = SQLiteChatRepository(":memory:")
        self.test_analytics_service = AnalyticsService(self.test_chat_repo, self.test_message_repo)
        self.test_ingestion_service = IngestionService(self.test_chat_repo, self.test_message_repo)
        self.test_decision_service = DecisionService(self.test_message_repo)

        app.dependency_overrides[get_message_repo] = lambda: self.test_message_repo
        app.dependency_overrides[get_chat_repo] = lambda: self.test_chat_repo
        app.dependency_overrides[get_analytics_service] = lambda: self.test_analytics_service
        app.dependency_overrides[get_ingestion_service] = lambda: self.test_ingestion_service
        app.dependency_overrides[get_decision_service] = lambda: self.test_decision_service

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.test_message_repo.close()
        self.test_chat_repo.close()

    def test_health_check(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["app"], "Telegnize API")

    def test_create_and_get_message(self):
        payload = {
            "telegram_msg_id": 501,
            "sender_id": "user_500",
            "sender_name": "Alice",
            "timestamp": "2026-08-23T10:00:00",
            "text": "Is this a question?",
            "reply_to_msg_id": None,
            "content_type": "text",
            "is_forwarded": False,
        }
        response = self.client.post("/messages", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["sender_id"], "user_500")
        self.assertEqual(data["text"], "Is this a question?")
        self.assertTrue(data["is_question"])
        self.assertEqual(data["word_count"], 4)

        # Get by DB ID
        msg_id = data["id"]
        get_res = self.client.get(f"/messages/{msg_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["sender_name"], "Alice")

        # Get by Telegram ID
        tg_res = self.client.get("/messages/telegram/501")
        self.assertEqual(tg_res.status_code, 200)
        self.assertEqual(tg_res.json()["id"], msg_id)

    def test_get_all_messages(self):
        msg1 = Message(
            id=0,
            telegram_msg_id=1,
            sender_id="u1",
            sender_name="User 1",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 8, 23, 10, 0, 0),
            text="First message",
        )
        msg2 = Message(
            id=0,
            telegram_msg_id=2,
            sender_id="u2",
            sender_name="User 2",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 8, 23, 11, 0, 0),
            text="Second message",
        )
        self.test_message_repo.save_batch([msg1, msg2])

        response = self.client.get("/messages")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["sender_name"], "User 1")
        self.assertEqual(items[1]["sender_name"], "User 2")

    def test_parse_json_payload(self):
        payload = {
            "name": "Chat",
            "messages": [
                {
                    "id": 10,
                    "type": "message",
                    "date": "2026-08-23T12:00:00",
                    "from": "Bob",
                    "from_id": "user_bob",
                    "text": "Hello API test!"
                }
            ]
        }
        response = self.client.post("/messages/parse", json=payload)
        self.assertEqual(response.status_code, 201)
        res_data = response.json()
        self.assertEqual(res_data["parsed_count"], 1)
        self.assertEqual(res_data["messages"][0]["sender_name"], "Bob")
        self.assertEqual(res_data["messages"][0]["text"], "Hello API test!")

    def test_upload_json_file(self):
        export_data = {
            "name": "Test Group",
            "messages": [
                {
                    "id": 99,
                    "type": "message",
                    "date": "2026-08-23T14:00:00",
                    "from": "Charlie",
                    "from_id": "user_charlie",
                    "text": "Uploaded message test"
                }
            ]
        }
        file_bytes = json.dumps(export_data).encode("utf-8")
        files = {"file": ("result.json", file_bytes, "application/json")}

        response = self.client.post("/messages/upload", files=files)
        self.assertEqual(response.status_code, 201)
        res_data = response.json()
        self.assertEqual(res_data["parsed_count"], 1)
        self.assertEqual(res_data["messages"][0]["sender_name"], "Charlie")

    def test_chat_streaming_upload_and_analytics(self):
        export_data = {
            "name": "Armita",
            "type": "personal_chat",
            "id": 129778989,
            "messages": [
                {
                    "id": 1,
                    "type": "message",
                    "date": "2026-05-27T00:01:00",
                    "from": "Farnam",
                    "from_id": "user_farnam",
                    "text": "سلام، چطوری؟"
                },
                {
                    "id": 2,
                    "type": "message",
                    "date": "2026-05-27T00:02:00",
                    "from": "Armita",
                    "from_id": "user_armita",
                    "reply_to_message_id": 1,
                    "text": "سلام قربانت تو چطوری؟"
                }
            ]
        }
        file_bytes = json.dumps(export_data).encode("utf-8")
        files = {"file": ("export.json", file_bytes, "application/json")}

        upload_res = self.client.post("/api/chats/upload", files=files)
        self.assertEqual(upload_res.status_code, 201)
        upload_data = upload_res.json()
        self.assertEqual(upload_data["total_messages"], 2)
        chat_id = upload_data["chat"]["id"]

        # Analytics endpoint
        analytics_res = self.client.get(f"/api/analytics/{chat_id}")
        self.assertEqual(analytics_res.status_code, 200)
        analytics_data = analytics_res.json()
        self.assertEqual(analytics_data["total_messages"], 2)
        self.assertEqual(len(analytics_data["participants"]), 2)
        self.assertIn("fa", analytics_data["language_breakdown"])

    def test_custom_laya_decision(self):
        payload = {
            "state": "Thank you so much for the assistance!",
            "questions": {
                "sentiment": {
                    "type": "choice",
                    "instructions": "What is the sentiment?",
                    "criteria": {
                        "positive": "gratitude, praise, appreciation",
                        "negative": "complaint, anger"
                    }
                }
            }
        }
        res = self.client.post("/api/decisions/custom", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("answers", data)
        self.assertIn("sentiment", data["answers"])


if __name__ == "__main__":
    unittest.main()
