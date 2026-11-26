import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path="calendar_demo.db"):
        self.db_path = str(Path(db_path))
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.conn = self.connection

    def init_db(self):
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'member',
                first_name TEXT,
                last_name TEXT
            );

            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                creator_id INTEGER NOT NULL,
                FOREIGN KEY (creator_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (group_id, user_id),
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                access_type TEXT NOT NULL CHECK (access_type IN ('private', 'limited', 'public')),
                category TEXT NOT NULL DEFAULT 'personal' CHECK (category IN ('personal', 'work', 'rest')),
                author_id INTEGER NOT NULL,
                group_id INTEGER,
                FOREIGN KEY (author_id) REFERENCES users(id),
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS event_access (
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                permission TEXT NOT NULL CHECK (permission IN ('read', 'edit_tasks', 'full')),
                PRIMARY KEY (event_id, user_id),
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_events_author ON events(author_id);
            CREATE INDEX IF NOT EXISTS idx_events_group ON events(group_id);
            CREATE INDEX IF NOT EXISTS idx_event_access_user ON event_access(user_id);
            """
        )
        self.connection.commit()
        return self

    def close(self):
        self.connection.close()
