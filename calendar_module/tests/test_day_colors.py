import unittest
from datetime import date

from calendar_module.day_colors import dominant_event, events_by_day


def ev(event_id, start, end, category="work"):
    return {"id": event_id, "start_time": start, "end_time": end, "category": category}


class DayColorsTests(unittest.TestCase):
    def test_multi_day_event_covers_every_day(self):
        days = events_by_day([ev(1, "2026-11-17 12:00", "2026-11-19 16:00")])
        self.assertEqual(sorted(days), [date(2026, 11, 17), date(2026, 11, 18), date(2026, 11, 19)])

    def test_long_event_wins_over_short_one_in_the_middle(self):
        long_event = ev(1, "2026-11-17 12:00", "2026-11-19 16:00", "personal")
        short_event = ev(2, "2026-11-18 09:00", "2026-11-18 10:00", "rest")
        days = events_by_day([long_event, short_event])
        self.assertEqual(dominant_event(days[date(2026, 11, 18)])["id"], 1)

    def test_short_event_keeps_its_own_color_on_its_own_day(self):
        short_event = ev(2, "2026-11-20 09:00", "2026-11-20 10:00", "rest")
        days = events_by_day([ev(1, "2026-11-17 12:00", "2026-11-19 16:00"), short_event])
        self.assertEqual(dominant_event(days[date(2026, 11, 20)])["id"], 2)

    def test_tie_goes_to_earlier_then_lower_id(self):
        a = ev(5, "2026-11-18 11:00", "2026-11-18 12:00")
        b = ev(3, "2026-11-18 09:00", "2026-11-18 10:00")
        c = ev(2, "2026-11-18 09:00", "2026-11-18 10:00")
        self.assertEqual(dominant_event([a, b, c])["id"], 2)


if __name__ == "__main__":
    unittest.main()
