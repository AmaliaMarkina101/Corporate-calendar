import customtkinter as ctk
from tkinter import messagebox

from event_service import EventService
from ui.task_card import TaskCard
from ui.create_task_dialog import CreateTaskDialog
from ui.comments_dialog import CommentsDialog
from ui.assign_dialog import AssignDialog


class MainWindow(ctk.CTk):
    def __init__(self, database, current_user, event_id: int):
        super().__init__()
        self.db = database
        self.current_user = current_user
        self.event_id = event_id
        from task_service import TaskService
        self.service = TaskService(database, current_user)
        self.events = EventService(database)

        event = self.events.get_event(event_id)
        self.title(f"Задачи — {event['title']}")
        self.geometry("1050x720")
        self.minsize(760, 520)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text=event["title"],
            font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            header,
            text=f"Пользователь: {current_user.username} ({current_user.role})",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))
        ctk.CTkButton(
            header, text="Создать задачу", command=self._open_create
        ).grid(row=0, column=1, rowspan=2, padx=14, pady=12)

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
            ctk.CTkLabel(
                self.task_list, text="Задач пока нет. Нажмите «Создать задачу», чтобы добавить первую."
            ).grid(row=0, column=0, padx=12, pady=24, sticky="w")
            return
        for index, task in enumerate(tasks):
            card = TaskCard(
                self.task_list, task, self.service, self.current_user,
                on_changed=self.refresh_tasks,
                on_comments=lambda selected: self._open_comments(selected),
                on_assign=lambda selected: self._open_assign(selected),
            )
            card.grid(row=index, column=0, sticky="ew", padx=6, pady=6)

    def _open_create(self):
        CreateTaskDialog(self, self.service, self.current_user, self.event_id, self.refresh_tasks)

    def _open_comments(self, task):
        CommentsDialog(self, self.service, self.current_user, task, self.refresh_tasks)

    def _open_assign(self, task):
        if self.current_user.role != "teamlead":
            messagebox.showerror("Недостаточно прав", "Назначать исполнителей может только тимлид.", parent=self)
            return
        AssignDialog(self, self.service, self.current_user, task, self.refresh_tasks)
