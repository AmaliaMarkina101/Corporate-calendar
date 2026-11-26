import unittest

from calendar_module.database import Database
from calendar_module.event_service import add_event_access, add_user_to_group, create_event, create_group
from chat_module.service import ChatService
from core.models import AuthorizationError

ALEX, MARIA, IVAN, OLGA = 1, 2, 3, 4
USERS = [
    (ALEX, "alex", "Алексей", "Смирнов", "teamlead"),
    (MARIA, "maria", "Мария", "Иванова", "member"),
    (IVAN, "ivan", "Иван", "Петров", "member"),
    (OLGA, "olga", "Ольга", "Иванова", "member"),
]


class ChatBase(unittest.TestCase):
    def setUp(self):
        self.database = Database(":memory:")
        self.database.init_db()
        self.database.connection.executemany(
            "INSERT INTO users (id, username, email, role, first_name, last_name) VALUES (?, ?, ?, ?, ?, ?)",
            [(i, name, name + "@x.com", role, first, last) for i, name, first, last, role in USERS],
        )
        self.database.connection.commit()
        group = create_group("Команда", ALEX, self.database)
        add_user_to_group(group, MARIA, self.database)
        add_user_to_group(group, IVAN, self.database)
        t = ("2026-12-01 10:00", "2026-12-01 11:00")
        # e1: публичное с группой; e2: ограниченное (maria, ivan); e3: приватное; e4: публичное без группы
        self.e1 = create_event("Публичное с группой", *t, ALEX, "public", "", "work", group, self.database)
        self.e2 = create_event("Ограниченное", *t, ALEX, "limited", "", "work", None, self.database)
        self.e3 = create_event("Приватное", *t, ALEX, "private", "", "work", None, self.database)
        self.e4 = create_event("Публичное без группы", *t, ALEX, "public", "", "work", None, self.database)
        add_event_access(self.e2, MARIA, "read", self.database)
        add_event_access(self.e2, IVAN, "edit_tasks", self.database)

    def svc(self, user_id):
        name = {u[0]: u[1] for u in USERS}[user_id]
        role = {u[0]: u[4] for u in USERS}[user_id]
        return ChatService(self.database, {"id": user_id, "username": name, "role": role})


class GroupChatTests(ChatBase):
    def test_who_can_write_to_event_chat(self):
        allowed = {
            self.e1: [ALEX, MARIA, IVAN], self.e2: [ALEX, MARIA, IVAN],
            self.e3: [ALEX], self.e4: [ALEX, MARIA, IVAN, OLGA],
        }
        for event_id, users in allowed.items():
            for user_id in (ALEX, MARIA, IVAN, OLGA):
                service = self.svc(user_id)
                if user_id in users:
                    service.send_group_message(event_id, user_id, "привет")
                    self.assertTrue(service.get_group_messages(event_id))
                else:
                    with self.assertRaises(AuthorizationError, msg=(event_id, user_id)):
                        service.send_group_message(event_id, user_id, "привет")
                    with self.assertRaises(AuthorizationError, msg=(event_id, user_id)):
                        service.get_group_messages(event_id)

    def test_only_last_50_in_chronological_order(self):
        service = self.svc(ALEX)
        for number in range(60):
            service.send_group_message(self.e1, ALEX, f"сообщение {number}")
        messages = service.get_group_messages(self.e1)
        self.assertEqual(len(messages), 50)
        self.assertEqual(messages[0]["text"], "сообщение 10")
        self.assertEqual(messages[-1]["text"], "сообщение 59")

    def test_sender_name_is_full_name(self):
        self.svc(MARIA).send_group_message(self.e1, MARIA, "я здесь")
        self.assertEqual(self.svc(ALEX).get_group_messages(self.e1)[0]["sender_name"], "Мария Иванова")

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.svc(ALEX).send_group_message(self.e1, ALEX, "   ")
        with self.assertRaises(AuthorizationError):
            self.svc(ALEX).send_group_message(self.e1, MARIA, "от чужого имени")


class PrivateChatTests(ChatBase):
    def test_history_both_directions(self):
        self.svc(ALEX).send_private_message(ALEX, MARIA, "привет")
        self.svc(MARIA).send_private_message(MARIA, ALEX, "здравствуй")
        for viewer in (ALEX, MARIA):
            history = self.svc(viewer).get_private_messages(ALEX, MARIA)
            self.assertEqual([m["text"] for m in history], ["привет", "здравствуй"])

    def test_cannot_read_foreign_conversation(self):
        self.svc(ALEX).send_private_message(ALEX, MARIA, "секрет")
        with self.assertRaises(AuthorizationError):
            self.svc(IVAN).get_private_messages(ALEX, MARIA)
        self.assertEqual(self.svc(IVAN).get_private_messages(IVAN, ALEX), [])

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.svc(ALEX).send_private_message(ALEX, ALEX, "себе")
        with self.assertRaises(ValueError):
            self.svc(ALEX).send_private_message(ALEX, MARIA, "")
        with self.assertRaises(ValueError):
            self.svc(ALEX).send_private_message(ALEX, 999, "никому")
        with self.assertRaises(AuthorizationError):
            self.svc(ALEX).send_private_message(MARIA, ALEX, "подмена отправителя")


