from __future__ import annotations

from db import Database
from auth import User, AuthorizationError


class EventService:
    def __init__(self, database: Database):
        self.db = database

    def get_event(self, event_id: int) -> dict:
        event = self.db.fetch_one(
            """SELECT e.*, t.teamlead_id
               FROM events e JOIN teams t ON t.id = e.team_id
               WHERE e.id = ?""",
            (event_id,),
        )
        if not event:
            raise ValueError(f"Событие с id={event_id} не найдено")
        return event

    def has_access_to_event(self, user_id: int, event_id: int) -> bool:
        user = self.db.fetch_one("SELECT id FROM users WHERE id = ?", (user_id,))
        if not user:
            return False
        event = self.db.fetch_one(
            "SELECT team_id, creator_id, visibility FROM events WHERE id = ?", (event_id,)
        )
        if not event:
            return False
        if event["creator_id"] == user_id:
            return True
        if event["visibility"] == "private":
            return False
        if event["visibility"] == "public":
            return bool(self.db.fetch_one(
                """SELECT 1 FROM teams t
                   WHERE t.id = ? AND (t.teamlead_id = ? OR EXISTS (
                       SELECT 1 FROM team_members tm
                       WHERE tm.team_id = t.id AND tm.user_id = ?
                   ))""",
                (event["team_id"], user_id, user_id),
            ))
        return bool(self.db.fetch_one(
            "SELECT 1 AS ok FROM event_members WHERE event_id=? AND user_id=?",
            (event_id, user_id),
        ))

    def require_event_access(self, user_id: int, event_id: int) -> None:
        if not self.has_access_to_event(user_id, event_id):
            raise AuthorizationError("У вас нет доступа к этому событию.")

    def is_teamlead_of_event(self, user_id: int, event_id: int) -> bool:
        return bool(self.db.fetch_one(
            """SELECT 1 AS ok
               FROM events e JOIN teams t ON t.id=e.team_id
               WHERE e.id=? AND t.teamlead_id=?""",
            (event_id, user_id),
        ))

    def get_team_members_for_event(self, event_id: int) -> list[dict]:
        event = self.get_event(event_id)
        return self.db.fetch_all(
            """SELECT DISTINCT u.id, u.username, u.email, u.role
               FROM users u
               JOIN team_members tm ON tm.user_id=u.id
               WHERE tm.team_id=? AND u.id != ?
               ORDER BY u.username""",
            (event["team_id"], event["teamlead_id"]),
        )

    def get_event_members(self, event_id: int) -> list[dict]:
        return self.db.fetch_all(
            """SELECT u.id, u.username, u.email, u.role
               FROM event_members em JOIN users u ON u.id=em.user_id
               WHERE em.event_id=? ORDER BY u.username""",
            (event_id,),
        )
