# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime as dt
import logging
import re
import time

log = logging.getLogger("nbxmpp.m.date_and_time")

PATTERN_DATETIME = re.compile(
    r"""
    ([0-9]{4}-[0-9]{2}-[0-9]{2})    # Date
    T                               # Separator
    ([0-9]{2}:[0-9]{2}:[0-9]{2})    # Time
    (?P<frac>\.[0-9]{0,6})?         # Fractual Seconds
    [0-9]*                          # lose everything > 6
    (Z|[-+][0-9]{2}:[0-9]{2})       # UTC Offset
    $                               # End of String
""",
    re.VERBOSE,
)

ZERO = dt.timedelta(0)
HOUR = dt.timedelta(hours=1)
SECOND = dt.timedelta(seconds=1)

STDOFFSET = dt.timedelta(seconds=-time.timezone)
if time.daylight:
    dstoffset = dt.timedelta(seconds=-time.altzone)
else:
    dstoffset = STDOFFSET

DSTOFFSET = dstoffset
DSTDIFF = DSTOFFSET - STDOFFSET


class LocalTimezone(dt.tzinfo):
    """
    A class capturing the platform's idea of local time.
    May result in wrong values on historical times in
    timezones where UTC offset and/or the DST rules had
    changed in the past.
    """

    def fromutc(self, dt_input: dt.datetime) -> dt.datetime:
        stamp = (dt_input - dt.datetime(1970, 1, 1, tzinfo=self)) // SECOND
        args = time.localtime(stamp)[:6]
        dst_diff = DSTDIFF // SECOND
        # Detect fold
        fold = args == time.localtime(stamp - dst_diff)
        return dt.datetime(
            *args, microsecond=dt_input.microsecond, tzinfo=self, fold=fold
        )

    def utcoffset(self, dt_input: dt.datetime) -> dt.timedelta:  # type: ignore
        if self._isdst(dt_input):
            return DSTOFFSET
        return STDOFFSET

    def dst(self, dt_input: dt.datetime) -> dt.timedelta:  # type: ignore
        if self._isdst(dt_input):
            return DSTDIFF
        return ZERO

    def tzname(self, _dt_input: dt.datetime) -> str:  # type: ignore
        return "local"

    @staticmethod
    def _isdst(dt_input: dt.datetime) -> bool:
        tt = (
            dt_input.year,
            dt_input.month,
            dt_input.day,
            dt_input.hour,
            dt_input.minute,
            dt_input.second,
            dt_input.weekday(),
            0,
            0,
        )
        stamp = time.mktime(tt)
        tt = time.localtime(stamp)
        return tt.tm_isdst > 0


def create_tzinfo(
    hours: int = 0, minutes: int = 0, tz_string: str | None = None
) -> dt.timezone | None:
    if tz_string is None:
        return dt.timezone(dt.timedelta(hours=hours, minutes=minutes))

    if tz_string.lower() == "z":
        return dt.timezone.utc

    try:
        hours, minutes = map(int, tz_string.split(":"))
    except Exception:
        log.warning("Wrong tz string: %s", tz_string)
        return None

    if hours not in range(-24, 24):
        log.warning("Wrong tz string: %s", tz_string)
        return None

    if minutes not in range(59):
        log.warning("Wrong tz string: %s", tz_string)
        return None

    if hours in (24, -24) and minutes != 0:
        log.warning("Wrong tz string: %s", tz_string)
        return None
    return dt.timezone(dt.timedelta(hours=hours, minutes=minutes))


def parse_datetime(
    timestring: str | None,
    check_utc: bool = False,
    convert: str | None = "utc",
    epoch: bool = False,
) -> dt.datetime | float | None:
    """
    Parse a XEP-0082 DateTime Profile String

    :param timestring: a XEP-0082 DateTime profile formated string

    :param check_utc:  if True, returns None if timestring is not
                       a timestring expressing UTC

    :param convert:    convert the given timestring to utc or local time

    :param epoch:      if True, returns the time in epoch

    Examples:
    '2017-11-05T01:41:20Z'
    '2017-11-05T01:41:20.123Z'
    '2017-11-05T01:41:20.123+05:00'

    return a datetime or epoch
    """
    if timestring is None:
        return None
    if convert not in (None, "utc", "local"):
        raise TypeError('"%s" is not a valid value for convert')

    match = PATTERN_DATETIME.match(timestring)
    if match is None:
        return None

    timestring = "".join(match.groups(""))
    strformat = "%Y-%m-%d%H:%M:%S%z"
    if match.group("frac"):
        # Fractional second addendum to Time
        strformat = "%Y-%m-%d%H:%M:%S.%f%z"

    try:
        date_time = dt.datetime.strptime(timestring, strformat)
    except ValueError:
        return None

    if not 1 < date_time.year < 9999:
        # Raise/Reduce MIN/MAX year so converting to different
        # timezones cannot get out of range
        return None

    if check_utc:
        if convert != "utc":
            raise ValueError('check_utc can only be used with convert="utc"')

        if date_time.tzinfo != dt.timezone.utc:
            return None

        if epoch:
            return date_time.timestamp()
        return date_time

    if convert == "utc":
        date_time = date_time.astimezone(dt.timezone.utc)
        if epoch:
            return date_time.timestamp()
        return date_time

    if epoch:
        # epoch is always UTC, use convert='utc' or check_utc=True
        raise ValueError("epoch not available while converting to local")

    if convert == "local":
        date_time = date_time.astimezone(LocalTimezone())
        return date_time

    # convert=None
    return date_time


def get_local_time() -> tuple[str, str]:
    formated_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    isdst = time.localtime().tm_isdst
    zone = -(time.timezone, time.altzone)[isdst] / 60.0
    zone = (zone / 60, abs(zone % 60))
    tzo = "%+03d:%02d" % zone
    return formated_time, tzo
