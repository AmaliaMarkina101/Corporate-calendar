"""Доступ к общей базе приложения (той же, что использует календарь)."""
from __future__ import annotations

import sqlite3


def get_connection(database):
    """Достаёт sqlite3.Connection из Database приложения (так же, как это делает календарь)."""
    if isinstance(database, sqlite3.Connection):
        return database
    for attribute in ("connection", "conn", "connection_db"):
        connection = getattr(database, attribute, None)
        if isinstance(connection, sqlite3.Connection):
            return connection
    getter = getattr(database, "get_connection", None)
    if callable(getter):
        connection = getter()
        if isinstance(connection, sqlite3.Connection):
            return connection
    raise TypeError("Передан неподдерживаемый объект базы данных")


class Db:
    """Тонкая обёртка: fetch_one / fetch_all возвращают dict независимо от row_factory."""

    def __init__(self, database):
        self.conn = get_connection(database)

    @classmethod
    def wrap(cls, database) -> "Db":
        return database if isinstance(database, cls) else cls(database)

    @staticmethod
    def _to_dicts(cursor):
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def fetch_all(self, query, params=()):
        return self._to_dicts(self.conn.execute(query, tuple(params)))

    def fetch_one(self, query, params=()):
        rows = self.fetch_all(query, params)
        return rows[0] if rows else None

    def execute(self, query, params=()):
        cursor = self.conn.execute(query, tuple(params))
        self.conn.commit()
        return cursor.lastrowid
