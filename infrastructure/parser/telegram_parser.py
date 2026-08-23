import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from domain.models.message import ContentType, Message, MessageId


class TelegramJsonParser:
    """Parses Telegram exported JSONs into Message entity."""

    def parse_message_dict(self, msg_dict: Dict[str, Any]) -> Optional[Message]:
        """Parses a single Telegram message dictionary into a domain Message entity."""
        if not isinstance(msg_dict, dict):
            return None

        # Skip service messages or non-message entries
        if msg_dict.get("type") != "message":
            return None

        if "id" not in msg_dict:
            return None

        try:
            telegram_msg_id = int(msg_dict["id"])
        except (ValueError, TypeError):
            return None

        # Sender ID extraction
        from_id = msg_dict.get("from_id")
        if from_id is not None:
            sender_id = str(from_id)
        else:
            sender_id = str(msg_dict.get("actor_id", msg_dict.get("from", "unknown")))

        sender_name = str(msg_dict.get("from", msg_dict.get("actor", "Unknown")))

        # Reply to message ID handling
        raw_reply_id = msg_dict.get("reply_to_message_id", msg_dict.get("reply_to_msg_id"))
        if raw_reply_id is not None:
            try:
                reply_to_msg_id = int(raw_reply_id)
                reply_to_id = MessageId(reply_to_msg_id)
            except (ValueError, TypeError):
                reply_to_msg_id = None
                reply_to_id = None
        else:
            reply_to_msg_id = None
            reply_to_id = None

        # Timestamp parsing
        timestamp = self._parse_timestamp(msg_dict)

        # Text extraction
        text = self._extract_text(msg_dict.get("text", ""))

        # Content type determination
        content_type = self._determine_content_type(msg_dict)

        # Forwarded status
        is_forwarded = bool(
            msg_dict.get("forwarded_from")
            or msg_dict.get("forwarded_from_id")
            or msg_dict.get("is_forwarded", False)
        )

        return Message(
            id=0,
            telegram_msg_id=telegram_msg_id,
            sender_id=sender_id,
            sender_name=sender_name,
            reply_to_msg_id=reply_to_msg_id,
            timestamp=timestamp,
            text=text,
            content_type=content_type,
            reply_to_id=reply_to_id,
            is_forwarded=is_forwarded,
        )

    def parse_data(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
    ) -> List[Message]:
        """Parses a dictionary or list containing Telegram exported JSON data."""
        if isinstance(data, dict):
            messages_raw = data.get("messages", [data])
        elif isinstance(data, list):
            messages_raw = data
        else:
            raise ValueError("Input data must be a dict or list.")

        parsed_messages: List[Message] = []
        for msg_dict in messages_raw:
            msg = self.parse_message_dict(msg_dict)
            if msg is not None:
                parsed_messages.append(msg)

        return parsed_messages

    def parse_json(self, json_str: str) -> List[Message]:
        """Parses a JSON string into Message entities."""
        data = json.loads(json_str)
        return self.parse_data(data)

    def parse_file(self, file_path: Union[str, Path]) -> List[Message]:
        """Parses a Telegram export JSON file into Message entities."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.parse_data(data)

    def _extract_text(self, text_val: Any) -> str:
        """Extracts plain text from Telegram text field (which can be str, list of entity dicts, or None)."""
        if isinstance(text_val, str):
            return text_val
        elif isinstance(text_val, list):
            parts = []
            for part in text_val:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    parts.append(str(part.get("text", "")))
            return "".join(parts)
        elif text_val is None:
            return ""
        return str(text_val)

    def _parse_timestamp(self, msg_dict: Dict[str, Any]) -> datetime:
        """Parses timestamp from 'date' string or 'date_unixtime' integer."""
        date_str = msg_dict.get("date")
        if date_str and isinstance(date_str, str):
            try:
                return datetime.fromisoformat(date_str)
            except ValueError:
                pass
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    pass

        unixtime = msg_dict.get("date_unixtime")
        if unixtime is not None:
            try:
                return datetime.fromtimestamp(int(unixtime))
            except (ValueError, TypeError):
                pass

        return datetime.now()

    def _determine_content_type(self, msg_dict: Dict[str, Any]) -> ContentType:
        """Determines ContentType from Telegram message fields."""
        media_type = msg_dict.get("media_type")

        if media_type == "voice_message":
            return ContentType.VOICE

        if media_type == "sticker" or "sticker_emoji" in msg_dict:
            return ContentType.STICKER

        if "photo" in msg_dict or media_type == "photo":
            return ContentType.PHOTO

        if (
            media_type in ("document", "video_file", "animation", "audio_file", "video_message")
            or "file" in msg_dict
        ):
            return ContentType.DOCUMENT

        return ContentType.TEXT