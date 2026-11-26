import os
import time
import unittest

from core.timeutil import utc_to_local_text


@unittest.skipUnless(hasattr(time, "tzset"), "time.tzset нет в Windows")
class TimeUtilTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/London"
        time.tzset()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._old
        time.tzset()

    def test_summer_time_is_shifted(self):
        self.assertEqual(utc_to_local_text("2026-07-01 12:00:00"), "01.07.2026 13:00")

    def test_winter_time_is_not_shifted(self):
        self.assertEqual(utc_to_local_text("2026-11-25 12:00:00.123456", "%H:%M"), "12:00")

    def test_garbage_is_returned_as_is(self):
        self.assertEqual(utc_to_local_text("не дата"), "не дата")


if __name__ == "__main__":
    unittest.main()
