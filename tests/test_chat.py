import pathlib
import sqlite3
import tempfile
import unittest

import auth
import db
import main
from chat import service
from task_service import TaskService


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = db.Database(pathlib.Path(self.directory.name) / "test.db")
        self.database.init_db()
        main.seed_demo_data(self.database)
        self.users = {}
        self.chats = {}
        for row in self.database.fetch_all("SELECT * FROM users"):
            self.users[row["id"]] = auth.User.from_row(row)
            self.chats[row["id"]] = service.ChatService(self.database, self.users[row["id"]])

    def create_event(self, visibility, creator=1, members=()):
        event_id = self.database.execute(
            "INSERT INTO events (team_id, title, creator_id, visibility) VALUES (1, ?, ?, ?)",
            ("Проверка доступа", creator, visibility),
        )
        for user_id in members:
            self.database.execute(
                "INSERT INTO event_members (event_id, user_id) VALUES (?, ?)", (event_id, user_id)
            )
        return event_id

    def test_private_dialog_has_both_directions_and_persists(self):
        text = "Привет, 'Анна'!\nОбсудим проект?"
        self.chats[1].send_private_message(1, 2, text)
        self.chats[2].send_private_message(2, 1, "Да")
        history = self.chats[1].get_private_messages(1, 2)
        self.assertEqual([m["text"] for m in history], [text, "Да"])
        self.assertEqual(history, self.chats[2].get_private_messages(2, 1))
        other_connection = db.Database(self.database.path)
        reopened = service.ChatService(other_connection, self.users[1])
        self.assertEqual(reopened.get_private_messages(1, 2), history)
        personal = [c for c in reopened.get_user_chats(1) if c["type"] == "private"]
        self.assertEqual([(c["id"], c["last_message"]) for c in personal], [(2, "Да")])

    def test_cannot_read_other_dialog_or_impersonate_sender(self):
        self.chats[2].send_private_message(2, 3, "Личное сообщение")
        with self.assertRaises(auth.AuthorizationError):
            self.chats[1].get_private_messages(2, 3)
        with self.assertRaises(auth.AuthorizationError):
            self.chats[1].get_user_chats(2)
        with self.assertRaises(auth.AuthorizationError):
            self.chats[1].send_private_message(2, 3, "Подмена")
        with self.assertRaises(auth.AuthorizationError):
            self.chats[1].send_group_message(1, 2, "Подмена")
        self.assertFalse(any(c["type"] == "private" for c in self.chats[1].get_user_chats(1)))

    def test_empty_messages_and_missing_users_are_rejected(self):
        for text in ("", " \n\t "):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    self.chats[1].send_private_message(1, 2, text)
                with self.assertRaises(ValueError):
                    self.chats[1].send_group_message(1, 1, text)
        with self.assertRaises(ValueError):
            self.chats[1].send_private_message(1, 999, "Привет")
        self.assertEqual(self.chats[1].get_private_messages(1, 2), [])
        self.assertEqual(self.chats[1].get_group_messages(1), [])

    def test_group_access_for_every_visibility(self):
        private = self.create_event("private", creator=2, members=(1, 3, 4))
        restricted = self.create_event("restricted", creator=2, members=(3,))
        public = self.create_event("public")
        expected = {
            private: {2},
            restricted: {2, 3},
            public: {1, 2, 3},
        }
        for event_id, allowed in expected.items():
            for user_id in (1, 2, 3, 4):
                with self.subTest(event=event_id, user=user_id):
                    chat = self.chats[user_id]
                    if user_id in allowed:
                        chat.send_group_message(event_id, user_id, "Разрешено")
                        self.assertTrue(chat.get_group_messages(event_id))
                    else:
                        with self.assertRaises(auth.AuthorizationError):
                            chat.get_group_messages(event_id)
                        with self.assertRaises(auth.AuthorizationError):
                            chat.send_group_message(event_id, user_id, "Запрещено")
                    visible = {c["id"] for c in chat.get_user_chats(user_id) if c["type"] == "group"}
                    self.assertEqual(event_id in visible, user_id in allowed)

    def test_access_revocation_also_hides_history(self):
        event_id = self.create_event("restricted", members=(2,))
        self.chats[2].send_group_message(event_id, 2, "До отзыва доступа")
        self.database.execute("DELETE FROM event_members WHERE event_id = ? AND user_id = 2", (event_id,))
        with self.assertRaises(auth.AuthorizationError):
            self.chats[2].get_group_messages(event_id)
        with self.assertRaises(auth.AuthorizationError):
            self.chats[2].send_group_message(event_id, 2, "После отзыва доступа")
        self.assertNotIn(("group", event_id), {(c["type"], c["id"]) for c in self.chats[2].get_user_chats(2)})
        for chat in self.chats.values():
            with self.assertRaises(auth.AuthorizationError):
                chat.get_group_messages(999)

    def test_group_returns_latest_50_in_order_even_with_equal_times(self):
        for index in range(55):
            self.chats[1].send_group_message(1, 1, str(index))
        self.database.execute("UPDATE chat_messages SET created_at = '2026-11-14 10:00:00'")
        messages = self.chats[2].get_group_messages(1)
        self.assertEqual([m["text"] for m in messages], [str(i) for i in range(5, 55)])

    def test_chat_order_is_based_on_last_message_and_empty_events_remain(self):
        empty_event = self.create_event("public")
        first = self.chats[1].send_private_message(1, 2, "Личное")
        second = self.chats[1].send_group_message(1, 1, "Групповое")
        self.database.execute("UPDATE private_messages SET created_at = '2026-11-14 10:00:00' WHERE id = ?", (first,))
        self.database.execute("UPDATE chat_messages SET created_at = '2026-11-14 10:01:00' WHERE id = ?", (second,))
        chats = self.chats[1].get_user_chats(1)
        self.assertEqual([(c["type"], c["id"]) for c in chats], [("group", 1), ("private", 2), ("group", empty_event)])
        self.database.execute("UPDATE private_messages SET created_at = '2026-11-14 10:02:00' WHERE id = ?", (first,))
        self.assertEqual(self.chats[1].get_user_chats(1)[0]["type"], "private")

    def test_name_search_is_case_insensitive_for_russian(self):
        for query in ("АННА", "ПЕТРОВА", "анна петрова", "MEMBER1"):
            with self.subTest(query=query):
                self.assertEqual([u["id"] for u in self.chats[1].search_users(query)], [2])
        self.assertEqual(self.chats[1].search_users("  "), [])
        self.assertEqual(self.chats[1].search_users("Павел"), [])
        self.assertEqual(self.chats[1].search_users("Несуществующий"), [])

    def test_tasks_still_work_with_shared_permissions(self):
        tasks = TaskService(self.database, self.users[2])
        task_id = tasks.create_task(1, "Проверить чат", "", None, "2026-12-01 12:00")
        tasks.change_task_status(task_id, "in_progress")
        tasks.add_comment(task_id, 2, "Готово к проверке")
        self.assertEqual(tasks.get_tasks_by_event(1)[0]["status"], "in_progress")
        self.assertEqual(tasks.get_comments(task_id)[0]["text"], "Готово к проверке")


