import unittest
from datetime import datetime, timedelta

from alarm_service import AlarmService
from calendar_module.database import Database
from calendar_module.event_service import create_event
from tasks_module.task_service import TaskService

NOW = datetime(2026, 12, 1, 12, 0)


def fmt(moment):
    return moment.strftime("%Y-%m-%d %H:%M")


class AlarmTests(unittest.TestCase):
    def setUp(self):
        self.database = Database(":memory:").init_db()
        self.database.connection.executemany(
            "INSERT INTO users (id, username, email, role) VALUES (?, ?, ?, ?)",
            [(1, "lead", "l@x.com", "teamlead"), (2, "maria", "m@x.com", "member")],
        )
        self.database.connection.commit()
        self.event = create_event("Проект", "2026-12-01 09:00", "2026-12-02 18:00", 1, "public",
                                  database=self.database)
        self.lead = TaskService(self.database, {"id": 1, "username": "lead", "role": "teamlead"})
        self.alarm = AlarmService(self.database, {"id": 1, "username": "lead", "role": "teamlead"})

    def task(self, reminder, title="Задача"):
        return self.lead.create_task(self.event, title, "", 1, "2026-12-05 18:00", reminder)

    def test_fires_only_when_time_has_come(self):
        self.task(fmt(NOW + timedelta(minutes=1)))
        self.assertEqual(self.alarm.poll(NOW), [])
        self.assertEqual(len(self.alarm.poll(NOW + timedelta(minutes=1))), 1)

    def test_not_repeated_while_open_or_after_acknowledge(self):
        task_id = self.task(fmt(NOW))
        first = self.alarm.poll(NOW)
        self.assertEqual([i["id"] for i in first], [task_id])
        self.assertEqual(self.alarm.poll(NOW), [])          # окно ещё открыто
        self.alarm.acknowledge([task_id], NOW)
        self.assertEqual(self.alarm.poll(NOW), [])
        again = AlarmService(self.database, {"id": 1, "username": "lead", "role": "teamlead"})
        self.assertEqual(again.poll(NOW), [])               # и после перезапуска приложения

    def test_unacknowledged_reminder_returns_after_restart(self):
        self.task(fmt(NOW))
        self.alarm.poll(NOW)
        restarted = AlarmService(self.database, {"id": 1, "username": "lead", "role": "teamlead"})
        self.assertEqual(len(restarted.poll(NOW)), 1)

    def test_snooze(self):
        task_id = self.task(fmt(NOW))
        self.alarm.poll(NOW)
        self.alarm.snooze([task_id], 5, NOW)
        self.assertEqual(self.alarm.poll(NOW + timedelta(minutes=4)), [])
        self.assertEqual(len(self.alarm.poll(NOW + timedelta(minutes=5))), 1)

    def test_done_tasks_and_no_reminder_are_skipped(self):
        done = self.task(fmt(NOW), "готово")
        self.lead.change_task_status(done, "done")
        self.task(None, "без напоминания")
        self.assertEqual(self.alarm.poll(NOW + timedelta(hours=1)), [])

    def test_only_assignee_gets_reminder(self):
        self.task(fmt(NOW))
        other = AlarmService(self.database, {"id": 2, "username": "maria", "role": "member"})
        self.assertEqual(other.poll(NOW), [])

    def test_missed_flag(self):
        self.task(fmt(NOW - timedelta(hours=3)))
        item = self.alarm.poll(NOW)[0]
        self.assertTrue(item["missed"])
        self.assertEqual(item["event_title"], "Проект")


if __name__ == "__main__":
    unittest.main()
