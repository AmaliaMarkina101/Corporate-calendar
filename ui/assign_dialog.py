import customtkinter as ctk
from tkinter import messagebox

from event_service import EventService


class AssignDialog(ctk.CTkToplevel):
    def __init__(self, master, service, current_user, task, on_assigned):
        super().__init__(master)
        self.service = service
        self.task = task
        self.on_assigned = on_assigned
        self.title("Назначить исполнителя")
        self.geometry("390x180")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(
            self, text=f"Задача: {task['title']}",
            font=ctk.CTkFont(size=15, weight="bold"), wraplength=340
        ).pack(padx=18, pady=(18, 10))

        members = EventService(service.db).get_team_members_for_event(task["event_id"])
        self.members = {m["username"]: m["id"] for m in members}
        # Тимлид также может назначить задачу себе.
        self.members[current_user.username + " (я)"] = current_user.id
        choices = list(self.members)
        self.assignee_menu = ctk.CTkOptionMenu(self, values=choices, width=300)
        self.assignee_menu.pack(padx=18, pady=8, fill="x")
        current_name = next(
            (name for name, uid in self.members.items() if uid == task["assignee_id"]),
            choices[0] if choices else "",
        )
        if choices:
            self.assignee_menu.set(current_name)

        ctk.CTkButton(self, text="Назначить", command=self._submit).pack(pady=(4, 14))

    def _submit(self):
        name = self.assignee_menu.get()
        try:
            self.service.assign_task(self.task["id"], self.members[name])
            self.on_assigned()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Не удалось назначить задачу", str(exc), parent=self)
