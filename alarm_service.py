"""Логика будильника: какие напоминания по задачам пора показать. Без tkinter."""
from __future__ import annotations

from datetime import datetime, timedelta

from core.db_access import Db
from core.models import User
from tasks_module.schema import init_task_tables

TIME_FORMAT = "%Y-%m-%d %H:%M"  # так TaskService хранит deadline и reminder_time
MISSED_AFTER = timedelta(minutes=10)

_SHOWN_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_reminders_shown (
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shown_at TEXT NOT NULL,
    PRIMARY KEY (task_id, user_id)
);
"""


class AlarmService:
    """Напоминания для одного пользователя: только его невыполненные задачи.

    Показанные напоминания запоминаются в отдельной таблице task_reminders_shown,
    поэтому после перезапуска приложения они не повторяются, а пропущенные
    (приложение было закрыто) показываются при следующем входе.
    """

    def __init__(self, database, user):
        self.db = Db.wrap(database)
        self.user = User.from_any(user)
        init_task_tables(self.db.conn)
        self.db.conn.executescript(_SHOWN_SCHEMA)
        self.db.conn.commit()
        self._active: set[int] = set()            # окно с этим напоминанием сейчас открыто
        self._snoozed: dict[int, datetime] = {}   # отложены до указанного времени

    def poll(self, now: datetime | None = None) -> list[dict]:
        """Возвращает напоминания, которые пора показать, и помечает их как открытые."""
        now = now or datetime.now()
        rows = self.db.fetch_all(
            """SELECT t.id, t.title, t.event_id, t.deadline, t.reminder_time, e.title AS event_title
               FROM tasks t
               JOIN events e ON e.id = t.event_id
               WHERE t.assignee_id = ?
                 AND t.status != 'done'
                 AND t.reminder_time IS NOT NULL
                 AND t.reminder_time <= ?
                 AND NOT EXISTS (SELECT 1 FROM task_reminders_shown s
                                 WHERE s.task_id = t.id AND s.user_id = ?)
               ORDER BY t.reminder_time, t.id""",
            (self.user.id, now.strftime(TIME_FORMAT), self.user.id),
        )
        due = []
        for row in rows:
            task_id = row["id"]
            if task_id in self._active:
                continue
            until = self._snoozed.get(task_id)
            if until is not None:
                if until > now:
                    continue
                del self._snoozed[task_id]
            reminder = datetime.strptime(row["reminder_time"], TIME_FORMAT)
            row["missed"] = reminder < now - MISSED_AFTER
            due.append(row)
            self._active.add(task_id)
        return due

    def acknowledge(self, task_ids, now: datetime | None = None) -> None:
        """Пользователь увидел напоминание: больше не показывать."""
        stamp = (now or datetime.now()).strftime(TIME_FORMAT)
        for task_id in task_ids:
            self.db.conn.execute(
                "INSERT OR IGNORE INTO task_reminders_shown (task_id, user_id, shown_at) VALUES (?, ?, ?)",
                (task_id, self.user.id, stamp),
            )
            self._active.discard(task_id)
            self._snoozed.pop(task_id, None)
        self.db.conn.commit()

    def snooze(self, task_ids, minutes=5, now: datetime | None = None) -> None:
        """Напомнить позже (до перезапуска приложения)."""
        until = (now or datetime.now()) + timedelta(minutes=minutes)
        for task_id in task_ids:
            self._active.discard(task_id)
            self._snoozed[task_id] = until
