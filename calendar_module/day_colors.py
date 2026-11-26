"""Логика раскраски дней календаря. Без tkinter, поэтому легко тестируется."""
from datetime import datetime, timedelta


def _span(event):
    return (
        datetime.fromisoformat(event["start_time"]),
        datetime.fromisoformat(event["end_time"]),
    )


def events_by_day(events):
    """{дата: [события]} для каждого дня, который покрывает событие (включая многодневные)."""
    days = {}
    for event in events:
        start, end = _span(event)
        day = start.date()
        while day <= end.date():
            days.setdefault(day, []).append(event)
            day += timedelta(days=1)
    return days


def dominant_event(day_events):
    """Событие, цвет которого получает ячейка дня.

    Побеждает самое длинное: так многодневный проект не «рвётся» коротким
    событием в середине. При равной длительности выигрывает более раннее,
    затем с меньшим id.
    """
    def sort_key(event):
        start, end = _span(event)
        return (-(end - start).total_seconds(), start, event.get("id", 0))

    return min(day_events, key=sort_key)
