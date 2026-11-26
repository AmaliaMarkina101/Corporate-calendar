"""Таблицы модуля чата."""
from core.db_access import get_connection

CHAT_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL CHECK (length(trim(text)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS private_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL REFERENCES users(id),
    receiver_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL CHECK (length(trim(text)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_event ON chat_messages(event_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_private_messages_pair ON private_messages(sender_id, receiver_id, created_at, id);
"""


def init_chat_tables(database) -> None:
    """Создаёт таблицы чата, если их ещё нет. Можно вызывать много раз."""
    connection = get_connection(database)
    connection.executescript(CHAT_SCHEMA)
    connection.commit()
