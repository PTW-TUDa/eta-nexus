from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pandas as pd
from dateutil import tz

from eta_nexus.util import ensure_timezone, round_timestamp

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from eta_nexus.nodes import Node
    from eta_nexus.util.type_annotations import TimeStep


class SubscriptionHandler(ABC):
    """Subscription handlers do stuff to subscribed data points after they are received. Every handler must have a
    push method which can be called when data is received.

    :param write_interval: Interval for writing data to csv file.
    """

    def __init__(self, write_interval: TimeStep = 1) -> None:
        self._write_interval: float = (
            write_interval.total_seconds() if isinstance(write_interval, timedelta) else write_interval
        )
        self._local_tz = tz.tzlocal()
        # Method to round a datetime timestamp by the SubscriptionHandler._write_interval interval in seconds
        #: :py:func:`eta_nexus.util.round_timestamp`
        self._round_timestamp = lambda dt: round_timestamp(dt, self._write_interval)
        #: Method to ensure timezone by assigning local timezone
        #: :py:func:`eta_nexus.util.ensure_timezone`
        self._assert_tz_awareness = ensure_timezone

    def _convert_series(self, value: pd.Series | Sequence[Any], timestamp: pd.DatetimeIndex | TimeStep) -> pd.Series:
        """Helper function to convert a value, timestamp pair in which value is a Series or list to a Series with
        datetime index according to the given timestamp(s).

        :param value: Series of values. There must be corresponding timestamps for each value.
        :param timestamp: DatetimeIndex of the provided values. Alternatively an integer/timedelta can be provided to
                          determine the interval between data points. Use negative numbers to describe past data.
                          Integers are interpreted as seconds. If value is a pd.Series and has a pd.DatetimeIndex,
                          timestamp can be None.
        :return: pandas.Series with corresponding DatetimeIndex.
        """
        # Check timestamp first
        # timestamp as datetime-index:
        if isinstance(timestamp, pd.DatetimeIndex):
            if len(timestamp) != len(value):
                raise ValueError(
                    f"Length of timestamp ({len(timestamp)}) and value ({len(value)}) must match if "
                    f"timestamp is given as pd.DatetimeIndex."
                )
        # timestamp as int or timedelta:
        elif isinstance(timestamp, (int, timedelta)):
            if isinstance(timestamp, int):
                timestamp = timedelta(seconds=timestamp)
            if timestamp < timedelta(seconds=0):
                _freq = str((-timestamp).seconds) + "s"
                timestamp = pd.date_range(end=datetime.now(), freq=_freq, periods=len(value))
            else:
                _freq = str(timestamp.seconds) + "s"
                timestamp = pd.date_range(start=datetime.now(), freq=_freq, periods=len(value))
            timestamp = timestamp.round(_freq)
        # timestamp None:
        elif timestamp is None and isinstance(value, pd.Series):
            if not isinstance(value.index, pd.DatetimeIndex):
                raise TypeError("If timestamp is None, value must have a pd.DatetimeIndex")
            timestamp = value.index
        else:
            raise TypeError(
                f"timestamp must be pd.DatetimeIndex, int or timedelta, is {type(timestamp)}. Else, "
                f"value must have a pd.DatetimeIndex."
            )

        # Check value and build pd.Series
        if isinstance(value, pd.Series):
            value.index = timestamp
        else:
            value = pd.Series(data=value, index=timestamp)
            # If value is multidimensional, an Exception will be raised by pandas.

        # Round index to self._write_interval
        value.index = value.index.round(str(self._write_interval) + "s")

        return value

    @abstractmethod
    def push(self, node: Node, value: Any, timestamp: datetime | None = None) -> None:
        """Receive data from a subscription. This should contain the node that was requested, a value and a timestamp
        when data was received. If the timestamp is not provided, current time will be used.

        :param node: Node object the data belongs to.
        :param value: Value of the data.
        :param timestamp: Timestamp of receiving the data.
        """
