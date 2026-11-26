"""Главное меню, список событий для задач и управление ролями."""
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from auth_service import ROLES, AuthError, AuthService, display_name
from calendar_module.event_service import get_events_for_user
from core.models import AuthorizationError

ERROR_COLOR = ("#c0392b", "#ff7b72")


def _fmt(text, with_time=True):
    try:
        moment = datetime.strptime(text[:16], "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(text)
    return moment.strftime("%d.%m.%Y %H:%M" if with_time else "%d.%m.%Y")


class MenuFrame(ctk.CTkFrame):
    """Главный экран: приветствие, три большие кнопки и короткая сводка по задачам."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._job = None
        user = app.user_row
        name = display_name(user)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=40, pady=(30, 0))
        ctk.CTkLabel(top, text=f"Здравствуйте, {name}!", font=ctk.CTkFont(size=30, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            top, text=f"{ROLES.get(user['role'], user['role'])}  •  @{user['username']}", text_color="gray"
        ).pack(anchor="w", pady=(2, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=40, pady=30)
        entries = [
            ("Календарь", "события и расписание", app.open_calendar),
            ("Задачи", "по вашим событиям", app.open_tasks_picker),
            ("Чат", "личные и групповые", app.open_chat_window),
        ]
        for column, (title, hint, command) in enumerate(entries):
            buttons.grid_columnconfigure(column, weight=1, uniform="menu")
            ctk.CTkButton(
                buttons, text=f"{title}\n{hint}", height=150, font=ctk.CTkFont(size=22, weight="bold"),
                command=command,
            ).grid(row=0, column=column, padx=8, sticky="nsew")

        self.summary = ctk.CTkLabel(self, text="", justify="left", anchor="w")
        self.summary.pack(fill="x", padx=48)
        ctk.CTkLabel(
            self, text="Будильник включён: напоминания по задачам появятся во всплывающем окне.",
            text_color="gray", anchor="w",
        ).pack(fill="x", padx=48, pady=(4, 0))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=40, pady=24)
        if user["role"] == "admin":
            ctk.CTkButton(bottom, text="Пользователи и роли", width=190, fg_color="gray40",
                          hover_color="gray30", command=app.open_users_admin).pack(side="left")
        ctk.CTkButton(bottom, text="Выйти", width=110, fg_color="transparent", border_width=1,
                      text_color=("gray20", "gray90"), command=app.logout).pack(side="right")
        self.refresh()

    def refresh(self):
        self.summary.configure(text=self._summary_text())
        self._job = self.after(20_000, self.refresh)

    def _summary_text(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        row = self.app.db.fetch_one(
            """SELECT COUNT(*) AS total, MIN(deadline) AS nearest,
                      COALESCE(SUM(deadline < ?), 0) AS overdue
               FROM tasks WHERE assignee_id = ? AND status != 'done'""",
            (now, self.app.user.id),
        )
        if not row or not row["total"]:
            return "Невыполненных задач нет."
        text = f"Невыполненных задач: {row['total']}.  Ближайший дедлайн: {_fmt(row['nearest'])}."
        if row["overdue"]:
            text += f"\nПросрочено: {row['overdue']}."
        return text

    def destroy(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        super().destroy()


class TasksPickerWindow(ctk.CTkToplevel):
    """Общий список событий пользователя: выбираем событие и открываем его задачи."""

    def __init__(self, app, database, user, on_open_tasks, on_open_calendar):
        super().__init__(app)
        self.title("Задачи: выберите событие")
        self.geometry("720x560")
        self.minsize(560, 400)
        ctk.CTkLabel(self, text="Задачи", font=ctk.CTkFont(size=24, weight="bold")).pack(
            padx=24, pady=(20, 0), anchor="w"
        )
        ctk.CTkLabel(self, text="Задачи хранятся внутри событий. Выберите событие.", text_color="gray").pack(
            padx=24, pady=(0, 10), anchor="w"
        )
        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        events = get_events_for_user(user.id, database)
        counts = {}
        for row in app.db.fetch_all(
            """SELECT event_id, COUNT(*) AS total,
                      COALESCE(SUM(assignee_id = ? AND status != 'done'), 0) AS mine
               FROM tasks GROUP BY event_id""",
            (user.id,),
        ):
            counts[row["event_id"]] = row
        events.sort(key=lambda e: (-counts.get(e["id"], {}).get("mine", 0), e["start_time"]))

        if not events:
            ctk.CTkLabel(body, text="У вас пока нет событий. Создайте событие в календаре.").pack(pady=20)
            ctk.CTkButton(body, text="Открыть календарь", command=on_open_calendar).pack()
            return
        for event in events:
            stat = counts.get(event["id"], {"total": 0, "mine": 0})
            card = ctk.CTkFrame(body)
            card.pack(fill="x", padx=4, pady=5)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=event["title"], font=ctk.CTkFont(size=16, weight="bold"), anchor="w").grid(
                row=0, column=0, padx=14, pady=(10, 0), sticky="w"
            )
            ctk.CTkLabel(
                card,
                text=f"{_fmt(event['start_time'])} — {_fmt(event['end_time'])}\n"
                     f"Задач: {stat['total']}  •  моих невыполненных: {stat['mine']}",
                text_color="gray", justify="left", anchor="w",
            ).grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")
            ctk.CTkButton(
                card, text="Открыть задачи", width=140,
                command=lambda event_id=event["id"]: on_open_tasks(event_id),
            ).grid(row=0, column=1, rowspan=2, padx=14)


class UsersAdminWindow(ctk.CTkToplevel):
    """Администратор назначает роли (например, делает человека тимлидом)."""

    def __init__(self, app, auth: AuthService, current_user):
        super().__init__(app)
        self.auth = auth
        self.current_user = current_user
        self.title("Пользователи и роли")
        self.geometry("680x520")
        self.minsize(560, 360)
        ctk.CTkLabel(self, text="Пользователи и роли", font=ctk.CTkFont(size=24, weight="bold")).pack(
            padx=24, pady=(20, 0), anchor="w"
        )
        ctk.CTkLabel(
            self, text="Тимлид может создавать группы, назначать исполнителей и вести задачи команды.",
            text_color="gray", wraplength=600, justify="left",
        ).pack(padx=24, pady=(0, 10), anchor="w")
        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._label_to_role = {label: role for role, label in ROLES.items()}
        for user in auth.list_users():
            row = ctk.CTkFrame(body)
            row.pack(fill="x", padx=4, pady=4)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=user["display_name"], font=ctk.CTkFont(size=15, weight="bold"), anchor="w").grid(
                row=0, column=0, padx=12, pady=(8, 0), sticky="w"
            )
            ctk.CTkLabel(row, text=f"@{user['username']}  •  {user['email']}", text_color="gray", anchor="w").grid(
                row=1, column=0, padx=12, pady=(0, 8), sticky="w"
            )
            menu = ctk.CTkOptionMenu(row, values=list(ROLES.values()), width=170)
            menu.set(ROLES.get(user["role"], user["role"]))
            menu.configure(command=lambda choice, u=user, m=menu: self._change(u, m, choice))
            if user["id"] == current_user.id:
                menu.configure(state="disabled")  # чтобы случайно не лишить себя прав
            menu.grid(row=0, column=1, rowspan=2, padx=12)

    def _change(self, user, menu, choice):
        try:
            self.auth.set_role(self.current_user.id, user["id"], self._label_to_role[choice])
        except (AuthError, AuthorizationError) as exc:
            menu.set(ROLES.get(user["role"], user["role"]))
            messagebox.showerror("Роль не изменена", str(exc), parent=self)
            return
        user["role"] = self._label_to_role[choice]
