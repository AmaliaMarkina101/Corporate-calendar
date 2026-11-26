"""Демо чата на тех же демо-данных, что у календаря и задач.

Запуск из корня проекта:
    python -m chat_module.demo_main --user 1
    python -m chat_module.demo_main --user 2 --event 1   # сразу чат события 1
"""
import argparse

import customtkinter as ctk

from calendar_module.database import Database
from calendar_module.demo_main import DEMO_DATABASE, seed_demo_data
from core.models import User

from .window import open_chat


def main():
    parser = argparse.ArgumentParser(description="Чат (демо)")
    parser.add_argument("--user", type=int, default=1, help="1 alex (тимлид), 2 maria, 3 ivan")
    parser.add_argument("--event", type=int, help="1 публичное, 2 ограниченное, 3 приватное")
    args = parser.parse_args()

    database = Database(DEMO_DATABASE).init_db()
    seed_demo_data(database)
    row = database.connection.execute(
        "SELECT id, username, email, role FROM users WHERE id = ?", (args.user,)
    ).fetchone()
    if row is None:
        parser.error("Пользователь не найден (в демо есть id 1, 2, 3).")

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ctk.CTk()
    app.withdraw()
    window = open_chat(app, database, User.from_any(dict(row)), args.event)
    if window is None:
        app.destroy()
        return
    window.protocol("WM_DELETE_WINDOW", app.destroy)
    app.mainloop()
    database.close()


if __name__ == "__main__":
    main()
