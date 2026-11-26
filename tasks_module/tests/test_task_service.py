import unittest

from calendar_module.database import Database
from calendar_module.event_service import add_event_access, add_user_to_group, create_event, create_group
from core.event_access import EventAccess
from core.models import AuthorizationError
from tasks_module.task_service import TaskService

ALEX, MARIA, IVAN, OLGA, BORIS = 1, 2, 3, 4, 5


def users():
    return {
        ALEX: {"id": ALEX, "username": "alex", "role": "teamlead"},
        MARIA: {"id": MARIA, "username": "maria", "role": "member"},
        IVAN: {"id": IVAN, "username": "ivan", "role": "member"},
        OLGA: {"id": OLGA, "username": "olga", "role": "member"},
        BORIS: {"id": BORIS, "username": "boris", "role": "teamlead"},
    }


class TasksBase(unittest.TestCase):
    def setUp(self):
        self.database = Database(":memory:")
        self.database.init_db()
        self.users = users()
        self.database.connection.executemany(
            "INSERT INTO users (id, username, email, role) VALUES (?, ?, ?, ?)",
            [(u["id"], u["username"], u["username"] + "@x.com", u["role"]) for u in self.users.values()],
        )
        self.database.connection.commit()
        group = create_group("Команда", ALEX, self.database)
        add_user_to_group(group, MARIA, self.database)
        add_user_to_group(group, IVAN, self.database)
        t = ("2026-12-01 10:00", "2026-12-01 11:00")
        # e1: публичное с группой; e2: ограниченное; e3: приватное; e4: публичное без группы
        self.e1 = create_event("Публичное с группой", *t, ALEX, "public", "", "work", group, self.database)
        self.e2 = create_event("Ограниченное", *t, ALEX, "limited", "", "work", None, self.database)
        self.e3 = create_event("Приватное", *t, ALEX, "private", "", "work", None, self.database)
        self.e4 = create_event("Публичное без группы", *t, ALEX, "public", "", "work", None, self.database)
        add_event_access(self.e2, MARIA, "read", self.database)
        add_event_access(self.e2, IVAN, "edit_tasks", self.database)

    def svc(self, user_id):
        return TaskService(self.database, self.users[user_id])

    def make_task(self, user_id, event_id, **kwargs):
        args = dict(title="Задача", description="", assignee_id=None, deadline="2026-12-05 18:00")
        args.update(kwargs)
        return self.svc(user_id).create_task(event_id, **args)


class PermissionTests(TasksBase):
    def test_permission_matrix(self):
        access = EventAccess(self.database)
        expected = {
            (ALEX, self.e1): "full", (MARIA, self.e1): "edit_tasks", (OLGA, self.e1): None,
            (MARIA, self.e2): "read", (IVAN, self.e2): "edit_tasks", (OLGA, self.e2): None,
            (ALEX, self.e3): "full", (MARIA, self.e3): None, (IVAN, self.e3): None,
            (OLGA, self.e4): "edit_tasks", (MARIA, self.e4): "edit_tasks",
        }
        for (user_id, event_id), permission in expected.items():
            self.assertEqual(access.get_permission(user_id, event_id), permission, (user_id, event_id))

    def test_visibility_matches_calendar(self):
        from calendar_module.event_service import get_events_for_user
        access = EventAccess(self.database)
        for user_id in self.users:
            visible = {e["id"] for e in get_events_for_user(user_id, self.database)}
            mine = {e for e in (self.e1, self.e2, self.e3, self.e4) if access.has_access(user_id, e)}
            self.assertEqual(visible, mine, user_id)


class CreateTaskTests(TasksBase):
    def test_member_is_always_assignee(self):
        task_id = self.make_task(MARIA, self.e1, assignee_id=IVAN)
        task = self.svc(MARIA).get_tasks_by_event(self.e1)[0]
        self.assertEqual((task["id"], task["assignee_id"], task["creator_id"]), (task_id, MARIA, MARIA))
        self.assertEqual(task["status"], "not_started")
        self.assertIsNone(task["reminder_time"])

    def test_teamlead_assigns_team_member(self):
        self.make_task(ALEX, self.e1, assignee_id=MARIA)
        self.assertEqual(self.svc(ALEX).get_tasks_by_event(self.e1)[0]["assignee_id"], MARIA)

    def test_teamlead_cannot_assign_outsider_or_read_only_member(self):
        with self.assertRaises(ValueError):
            self.make_task(ALEX, self.e1, assignee_id=OLGA)
        with self.assertRaises(ValueError):
            self.make_task(ALEX, self.e2, assignee_id=MARIA)  # у Марии на e2 только чтение

    def test_read_only_and_no_access_cannot_create(self):
        with self.assertRaises(AuthorizationError):
            self.make_task(MARIA, self.e2)
        with self.assertRaises(AuthorizationError):
            self.make_task(MARIA, self.e3)
        with self.assertRaises(AuthorizationError):
            self.make_task(OLGA, self.e1)

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.make_task(ALEX, self.e1, title="  ")
        with self.assertRaises(ValueError):
            self.make_task(ALEX, self.e1, deadline="05.12.2026")
        with self.assertRaises(ValueError):
            self.make_task(ALEX, self.e1, deadline="")
        with self.assertRaises(ValueError):
            self.make_task(ALEX, self.e1, reminder_time="2026-12-06 09:00")  # позже дедлайна

    def test_reminder_saved(self):
        self.make_task(ALEX, self.e1, reminder_time="2026-12-05 17:00")
        self.assertEqual(self.svc(ALEX).get_tasks_by_event(self.e1)[0]["reminder_time"], "2026-12-05 17:00")


