from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from tkcalendar import Calendar

from .dialogs import CreateEventDialog, CreateGroupDialog
from .event_service import get_events_for_user


_CATEGORY_LABELS = {
    "personal": "Личное",
    "work": "Работа",
    "rest": "Отдых",
}


class CalendarWindow(ctk.CTkToplevel):
    def __init__(self, app, database, current_user):
        super().__init__(app)
        self.database = database
        self.current_user = self._normalize_user(current_user)
        self.events = []
        self.title("Календарь")
        self.geometry("1050x690")
        self.minsize(850, 590)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, padx=20, pady=(18, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=f"Календарь — {self.current_user.get('username', 'Пользователь')}",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="Создать группу", width=130, command=self._open_group_dialog).grid(
            row=0, column=1, padx=(8, 0)
        )
        ctk.CTkButton(header, text="Создать событие", width=150, command=self._open_event_dialog).grid(
            row=0, column=2, padx=(8, 0)
        )

        left = ctk.CTkFrame(self)
        left.grid(row=1, column=0, padx=(20, 10), pady=(0, 20), sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Выберите дату", font=ctk.CTkFont(size=17, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(14, 8), sticky="w"
        )
        self.calendar = Calendar(
            left,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            showweeknumbers=False,
            firstweekday="monday",
        )
        self.calendar.grid(row=1, column=0, padx=10, pady=8, sticky="ew")
        self.calendar.tag_config("personal", background="#D8C8F5", foreground="#252033")
        self.calendar.tag_config("work", background="#BBDCF8", foreground="#15283B")
        self.calendar.tag_config("rest", background="#BFE8CE", foreground="#183324")
        self.calendar.bind("<<CalendarSelected>>", self._on_date_selected)
        ctk.CTkLabel(
            left,
            text="Личное  •  Работа  •  Отдых",
            text_color="gray",
            font=ctk.CTkFont(size=12),
        ).grid(row=2, column=0, padx=12, pady=(4, 12))

        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, padx=(10, 20), pady=(0, 20), sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        self.selected_date_label = ctk.CTkLabel(
            right, text="События", font=ctk.CTkFont(size=18, weight="bold")
        )
        self.selected_date_label.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")
        self.events_frame = ctk.CTkScrollableFrame(right)
        self.events_frame.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.refresh_events()

    @staticmethod
    def _normalize_user(user):
        if isinstance(user, dict):
            return user
        return {
            "id": getattr(user, "id"),
            "username": getattr(user, "username", "Пользователь"),
            "email": getattr(user, "email", ""),
            "role": getattr(user, "role", "member"),
        }

    def refresh_events(self):
        try:
            self.events = get_events_for_user(self.current_user["id"], self.database)
        except Exception as error:
            messagebox.showerror("Ошибка загрузки событий", str(error), parent=self)
            self.events = []
        self._mark_calendar_events()
        self._show_selected_day()

    def _mark_calendar_events(self):
        self.calendar.calevent_remove("all")
        for event in self.events:
            start = datetime.fromisoformat(event["start_time"]).date()
            end = datetime.fromisoformat(event["end_time"]).date()
            current = start
            while current <= end:
                self.calendar.calevent_create(current, event["title"], event["category"])
                current += timedelta(days=1)

    def _on_date_selected(self, _event=None):
        self._show_selected_day()

    def _show_selected_day(self):
        selected_day = self.calendar.selection_get()
        self.selected_date_label.configure(text=f"События на {selected_day.strftime('%d.%m.%Y')}")
        for widget in self.events_frame.winfo_children():
            widget.destroy()
        day_events = []
        for event in self.events:
            start = datetime.fromisoformat(event["start_time"])
            end = datetime.fromisoformat(event["end_time"])
            if start.date() <= selected_day <= end.date():
                day_events.append(event)
        if not day_events:
            ctk.CTkLabel(self.events_frame, text="На эту дату событий нет.", text_color="gray").pack(
                padx=12, pady=18, anchor="w"
            )
            return
        for event in day_events:
            card = ctk.CTkFrame(self.events_frame)
            card.pack(fill="x", padx=4, pady=6)
            start = datetime.fromisoformat(event["start_time"])
            end = datetime.fromisoformat(event["end_time"])
            time_text = f"{start:%d.%m %H:%M} — {end:%d.%m %H:%M}"
            permission = event.get("user_permission", "")
            category = _CATEGORY_LABELS.get(event["category"], event["category"])
            ctk.CTkLabel(card, text=event["title"], font=ctk.CTkFont(size=16, weight="bold")).pack(
                padx=12, pady=(10, 2), anchor="w"
            )
            ctk.CTkLabel(card, text=f"{time_text}  •  {category}", text_color="gray").pack(
                padx=12, pady=2, anchor="w"
            )
            if event["description"]:
                ctk.CTkLabel(card, text=event["description"], wraplength=590, justify="left").pack(
                    padx=12, pady=(4, 2), anchor="w"
                )
            ctk.CTkLabel(card, text=f"Доступ: {permission}", text_color="gray", font=ctk.CTkFont(size=11)).pack(
                padx=12, pady=(2, 10), anchor="w"
            )

    def _open_event_dialog(self):
        CreateEventDialog(self, self.database, self.current_user, self.refresh_events)

    def _open_group_dialog(self):
        CreateGroupDialog(self, self.database, self.current_user, self.refresh_events)
