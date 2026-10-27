import customtkinter as ctk
from tkinter import messagebox

from task_service import STATUSES


class TaskCard(ctk.CTkFrame):
    def __init__(self, master, task, service, current_user, on_changed, on_comments, on_assign):
        super().__init__(master, corner_radius=10)
        self.task = task
        self.service = service
        self.current_user = current_user
        self.on_changed = on_changed
        self.on_comments = on_comments
        self.on_assign = on_assign

        self.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 3))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top, text=f"#{task['id']}  {task['title']}",
            font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            top, text=f"Исполнитель: {task['assignee_username']}",
            anchor="e"
        ).grid(row=0, column=1, padx=(8, 0))

        desc = task["description"] or "Описание не указано"
        ctk.CTkLabel(self, text=desc, anchor="w", justify="left", wraplength=760).grid(
            row=1, column=0, sticky="ew", padx=12, pady=3
        )
        ctk.CTkLabel(
            self,
            text=f"Дедлайн: {task['deadline']}   •   Напоминание: {task['reminder_time'] or 'не задано'}",
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=3)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="ew", padx=8, pady=(5, 10))

        self.status_menu = ctk.CTkOptionMenu(
            controls,
            values=list(STATUSES.keys()),
            command=self._change_status,
            width=150,
        )
        self.status_menu.set(task["status"])
        self.status_menu.pack(side="left", padx=4)

        ctk.CTkButton(
            controls, text="Комментарии", width=120,
            command=lambda: self.on_comments(self.task)
        ).pack(side="left", padx=4)

        if current_user.role == "teamlead":
            ctk.CTkButton(
                controls, text="Назначить", width=100,
                command=lambda: self.on_assign(self.task)
            ).pack(side="left", padx=4)

    def _change_status(self, new_status):
        try:
            self.service.change_task_status(self.task["id"], new_status)
            self.task["status"] = new_status
            self.on_changed()
        except Exception as exc:
            messagebox.showerror("Не удалось изменить статус", str(exc), parent=self)
            self.status_menu.set(self.task["status"])
