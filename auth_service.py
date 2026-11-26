"""Регистрация и вход. Не зависит от tkinter, поэтому легко тестируется."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3

from core.db_access import Db
from core.models import AuthorizationError, User

ROLES = {"admin": "Администратор", "teamlead": "Тимлид", "member": "Участник"}

MIN_PASSWORD = 6
_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 200_000
_USERNAME_RE = re.compile(r"^[\w.\-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_dummy_hash_cache = []


class AuthError(ValueError):
    """Понятная пользователю ошибка входа или регистрации."""


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Пароль в базе хранится только в виде соли и хеша: pbkdf2_sha256$итерации$соль$хеш."""
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = (stored or "").split("$")
        if algorithm != _ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def _dummy_hash() -> str:
    # проверка пароля для несуществующего логина занимает столько же времени, как для существующего
    if not _dummy_hash_cache:
        _dummy_hash_cache.append(hash_password("dummy-password"))
    return _dummy_hash_cache[0]


def display_name(user: dict) -> str:
    full = " ".join(p for p in (user.get("first_name"), user.get("last_name")) if p)
    return full or user.get("username", "")


class AuthService:
    def __init__(self, database):
        self.db = Db.wrap(database)

    # ---------- регистрация и вход ----------
    def register(self, username, email, password, first_name, last_name) -> User:
        """Создаёт пользователя. Первый зарегистрированный становится администратором, остальные участниками."""
        username = (username or "").strip()
        email = (email or "").strip().lower()
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        password = password or ""

        if not first_name or not last_name:
            raise AuthError("Укажите имя и фамилию: по ним вас смогут найти в чате.")
        if len(first_name) > 40 or len(last_name) > 40:
            raise AuthError("Имя и фамилия не длиннее 40 символов.")
        if not _USERNAME_RE.match(username):
            raise AuthError("Логин: 3-32 символа, только буквы, цифры, точка, дефис и подчёркивание.")
        if not _EMAIL_RE.match(email):
            raise AuthError("Введите корректный email.")
        if len(password) < MIN_PASSWORD:
            raise AuthError(f"Пароль должен быть не короче {MIN_PASSWORD} символов.")

        if self._find(username):
            raise AuthError("Этот логин уже занят.")
        if self._find(email):
            raise AuthError("Этот email уже зарегистрирован.")

        has_admin = self.db.fetch_one("SELECT 1 AS ok FROM users WHERE role = 'admin'")
        role = "member" if has_admin else "admin"
        try:
            user_id = self.db.execute(
                """INSERT INTO users (username, email, password, role, first_name, last_name)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, email, hash_password(password), role, first_name, last_name),
            )
        except sqlite3.IntegrityError as exc:
            raise AuthError("Пользователь с таким логином или email уже существует.") from exc
        return User(id=user_id, username=username, role=role, email=email)

    def login(self, identifier, password) -> User:
        """Вход по логину или email. Сообщение об ошибке одинаковое, чтобы нельзя было угадывать логины."""
        row = self._find((identifier or "").strip())
        ok = verify_password(password or "", row["password"] if row else _dummy_hash())
        if row is None or not ok:
            raise AuthError("Неверный логин или пароль.")
        return User.from_any(dict(row))

    def _find(self, identifier):
        # сравнение в Python: SQLite не умеет lower() для кириллицы
        key = identifier.casefold()
        if not key:
            return None
        for row in self.db.fetch_all("SELECT * FROM users"):
            if row["username"].casefold() == key or (row["email"] or "").casefold() == key:
                return row
        return None

    # ---------- пользователи и роли ----------
    def get_user(self, user_id):
        return self.db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))

    def list_users(self):
        users = self.db.fetch_all("SELECT id, username, email, role, first_name, last_name FROM users")
        for user in users:
            user["display_name"] = display_name(user)
        users.sort(key=lambda u: u["display_name"].casefold())
        return users

    def set_role(self, acting_user_id, target_user_id, role):
        """Роль меняет только администратор (проверка по базе, а не по данным сессии)."""
        acting = self.get_user(acting_user_id)
        if not acting or acting["role"] != "admin":
            raise AuthorizationError("Менять роли может только администратор.")
        if role not in ROLES:
            raise AuthError("Неизвестная роль.")
        target = self.get_user(target_user_id)
        if not target:
            raise AuthError("Пользователь не найден.")
        if target["role"] == "admin" and role != "admin":
            admins = self.db.fetch_one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")["n"]
            if admins <= 1:
                raise AuthError("Нельзя снять роль с последнего администратора.")
        self.db.execute("UPDATE users SET role = ? WHERE id = ?", (role, target_user_id))
