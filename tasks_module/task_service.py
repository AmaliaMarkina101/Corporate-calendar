from __future__ import annotations

from datetime import datetime

from core.db_access import Db
from core.event_access import EventAccess
from core.models import AuthorizationError, User

from .models import STATUSES
from .schema import init_task_tables

DATETIME_FORMAT = "%Y-%m-%d %H:%M"


class TaskService:
    def __init__(self, database, current_user):
        self.db = Db.wrap(database)
        init_task_tables(self.db.conn)
        self.current_user = User.from_any(current_user)
        self.events = EventAccess(self.db)

    # ---------- вспомогательное ----------
    @staticmethod
    def _parse_datetime(value, field_name, required):
        if value is None or not str(value).strip():
            if required:
                raise ValueError(f"Поле «{field_name}» обязательно.")
            return None
        try:
            parsed = datetime.strptime(str(value).strip(), DATETIME_FORMAT)
        except ValueError as exc:
            raise ValueError(f"Поле «{field_name}»: используйте формат ГГГГ-ММ-ДД ЧЧ:ММ.") from exc
        return parsed.strftime(DATETIME_FORMAT)

    def _get_task(self, task_id):
        task = self.db.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not task:
            raise ValueError(f"Задача с id={task_id} не найдена.")
        return task

    def _validate_assignee(self, event_id, assignee_id):
        if assignee_id == self.current_user.id:
            return
        members = self.events.get_team_members_for_event(event_id, self.current_user.id)
        if assignee_id not in [m["id"] for m in members]:
            raise ValueError(
                "Исполнитель должен входить в вашу группу и иметь право работать с задачами события."
            )

    # ---------- проверки прав для интерфейса ----------
    def can_create(self, event_id):
        return self.events.can_edit_tasks(self.current_user.id, event_id)

    def can_change_status(self, task):
        permission = self.events.get_permission(self.current_user.id, task["event_id"])
        if permission not in ("edit_tasks", "full"):
            return False
        return permission == "full" or self.current_user.id in (task["assignee_id"], task["creator_id"])

    def can_assign(self, task):
        if self.current_user.role != "teamlead":
            return False
        permission = self.events.get_permission(self.current_user.id, task["event_id"])
        if permission not in ("edit_tasks", "full"):
            return False
        return (
            permission == "full"
            or self.current_user.id in (task["creator_id"], task["assignee_id"])
            or self.events.is_in_team(self.current_user.id, task["assignee_id"])
            or self.events.is_in_team(self.current_user.id, task["creator_id"])
        )

    # ---------- функции из ТЗ ----------
    def create_task(self, event_id, title, description, assignee_id, deadline, reminder_time=None):
        self.events.require_task_edit(self.current_user.id, event_id)
        title = (title or "").strip()
        if not title:
            raise ValueError("Название задачи не может быть пустым.")
        deadline_value = self._parse_datetime(deadline, "Дедлайн", required=True)
        reminder_value = self._parse_datetime(reminder_time, "Время напоминания", required=False)
        if reminder_value and reminder_value > deadline_value:
            raise ValueError("Время напоминания не может быть позже дедлайна.")

        if self.current_user.role == "teamlead":
            if assignee_id is None:
                assignee_id = self.current_user.id
            self._validate_assignee(event_id, int(assignee_id))
        else:
            # Не-тимлид всегда исполнитель своей задачи, даже если передал другой id.
            assignee_id = self.current_user.id

        return self.db.execute(
            """INSERT INTO tasks
               (event_id, title, description, status, creator_id, assignee_id, reminder_time, deadline)
               VALUES (?, ?, ?, 'not_started', ?, ?, ?, ?)""",
            (
                event_id, title, (description or "").strip(),
                self.current_user.id, int(assignee_id), reminder_value, deadline_value,
            ),
        )

    def change_task_status(self, task_id, new_status):
        if new_status not in STATUSES:
            raise ValueError("Недопустимый статус задачи.")
        task = self._get_task(task_id)
        self.events.require_task_edit(self.current_user.id, task["event_id"])
        if not self.can_change_status(task):
            raise AuthorizationError("Менять статус может исполнитель, создатель задачи или автор события.")
        self.db.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))

    def add_comment(self, task_id, user_id, text):
        task = self._get_task(task_id)
        if user_id != self.current_user.id:
            raise AuthorizationError("Нельзя добавлять комментарии от имени другого пользователя.")
        self.events.require_access(self.current_user.id, task["event_id"])
        comment_text = (text or "").strip()
        if not comment_text:
            raise ValueError("Комментарий не может быть пустым.")
        return self.db.execute(
            "INSERT INTO task_comments (task_id, user_id, text) VALUES (?, ?, ?)",
            (task_id, user_id, comment_text),
        )

    def get_tasks_by_event(self, event_id):
        self.events.require_access(self.current_user.id, event_id)
        return self.db.fetch_all(
            """SELECT t.*, creator.username AS creator_username,
                      assignee.username AS assignee_username
               FROM tasks t
               JOIN users creator ON creator.id = t.creator_id
               JOIN users assignee ON assignee.id = t.assignee_id
               WHERE t.event_id = ?
               ORDER BY CASE t.status
                   WHEN 'in_progress' THEN 0 WHEN 'not_started' THEN 1 ELSE 2 END,
                   t.deadline ASC, t.id DESC""",
            (event_id,),
        )

    def assign_task(self, task_id, new_assignee_id):
        task = self._get_task(task_id)
        if self.current_user.role != "teamlead":
            raise AuthorizationError("Назначать исполнителя может только тимлид.")
        self.events.require_task_edit(self.current_user.id, task["event_id"])
        if not self.can_assign(task):
            raise AuthorizationError("Нельзя переназначать задачу, которая не относится к вашей команде.")
        self._validate_assignee(task["event_id"], int(new_assignee_id))
        self.db.execute("UPDATE tasks SET assignee_id = ? WHERE id = ?", (int(new_assignee_id), task_id))

    def get_comments(self, task_id):
        task = self._get_task(task_id)
        self.events.require_access(self.current_user.id, task["event_id"])
        return self.db.fetch_all(
            """SELECT c.*, u.username
               FROM task_comments c JOIN users u ON u.id = c.user_id
               WHERE c.task_id = ? ORDER BY c.created_at ASC, c.id ASC""",
            (task_id,),
        )
