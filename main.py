"""Точка входа приложения: вход или регистрация, затем главное меню.

Запуск из корня проекта:  python main.py
"""
import os
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from alarm_ui import AlarmManager
from auth_service import AuthService
from auth_ui import LoginFrame, RegisterFrame
from calendar_module.database import Database
from calendar_module.window import CalendarWindow
from chat_module.schema import init_chat_tables
from chat_module.window import open_chat
from core.db_access import Db
from core.models import User
from menu_ui import MenuFrame, TasksPickerWindow, UsersAdminWindow
from tasks_module.schema import init_task_tables
from tasks_module.window import open_tasks

DB_PATH = Path(os.environ.get("CORPORATE_CALENDAR_DB") or Path(__file__).resolve().with_name("corporate_calendar.db"))


def open_database(path=DB_PATH):
    """Одна общая база на всё приложение: таблицы календаря, задач и чата."""
    database = Database(path).init_db()
    init_task_tables(database)
    init_chat_tables(database)
    return database


class App(ctk.CTk):
    def __init__(self, database):
        super().__init__()
        self.database = database
        self.db = Db.wrap(database)
        self.auth = AuthService(database)
        self.user = None        # User текущего пользователя
        self.user_row = None    # его строка из таблицы users (имя, роль и т.д.)
        self.alarm = None
        self.windows = {}       # открытые окна модулей: чтобы не плодить дубли
        self.frame = None

        self.title("Корпоративный календарь")
        self.geometry("900x620")
        self.minsize(760, 560)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_login()

    # ---------- смена экранов ----------
    def _show(self, frame):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = frame
        frame.pack(fill="both", expand=True)

    def show_login(self):
        self._show(LoginFrame(self, self.auth, self.on_login, self.show_register))

    def show_register(self):
        self._show(RegisterFrame(self, self.auth, self.on_login, self.show_login))

    def on_login(self, user):
        self.user = user
        self.user_row = self.auth.get_user(user.id)
        self.alarm = AlarmManager(self, self.database, user, self.open_tasks_window)
        self.alarm.start()
        self._show(MenuFrame(self, self))

    def logout(self):
        self._close_windows()
        if self.alarm is not None:
            self.alarm.stop()
            self.alarm = None
        self.user = self.user_row = None
        self.show_login()

    def close(self):
        self._close_windows()
        if self.alarm is not None:
            self.alarm.stop()
        self.database.close()
        self.destroy()

    # ---------- окна модулей ----------
    def _alive(self, key):
        window = self.windows.get(key)
        try:
            if window is not None and window.winfo_exists():
                return window
        except tk.TclError:
            pass
        self.windows.pop(key, None)
        return None

    @staticmethod
    def _raise(window):
        window.deiconify()
        window.lift()
        window.focus_force()

    def _close_windows(self):
        for window in list(self.windows.values()):
            try:
                window.destroy()
            except tk.TclError:
                pass
        self.windows.clear()

    def open_calendar(self):
        window = self._alive("calendar")
        if window is None:
            window = CalendarWindow(
                self, self.database, self.user,
                on_open_tasks=self.open_tasks_window, on_open_chat=self.open_chat_window,
            )
            self.windows["calendar"] = window
        self._raise(window)

    def open_tasks_picker(self):
        window = self._alive("tasks_picker")
        if window is None:
            window = TasksPickerWindow(
                self, self.database, self.user, self.open_tasks_window, self.open_calendar
            )
            self.windows["tasks_picker"] = window
        self._raise(window)

    def open_tasks_window(self, event_id):
        key = ("tasks", event_id)
        window = self._alive(key)
        if window is None:
            window = open_tasks(self, self.database, self.user, event_id, on_open_chat=self.open_chat_window)
            if window is None:      # нет доступа: модуль сам показал сообщение
                return
            self.windows[key] = window
        self._raise(window)

    def open_chat_window(self, event_id=None):
        window = self._alive("chat")
        if window is None:
            window = open_chat(self, self.database, self.user, event_id, on_open_tasks=self.open_tasks_window)
            if window is None:
                return
            self.windows["chat"] = window
        elif event_id is not None:
            window.open_event(event_id)
        self._raise(window)

    def open_users_admin(self):
        window = self._alive("users_admin")
        if window is None:
            window = UsersAdminWindow(self, self.auth, self.user)
            self.windows["users_admin"] = window
        self._raise(window)


def main():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    App(open_database()).mainloop()


if __name__ == "__main__":
    main()
