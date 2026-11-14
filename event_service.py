from auth import AuthorizationError


class EventService:
    def __init__(self, database):
        self.db = database

    def get_event(self, event_id):
        event = self.db.fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
        if not event:
            raise ValueError("Событие не найдено.")
        return event

    def get_permission(self, user_id, event_id):
        if not self.db.fetch_one("SELECT id FROM users WHERE id = ?", (user_id,)):
            return None
        event = self.db.fetch_one(
            "SELECT author_id, access_type FROM events WHERE id = ?", (event_id,)
        )
        if not event:
            return None
        if event["author_id"] == user_id:
            return "full"
        if event["access_type"] == "private":
            return None
        if event["access_type"] == "public":
            return "edit_tasks"
        if event["access_type"] == "limited":
            access = self.db.fetch_one(
                "SELECT permission FROM event_access WHERE event_id = ? AND user_id = ?",
                (event_id, user_id),
            )
            return access["permission"] if access else None
        return None

    def has_access_to_event(self, user_id, event_id):
        return self.get_permission(user_id, event_id) is not None

    def require_event_access(self, user_id, event_id):
        if not self.has_access_to_event(user_id, event_id):
            raise AuthorizationError("У вас нет доступа к этому событию.")

    def require_task_edit(self, user_id, event_id):
        permission = self.get_permission(user_id, event_id)
        if permission not in ("edit_tasks", "full"):
            raise AuthorizationError("У вас нет права изменять задачи этого события.")
        return permission

    def get_team_members_for_event(self, event_id, teamlead_id):
        members = self.db.fetch_all(
            """SELECT DISTINCT u.id, u.username, u.email, u.role
               FROM users u JOIN group_members gm ON gm.user_id = u.id
               JOIN groups g ON g.id = gm.group_id
               WHERE g.creator_id = ? AND u.id != ? ORDER BY u.username""",
            (teamlead_id, teamlead_id),
        )
        return [user for user in members if self.has_access_to_event(user["id"], event_id)]
