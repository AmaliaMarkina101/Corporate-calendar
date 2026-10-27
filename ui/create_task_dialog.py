import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime

from event_service import EventService


class CreateTaskDialog(ctk.CTkToplevel):
    def __init__(self, master, service, current_user, event_id, on_created):
        super().__init__(master)
        self.service = service
        self.current_user = current_user
        self.event_id = event_id
        self.on_created = on_created
        self.title("Создать задачу")
        self.geometry("520x570")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Новая задача", font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 12)
        )

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=1, column=0, sticky="nsew", padx=20)
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(form, text="Название").grid(row=0, column=0, sticky="w")
        self.title_entry = ctk.CTkEntry(form, placeholder_text="Название задачи")
        self.title_entry.grid(row=1, column=0, sticky="ew", pady=(3, 10))

        ctk.CTkLabel(form, text="Описание").grid(row=2, column=0, sticky="w")
        self.description_box = ctk.CTkTextbox(form, height=100)
        self.description_box.grid(row=3, column=0, sticky="ew", pady=(3, 10))

        ctk.CTkLabel(form, text="Дедлайн (ГГГГ-ММ-ДД ЧЧ:ММ)").grid(row=4, column=0, sticky="w")
        self.deadline_entry = ctk.CTkEntry(form, placeholder_text="2026-11-02 18:30")
        self.deadline_entry.grid(row=5, column=0, sticky="ew", pady=(3, 10))
        self.deadline_entry.insert(0, datetime.now().strftime("%Y-%m-%d 18:00"))

        ctk.CTkLabel(form, text="Время напоминания (необязательно)").grid(row=6, column=0, sticky="w")
        self.reminder_entry = ctk.CTkEntry(form, placeholder_text="2026-11-02 17:30")
        self.reminder_entry.grid(row=7, column=0, sticky="ew", pady=(3, 10))

        self.assignee_ids = {}
        if current_user.role == "teamlead":
            ctk.CTkLabel(form, text="Исполнитель").grid(row=8, column=0, sticky="w")
            members = EventService(service.db).get_team_members_for_event(event_id)
            choices = [f"{m['username']} (id={m['id']})" for m in members]
            choices.insert(0, f"{current_user.username} (я, id={current_user.id})")
            for choice in choices:
                import re
                match = re.search(r"id=(\d+)", choice)
                self.assignee_ids[choice] = int(match.group(1))
            self.assignee_menu = ctk.CTkOptionMenu(form, values=choices)
            self.assignee_menu.grid(row=9, column=0, sticky="ew", pady=(3, 10))
            self.assignee_menu.set(choices[0])
        else:
            self.assignee_menu = None

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="e", padx=20, pady=18)
        ctk.CTkButton(buttons, text="Отмена", fg_color="gray", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(buttons, text="Создать", command=self._submit).pack(side="right")

    def _submit(self):
        assignee_id = None
        if self.assignee_menu is not None:
            assignee_id = self.assignee_ids[self.assignee_menu.get()]
        try:
            task_id = self.service.create_task(
                event_id=self.event_id,
                title=self.title_entry.get(),
                description=self.description_box.get("1.0", "end").strip(),
                assignee_id=assignee_id,
                deadline=self.deadline_entry.get(),
                reminder_time=self.reminder_entry.get().strip() or None,
            )
            self.on_created()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Не удалось создать задачу", str(exc), parent=self)
