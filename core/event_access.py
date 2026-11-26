"""Права доступа к событию. Правила видимости совпадают с календарём."""
from __future__ import annotations

from .db_access import Db
from .models import AuthorizationError

_EDIT_PERMISSIONS = ("edit_tasks", "full")


class EventAccess:
    def __init__(self, database):
        self.db = Db.wrap(database)

    def get_event(self, event_id):
        event = self.db.fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
        if not event:
            raise ValueError("Событие не найдено.")
        return event

    def get_permission(self, user_id, event_id):
        """'full' | 'edit_tasks' | 'read' | None (нет доступа).

        Правила те же, что в календаре:
        - автор события: полный доступ;
        - private: больше никто;
        - limited: только те, кому выдан доступ в event_access;
        - public без группы: все; public с группой: только участники группы.
        """
        if not self.db.fetch_one("SELECT id FROM users WHERE id = ?", (user_id,)):
            return None
        event = self.db.fetch_one(
            "SELECT author_id, access_type, group_id FROM events WHERE id = ?", (event_id,)
        )
        if not event:
            return None
        if event["author_id"] == user_id:
            return "full"
        access_type = event["access_type"]
        if access_type == "limited":
            access = self.db.fetch_one(
                "SELECT permission FROM event_access WHERE event_id = ? AND user_id = ?",
                (event_id, user_id),
            )
            return access["permission"] if access else None
        if access_type == "public":
            if event["group_id"] is None or self.db.fetch_one(
                "SELECT 1 AS ok FROM group_members WHERE group_id = ? AND user_id = ?",
                (event["group_id"], user_id),
            ):
                return "edit_tasks"
        return None

    def has_access(self, user_id, event_id):
        return self.get_permission(user_id, event_id) is not None

    def can_edit_tasks(self, user_id, event_id):
        return self.get_permission(user_id, event_id) in _EDIT_PERMISSIONS

    def require_access(self, user_id, event_id):
        if not self.has_access(user_id, event_id):
            raise AuthorizationError("У вас нет доступа к этому событию.")

    def require_task_edit(self, user_id, event_id):
        permission = self.get_permission(user_id, event_id)
        if permission not in _EDIT_PERMISSIONS:
            raise AuthorizationError("У вас нет права создавать и изменять задачи этого события.")
        return permission

    def is_in_team(self, teamlead_id, user_id):
        """Состоит ли user_id в какой-либо группе, созданной тимлидом."""
        return bool(
            self.db.fetch_one(
                """SELECT 1 AS ok FROM group_members gm
                   JOIN groups g ON g.id = gm.group_id
                   WHERE g.creator_id = ? AND gm.user_id = ?""",
                (teamlead_id, user_id),
            )
        )

    def get_team_members_for_event(self, event_id, teamlead_id):
        """Участники команд тимлида, которым можно поручить задачи этого события."""
        members = self.db.fetch_all(
            """SELECT DISTINCT u.id, u.username, u.email, u.role
               FROM users u
               JOIN group_members gm ON gm.user_id = u.id
               JOIN groups g ON g.id = gm.group_id
               WHERE g.creator_id = ? AND u.id != ?
               ORDER BY u.username""",
            (teamlead_id, teamlead_id),
        )
        return [m for m in members if self.can_edit_tasks(m["id"], event_id)]
