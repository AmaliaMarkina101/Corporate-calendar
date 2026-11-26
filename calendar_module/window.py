from datetime import datetime
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from tkcalendar import Calendar

from .day_colors import dominant_event, events_by_day
from .dialogs import CreateEventDialog, CreateGroupDialog
from .event_service import get_events_for_user


_CATEGORY_LABELS = {
    "personal": "Личное",
    "work": "Работа",
    "rest": "Отдых",
}

# Цвета ячеек календаря (фон, текст). Те же цвета использует легенда.
_CATEGORY_COLORS = {
    "personal": ("#D8C8F5", "#252033"),
    "work": ("#BBDCF8", "#15283B"),
    "rest": ("#BFE8CE", "#183324"),
}


class CalendarWindow(ctk.CTkToplevel):
    def __init__(self, app, database, current_user, on_open_tasks=None, on_open_chat=None):
        """on_open_tasks / on_open_chat: функции, принимающие event_id.

        Если они переданы, в карточке события появляются кнопки «Задачи» и «Чат».
        """
        super().__init__(app)
        self.database = database
        self.on_open_tasks = on_open_tasks
        self.on_open_chat = on_open_chat
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
            locale="ru_RU",
        )
        self.calendar.grid(row=1, column=0, padx=10, pady=8, sticky="ew")
        for category, (background, foreground) in _CATEGORY_COLORS.items():
            self.calendar.tag_config(category, background=background, foreground=foreground)
        self.calendar.bind("<<CalendarSelected>>", self._on_date_selected)
        legend = ctk.CTkFrame(left, fg_color="transparent")
        legend.grid(row=2, column=0, padx=12, pady=(4, 12))
        for category, (background, foreground) in _CATEGORY_COLORS.items():
            ctk.CTkLabel(
                legend,
                text=f"  {_CATEGORY_LABELS[category]}  ",
                fg_color=background,
                text_color=foreground,
                corner_radius=6,
                font=ctk.CTkFont(size=12),
            ).pack(side="left", padx=4)

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
        for day, day_events in events_by_day(self.events).items():
            # Цвет ячейки задаёт одно событие дня: самое длинное. Так многодневное
            # событие не перекрашивается коротким. Остальные события дня создаются
            # без цвета: они видны во всплывающей подсказке и в списке справа.
            winner = dominant_event(day_events)
            for event in day_events:
                if event is not winner:
                    self.calendar.calevent_create(day, event["title"])
            self.calendar.calevent_create(day, winner["title"], winner["category"])

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
                padx=12, pady=(2, 6 if (self.on_open_tasks or self.on_open_chat) else 10), anchor="w"
            )
            if self.on_open_tasks or self.on_open_chat:
                buttons = ctk.CTkFrame(card, fg_color="transparent")
                buttons.pack(padx=12, pady=(0, 10), anchor="w")
                if self.on_open_tasks:
                    ctk.CTkButton(
                        buttons, text="Задачи события", width=130,
                        command=lambda event_id=event["id"]: self.on_open_tasks(event_id),
                    ).pack(side="left", padx=(0, 8))
                if self.on_open_chat:
                    ctk.CTkButton(
                        buttons, text="Чат события", width=130,
                        command=lambda event_id=event["id"]: self.on_open_chat(event_id),
                    ).pack(side="left")

    def _open_event_dialog(self):
        CreateEventDialog(self, self.database, self.current_user, self.refresh_events)

    def _open_group_dialog(self):
        CreateGroupDialog(self, self.database, self.current_user, self.refresh_events)
