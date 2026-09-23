-- Telegnize SQLite schema.
-- Applied once per Database instance; every statement must be idempotent.

CREATE TABLE IF NOT EXISTS chats (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id  INTEGER UNIQUE NOT NULL,
    name              TEXT    NOT NULL,
    type              TEXT    NOT NULL DEFAULT 'personal_chat',
    total_messages    INTEGER NOT NULL DEFAULT 0,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id          INTEGER NOT NULL DEFAULT 1 REFERENCES chats(id) ON DELETE CASCADE,
    telegram_msg_id  INTEGER NOT NULL,
    sender_id        TEXT    NOT NULL,
    sender_name      TEXT    NOT NULL,
    timestamp        DATETIME NOT NULL,
    text_content     TEXT    NOT NULL DEFAULT '',
    normalized_text  TEXT    NOT NULL DEFAULT '',
    language         TEXT    NOT NULL DEFAULT 'unknown',
    content_type     TEXT    NOT NULL DEFAULT 'text',
    reply_to_msg_id  INTEGER,
    is_forwarded     INTEGER NOT NULL DEFAULT 0,
    -- Derived at write time so analytics never has to load rows into Python.
    word_count       INTEGER NOT NULL DEFAULT 0,
    char_count       INTEGER NOT NULL DEFAULT 0,
    is_question      INTEGER NOT NULL DEFAULT 0,
    is_cold_closure  INTEGER NOT NULL DEFAULT 0,
    -- Asks something by punctuation or by wording; a short validation and
    -- nothing else. Both are whole-message readings, see domain/models.
    is_interrogative INTEGER NOT NULL DEFAULT 0,
    is_backchannel   INTEGER NOT NULL DEFAULT 0,
    -- Length of a voice message or video, as the export reports it.
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    -- Expressive markers; see domain/models/lexicons.py for what they mean.
    exclamation_count          INTEGER NOT NULL DEFAULT 0,
    emoji_count                INTEGER NOT NULL DEFAULT 0,
    affection_count            INTEGER NOT NULL DEFAULT 0,
    apology_count              INTEGER NOT NULL DEFAULT 0,
    gratitude_count            INTEGER NOT NULL DEFAULT 0,
    self_reference_count       INTEGER NOT NULL DEFAULT 0,
    collective_reference_count INTEGER NOT NULL DEFAULT 0,
    absolutist_count           INTEGER NOT NULL DEFAULT 0,
    elongation_count           INTEGER NOT NULL DEFAULT 0,
    hedge_count                INTEGER NOT NULL DEFAULT 0,
    link_count                 INTEGER NOT NULL DEFAULT 0,
    UNIQUE(chat_id, telegram_msg_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_ts     ON messages(chat_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_chat_sender ON messages(chat_id, sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_reply  ON messages(chat_id, reply_to_msg_id);

CREATE TABLE IF NOT EXISTS decisions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type    TEXT NOT NULL,          -- 'message' | 'chat'
    target_id      INTEGER NOT NULL,
    question_key   TEXT NOT NULL,
    decision_type  TEXT NOT NULL,          -- 'choice' | 'score' | 'noul'
    result_value   TEXT NOT NULL,
    confidence     REAL NOT NULL DEFAULT 0.0,
    probabilities  TEXT NOT NULL DEFAULT '{}',  -- JSON object
    engine_metadata TEXT NOT NULL DEFAULT '{}', -- JSON object
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(target_type, target_id, question_key)
);

CREATE INDEX IF NOT EXISTS idx_decisions_target ON decisions(target_type, target_id);

-- Messages created outside an import (single-message POSTs, ad-hoc parsing)
-- need a chat to hang off; row 1 is reserved for them.
INSERT OR IGNORE INTO chats (id, telegram_chat_id, name, type)
VALUES (1, 0, 'Default Chat', 'personal_chat');
