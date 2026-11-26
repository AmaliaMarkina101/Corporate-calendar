from __future__ import annotations

from datetime import datetime, timezone

from core.db_access import Db
from core.event_access import EventAccess
from core.models import AuthorizationError, User

from .schema import init_chat_tables

SEARCH_LIMIT = 20
GROUP_HISTORY_LIMIT = 50


def person_name(user):
    """«Имя Фамилия», а если имени нет, то логин."""
    full = " ".join(part for part in (user.get("first_name"), user.get("last_name")) if part).strip()
    return full or user["username"]


def display_name(user):
    """«Имя Фамилия (логин)» для списков поиска, чтобы не перепутать однофамильцев."""
    full = " ".join(part for part in (user.get("first_name"), user.get("last_name")) if part).strip()
    return f"{full} ({user['username']})" if full else user["username"]


class ChatService:
    def __init__(self, database, current_user):
        self.db = Db.wrap(database)
        init_chat_tables(self.db.conn)
        self.current_user = User.from_any(current_user)
        self.events = EventAccess(self.db)
        self._get_user(self.current_user.id)

    # ---------- вспомогательное ----------
    def _get_user(self, user_id):
        user = self.db.fetch_one(
            "SELECT id, username, first_name, last_name FROM users WHERE id = ?", (user_id,)
        )
        if not user:
            raise ValueError("Пользователь не найден.")
        return user

    def _check_current_user(self, user_id):
        if user_id != self.current_user.id:
            raise AuthorizationError("Нельзя выполнять это действие от имени другого пользователя.")

    @staticmethod
    def _message_text(text):
        text = (text or "").strip()
        if not text:
            raise ValueError("Сообщение не может быть пустым.")
        return text

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # ---------- функции из ТЗ ----------
    def send_group_message(self, event_id, sender_id, text):
        self._check_current_user(sender_id)
        self.events.require_access(sender_id, event_id)
        text = self._message_text(text)
        return self.db.execute(
            "INSERT INTO chat_messages (event_id, sender_id, text, created_at) VALUES (?, ?, ?, ?)",
            (event_id, sender_id, text, self._now()),
        )

    def get_group_messages(self, event_id):
        """Последние 50 сообщений события, от старых к новым."""
        self.events.require_access(self.current_user.id, event_id)
        messages = self.db.fetch_all(
            """SELECT m.*, u.username, u.first_name, u.last_name
               FROM chat_messages m JOIN users u ON u.id = m.sender_id
               WHERE m.event_id = ?
               ORDER BY m.created_at DESC, m.id DESC LIMIT ?""",
            (event_id, GROUP_HISTORY_LIMIT),
        )
        messages.reverse()
        for message in messages:
            message["sender_name"] = person_name(message)
        return messages

    def send_private_message(self, sender_id, receiver_id, text):
        self._check_current_user(sender_id)
        self._get_user(receiver_id)
        if sender_id == receiver_id:
            raise ValueError("Нельзя написать самому себе.")
        text = self._message_text(text)
        return self.db.execute(
            "INSERT INTO private_messages (sender_id, receiver_id, text, created_at) VALUES (?, ?, ?, ?)",
            (sender_id, receiver_id, text, self._now()),
        )

    def get_private_messages(self, user1_id, user2_id):
        if self.current_user.id not in (user1_id, user2_id):
            raise AuthorizationError("Нет доступа к чужой переписке.")
        self._get_user(user1_id)
        self._get_user(user2_id)
        messages = self.db.fetch_all(
            """SELECT m.*, u.username, u.first_name, u.last_name
               FROM private_messages m JOIN users u ON u.id = m.sender_id
               WHERE (m.sender_id = ? AND m.receiver_id = ?)
                  OR (m.sender_id = ? AND m.receiver_id = ?)
               ORDER BY m.created_at, m.id""",
            (user1_id, user2_id, user2_id, user1_id),
        )
        for message in messages:
            message["sender_name"] = person_name(message)
        return messages

    def get_user_chats(self, user_id):
        """Личные и групповые чаты, сверху тот, где писали последним."""
        self._check_current_user(user_id)
        chats = []
        for event in self.db.fetch_all("SELECT id, title FROM events"):
            if not self.events.has_access(user_id, event["id"]):
                continue
            last = self.db.fetch_one(
                """SELECT id, text, created_at FROM chat_messages WHERE event_id = ?
                   ORDER BY created_at DESC, id DESC LIMIT 1""",
                (event["id"],),
            )
            chats.append({
                "type": "group", "id": event["id"], "title": event["title"],
                "last_message": last["text"] if last else "",
                "last_message_at": last["created_at"] if last else "",
                "last_message_id": last["id"] if last else 0,
            })

        people = self.db.fetch_all(
            """SELECT receiver_id AS id FROM private_messages WHERE sender_id = ?
               UNION
               SELECT sender_id AS id FROM private_messages WHERE receiver_id = ?""",
            (user_id, user_id),
        )
        for person in people:
            user = self._get_user(person["id"])
            last = self.db.fetch_one(
                """SELECT id, text, created_at FROM private_messages
                   WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
                   ORDER BY created_at DESC, id DESC LIMIT 1""",
                (user_id, person["id"], person["id"], user_id),
            )
            chats.append({
                "type": "private", "id": user["id"], "title": display_name(user),
                "last_message": last["text"], "last_message_at": last["created_at"],
                "last_message_id": last["id"],
            })

        chats.sort(key=lambda chat: (chat["last_message_at"], chat["last_message_id"]), reverse=True)
        return chats

    def search_users(self, query=""):
        """Поиск по имени, фамилии или логину. Каждое слово запроса должно где-то встретиться."""
        tokens = (query or "").casefold().split()
        found = []
        rows = self.db.fetch_all(
            "SELECT id, username, first_name, last_name FROM users WHERE id != ?",
            (self.current_user.id,),
        )
        for user in rows:
            haystack = " ".join(
                str(user.get(key) or "") for key in ("first_name", "last_name", "username")
            ).casefold()
            if all(token in haystack for token in tokens):
                user["display_name"] = display_name(user)
                found.append(user)
        found.sort(key=lambda user: user["display_name"].casefold())
        return found[:SEARCH_LIMIT]

    def get_group_info(self, event_id):
        self.events.require_access(self.current_user.id, event_id)
        event = self.events.get_event(event_id)
        event["group_title"] = None
        if event.get("group_id") is not None:
            group = self.db.fetch_one("SELECT title FROM groups WHERE id = ?", (event["group_id"],))
            event["group_title"] = group["title"] if group else None
        event["members"] = []
        event["author_name"] = "Не указан"
        for user in self.db.fetch_all(
            "SELECT id, username, first_name, last_name FROM users ORDER BY username"
        ):
            if user["id"] == event["author_id"]:
                event["author_name"] = display_name(user)
            if self.events.has_access(user["id"], event_id):
                user["display_name"] = display_name(user)
                event["members"].append(user)
        return event
