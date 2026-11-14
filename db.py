from __future__ import annotations

import sqlite3
import contextlib
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "tasks_app.db"


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def init_db(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'teamlead', 'member'))
        );

        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            creator_id INTEGER NOT NULL REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (group_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            access_type TEXT NOT NULL CHECK (access_type IN ('private', 'limited', 'public')),
            category TEXT NOT NULL DEFAULT 'work' CHECK (category IN ('personal', 'work', 'rest')),
            author_id INTEGER NOT NULL REFERENCES users(id),
            group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS event_access (
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            permission TEXT NOT NULL CHECK (permission IN ('read', 'edit_tasks', 'full')),
            PRIMARY KEY (event_id, user_id)
        );

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

        CREATE INDEX IF NOT EXISTS idx_tasks_event_id ON tasks(event_id);
        CREATE INDEX IF NOT EXISTS idx_task_comments_task_id ON task_comments(task_id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_event
            ON chat_messages(event_id, created_at, id);
        CREATE INDEX IF NOT EXISTS idx_private_messages_pair
            ON private_messages(sender_id, receiver_id, created_at, id);
        """
        with contextlib.closing(self.connect()) as conn, conn:
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(events)")]
            if columns and (
                "author_id" not in columns
                or "access_type" not in columns
                or "group_id" not in columns
            ):
                raise ValueError(
                    "В базе осталась прежняя схема событий. Сохраните её копию "
                    "и подключите базу со схемой из задания."
                )
            conn.executescript(schema)

    def fetch_one(self, query: str, params: Iterable[Any] = ()) -> dict | None:
        with contextlib.closing(self.connect()) as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: Iterable[Any] = ()) -> list[dict]:
        with contextlib.closing(self.connect()) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(row) for row in rows]

    def execute(self, query: str, params: Iterable[Any] = ()) -> int:
        with contextlib.closing(self.connect()) as conn, conn:
            cursor = conn.execute(query, tuple(params))
            return int(cursor.lastrowid or 0)


db = Database()
