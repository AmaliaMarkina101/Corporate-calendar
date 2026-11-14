import customtkinter as ctk
import contextlib

from db import db
from auth import User
from ui.main_window import MainWindow


# Для проверки участника поменяйте на 2; для тимлида — 1.
DEMO_USER_ID = 1
DEMO_EVENT_ID = 1


def seed_demo_data(database=db):
    """Добавляет демоданные только в пустую базу."""
    with contextlib.closing(database.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing:
            return

        conn.execute(
            "INSERT INTO users (id, username, email, password, role) VALUES (1, 'lead', 'lead@example.com', 'demo', 'teamlead')"
        )
        conn.execute(
            "INSERT INTO users (id, username, email, password, role) VALUES (2, 'member1', 'member1@example.com', 'demo', 'member')"
        )
        conn.execute(
            "INSERT INTO users (id, username, email, password, role) VALUES (3, 'member2', 'member2@example.com', 'demo', 'member')"
        )
        conn.execute(
            "INSERT INTO users (id, username, email, password, role) VALUES (4, 'admin', 'admin@example.com', 'demo', 'admin')"
        )
        conn.execute("INSERT INTO teams (id, name, teamlead_id) VALUES (1, 'Команда 1', 1)")
        conn.executemany(
            "INSERT INTO team_members (team_id, user_id) VALUES (1, ?)",
            [(1,), (2,), (3,)],
        )
        conn.execute("""UPDATE users SET first_name = CASE id
                            WHEN 1 THEN 'Павел' WHEN 2 THEN 'Анна'
                            WHEN 3 THEN 'Иван' ELSE 'Администратор' END,
                            last_name = CASE id WHEN 1 THEN 'Иванов'
                            WHEN 2 THEN 'Петрова' WHEN 3 THEN 'Соколов' ELSE '' END""")
        conn.execute("""INSERT INTO events (id, team_id, title, creator_id, visibility)
                        VALUES (1, 1, 'Подготовка проекта', 1, 'restricted')""")
        conn.executemany(
            "INSERT INTO event_members (event_id, user_id) VALUES (1, ?)",
            [(1,), (2,), (3,)],
        )


def main():
    db.init_db()
    seed_demo_data()

    row = db.fetch_one("SELECT id, username, email, role FROM users WHERE id=?", (DEMO_USER_ID,))
    if not row:
        raise RuntimeError(f"Демонстрационный пользователь id={DEMO_USER_ID} не найден.")
    current_user = User.from_row(row)

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = MainWindow(db, current_user, DEMO_EVENT_ID)
    app.mainloop()


if __name__ == "__main__":
    main()