class ChatListTests(ChatBase):
    def test_only_accessible_groups(self):
        titles = {c["title"] for c in self.svc(MARIA).get_user_chats(MARIA) if c["type"] == "group"}
        self.assertEqual(titles, {"Публичное с группой", "Ограниченное", "Публичное без группы"})
        titles = {c["title"] for c in self.svc(OLGA).get_user_chats(OLGA)}
        self.assertEqual(titles, {"Публичное без группы"})

    def test_sorted_by_last_message(self):
        self.svc(MARIA).send_group_message(self.e1, MARIA, "в группе 1")
        self.svc(IVAN).send_private_message(IVAN, MARIA, "личное")
        self.svc(MARIA).send_group_message(self.e2, MARIA, "в ограниченном")
        chats = self.svc(MARIA).get_user_chats(MARIA)
        self.assertEqual([c["title"] for c in chats[:3]],
                         ["Ограниченное", "Иван Петров (ivan)", "Публичное с группой"])
        # чат без сообщений идёт в самом конце
        self.assertEqual(chats[-1]["title"], "Публичное без группы")
        self.assertEqual(chats[-1]["last_message"], "")

    def test_reply_moves_chat_to_top(self):
        self.svc(IVAN).send_private_message(IVAN, MARIA, "раз")
        self.svc(OLGA).send_private_message(OLGA, MARIA, "два")
        self.assertEqual(self.svc(MARIA).get_user_chats(MARIA)[0]["id"], OLGA)
        self.svc(MARIA).send_private_message(MARIA, IVAN, "ответ")
        self.assertEqual(self.svc(MARIA).get_user_chats(MARIA)[0]["id"], IVAN)

    def test_cannot_list_chats_of_another_user(self):
        with self.assertRaises(AuthorizationError):
            self.svc(ALEX).get_user_chats(MARIA)


class SearchTests(ChatBase):
    def names(self, user_id, query):
        return [u["id"] for u in self.svc(user_id).search_users(query)]

    def test_by_first_name_last_name_and_login(self):
        self.assertEqual(self.names(ALEX, "Мария"), [MARIA])
        self.assertEqual(self.names(ALEX, "петров"), [IVAN])
        self.assertEqual(self.names(ALEX, "olga"), [OLGA])

    def test_case_insensitive_cyrillic_and_partial(self):
        self.assertEqual(self.names(ALEX, "МАРИ"), [MARIA])
        self.assertEqual(self.names(ALEX, "ИВАН"), [IVAN, MARIA, OLGA])  # Иван, Иванова, Иванова (по алфавиту)

    def test_full_name_narrows_down(self):
        self.assertEqual(self.names(ALEX, "Мария Иванова"), [MARIA])
        self.assertEqual(self.names(ALEX, "иванова ольга"), [OLGA])

    def test_excludes_self_and_empty_query_lists_everyone(self):
        self.assertNotIn(ALEX, self.names(ALEX, "алексей"))
        self.assertEqual(set(self.names(ALEX, "")), {MARIA, IVAN, OLGA})

    def test_display_name_shows_login(self):
        self.assertEqual(self.svc(ALEX).search_users("петров")[0]["display_name"], "Иван Петров (ivan)")

    def test_limit_is_20(self):
        self.database.connection.executemany(
            "INSERT INTO users (username, email, role, first_name, last_name) VALUES (?, ?, 'member', 'Тест', ?)",
            [(f"t{i}", f"t{i}@x.com", f"Номер{i}") for i in range(30)],
        )
        self.database.connection.commit()
        self.assertEqual(len(self.svc(ALEX).search_users("тест")), 20)


class GroupInfoTests(ChatBase):
    def test_members_follow_event_access(self):
        info = self.svc(ALEX).get_group_info(self.e1)
        self.assertEqual({m["id"] for m in info["members"]}, {ALEX, MARIA, IVAN})
        self.assertEqual(info["group_title"], "Команда")
        self.assertEqual({m["id"] for m in self.svc(ALEX).get_group_info(self.e2)["members"]}, {ALEX, MARIA, IVAN})
        with self.assertRaises(AuthorizationError):
            self.svc(MARIA).get_group_info(self.e3)


if __name__ == "__main__":
    unittest.main()
