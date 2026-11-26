import customtkinter as ctk
from tkinter import messagebox

from .dialogs import AssignDialog, CommentsDialog, CreateTaskDialog
from core.event_access import EventAccess
from core.models import AuthorizationError, User
from .task_card import TaskCard
from .task_service import TaskService

_ROLE_LABELS = {"admin": "Администратор", "teamlead": "Тимлид", "member": "Участник"}


class TasksWindow(ctk.CTkToplevel):
    def __init__(self, parent, database, current_user, event_id, on_open_chat=None):
        """Окно задач события.

        on_open_chat: необязательная функция, принимающая event_id. Если передана,
        в шапке появляется кнопка «Чат события».
        """
        super().__init__(parent)
        self.current_user = User.from_any(current_user)
        self.event_id = event_id
        self.service = TaskService(database, self.current_user)
        event = self.service.events.get_event(event_id)

        self.title(f"Задачи — {event['title']}")
        self.geometry("1050x720")
        self.minsize(760, 520)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text=f"Событие: {event['title']}", font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w", wraplength=650,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        role = _ROLE_LABELS.get(self.current_user.role, self.current_user.role)
        ctk.CTkLabel(header, text=f"Пользователь: {self.current_user.username} — {role}").grid(
            row=1, column=0, sticky="w", padx=14, pady=(0, 12)
        )

        buttons = ctk.CTkFrame(header, fg_color="transparent")
        buttons.grid(row=0, column=1, rowspan=2, padx=14, pady=12)
        self.create_button = ctk.CTkButton(buttons, text="Создать задачу", command=self._open_create)
        self.create_button.pack(side="left", padx=4)
        if not self.service.can_create(event_id):
            self.create_button.configure(state="disabled")
            ctk.CTkLabel(
                header, text="У вас доступ только для чтения: задачи создавать нельзя.", text_color="gray"
            ).grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))
        if on_open_chat:
            ctk.CTkButton(buttons, text="Чат события", command=lambda: on_open_chat(event_id)).pack(
                side="left", padx=4
            )

        self.task_list = ctk.CTkScrollableFrame(self, label_text="Список задач")
        self.task_list.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.task_list.grid_columnconfigure(0, weight=1)
        self.refresh_tasks()

    def refresh_tasks(self):
        for child in self.task_list.winfo_children():
            child.destroy()
        try:
            tasks = self.service.get_tasks_by_event(self.event_id)
        except Exception as exc:
            messagebox.showerror("Не удалось загрузить задачи", str(exc), parent=self)
            return
        if not tasks:
            ctk.CTkLabel(self.task_list, text="Задач пока нет.").grid(row=0, column=0, padx=12, pady=24, sticky="w")
            return
        for index, task in enumerate(tasks):
            card = TaskCard(
                self.task_list, task, self.service,
                on_changed=self.refresh_tasks,
                on_comments=self._open_comments,
                on_assign=self._open_assign,
            )
            card.grid(row=index, column=0, sticky="ew", padx=6, pady=6)

    def _open_create(self):
        CreateTaskDialog(self, self.service, self.event_id, self.refresh_tasks)

    def _open_comments(self, task):
        CommentsDialog(self, self.service, task, self.refresh_tasks)

    def _open_assign(self, task):
        AssignDialog(self, self.service, task, self.refresh_tasks)


def open_tasks(parent, database, current_user, event_id, on_open_chat=None):
    """Открывает окно задач события. Возвращает окно или None, если доступа нет."""
    user = User.from_any(current_user)
    try:
        EventAccess(database).get_event(event_id)
        EventAccess(database).require_access(user.id, event_id)
    except (AuthorizationError, ValueError) as exc:
        messagebox.showerror("Задачи недоступны", str(exc), parent=parent)
        return None
    return TasksWindow(parent, database, user, event_id, on_open_chat)
