from __future__ import annotations

from datetime import datetime
from typing import Any

from db import Database
from auth import User, AuthorizationError
from event_service import EventService


STATUSES = {
    "not_started": "Не начата",
    "in_progress": "В работе",
    "done": "Выполнена",
}


class TaskService:
    def __init__(self, database: Database, current_user: User):
        self.db = database
        self.current_user = current_user
        self.events = EventService(database)

    @staticmethod
    def _parse_datetime(value: str | None, field_name: str, required: bool) -> str | None:
        if value is None or not str(value).strip():
            if required:
                raise ValueError(f"Поле «{field_name}» обязательно.")
            return None
        value = str(value).strip()
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError as exc:
            raise ValueError(
                f"Поле «{field_name}»: используйте формат ГГГГ-ММ-ДД ЧЧ:ММ."
            ) from exc
        return parsed.strftime("%Y-%m-%d %H:%M")

    def _get_task(self, task_id: int) -> dict:
        task = self.db.fetch_one("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not task:
            raise ValueError(f"Задача с id={task_id} не найдена.")
        return task

    def create_task(
        self,
        event_id: int,
        title: str,
        description: str,
        assignee_id: int | None,
        deadline: str,
        reminder_time: str | None = None,
    ) -> int:
        self.events.require_event_access(self.current_user.id, event_id)
        title = (title or "").strip()
        if not title:
            raise ValueError("Название задачи не может быть пустым.")
        deadline_value = self._parse_datetime(deadline, "Дедлайн", required=True)
        reminder_value = self._parse_datetime(
            reminder_time, "Время напоминания", required=False
        )
        if reminder_value and reminder_value > deadline_value:
            raise ValueError("Время напоминания не может быть позже дедлайна.")

        if self.current_user.role == "teamlead":
            if not self.events.is_teamlead_of_event(self.current_user.id, event_id):
                raise AuthorizationError("Назначать исполнителей может только тимлид этой команды.")
            if assignee_id is None:
                assignee_id = self.current_user.id
            self._validate_assignee(event_id, int(assignee_id))
        else:
            # Участник не может подменить исполнителя аргументом функции.
            assignee_id = self.current_user.id

        return self.db.execute(
            """INSERT INTO tasks
               (event_id, title, description, status, creator_id, assignee_id, reminder_time, deadline)
               VALUES (?, ?, ?, 'not_started', ?, ?, ?, ?)""",
            (
                event_id, title, (description or "").strip(),
                self.current_user.id, assignee_id, reminder_value, deadline_value,
            ),
        )

    def change_task_status(self, task_id: int, new_status: str) -> None:
        if new_status not in STATUSES:
            raise ValueError("Недопустимый статус задачи.")
        task = self._get_task(task_id)
        self.events.require_event_access(self.current_user.id, task["event_id"])
        can_change = (
            self.current_user.role == "admin"
            or task["assignee_id"] == self.current_user.id
            or task["creator_id"] == self.current_user.id
            or self.events.is_teamlead_of_event(self.current_user.id, task["event_id"])
        )
        if not can_change:
            raise AuthorizationError("Менять статус может исполнитель, создатель или тимлид команды.")
        self.db.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))

    def add_comment(self, task_id: int, user_id: int, text: str) -> int:
        task = self._get_task(task_id)
        self.events.require_event_access(user_id, task["event_id"])
        # Не разрешаем вызывать функцию от имени другого пользователя.
        if user_id != self.current_user.id and self.current_user.role != "admin":
            raise AuthorizationError("Нельзя добавлять комментарии от имени другого пользователя.")
        comment_text = (text or "").strip()
        if not comment_text:
            raise ValueError("Комментарий не может быть пустым.")
        return self.db.execute(
            "INSERT INTO task_comments (task_id, user_id, text) VALUES (?, ?, ?)",
            (task_id, user_id, comment_text),
        )

    def get_tasks_by_event(self, event_id: int) -> list[dict]:
        self.events.require_event_access(self.current_user.id, event_id)
        return self.db.fetch_all(
            """SELECT t.*, creator.username AS creator_username,
                      assignee.username AS assignee_username
               FROM tasks t
               JOIN users creator ON creator.id=t.creator_id
               JOIN users assignee ON assignee.id=t.assignee_id
               WHERE t.event_id=?
               ORDER BY CASE t.status
                   WHEN 'in_progress' THEN 0 WHEN 'not_started' THEN 1 ELSE 2 END,
                   t.deadline ASC, t.id DESC""",
            (event_id,),
        )

    def assign_task(self, task_id: int, new_assignee_id: int) -> None:
        task = self._get_task(task_id)
        self.events.require_event_access(self.current_user.id, task["event_id"])
        if self.current_user.role != "teamlead" or not self.events.is_teamlead_of_event(
            self.current_user.id, task["event_id"]
        ):
            raise AuthorizationError("Назначать исполнителя может только тимлид этой команды.")
        self._validate_assignee(task["event_id"], new_assignee_id)
        self.db.execute(
            "UPDATE tasks SET assignee_id=? WHERE id=?",
            (new_assignee_id, task_id),
        )

    def _validate_assignee(self, event_id: int, assignee_id: int) -> None:
        event = self.events.get_event(event_id)
        if assignee_id == event["teamlead_id"]:
            return
        valid = self.db.fetch_one(
            """SELECT 1 AS ok FROM team_members tm
               WHERE tm.team_id=? AND tm.user_id=?""",
            (event["team_id"], assignee_id),
        )
        if not valid:
            raise ValueError("Исполнитель должен входить в команду этого события.")

    def get_comments(self, task_id: int) -> list[dict]:
        task = self._get_task(task_id)
        self.events.require_event_access(self.current_user.id, task["event_id"])
        return self.db.fetch_all(
            """SELECT c.*, u.username
               FROM task_comments c JOIN users u ON u.id=c.user_id
               WHERE c.task_id=? ORDER BY c.created_at ASC, c.id ASC""",
            (task_id,),
        )
