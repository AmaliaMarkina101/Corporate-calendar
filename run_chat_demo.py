import argparse
import contextlib
import pathlib
import tkinter.messagebox as messagebox

import customtkinter as ctk

import auth
import db
import main
from chat import service
from chat.window import ChatWindow


def prepare_demo(database):
    database.init_db()
    main.seed_demo_data(database)
    with contextlib.closing(database.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""CREATE TABLE IF NOT EXISTS chat_demo_settings (
            name TEXT PRIMARY KEY
        )""")
        if conn.execute("SELECT 1 FROM chat_demo_settings WHERE name = 'ready'").fetchone():
            return
        conn.executemany(
            """INSERT INTO events (team_id, title, creator_id, visibility)
               VALUES (1, ?, ?, ?)""",
            [("Общее обсуждение", 1, "public"), ("Личный план Анны", 2, "private"),
             ("Закрытое обсуждение", 1, "restricted")],
        )
        restricted_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO event_members (event_id, user_id) VALUES (?, 2)", (restricted_id,))
        conn.execute("INSERT INTO chat_demo_settings (name) VALUES ('ready')")


class DemoWindow(ctk.CTk):
    def __init__(self, database, user_id=None):
        super().__init__()
        self.database = database
        self.chat_windows = []
        self.title("Проверка чата")
        self.geometry("420x250")
        self.resizable(False, False)
        users = database.fetch_all("SELECT * FROM users ORDER BY id")
        self.users = {f"{service.display_name(user)} (@{user['username']})": user for user in users}
        ctk.CTkLabel(self, text="Открыть чат от имени пользователя", font=ctk.CTkFont(size=17)).pack(
            padx=20, pady=(24, 14)
        )
        self.user_menu = ctk.CTkOptionMenu(self, values=list(self.users), width=360)
        self.user_menu.pack(padx=20, pady=6)
        ctk.CTkButton(self, text="Открыть чат", command=self.open_chat).pack(pady=14)
        ctk.CTkLabel(self, text="Можно открыть чаты двух пользователей\nи проверить переписку между ними.").pack()
        if user_id is not None:
            for label, user in self.users.items():
                if user["id"] == user_id:
                    self.user_menu.set(label)
                    self.after(0, self.open_chat)
                    break

    def open_chat(self):
        row = self.users[self.user_menu.get()]
        try:
            window = ChatWindow(self, self.database, auth.User.from_row(row))
        except (ValueError, PermissionError) as exc:
            messagebox.showerror("Не удалось открыть чат", str(exc), parent=self)
            return
        self.chat_windows.append(window)


def run():
    parser = argparse.ArgumentParser(description="Локальная проверка личных и групповых чатов")
    parser.add_argument("--user", type=int, help="Сразу открыть чат указанного пользователя")
    args = parser.parse_args()
    database = db.Database(pathlib.Path(__file__).resolve().parent / "chat_demo.db")
    prepare_demo(database)
    if args.user is not None and not database.fetch_one("SELECT id FROM users WHERE id = ?", (args.user,)):
        parser.error("Пользователь с таким id не найден")
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = DemoWindow(database, args.user)
    app.mainloop()


if __name__ == "__main__":
    run()
