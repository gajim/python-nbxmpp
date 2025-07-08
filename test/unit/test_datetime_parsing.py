import unittest
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from zoneinfo import ZoneInfo

from nbxmpp.modules.date_and_time import create_tzinfo
from nbxmpp.modules.date_and_time import LocalTimezone
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.date_and_time import to_xmpp_dt


class TestDateTime(unittest.TestCase):

    def test_convert_to_utc(self):

        strings = {
            # Valid UTC strings and fractions
            "2017-11-05T01:41:20Z": 1509846080.0,
            "2017-11-05T01:41:20.123Z": 1509846080.123,
            "2017-11-05T01:41:20.123123123+00:00": 1509846080.123123,
            "2017-11-05T01:41:20.123123123123123-00:00": 1509846080.123123,
            # Invalid strings
            "2017-11-05T01:41:20Z+05:00": None,
            "2017-11-05T01:41:20+0000": None,
            "2017-11-05T01:41:20-0000": None,
            # Valid strings with offset
            "2017-11-05T01:41:20-05:00": 1509864080.0,
            "2017-11-05T01:41:20+05:00": 1509828080.0,
            "2017-11-05T01:41:20-00:00": 1509846080.0,
            "2017-11-05T01:41:20+00:00": 1509846080.0,
        }

        strings2 = {
            # Valid strings with offset
            "2017-11-05T07:41:20-05:00": datetime(
                2017, 11, 5, 12, 41, 20, 0, timezone.utc
            ),
            "2017-11-05T07:41:20+05:00": datetime(
                2017, 11, 5, 2, 41, 20, 0, timezone.utc
            ),
            "2017-11-05T01:41:20+00:00": datetime(
                2017, 11, 5, 1, 41, 20, 0, timezone.utc
            ),
            "2017-11-05T01:41:20Z": datetime(2017, 11, 5, 1, 41, 20, 0, timezone.utc),
            "0002-11-05T01:41:20Z": datetime(2, 11, 5, 1, 41, 20, 0, timezone.utc),
            "9998-11-05T01:41:20Z": datetime(9998, 11, 5, 1, 41, 20, 0, timezone.utc),
            "0001-11-05T01:41:20Z": None,
            "9999-11-05T01:41:20Z": None,
        }

        for time_string, expected_value in strings.items():
            result = parse_datetime(time_string, convert="utc", epoch=True)
            self.assertEqual(result, expected_value)

        for time_string, expected_value in strings2.items():
            result = parse_datetime(time_string, convert="utc")
            self.assertEqual(result, expected_value)

    def test_convert_to_local(self):

        strings = {
            # Valid UTC strings and fractions
            "2017-11-05T01:41:20Z": datetime(2017, 11, 5, 1, 41, 20, 0, timezone.utc),
            "2017-11-05T01:41:20.123Z": datetime(
                2017, 11, 5, 1, 41, 20, 123000, timezone.utc
            ),
            "2017-11-05T01:41:20.123123123+00:00": datetime(
                2017, 11, 5, 1, 41, 20, 123123, timezone.utc
            ),
            "2017-11-05T01:41:20.123123123123123-00:00": datetime(
                2017, 11, 5, 1, 41, 20, 123123, timezone.utc
            ),
            # Valid strings with offset
            "2017-11-05T01:41:20-05:00": datetime(
                2017, 11, 5, 1, 41, 20, 0, create_tzinfo(hours=-5)
            ),
            "2017-11-05T01:41:20+05:00": datetime(
                2017, 11, 5, 1, 41, 20, 0, create_tzinfo(hours=5)
            ),
        }

        for time_string, expected_value in strings.items():
            result = parse_datetime(time_string, convert="local")
            self.assertEqual(result, expected_value.astimezone(LocalTimezone()))

    def test_no_convert(self):

        strings = {
            # Valid UTC strings and fractions
            "2017-11-05T01:41:20Z": timedelta(0),
            "2017-11-05T01:41:20.123Z": timedelta(0),
            "2017-11-05T01:41:20.123123123+00:00": timedelta(0),
            "2017-11-05T01:41:20.123123123123123-00:00": timedelta(0),
            # Valid strings with offset
            "2017-11-05T01:41:20-05:00": timedelta(hours=-5),
            "2017-11-05T01:41:20+05:00": timedelta(hours=5),
        }

        for time_string, expected_value in strings.items():
            result = parse_datetime(time_string, convert=None)
            assert result is not None
            self.assertEqual(result.utcoffset(), expected_value)

    def test_check_utc(self):

        strings = {
            # Valid UTC strings and fractions
            "2017-11-05T01:41:20Z": 1509846080.0,
            "2017-11-05T01:41:20.123Z": 1509846080.123,
            "2017-11-05T01:41:20.123123123+00:00": 1509846080.123123,
            "2017-11-05T01:41:20.123123123123123-00:00": 1509846080.123123,
            # Valid strings with offset
            "2017-11-05T01:41:20-05:00": None,
            "2017-11-05T01:41:20+05:00": None,
        }

        for time_string, expected_value in strings.items():
            result = parse_datetime(time_string, check_utc=True, epoch=True)
            self.assertEqual(result, expected_value)

    def test_to_xmpp_dt(self):
        valid_dt = [
            (
                datetime(
                    year=2025,
                    month=1,
                    day=3,
                    hour=20,
                    minute=10,
                    second=10,
                    microsecond=123456,
                    tzinfo=timezone.utc,
                ),
                "2025-01-03T20:10:10.123456Z",
            ),
            (
                datetime(
                    year=2025,
                    month=1,
                    day=3,
                    hour=20,
                    minute=10,
                    second=10,
                    tzinfo=timezone.utc,
                ),
                "2025-01-03T20:10:10Z",
            ),
            (
                datetime(
                    year=2025,
                    month=1,
                    day=3,
                    hour=20,
                    minute=10,
                    second=10,
                    microsecond=123456,
                    tzinfo=timezone(timedelta(seconds=60)),
                ),
                "2025-01-03T20:10:10.123456+00:01",
            ),
            (
                datetime(
                    year=2025,
                    month=1,
                    day=3,
                    hour=20,
                    minute=10,
                    second=10,
                    microsecond=123456,
                    tzinfo=ZoneInfo("Europe/Berlin"),
                ),
                "2025-01-03T20:10:10.123456+01:00",
            ),
        ]

        for dt, res in valid_dt:
            self.assertEqual(to_xmpp_dt(dt), res)

        invalid_dt = [
            datetime(year=2025, month=1, day=3, hour=20, minute=10, second=10),
            datetime(
                year=2025,
                month=1,
                day=3,
                hour=20,
                minute=10,
                second=10,
                microsecond=123456,
                tzinfo=timezone(timedelta(seconds=59)),
            ),
            datetime(
                year=2025,
                month=1,
                day=3,
                hour=20,
                minute=10,
                second=10,
                microsecond=123456,
                tzinfo=timezone(timedelta(microseconds=61)),
            ),
        ]

        for dt in invalid_dt:
            with self.assertRaises(ValueError):
                to_xmpp_dt(dt)


if __name__ == "__main__":
    unittest.main()
