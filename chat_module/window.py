import sqlite3
import tkinter.messagebox as messagebox

import customtkinter as ctk

from core.event_access import EventAccess
from core.models import AuthorizationError, User
from core.timeutil import utc_to_local_text

from .service import SEARCH_LIMIT, ChatService

_SELECTED = ("#d5e5f2", "#25445d")
_ERRORS = (ValueError, PermissionError, sqlite3.Error)


def _shorten(text, limit):
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


class ChatRow(ctk.CTkFrame):
    """Строка списка чатов. Обе подписи выровнены по левому краю (в кнопке многострочный
    текст центрировался, и заголовки разной длины стояли с разным отступом)."""

    def __init__(self, master, title, preview, selected, command):
        super().__init__(master, corner_radius=8, fg_color=_SELECTED if selected else "transparent")
        self.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(
            self, text=title, anchor="w", justify="left", font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 0))
        preview_label = ctk.CTkLabel(
            self, text=preview, anchor="w", justify="left", text_color=("gray35", "gray70"),
            font=ctk.CTkFont(size=12),
        )
        preview_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 7))
        for widget in (self, title_label, preview_label):
            widget.bind("<Button-1>", lambda event: command())


class NewDialog(ctk.CTkToplevel):
    def __init__(self, master, chat_service, on_select):
        super().__init__(master)
        self.service = chat_service
        self.on_select = on_select
        self.title("Новый диалог")
        self.geometry("430x520")
        self.minsize(360, 360)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self, text="Найти человека", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(16, 4)
        )
        self.search = ctk.CTkEntry(self, placeholder_text="Имя, фамилия или логин")
        self.search.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.search.bind("<KeyRelease>", self._load_users)
        self.people = ctk.CTkScrollableFrame(self)
        self.people.grid(row=2, column=0, sticky="nsew", padx=12)
        self.people.grid_columnconfigure(0, weight=1)
        self.note = ctk.CTkLabel(self, text="", wraplength=370, justify="left")
        self.note.grid(row=3, column=0, sticky="ew", padx=16, pady=12)
        self._load_users()
        self.search.focus_set()

    def _load_users(self, event=None):
        for child in self.people.winfo_children():
            child.destroy()
        try:
            users = self.service.search_users(self.search.get())
        except _ERRORS as exc:
            self.note.configure(text=str(exc))
            return
        if not users:
            self.note.configure(text="Пользователи не найдены. Попробуйте другое имя или логин.")
            return
        if len(users) == SEARCH_LIMIT:
            self.note.configure(text=f"Показаны первые {SEARCH_LIMIT}. Уточните запрос.")
        else:
            self.note.configure(text="Выберите человека.")
        for row, user in enumerate(users):
            ctk.CTkButton(
                self.people, text=user["display_name"], anchor="w", height=48,
                command=lambda person=user: self._select_user(person),
            ).grid(row=row, column=0, sticky="ew", padx=4, pady=4)

    def _select_user(self, user):
        self.on_select({"type": "private", "id": user["id"], "title": user["display_name"]})
        self.destroy()


