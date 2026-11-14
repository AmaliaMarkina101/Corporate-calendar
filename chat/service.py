import datetime
import contextlib

import auth
import event_service


def display_name(user):
    name = f"{user['first_name']} {user['last_name']}".strip()
    return name or user["username"]


class ChatService:
    def __init__(self, database, current_user):
        self.db = database
        self.current_user = current_user
        self.events = event_service.EventService(database)
        self._get_user(current_user.id)

    def _get_user(self, user_id):
        user = self.db.fetch_one(
            "SELECT id, username, first_name, last_name FROM users WHERE id = ?",
            (user_id,),
        )
        if not user:
            raise ValueError("Пользователь не найден.")
        return user

    def _check_current_user(self, user_id):
        if user_id != self.current_user.id:
            raise auth.AuthorizationError("Нельзя выполнять это действие от имени другого пользователя.")
        self._get_user(user_id)

    def _message_text(self, text):
        text = text.strip()
        if not text:
            raise ValueError("Сообщение не может быть пустым.")
        return text

    def _now(self):
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    def send_group_message(self, event_id, sender_id, text):
        self._check_current_user(sender_id)
        self.events.require_event_access(sender_id, event_id)
        text = self._message_text(text)
        return self.db.execute(
            """INSERT INTO chat_messages (event_id, sender_id, text, created_at)
               VALUES (?, ?, ?, ?)""",
            (event_id, sender_id, text, self._now()),
        )

    def get_group_messages(self, event_id):
        self.events.require_event_access(self.current_user.id, event_id)
        messages = self.db.fetch_all(
            """SELECT m.*, u.username, u.first_name, u.last_name
               FROM chat_messages m JOIN users u ON u.id = m.sender_id
               WHERE m.event_id = ?
               ORDER BY m.created_at DESC, m.id DESC LIMIT 50""",
            (event_id,),
        )
        messages.reverse()
        for message in messages:
            message["sender_name"] = display_name(message)
        return messages

    def send_private_message(self, sender_id, receiver_id, text):
        self._check_current_user(sender_id)
        self._get_user(receiver_id)
        text = self._message_text(text)
        return self.db.execute(
            """INSERT INTO private_messages (sender_id, receiver_id, text, created_at)
               VALUES (?, ?, ?, ?)""",
            (sender_id, receiver_id, text, self._now()),
        )

    def get_private_messages(self, user1_id, user2_id):
        if self.current_user.id not in (user1_id, user2_id):
            raise auth.AuthorizationError("Нет доступа к чужой переписке.")
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
            message["sender_name"] = display_name(message)
        return messages

    def get_user_chats(self, user_id):
        self._check_current_user(user_id)
        chats = []
        events = self.db.fetch_all(
            """SELECT e.id, e.title, m.text, m.created_at, m.id AS message_id
               FROM events e LEFT JOIN chat_messages m ON m.id = (
                   SELECT id FROM chat_messages WHERE event_id = e.id
                   ORDER BY created_at DESC, id DESC LIMIT 1
               )"""
        )
        for event in events:
            if self.events.has_access_to_event(user_id, event["id"]):
                chats.append({
                    "type": "group", "id": event["id"], "title": event["title"],
                    "last_message": event["text"] or "",
                    "last_message_at": event["created_at"] or "",
                    "last_message_id": event["message_id"] or 0,
                })

        people = self.db.fetch_all(
            """SELECT u.id, u.username, u.first_name, u.last_name,
                      m.text, m.created_at, m.id AS message_id
               FROM users u JOIN private_messages m ON m.id = (
                   SELECT id FROM private_messages
                   WHERE (sender_id = ? AND receiver_id = u.id)
                      OR (receiver_id = ? AND sender_id = u.id)
                   ORDER BY created_at DESC, id DESC LIMIT 1
               )""",
            (user_id, user_id),
        )
        for person in people:
            chats.append({
                "type": "private", "id": person["id"], "title": display_name(person),
                "last_message": person["text"], "last_message_at": person["created_at"],
                "last_message_id": person["message_id"],
            })

        chats.sort(key=lambda chat: (
            chat["last_message_at"], chat["last_message_id"], chat["type"], chat["id"]
        ), reverse=True)
        return chats

    def search_users(self, query=""):
        self._check_current_user(self.current_user.id)
        query = query.strip().casefold()
        found = []
        with contextlib.closing(self.db.connect()) as conn:
            users = conn.execute(
                """SELECT id, username, first_name, last_name FROM users
                   WHERE id != ? ORDER BY last_name, first_name, username""",
                (self.current_user.id,),
            )
            for row in users:
                user = dict(row)
                name = display_name(user)
                if not query or query in name.casefold() or query in user["username"].casefold():
                    user["display_name"] = name
                    found.append(user)
                    if len(found) == 20:
                        break
        return found

    def get_group_info(self, event_id):
        self.events.require_event_access(self.current_user.id, event_id)
        event = self.events.get_event(event_id)
        users = self.db.fetch_all(
            "SELECT id, username, first_name, last_name FROM users ORDER BY last_name, first_name, username"
        )
        event["members"] = []
        event["creator_name"] = "Не указан"
        for user in users:
            if user["id"] == event["creator_id"]:
                event["creator_name"] = display_name(user)
            if self.events.has_access_to_event(user["id"], event_id):
                user["display_name"] = display_name(user)
                event["members"].append(user)
        return event
