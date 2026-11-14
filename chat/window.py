import datetime
import sqlite3
import tkinter as tk
import tkinter.messagebox as messagebox

import customtkinter as ctk

from chat import service


class ChatWindow(ctk.CTkToplevel):
    def __init__(self, master, database, current_user, event_id=None):
        super().__init__(master)
        self.current_user = current_user
        self.service = service.ChatService(database, current_user)
        self.selected_chat = None
        self._chat_signature = None
        self._message_signature = None
        self._poll_job = None
        self._search_job = None

        self.title(f"Чат — {current_user.username}")
        self.geometry("1000x680")
        self.minsize(760, 500)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(sidebar, text="Чаты", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 10)
        )
        self.search = tk.StringVar(master=self)
        ctk.CTkEntry(
            sidebar, textvariable=self.search, placeholder_text="Имя, фамилия или логин",
            width=260,
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.chat_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.chat_list.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self.chat_list.grid_columnconfigure(0, weight=1)
        self.search.trace_add("write", self._search_changed)

        content = ctk.CTkFrame(self, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)
        self.heading = ctk.CTkLabel(
            content, text="Выберите чат", anchor="w",
            font=ctk.CTkFont(size=20, weight="bold"), wraplength=530,
        )
        self.heading.grid(row=0, column=0, sticky="ew", padx=16, pady=14)
        self.history = ctk.CTkTextbox(content, wrap="word", state="disabled")
        self.history.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.status = ctk.CTkLabel(content, text="", anchor="w", wraplength=550)
        self.status.grid(row=2, column=0, sticky="ew", padx=16)

        bottom = ctk.CTkFrame(content, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 12))
        bottom.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkTextbox(bottom, height=80, wrap="word", state="disabled")
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.input_box.bind("<Return>", self._enter_pressed)
        self.send_button = ctk.CTkButton(
            bottom, text="Отправить", width=110, state="disabled", command=self._send_message
        )
        self.send_button.grid(row=0, column=1, sticky="se")

        self._refresh_chats()
        if event_id is not None:
            self.open_event(event_id)
        self._poll_job = self.after(2000, self._poll)

    def _search_changed(self, *args):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._run_search)

    def _run_search(self):
        self._search_job = None
        self._refresh_chats()

    def _refresh_chats(self):
        query = self.search.get().strip()
        try:
            if query:
                people = self.service.search_users(query)
                chats = [{
                    "type": "private", "id": person["id"],
                    "title": person["display_name"],
                    "last_message": "@" + person["username"],
                } for person in people]
            else:
                chats = self.service.get_user_chats(self.current_user.id)
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            self.status.configure(text=f"Не удалось обновить чаты: {exc}")
            return

        signature = (query, self.selected_chat, tuple(
            (chat["type"], chat["id"], chat["title"], chat["last_message"])
            for chat in chats
        ))
        if signature == self._chat_signature:
            return
        self._chat_signature = signature
        for child in self.chat_list.winfo_children():
            child.destroy()
        if not chats:
            text = "Никого не найдено" if query else "Переписок пока нет"
            ctk.CTkLabel(self.chat_list, text=text).grid(row=0, column=0, padx=8, pady=16)
            return
        for row, chat in enumerate(chats):
            title = chat["title"]
            if chat["type"] == "group":
                title = "Группа: " + title
            if len(title) > 30:
                title = title[:29] + "…"
            preview = chat["last_message"].replace("\n", " ")
            if len(preview) > 32:
                preview = preview[:32] + "…"
            selected = self.selected_chat == (chat["type"], chat["id"])
            ctk.CTkButton(
                self.chat_list, text=f"{title}\n{preview or 'Пока нет сообщений'}",
                anchor="w", height=58,
                fg_color=("#d5e5f2", "#25445d") if selected else "transparent",
                text_color=("#202020", "#eeeeee"),
                command=lambda selected=chat: self._select_chat(selected),
            ).grid(row=row, column=0, sticky="ew", padx=2, pady=3)

    def _select_chat(self, chat):
        self.selected_chat = (chat["type"], chat["id"])
        self._message_signature = None
        self.heading.configure(text=chat["title"])
        self.input_box.configure(state="normal")
        self.input_box.delete("1.0", "end")
        self.send_button.configure(state="normal")
        if self.search.get():
            self.search.set("")
        self._load_messages(force=True)
        self._refresh_chats()
        self.input_box.focus_set()

    def open_event(self, event_id):
        try:
            self.service.events.require_event_access(self.current_user.id, event_id)
            event = self.service.events.get_event(event_id)
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            self.status.configure(text=str(exc))
            return
        self._select_chat({"type": "group", "id": event_id, "title": event["title"]})

    def _load_messages(self, force=False):
        if self.selected_chat is None:
            return
        chat_type, chat_id = self.selected_chat
        try:
            if chat_type == "group":
                messages = self.service.get_group_messages(chat_id)
            else:
                messages = self.service.get_private_messages(self.current_user.id, chat_id)
        except (ValueError, PermissionError) as exc:
            self.selected_chat = None
            self._message_signature = None
            self.heading.configure(text="Чат недоступен")
            self.history.configure(state="normal")
            self.history.delete("1.0", "end")
            self.history.configure(state="disabled")
            self.input_box.delete("1.0", "end")
            self.input_box.configure(state="disabled")
            self.send_button.configure(state="disabled")
            self.status.configure(text=str(exc))
            return
        except sqlite3.Error as exc:
            self.status.configure(text=f"Не удалось загрузить сообщения: {exc}")
            return

        self.status.configure(text="")
        signature = tuple((m["id"], m["text"], m["sender_name"], m["created_at"]) for m in messages)
        if not force and signature == self._message_signature:
            return
        self._message_signature = signature
        position = self.history.yview()
        scroll_to_end = force or position[1] >= 0.98
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        if not messages:
            self.history.insert("end", "Сообщений пока нет.\n")
        for message in messages:
            name = "Вы" if message["sender_id"] == self.current_user.id else message["sender_name"]
            sent_at = datetime.datetime.fromisoformat(message["created_at"])
            sent_at = sent_at.replace(tzinfo=datetime.timezone.utc).astimezone()
            self.history.insert("end", f"{name} · {sent_at:%d.%m %H:%M}\n{message['text']}\n\n")
        self.history.configure(state="disabled")
        if scroll_to_end:
            self.history.see("end")
        else:
            self.history.yview_moveto(position[0])

    def _send_message(self):
        if self.selected_chat is None:
            return
        chat_type, chat_id = self.selected_chat
        text = self.input_box.get("1.0", "end").strip()
        try:
            if chat_type == "group":
                self.service.send_group_message(chat_id, self.current_user.id, text)
            else:
                self.service.send_private_message(self.current_user.id, chat_id, text)
        except (ValueError, PermissionError, sqlite3.Error) as exc:
            messagebox.showerror("Не удалось отправить сообщение", str(exc), parent=self)
            return
        self.input_box.delete("1.0", "end")
        self._load_messages(force=True)
        self._refresh_chats()

    def _enter_pressed(self, event):
        if event.state & 1:
            return
        self._send_message()
        return "break"

    def _poll(self):
        self._poll_job = None
        self._refresh_chats()
        self._load_messages()
        self._poll_job = self.after(2000, self._poll)

    def destroy(self):
        for job in (self._poll_job, self._search_job):
            if job is not None:
                self.after_cancel(job)
        self._poll_job = None
        self._search_job = None
        super().destroy()
