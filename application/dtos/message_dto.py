from dataclasses import dataclass
from datetime import datetime


@dataclass
class MessageDTO:
    id: int
    sender_id: str
    sender_name: str
    timestamp: datetime
    text: str
    word_count: int
    is_question: bool