class ChatWindow(ctk.CTkToplevel):
    def __init__(self, master, database, current_user, event_id=None, on_open_tasks=None):
        """Окно чата. event_id: сразу открыть чат этого события.

        on_open_tasks: необязательная функция, принимающая event_id. Если передана,
        в шапке чата события появляется кнопка «Задачи».
        """
        super().__init__(master)
        self.current_user = User.from_any(current_user)
        self.service = ChatService(database, self.current_user)
        self.on_open_tasks = on_open_tasks
        self.selected_chat = None
        self._shown_chats = None
        self._shown_messages = None
        self._poll_job = None
        self.new_dialog = None

        self.title(f"Чат — {self.current_user.username}")
        self.geometry("1000x680")
        self.minsize(760, 500)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(sidebar, text="Чаты", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 10)
        )
        ctk.CTkButton(sidebar, text="Новый диалог", command=self._open_new_dialog).grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 12)
        )
        ctk.CTkLabel(sidebar, text="Поиск людей", anchor="w").grid(
            row=2, column=0, sticky="ew", padx=14, pady=(0, 4)
        )
        self.search = ctk.CTkEntry(sidebar, placeholder_text="Имя, фамилия или логин", width=260)
        self.search.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.search.bind("<KeyRelease>", self._refresh_chats)
        self.chat_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.chat_list.grid(row=4, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self.chat_list.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(self, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=12)
        header.grid_columnconfigure(0, weight=1)
        self.heading = ctk.CTkLabel(
            header, text="Выберите чат", anchor="w", font=ctk.CTkFont(size=20, weight="bold"), wraplength=450,
        )
        self.heading.grid(row=0, column=0, sticky="ew")
        self.chat_note = ctk.CTkLabel(header, text="", anchor="w", wraplength=450, justify="left")
        self.chat_note.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.header_buttons = ctk.CTkFrame(header, fg_color="transparent")
        self.header_buttons.grid(row=0, column=1, rowspan=2, padx=(8, 0))
        self.members_button = ctk.CTkButton(
            self.header_buttons, text="Участники", width=105, command=self._show_members
        )
        self.members_button.pack(side="left", padx=2)
        self.tasks_button = None
        if on_open_tasks:
            self.tasks_button = ctk.CTkButton(
                self.header_buttons, text="Задачи", width=90, command=self._open_tasks
            )
            self.tasks_button.pack(side="left", padx=2)
        self.header_buttons.grid_remove()
        self.history = ctk.CTkTextbox(content, wrap="word", state="disabled")
        self.history.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self._set_history_text(
            "Выберите чат слева или нажмите «Новый диалог», чтобы написать человеку.\n\n"
            "Чаты событий появляются, когда у вас есть доступ к соответствующим событиям."
        )
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

    # ---------- левая колонка ----------
    def _open_new_dialog(self):
        if self.new_dialog is None or not self.new_dialog.winfo_exists():
            self.new_dialog = NewDialog(self, self.service, self._select_chat)
        else:
            self.new_dialog.lift()
            self.new_dialog.focus_set()

    def _refresh_chats(self, event=None):
        query = self.search.get().strip()
        try:
            if query:
                chats = [
                    {"type": "private", "id": person["id"], "title": person["display_name"],
                     "last_message": "Открыть диалог"}
                    for person in self.service.search_users(query)
                ]
            else:
                chats = self.service.get_user_chats(self.current_user.id)
            for chat in chats:
                if self.selected_chat == (chat["type"], chat["id"]):
                    prefix = "Чат события: " if chat["type"] == "group" else ""
                    self.heading.configure(text=prefix + chat["title"])
        except _ERRORS as exc:
            self.status.configure(text=f"Не удалось обновить чаты: {exc}")
            return

        shown = (query, self.selected_chat, chats)
        if shown == self._shown_chats:
            return
        self._shown_chats = shown
        for child in self.chat_list.winfo_children():
            child.destroy()
        if not chats:
            text = "Никого не найдено" if query else "Переписок пока нет.\nНажмите «Новый диалог»,\nчтобы написать человеку."
            if not query and self.selected_chat is not None:
                text = "Диалог появится в списке\nпосле первого сообщения."
            ctk.CTkLabel(self.chat_list, text=text, wraplength=240, justify="left").grid(
                row=0, column=0, padx=8, pady=16
            )
            return
        for row, chat in enumerate(chats):
            title = _shorten(("Событие: " if chat["type"] == "group" else "") + chat["title"], 30)
            preview = _shorten(chat["last_message"], 34) or "Пока нет сообщений"
            ChatRow(
                self.chat_list, title, preview,
                selected=self.selected_chat == (chat["type"], chat["id"]),
                command=lambda selected=chat: self._select_chat(selected),
            ).grid(row=row, column=0, sticky="ew", padx=2, pady=3)

    # ---------- выбор чата ----------
    def _select_chat(self, chat):
        self.selected_chat = (chat["type"], chat["id"])
        self._shown_messages = None
        prefix = "Чат события: " if chat["type"] == "group" else ""
        self.heading.configure(text=prefix + chat["title"])
        if chat["type"] == "group":
            self.chat_note.configure(text="Участники определяются доступом к событию.")
            self.header_buttons.grid()
        else:
            self.chat_note.configure(text="Личная переписка")
            self.header_buttons.grid_remove()
        self.input_box.configure(state="normal")
        self.input_box.delete("1.0", "end")
        self.send_button.configure(state="normal")
        if self.search.get():
            self.search.delete(0, "end")
        self._load_messages(force=True)
        self._refresh_chats()
        self.input_box.focus_set()

    def open_event(self, event_id):
        try:
            self.service.events.require_access(self.current_user.id, event_id)
            event = self.service.events.get_event(event_id)
        except _ERRORS + (AuthorizationError,) as exc:
            self.status.configure(text=str(exc))
            return
        self._select_chat({"type": "group", "id": event_id, "title": event["title"]})

    def _open_tasks(self):
        if self.selected_chat is not None and self.selected_chat[0] == "group" and self.on_open_tasks:
            self.on_open_tasks(self.selected_chat[1])

    def _show_members(self):
        if self.selected_chat is None or self.selected_chat[0] != "group":
            return
        try:
            event = self.service.get_group_info(self.selected_chat[1])
        except _ERRORS as exc:
            messagebox.showerror("Не удалось загрузить участников", str(exc), parent=self)
            return
        if event["access_type"] == "public":
            access = f"Группа «{event['group_title']}»" if event["group_title"] else "Все пользователи"
        else:
            access = {"private": "Только автор", "limited": "Выбранные пользователи"}[event["access_type"]]
        people = "\n".join(user["display_name"] for user in event["members"])
        messagebox.showinfo(
            "Участники чата события",
            f"{event['title']}\nАвтор: {event['author_name']}\nДоступ: {access}\n\nУчастники:\n{people}\n\n"
            "Доступ к чату определяется доступом к событию. "
            "Добавление и исключение участников выполняется в настройках события.",
            parent=self,
        )

    # ---------- переписка ----------
    def _set_history_text(self, text):
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        self.history.insert("end", text)
        self.history.configure(state="disabled")

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
            self._shown_messages = None
            self.heading.configure(text="Чат недоступен")
            self.chat_note.configure(text="Доступ к событию мог измениться.")
            self.header_buttons.grid_remove()
            self._set_history_text("")
            self.input_box.delete("1.0", "end")
            self.input_box.configure(state="disabled")
            self.send_button.configure(state="disabled")
            self.status.configure(text=str(exc))
            return
        except sqlite3.Error as exc:
            self.status.configure(text=f"Не удалось загрузить сообщения: {exc}")
            return

        self.status.configure(text="")
        if not force and messages == self._shown_messages:
            return
        self._shown_messages = messages
        position = self.history.yview()
        scroll_to_end = force or position[1] >= 0.98
        if messages:
            lines = []
            for message in messages:
                name = "Вы" if message["sender_id"] == self.current_user.id else message["sender_name"]
                lines.append(f"{name} · {utc_to_local_text(message['created_at'], '%d.%m %H:%M')}\n{message['text']}\n\n")
            self._set_history_text("".join(lines))
        else:
            self._set_history_text("Сообщений пока нет.\n")
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
        except _ERRORS as exc:
            messagebox.showerror("Не удалось отправить сообщение", str(exc), parent=self)
            return
        self.input_box.delete("1.0", "end")
        self._load_messages(force=True)
        self._refresh_chats()

    def _enter_pressed(self, event):
        if event.state & 1:  # Shift+Enter: перенос строки
            return None
        self._send_message()
        return "break"

    def _poll(self):
        self._poll_job = None
        self._refresh_chats()
        self._load_messages()
        self._poll_job = self.after(2000, self._poll)

    def destroy(self):
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
        self._poll_job = None
        super().destroy()


def open_chat(parent, database, current_user, event_id=None, on_open_tasks=None):
    """Открывает окно чата (с чатом события, если указан event_id). None, если доступа нет."""
    user = User.from_any(current_user)
    if event_id is not None:
        try:
            access = EventAccess(database)
            access.get_event(event_id)
            access.require_access(user.id, event_id)
        except (AuthorizationError, ValueError) as exc:
            messagebox.showerror("Чат недоступен", str(exc), parent=parent)
            return None
    return ChatWindow(parent, database, user, event_id, on_open_tasks)
