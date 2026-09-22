from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Set


@dataclass
class Chat:
    id: int
    telegram_chat_id: int
    name: str
    type: str = "personal_chat"
    total_messages: int = 0
    created_at: Optional[datetime] = None
    participants: Set[str] = field(default_factory=set)
