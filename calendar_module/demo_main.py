from pathlib import Path

import customtkinter as ctk

from .database import Database
from .event_service import add_event_access, add_user_to_group, create_event, create_group
from .window import CalendarWindow


DEMO_DATABASE = Path(__file__).resolve().with_name("calendar_demo.db")


def seed_demo_data(database):
    connection = database.connection
    demo_users = [
        (1, "alex", "alex@example.com", "", "teamlead", "Алексей", "Смирнов"),
        (2, "maria", "maria@example.com", "", "member", "Мария", "Иванова"),
        (3, "ivan", "ivan@example.com", "", "member", "Иван", "Петров"),
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO users
            (id, username, email, password, role, first_name, last_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        demo_users,
    )
    connection.commit()
    groups = connection.execute("SELECT id FROM groups WHERE title = ?", ("Команда разработки",)).fetchone()
    if groups is None:
        group_id = create_group("Команда разработки", 1, database, "Демонстрационная группа")
        add_user_to_group(group_id, 2, database)
        add_user_to_group(group_id, 3, database)
    else:
        group_id = groups["id"]
    existing = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if existing == 0:
        public_id = create_event(
            "Обсуждение проекта",
            "2026-11-16 10:00",
            "2026-11-16 11:00",
            1,
            "public",
            "Общее событие для команды.",
            "work",
            group_id,
            database,
        )
        limited_id = create_event(
            "Подготовка материалов",
            "2026-11-17 12:00",
            "2026-11-19 16:00",
            1,
            "limited",
            "Демонстрационное событие на несколько дней.",
            "personal",
            None,
            database,
        )
        create_event(
            "Личное дело",
            "2026-11-18 09:00",
            "2026-11-18 10:00",
            1,
            "private",
            "Это событие видно только автору.",
            "rest",
            None,
            database,
        )
        add_event_access(limited_id, 2, "read", database)
        add_event_access(limited_id, 3, "edit_tasks", database)


def main():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    database = Database(DEMO_DATABASE).init_db()
    seed_demo_data(database)
    current_user = {
        "id": 1,
        "username": "alex",
        "email": "alex@example.com",
        "role": "teamlead",
    }
    app = ctk.CTk()
    app.withdraw()
    calendar_window = CalendarWindow(app, database, current_user)
    calendar_window.protocol("WM_DELETE_WINDOW", app.destroy)
    app.mainloop()
    database.close()


if __name__ == "__main__":
    main()
