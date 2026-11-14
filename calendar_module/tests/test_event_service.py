import tempfile
import unittest
from pathlib import Path

from calendar_module.database import Database
from calendar_module.event_service import (
    add_event_access,
    add_user_to_group,
    create_event,
    create_group,
    get_events_for_user,
    remove_event_access,
)


class EventServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.db").init_db()
        self.database.connection.executemany(
            "INSERT INTO users (id, username, email, password, role) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "author", "author@example.com", "", "teamlead"),
                (2, "invited", "invited@example.com", "", "member"),
                (3, "outsider", "outsider@example.com", "", "member"),
            ],
        )
        self.database.connection.commit()

    def tearDown(self):
        self.database.close()
        self.temp_dir.cleanup()

    def test_private_event_is_visible_only_to_author(self):
        create_event("Private", "2026-11-15 09:00", "2026-11-15 10:00", 1, "private", database=self.database)
        self.assertEqual(len(get_events_for_user(1, self.database)), 1)
        self.assertEqual(len(get_events_for_user(2, self.database)), 0)

    def test_limited_event_is_visible_to_invited_user_and_can_be_revoked(self):
        event_id = create_event("Limited", "2026-11-15 09:00", "2026-11-15 10:00", 1, "limited", database=self.database)
        add_event_access(event_id, 2, "read", self.database)
        invited_events = get_events_for_user(2, self.database)
        self.assertEqual(len(invited_events), 1)
        self.assertEqual(invited_events[0]["user_permission"], "read")
        self.assertTrue(remove_event_access(event_id, 2, self.database))
        self.assertEqual(len(get_events_for_user(2, self.database)), 0)

    def test_group_public_event_is_visible_to_group_members(self):
        group_id = create_group("Team", 1, self.database)
        add_user_to_group(group_id, 2, self.database)
        create_event(
            "Public for group",
            "2026-11-15 09:00",
            "2026-11-15 10:00",
            1,
            "public",
            group_id=group_id,
            database=self.database,
        )
        self.assertEqual(len(get_events_for_user(2, self.database)), 1)
        self.assertEqual(len(get_events_for_user(3, self.database)), 0)

    def test_event_with_end_before_start_is_rejected(self):
        with self.assertRaises(ValueError):
            create_event("Wrong dates", "2026-11-16 10:00", "2026-11-15 10:00", 1, "private", database=self.database)

    def test_permission_is_validated(self):
        event_id = create_event("Limited", "2026-11-15 09:00", "2026-11-15 10:00", 1, "limited", database=self.database)
        with self.assertRaises(ValueError):
            add_event_access(event_id, 2, "wrong", self.database)


if __name__ == "__main__":
    unittest.main()