class MigrationTests(unittest.TestCase):
    def test_old_database_is_upgraded_without_losing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database = db.Database(pathlib.Path(directory) / "old.db")
            with sqlite3.connect(database.path) as conn:
                conn.executescript("""
                    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                        email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, role TEXT NOT NULL);
                    CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT NOT NULL, teamlead_id INTEGER NOT NULL);
                    CREATE TABLE events (id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL, title TEXT NOT NULL);
                    CREATE TABLE event_members (event_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                        PRIMARY KEY (event_id, user_id));
                    CREATE TABLE tasks (id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL,
                        title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'not_started', creator_id INTEGER NOT NULL,
                        assignee_id INTEGER NOT NULL, reminder_time TEXT,
                        deadline TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                    INSERT INTO users VALUES (1, 'lead', 'lead@example.com', 'demo', 'teamlead');
                    INSERT INTO users VALUES (2, 'member1', 'member1@example.com', 'demo', 'member');
                    INSERT INTO teams VALUES (1, 'Старая команда', 1);
                    INSERT INTO events VALUES (1, 1, 'Старое событие');
                    INSERT INTO event_members VALUES (1, 2);
                    INSERT INTO tasks (id, event_id, title, creator_id, assignee_id, deadline)
                        VALUES (1, 1, 'Старая задача', 1, 2, '2026-12-01 12:00');
                """)
            database.init_db()
            database.init_db()
            user = auth.User.from_row(database.fetch_one("SELECT * FROM users WHERE id = 2"))
            chat = service.ChatService(database, user)
            chat.send_group_message(1, 2, "После обновления")
            self.assertEqual(chat.get_group_messages(1)[0]["text"], "После обновления")
            self.assertEqual(database.fetch_one("SELECT title FROM tasks WHERE id = 1")["title"], "Старая задача")
            event = database.fetch_one("SELECT * FROM events WHERE id = 1")
            self.assertEqual((event["title"], event["visibility"], event["creator_id"]), ("Старое событие", "restricted", 1))
            self.assertEqual(database.fetch_one("PRAGMA foreign_key_check"), None)


if __name__ == "__main__":
    unittest.main()
