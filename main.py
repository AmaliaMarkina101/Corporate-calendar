import customtkinter as ctk
import argparse
import contextlib

from db import db
from auth import User
from ui.main_window import MainWindow


DEMO_EVENT_ID = 1


def seed_demo_data(database=db):
    """Добавляет демоданные только в пустую базу."""
    with contextlib.closing(database.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing:
            return

        conn.executemany(
            """INSERT INTO users (id, username, email, password, role, first_name, last_name)
               VALUES (?, ?, ?, 'demo', ?, ?, ?)""",
            [
                (1, 'lead', 'lead@example.com', 'teamlead', 'Павел', 'Иванов'),
                (2, 'member1', 'member1@example.com', 'member', 'Анна', 'Петрова'),
                (3, 'member2', 'member2@example.com', 'member', 'Иван', 'Соколов'),
                (4, 'admin', 'admin@example.com', 'admin', 'Администратор', ''),
            ],
        )
        conn.execute("INSERT INTO teams (id, name, teamlead_id) VALUES (1, 'Команда 1', 1)")
        conn.executemany(
            "INSERT INTO team_members (team_id, user_id) VALUES (1, ?)",
            [(1,), (2,), (3,)],
        )
        conn.execute("""INSERT INTO events (id, team_id, title, creator_id, visibility)
                        VALUES (1, 1, 'Подготовка проекта', 1, 'restricted')""")
        conn.executemany(
            "INSERT INTO event_members (event_id, user_id) VALUES (1, ?)",
            [(1,), (2,), (3,)],
        )


def main():
    parser = argparse.ArgumentParser(description="Календарь: задачи и переписка")
    parser.add_argument("--user", type=int, default=1, help="ID пользователя для локального запуска")
    args = parser.parse_args()
    db.init_db()
    seed_demo_data()

    row = db.fetch_one("SELECT id, username, email, role FROM users WHERE id=?", (args.user,))
    if not row:
        parser.error(f"Пользователь id={args.user} не найден.")
    current_user = User.from_row(row)

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = MainWindow(db, current_user, DEMO_EVENT_ID)
    app.mainloop()


if __name__ == "__main__":
    main()
