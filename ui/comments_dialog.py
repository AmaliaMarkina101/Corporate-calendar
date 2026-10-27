import customtkinter as ctk
from tkinter import messagebox


class CommentsDialog(ctk.CTkToplevel):
    def __init__(self, master, service, current_user, task, on_changed=None):
        super().__init__(master)
        self.service = service
        self.current_user = current_user
        self.task = task
        self.on_changed = on_changed
        self.title(f"Комментарии — {task['title']}")
        self.geometry("620x540")
        self.minsize(480, 400)
        self.transient(master)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=f"Комментарии к задаче #{task['id']}",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=16, pady=12)

        self.history = ctk.CTkScrollableFrame(self)
        self.history.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.history.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        bottom.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkTextbox(bottom, height=75)
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(bottom, text="Отправить", width=110, command=self._send).grid(
            row=0, column=1, sticky="se"
        )
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
            ctk.CTkLabel(self.history, text="Комментариев пока нет.").grid(
                row=0, column=0, sticky="w", padx=8, pady=8
            )
            return
        for i, comment in enumerate(comments):
            card = ctk.CTkFrame(self.history, corner_radius=8)
            card.grid(row=i, column=0, sticky="ew", padx=4, pady=4)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card, text=f"{comment['username']} • {comment['created_at']}",
                font=ctk.CTkFont(size=11, weight="bold"), anchor="w"
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            ctk.CTkLabel(
                card, text=comment["text"], anchor="w", justify="left", wraplength=520
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 8))

    def _send(self):
        try:
            self.service.add_comment(
                task_id=self.task["id"],
                user_id=self.current_user.id,
                text=self.input_box.get("1.0", "end").strip(),
            )
            self.input_box.delete("1.0", "end")
            self._load_comments()
            if self.on_changed:
                self.on_changed()
        except Exception as exc:
            messagebox.showerror("Не удалось отправить комментарий", str(exc), parent=self)