class ReadAndCommentTests(TasksBase):
    def test_no_access_cannot_read(self):
        with self.assertRaises(AuthorizationError):
            self.svc(OLGA).get_tasks_by_event(self.e1)
        with self.assertRaises(AuthorizationError):
            self.svc(MARIA).get_tasks_by_event(self.e3)
        self.assertEqual(self.svc(OLGA).get_tasks_by_event(self.e4), [])

    def test_read_only_user_sees_tasks_and_can_comment(self):
        task_id = self.make_task(ALEX, self.e2, assignee_id=IVAN)
        self.assertEqual(len(self.svc(MARIA).get_tasks_by_event(self.e2)), 1)
        self.svc(MARIA).add_comment(task_id, MARIA, "Вижу задачу")
        comments = self.svc(ALEX).get_comments(task_id)
        self.assertEqual([c["username"] for c in comments], ["maria"])

    def test_comment_rules(self):
        task_id = self.make_task(ALEX, self.e1)
        with self.assertRaises(AuthorizationError):
            self.svc(OLGA).add_comment(task_id, OLGA, "я чужой")
        with self.assertRaises(AuthorizationError):
            self.svc(MARIA).add_comment(task_id, ALEX, "от имени другого")
        with self.assertRaises(ValueError):
            self.svc(MARIA).add_comment(task_id, MARIA, "   ")
        with self.assertRaises(ValueError):
            self.svc(MARIA).add_comment(9999, MARIA, "нет такой задачи")


class StatusAndAssignTests(TasksBase):
    def test_status_change_rules(self):
        task_id = self.make_task(MARIA, self.e1)
        self.svc(MARIA).change_task_status(task_id, "in_progress")
        self.svc(ALEX).change_task_status(task_id, "done")  # автор события: full
        self.assertEqual(self.svc(ALEX).get_tasks_by_event(self.e1)[0]["status"], "done")
        with self.assertRaises(AuthorizationError):
            self.svc(IVAN).change_task_status(task_id, "not_started")  # чужая задача
        with self.assertRaises(ValueError):
            self.svc(MARIA).change_task_status(task_id, "finished")

    def test_assign_only_teamlead(self):
        task_id = self.make_task(MARIA, self.e1)
        with self.assertRaises(AuthorizationError):
            self.svc(MARIA).assign_task(task_id, IVAN)
        self.svc(ALEX).assign_task(task_id, IVAN)
        self.assertEqual(self.svc(ALEX).get_tasks_by_event(self.e1)[0]["assignee_id"], IVAN)

    def test_assign_rejects_outsider_and_foreign_teamlead(self):
        task_id = self.make_task(MARIA, self.e1)
        with self.assertRaises(ValueError):
            self.svc(ALEX).assign_task(task_id, OLGA)
        # Борис — тимлид, но задача на e4 принадлежит Ольге, которая не в его команде
        olga_task = self.make_task(OLGA, self.e4)
        with self.assertRaises(AuthorizationError):
            self.svc(BORIS).assign_task(olga_task, BORIS)

    def test_ui_permission_helpers(self):
        task_id = self.make_task(MARIA, self.e1)
        task = self.svc(MARIA).get_tasks_by_event(self.e1)[0]
        self.assertTrue(self.svc(MARIA).can_change_status(task))
        self.assertFalse(self.svc(IVAN).can_change_status(task))
        self.assertTrue(self.svc(ALEX).can_assign(task))
        self.assertFalse(self.svc(MARIA).can_assign(task))
        self.assertFalse(self.svc(MARIA).can_create(self.e2))
        self.assertTrue(self.svc(IVAN).can_create(self.e2))


if __name__ == "__main__":
    unittest.main()
