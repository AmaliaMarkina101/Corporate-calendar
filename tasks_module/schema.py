"""Таблицы модуля задач."""
from core.db_access import get_connection


TASK_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'not_started'
        CHECK (status IN ('not_started', 'in_progress', 'done')),
    creator_id INTEGER NOT NULL REFERENCES users(id),
    assignee_id INTEGER NOT NULL REFERENCES users(id),
    reminder_time TEXT,
    deadline TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_event_id ON tasks(event_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_task_id ON task_comments(task_id);
"""


def init_task_tables(database) -> None:
    """Создаёт таблицы tasks и task_comments, если их ещё нет. Можно вызывать много раз."""
    connection = get_connection(database)
    connection.executescript(TASK_SCHEMA)
    connection.commit()
