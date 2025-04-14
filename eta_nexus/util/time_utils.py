from __future__ import annotations

import math
from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING

from dateutil import tz

if TYPE_CHECKING:
    pass


log = getLogger(__name__)


def ensure_timezone(dt_value: datetime) -> datetime:
    """Helper function to check if datetime has timezone and if not assign local time zone.

    :param dt_value: Datetime object
    :return: datetime object with timezone information"""
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=tz.tzlocal())
    return dt_value


def round_timestamp(dt_value: datetime, interval: float = 1, ensure_tz: bool = True) -> datetime:
    """Helper method for rounding date time objects to specified interval in seconds.
    The method will also add local timezone information is None in datetime and
    if ensure_timezone is True.

    :param dt_value: Datetime object to be rounded
    :param interval: Interval in seconds to be rounded to
    :param ensure_tz: Boolean value to ensure or not timezone info in datetime
    :return: Rounded datetime object
    """
    if ensure_tz:
        dt_value = ensure_timezone(dt_value)
    timezone_store = dt_value.tzinfo

    rounded_timestamp = math.ceil(dt_value.timestamp() / interval) * interval

    return datetime.fromtimestamp(rounded_timestamp, tz=timezone_store)
