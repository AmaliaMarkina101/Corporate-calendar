import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox

import customtkinter as ctk

from core.timeutil import utc_to_local_text


def _fit_height(window, wanted):
    """Высота окна не больше экрана (с запасом под панель задач и заголовок)."""
    return max(380, min(wanted, window.winfo_screenheight() - 120))


def _safe_grab(window):
    # Сразу после создания окно может быть ещё не видно, и grab_set падает на Linux/WSL.
    try:
        window.grab_set()
    except tk.TclError:
        window.after(100, lambda: _safe_grab(window))


class CreateTaskDialog(ctk.CTkToplevel):
    def __init__(self, master, service, event_id, on_created):
        super().__init__(master)
        self.service = service
        self.current_user = service.current_user
        self.event_id = event_id
        self.on_created = on_created
        self.title("Создать задачу")
        self.geometry(f"520x{_fit_height(self, 640)}")
        self.minsize(460, 380)
        self.transient(master)
        self.after(50, lambda: _safe_grab(self))

        # Поля в прокручиваемой области, кнопки закреплены внизу и видны на любом экране.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        form = ctk.CTkScrollableFrame(self)
        form.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(form, text="Новая задача", font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 10)
        )

        tomorrow = datetime.now() + timedelta(days=1)
        deadline_default = tomorrow.strftime("%Y-%m-%d 18:00")
        reminder_hint = tomorrow.strftime("%Y-%m-%d 17:30")

        ctk.CTkLabel(form, text="Название").grid(row=1, column=0, sticky="w", padx=10)
        self.title_entry = ctk.CTkEntry(form, placeholder_text="Название задачи")
        self.title_entry.grid(row=2, column=0, sticky="ew", padx=10, pady=(3, 10))

        ctk.CTkLabel(form, text="Описание").grid(row=3, column=0, sticky="w", padx=10)
        self.description_box = ctk.CTkTextbox(form, height=100)
        self.description_box.grid(row=4, column=0, sticky="ew", padx=10, pady=(3, 10))

        ctk.CTkLabel(form, text="Дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ)").grid(row=5, column=0, sticky="w", padx=10)
        self.deadline_entry = ctk.CTkEntry(form)
        self.deadline_entry.grid(row=6, column=0, sticky="ew", padx=10, pady=(3, 10))
        self.deadline_entry.insert(0, deadline_default)

        ctk.CTkLabel(form, text="Время напоминания (необязательно, ГГГГ-ММ-ДД ЧЧ:ММ)").grid(
            row=7, column=0, sticky="w", padx=10
        )
        self.reminder_entry = ctk.CTkEntry(form, placeholder_text=f"например, {reminder_hint}")
        self.reminder_entry.grid(row=8, column=0, sticky="ew", padx=10, pady=(3, 10))

        self.assignee_ids = {}
        self.assignee_menu = None
        if self.current_user.role == "teamlead":
            ctk.CTkLabel(form, text="Исполнитель").grid(row=9, column=0, sticky="w", padx=10)
            self.assignee_ids[f"{self.current_user.username} (я)"] = self.current_user.id
            for member in service.events.get_team_members_for_event(event_id, self.current_user.id):
                self.assignee_ids[member["username"]] = member["id"]
            choices = list(self.assignee_ids)
            self.assignee_menu = ctk.CTkOptionMenu(form, values=choices)
            self.assignee_menu.set(choices[0])
            self.assignee_menu.grid(row=10, column=0, sticky="ew", padx=10, pady=(3, 10))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="e", padx=20, pady=14)
        ctk.CTkButton(buttons, text="Отмена", fg_color="gray", command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Создать", command=self._submit).pack(side="right")

    def _submit(self):
        assignee_id = None
        if self.assignee_menu is not None:
            assignee_id = self.assignee_ids[self.assignee_menu.get()]
        try:
            self.service.create_task(
                event_id=self.event_id,
                title=self.title_entry.get(),
                description=self.description_box.get("1.0", "end").strip(),
                assignee_id=assignee_id,
                deadline=self.deadline_entry.get(),
                reminder_time=self.reminder_entry.get().strip() or None,
            )
        except Exception as exc:
            messagebox.showerror("Не удалось создать задачу", str(exc), parent=self)
            return
        self.on_created()
        self.destroy()


class AssignDialog(ctk.CTkToplevel):
    def __init__(self, master, service, task, on_assigned):
        super().__init__(master)
        self.service = service
        self.task = task
        self.on_assigned = on_assigned
        self.title("Назначить исполнителя")
        self.geometry("400x200")
        self.resizable(False, False)
        self.transient(master)
        self.after(50, lambda: _safe_grab(self))

        ctk.CTkLabel(
            self, text=f"Задача: {task['title']}", font=ctk.CTkFont(size=15, weight="bold"), wraplength=350
        ).pack(padx=18, pady=(18, 10))

        user = service.current_user
        self.members = {f"{user.username} (я)": user.id}
        for member in service.events.get_team_members_for_event(task["event_id"], user.id):
            self.members[member["username"]] = member["id"]
        choices = list(self.members)
        self.assignee_menu = ctk.CTkOptionMenu(self, values=choices, width=300)
        self.assignee_menu.pack(padx=18, pady=8, fill="x")
        current_name = next(
            (name for name, uid in self.members.items() if uid == task["assignee_id"]), choices[0]
        )
        self.assignee_menu.set(current_name)
        ctk.CTkButton(self, text="Назначить", command=self._submit).pack(pady=(4, 14))

    def _submit(self):
        try:
            self.service.assign_task(self.task["id"], self.members[self.assignee_menu.get()])
        except Exception as exc:
            messagebox.showerror("Не удалось назначить задачу", str(exc), parent=self)
            return
        self.on_assigned()
        self.destroy()


class CommentsDialog(ctk.CTkToplevel):
    def __init__(self, master, service, task, on_changed=None):
        super().__init__(master)
        self.service = service
        self.task = task
        self.on_changed = on_changed
        self.title(f"Комментарии — {task['title']}")
        self.geometry(f"620x{_fit_height(self, 540)}")
        self.minsize(480, 380)
        self.transient(master)
        self.after(50, lambda: _safe_grab(self))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=f"Комментарии: {task['title']}", font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w", wraplength=560,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=12)

        self.history = ctk.CTkScrollableFrame(self)
        self.history.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.history.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        bottom.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkTextbox(bottom, height=75)
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(bottom, text="Отправить", width=110, command=self._send).grid(row=0, column=1, sticky="se")
        self._load_comments()

    def _load_comments(self):
        for child in self.history.winfo_children():
            child.destroy()
        try:
            comments = self.service.get_comments(self.task["id"])
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        if not comments:
            ctk.CTkLabel(self.history, text="Комментариев пока нет.").grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return
        for index, comment in enumerate(comments):
            card = ctk.CTkFrame(self.history, corner_radius=8)
            card.grid(row=index, column=0, sticky="ew", padx=4, pady=4)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card, text=f"{comment['username']} • {utc_to_local_text(comment['created_at'])}",
                font=ctk.CTkFont(size=11, weight="bold"), anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            ctk.CTkLabel(card, text=comment["text"], anchor="w", justify="left", wraplength=520).grid(
                row=1, column=0, sticky="ew", padx=10, pady=(2, 8)
            )

    def _send(self):
        try:
            self.service.add_comment(
                task_id=self.task["id"],
                user_id=self.service.current_user.id,
                text=self.input_box.get("1.0", "end").strip(),
            )
        except Exception as exc:
            messagebox.showerror("Не удалось отправить комментарий", str(exc), parent=self)
            return
        self.input_box.delete("1.0", "end")
        self._load_comments()
        if self.on_changed:
            self.on_changed()
