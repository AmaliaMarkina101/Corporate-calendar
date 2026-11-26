import sqlite3
from datetime import date, datetime



_VALID_ACCESS_TYPES = {"private", "limited", "public"}
_VALID_CATEGORIES = {"personal", "work", "rest"}
_VALID_PERMISSIONS = {"read", "edit_tasks", "full"}
def _get_connection(database=None):
    if database is None:
        raise TypeError("Не передана база данных. Передайте общую Database приложения.")
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


def _datetime_to_text(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    text = str(value).strip()
    try:
        datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError("Дата должна быть в формате ГГГГ-ММ-ДД ЧЧ:ММ") from error
    return text


def create_event(
    title,
    start_time,
    end_time,
    author_id,
    access_type,
    description="",
    category="personal",
    group_id=None,
    database=None,
):
    title = str(title).strip()
    if not title:
        raise ValueError("Название события не может быть пустым")
    if access_type not in _VALID_ACCESS_TYPES:
        raise ValueError("Неизвестный тип доступа")
    if category not in _VALID_CATEGORIES:
        raise ValueError("Неизвестная категория события")
    start_text = _datetime_to_text(start_time)
    end_text = _datetime_to_text(end_time)
    if datetime.fromisoformat(end_text) < datetime.fromisoformat(start_text):
        raise ValueError("Дата окончания не может быть раньше даты начала")
    connection = _get_connection(database)
    cursor = connection.execute(
        """
        INSERT INTO events
            (title, description, start_time, end_time, access_type, category, author_id, group_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (title, str(description).strip(), start_text, end_text, access_type, category, author_id, group_id),
    )
    connection.commit()
    return cursor.lastrowid


def get_events_for_user(user_id, database=None):
    connection = _get_connection(database)
    cursor = connection.execute(
        """
        SELECT DISTINCT
            e.*,
            CASE
                WHEN e.author_id = ? THEN 'owner'
                ELSE (
                    SELECT ea.permission
                    FROM event_access AS ea
                    WHERE ea.event_id = e.id AND ea.user_id = ?
                )
            END AS user_permission
        FROM events AS e
        WHERE
            e.author_id = ?
            OR (
                e.access_type = 'limited'
                AND EXISTS (
                    SELECT 1 FROM event_access AS ea
                    WHERE ea.event_id = e.id AND ea.user_id = ?
                )
            )
            OR (
                e.access_type = 'public'
                AND (
                    e.group_id IS NULL
                    OR EXISTS (
                        SELECT 1 FROM group_members AS gm
                        WHERE gm.group_id = e.group_id AND gm.user_id = ?
                    )
                )
            )
        ORDER BY e.start_time, e.id
        """,
        (user_id, user_id, user_id, user_id, user_id),
    )
    columns = [column[0] for column in cursor.description]
    return [dict(row) if isinstance(row, sqlite3.Row) else dict(zip(columns, row)) for row in cursor.fetchall()]


def add_event_access(event_id, user_id, permission, database=None):
    if permission not in _VALID_PERMISSIONS:
        raise ValueError("Уровень доступа должен быть read, edit_tasks или full")
    connection = _get_connection(database)
    event = connection.execute(
        "SELECT access_type FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    if event is None:
        raise ValueError("Событие не найдено")
    if event[0] != "limited":
        raise ValueError("Выдавать персональный доступ можно только к limited-событию")
    connection.execute(
        """
        INSERT INTO event_access (event_id, user_id, permission)
        VALUES (?, ?, ?)
        ON CONFLICT(event_id, user_id)
        DO UPDATE SET permission = excluded.permission
        """,
        (event_id, user_id, permission),
    )
    connection.commit()
    return True


def remove_event_access(event_id, user_id, database=None):
    connection = _get_connection(database)
    cursor = connection.execute(
        "DELETE FROM event_access WHERE event_id = ? AND user_id = ?",
        (event_id, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def create_group(title, creator_id, database=None, description=""):
    title = str(title).strip()
    if not title:
        raise ValueError("Название группы не может быть пустым")
    connection = _get_connection(database)
    cursor = connection.execute(
        "INSERT INTO groups (title, description, creator_id) VALUES (?, ?, ?)",
        (title, str(description).strip(), creator_id),
    )
    group_id = cursor.lastrowid
    connection.execute(
        "INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)",
        (group_id, creator_id),
    )
    connection.commit()
    return group_id


def add_user_to_group(group_id, user_id, database=None):
    connection = _get_connection(database)
    connection.execute(
        "INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)",
        (group_id, user_id),
    )
    connection.commit()
    return True


def get_users(database=None, exclude_user_id=None):
    connection = _get_connection(database)
    if exclude_user_id is None:
        cursor = connection.execute(
            "SELECT id, username, email, role FROM users ORDER BY username"
        )
    else:
        cursor = connection.execute(
            "SELECT id, username, email, role FROM users WHERE id != ? ORDER BY username",
            (exclude_user_id,),
        )
    columns = [column[0] for column in cursor.description]
    return [dict(row) if isinstance(row, sqlite3.Row) else dict(zip(columns, row)) for row in cursor.fetchall()]


def get_groups_for_user(user_id, database=None):
    connection = _get_connection(database)
    cursor = connection.execute(
        """
        SELECT DISTINCT g.id, g.title, g.description, g.creator_id
        FROM groups AS g
        LEFT JOIN group_members AS gm ON gm.group_id = g.id
        WHERE gm.user_id = ? OR g.creator_id = ?
        ORDER BY g.title
        """,
        (user_id, user_id),
    )
    columns = [column[0] for column in cursor.description]
    return [dict(row) if isinstance(row, sqlite3.Row) else dict(zip(columns, row)) for row in cursor.fetchall()]
