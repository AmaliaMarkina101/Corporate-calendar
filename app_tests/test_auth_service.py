import unittest

from auth_service import AuthError, AuthService, hash_password, verify_password
from calendar_module.database import Database
from core.models import AuthorizationError


def make():
    database = Database(":memory:").init_db()
    return database, AuthService(database)


def reg(auth, name="anna", email="anna@example.com", password="secret1", first="Анна", last="Белова"):
    return auth.register(name, email, password, first, last)


class AuthTests(unittest.TestCase):
    def test_hash_is_salted_and_verifiable(self):
        a, b = hash_password("secret1"), hash_password("secret1")
        self.assertNotEqual(a, b)
        self.assertNotIn("secret1", a)
        self.assertTrue(verify_password("secret1", a))
        self.assertFalse(verify_password("wrong", a))
        self.assertFalse(verify_password("", ""))
        self.assertFalse(verify_password("demo", "demo"))  # открытый пароль не принимается

    def test_first_user_is_admin_next_are_members(self):
        _, auth = make()
        self.assertEqual(reg(auth).role, "admin")
        self.assertEqual(reg(auth, "boris", "b@example.com").role, "member")

    def test_password_not_stored_in_plain_text(self):
        database, auth = make()
        reg(auth)
        stored = database.connection.execute("SELECT password FROM users").fetchone()[0]
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))

    def test_login_by_username_and_email_case_insensitive(self):
        _, auth = make()
        user = reg(auth, "Анна_К", "Anna@Example.com")
        self.assertEqual(auth.login("анна_к", "secret1").id, user.id)
        self.assertEqual(auth.login("ANNA@example.com", "secret1").id, user.id)

    def test_wrong_credentials_same_message(self):
        _, auth = make()
        reg(auth)
        with self.assertRaises(AuthError) as bad_password:
            auth.login("anna", "nope")
        with self.assertRaises(AuthError) as bad_login:
            auth.login("ghost", "nope")
        self.assertEqual(str(bad_password.exception), str(bad_login.exception))

    def test_users_without_password_cannot_log_in(self):
        database, auth = make()
        database.connection.execute("INSERT INTO users (username, email, password) VALUES ('old', 'o@x.com', '')")
        with self.assertRaises(AuthError):
            auth.login("old", "")

    def test_validation_and_duplicates(self):
        _, auth = make()
        reg(auth)
        bad = [
            dict(name="ab"), dict(name="has space"), dict(email="nomail"), dict(password="123"),
            dict(first=""), dict(last=" "), dict(name="ANNA", email="other@example.com"),
            dict(name="other", email="ANNA@example.com"),
        ]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises(AuthError):
                reg(auth, **kwargs)

    def test_set_role_rules(self):
        _, auth = make()
        admin, member = reg(auth), reg(auth, "boris", "b@example.com")
        auth.set_role(admin.id, member.id, "teamlead")
        self.assertEqual(auth.get_user(member.id)["role"], "teamlead")
        with self.assertRaises(AuthorizationError):       # не админ
            auth.set_role(member.id, admin.id, "member")
        with self.assertRaises(AuthError):                # последний админ
            auth.set_role(admin.id, admin.id, "member")
        with self.assertRaises(AuthError):
            auth.set_role(admin.id, member.id, "superuser")
        auth.set_role(admin.id, member.id, "admin")       # теперь админов двое
        auth.set_role(admin.id, admin.id, "member")

    def test_list_users_has_display_name(self):
        _, auth = make()
        reg(auth)
        self.assertEqual(auth.list_users()[0]["display_name"], "Анна Белова")


if __name__ == "__main__":
    unittest.main()
