"""Всплывающее окно будильника и таймер, который его запускает."""
import sqlite3

import customtkinter as ctk

from alarm_service import AlarmService

SNOOZE_MINUTES = 5
MAX_SHOWN = 5


def _fmt(text):
    # "2026-12-01 18:00" -> "01.12.2026 18:00"
    try:
        year_month_day, clock = text.split(" ")
        year, month, day = year_month_day.split("-")
        return f"{day}.{month}.{year} {clock}"
    except ValueError:
        return text


class AlarmPopup(ctk.CTkToplevel):
    def __init__(self, app, items, on_ack, on_snooze, on_open):
        super().__init__(app)
        self.items = items
        self._on_ack, self._on_snooze, self._on_open = on_ack, on_snooze, on_open
        self._done = False
        self.title("Напоминание")
        self.minsize(460, 220)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._ack)

        ctk.CTkLabel(self, text="Напоминание о задачах", font=ctk.CTkFont(size=22, weight="bold")).pack(
            padx=24, pady=(20, 8), anchor="w"
        )
        for item in items[:MAX_SHOWN]:
            card = ctk.CTkFrame(self)
            card.pack(padx=24, pady=5, fill="x")
            ctk.CTkLabel(card, text=item["title"], font=ctk.CTkFont(size=15, weight="bold"), anchor="w",
                         wraplength=400, justify="left").pack(padx=12, pady=(8, 0), fill="x")
            lines = [f"Событие: {item['event_title']}", f"Дедлайн: {_fmt(item['deadline'])}"]
            if item["missed"]:
                lines.append(f"Пропущено: напоминание было на {_fmt(item['reminder_time'])}")
            ctk.CTkLabel(card, text="\n".join(lines), anchor="w", justify="left", text_color="gray").pack(
                padx=12, pady=(2, 8), fill="x"
            )
        if len(items) > MAX_SHOWN:
            ctk.CTkLabel(self, text=f"и ещё {len(items) - MAX_SHOWN}", text_color="gray").pack(padx=24, anchor="w")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(padx=24, pady=(12, 20), fill="x")
        ctk.CTkButton(buttons, text="Открыть задачи", command=self._open).pack(side="left")
        ctk.CTkButton(buttons, text=f"Через {SNOOZE_MINUTES} мин", fg_color="gray40", hover_color="gray30",
                      command=self._snooze).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Понятно", fg_color="transparent", border_width=1,
                      text_color=("gray20", "gray90"), command=self._ack).pack(side="right")

        self.lift()
        self.bell()

    def _finish(self, action):
        if self._done:
            return
        self._done = True
        action()
        self.destroy()

    def _ack(self):
        self._finish(lambda: self._on_ack(self.items))

    def _snooze(self):
        self._finish(lambda: self._on_snooze(self.items))

    def _open(self):
        self._finish(lambda: self._on_open(self.items))


class AlarmManager:
    """Раз в interval_ms проверяет базу и показывает окно, если пора напомнить."""

    def __init__(self, app, database, user, on_open_tasks, interval_ms=20_000):
        self.app = app
        self.service = AlarmService(database, user)
        self.on_open_tasks = on_open_tasks
        self.interval_ms = interval_ms
        self._job = None
        self._popups = []

    def start(self):
        self.stop()
        self._job = self.app.after(1000, self.tick)

    def stop(self):
        if self._job is not None:
            self.app.after_cancel(self._job)
            self._job = None
        for popup in self._popups:
            try:
                popup.destroy()
            except Exception:
                pass
        self._popups = []

    def tick(self):
        self._job = None
        try:
            items = self.service.poll()
        except sqlite3.Error:
            items = []
        if items:
            self._popups = [p for p in self._popups if p.winfo_exists()]
            self._popups.append(AlarmPopup(self.app, items, self._ack, self._snooze, self._open))
        self._job = self.app.after(self.interval_ms, self.tick)

    def _ack(self, items):
        self.service.acknowledge([i["id"] for i in items])

    def _snooze(self, items):
        self.service.snooze([i["id"] for i in items], SNOOZE_MINUTES)

    def _open(self, items):
        self._ack(items)
        seen = []
        for item in items:
            if item["event_id"] not in seen:
                seen.append(item["event_id"])
        for event_id in seen[:3]:
            self.on_open_tasks(event_id)
