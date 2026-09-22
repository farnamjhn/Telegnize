-- Schema for Telegnize SQLite Database

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'personal_chat',
    total_messages INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL DEFAULT 1,
    telegram_msg_id INTEGER NOT NULL,
    sender_id TEXT NOT NULL,
    sender_name TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    text_content TEXT,
    normalized_text TEXT,
    language TEXT DEFAULT 'unknown',
    content_type TEXT NOT NULL DEFAULT 'text',
    reply_to_msg_id INTEGER,
    is_forwarded BOOLEAN DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    char_count INTEGER DEFAULT 0,
    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    UNIQUE(chat_id, telegram_msg_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_chat_sender ON messages(chat_id, sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_reply ON messages(chat_id, reply_to_msg_id);
CREATE INDEX IF NOT EXISTS idx_messages_telegram_msg_id ON messages(telegram_msg_id);

CREATE TABLE IF NOT EXISTS laya_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL, -- 'message' or 'chat'
    target_id INTEGER NOT NULL,
    question_key TEXT NOT NULL,
    decision_type TEXT NOT NULL, -- 'choice', 'score', 'noul'
    result_value TEXT NOT NULL,
    confidence REAL,
    probabilities TEXT, -- JSON-encoded dictionary
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(target_type, target_id, question_key)
);

CREATE INDEX IF NOT EXISTS idx_decisions_target ON laya_decisions(target_type, target_id);
