from __future__ import annotations

import sqlite3
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

        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            teamlead_id INTEGER NOT NULL,
            FOREIGN KEY (teamlead_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS team_members (
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (team_id, user_id),
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS event_members (
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (event_id, user_id),
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'not_started'
                CHECK (status IN ('not_started', 'in_progress', 'done')),
            creator_id INTEGER NOT NULL,
            assignee_id INTEGER NOT NULL,
            reminder_time TEXT NULL,
            deadline TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (creator_id) REFERENCES users(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS task_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_event_id ON tasks(event_id);
        CREATE INDEX IF NOT EXISTS idx_task_comments_task_id ON task_comments(task_id);
        """
        with self.connect() as conn:
            conn.executescript(schema)

    def fetch_one(self, query: str, params: Iterable[Any] = ()) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: Iterable[Any] = ()) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(row) for row in rows]

    def execute(self, query: str, params: Iterable[Any] = ()) -> int:
        """Выполняет изменение и возвращает lastrowid."""
        with self.connect() as conn:
            cursor = conn.execute(query, tuple(params))
            return int(cursor.lastrowid or 0)


db = Database()
