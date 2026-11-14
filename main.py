import customtkinter as ctk
import argparse

from db import db
from auth import User
from event_service import EventService
from chat.window import ChatWindow
from ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(description="Календарь: задачи и переписка")
    parser.add_argument("--user", type=int, required=True, help="ID существующего пользователя")
    parser.add_argument("--event", type=int, help="ID события, задачи которого нужно открыть")
    args = parser.parse_args()
    try:
        db.init_db()
    except ValueError as exc:
        parser.error(str(exc))

    row = db.fetch_one("SELECT id, username, email, role FROM users WHERE id=?", (args.user,))
    if not row:
        parser.error("Пользователь не найден. Его должен создать модуль регистрации или авторизации.")
    current_user = User.from_row(row)
    if args.event is not None:
        try:
            EventService(db).require_event_access(current_user.id, args.event)
        except PermissionError as exc:
            parser.error(str(exc))

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    if args.event is None:
        app = ctk.CTk()
        app.withdraw()
        chat = ChatWindow(app, db, current_user)
        chat.protocol("WM_DELETE_WINDOW", app.destroy)
    else:
        app = MainWindow(db, current_user, args.event)
    app.mainloop()


if __name__ == "__main__":
    main()
