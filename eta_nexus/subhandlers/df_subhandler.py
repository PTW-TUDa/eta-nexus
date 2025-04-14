from __future__ import annotations

import threading
from datetime import datetime
from logging import getLogger
from threading import Lock
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from eta_nexus.nodes import Node

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from eta_nexus.util.type_annotations import TimeStep

from eta_nexus.subhandlers.subhandler import SubscriptionHandler

log = getLogger(__name__)


class DFSubHandler(SubscriptionHandler):
    """Subscription handler for returning pandas.DataFrames when requested.

    :param write_interval: Interval between index values in the data frame (value to which time is rounded).
    :param size_limit: Number of rows to keep in memory.
    :param auto_fillna: If True, missing values in self._data are filled with the pandas-method
                        df.ffill() each time self.data is called.
    """

    def __init__(self, write_interval: TimeStep = 1, size_limit: int = 100, auto_fillna: bool = True) -> None:
        super().__init__(write_interval=write_interval)
        self._data: pd.DataFrame = pd.DataFrame()
        self._data_lock: threading.Lock = Lock()
        self.keep_data_rows: int = size_limit
        self.auto_fillna: bool = auto_fillna

    def push(
        self,
        node: Node,
        value: Any | pd.Series | Sequence[Any],
        timestamp: datetime | pd.DatetimeIndex | TimeStep | None = None,
    ) -> None:
        """Append values to the dataframe.

        :param node: Node object the data belongs to.
        :param value: Value of the data or Series of values. There must be corresponding timestamps for each value.
        :param timestamp: Timestamp of receiving the data or DatetimeIndex if pushing multiple values. Alternatively
                          an integer/timedelta can be provided to determine the interval between data points. Use
                          negative numbers to describe past data. Integers are interpreted as seconds. If value is a
                          pd.Series and has a pd.DatetimeIndex, timestamp is ignored.
        """
        # Check if node.name is in _data.columns
        self._data_lock.acquire()
        if node.name not in self._data.columns:
            self._data[node.name] = np.nan
        self._data_lock.release()

        # Multiple values
        if not isinstance(value, str) and hasattr(value, "__len__"):
            value = self._convert_series(value, timestamp)
            # Push Series
            # Values are rounded to self.write_interval in _convert_series
            for _timestamp, _value in value.items():
                _timestamp = self._assert_tz_awareness(_timestamp)
                self._data_lock.acquire()

                # Replace NaN with -inf to distinguish between the 'real' NaN and the 'fill' NaN
                if pd.isna(_value):
                    _value = -np.inf
                self._data.loc[_timestamp, node.name] = _value
                self._data_lock.release()

        # Single value
        else:
            if not isinstance(timestamp, datetime) and timestamp is not None:
                raise ValueError("Timestamp must be a datetime object or None.")
            timestamp = self._round_timestamp(timestamp if timestamp is not None else datetime.now())
            self._data_lock.acquire()

            # Replace NaN with -inf to distinguish between the 'real' NaN and the 'fill' NaN
            if pd.isna(value):
                value = -np.inf
            self._data.loc[timestamp, node.name] = value
            self._data_lock.release()

        # Housekeeping (Keep internal data short)
        self._housekeeping()

    def get_latest(self) -> pd.DataFrame | None:
        """Return a copy of the dataframe, this ensures they can be worked on freely. Returns None if data is empty."""
        self._data_lock.acquire()
        if len(self._data.index) == 0:
            self._data_lock.release()
            return None  # If no data in self._data, return None
        self._data_lock.release()
        return self.data.iloc[[-1]]

    @property
    def data(self) -> pd.DataFrame:
        """This contains the interval dataframe and will return a copy of that."""
        self._data_lock.acquire()
        if self.auto_fillna:
            self._data = self._data.ffill()
        data = self._data.replace(-np.inf, np.nan, inplace=False)
        self._data_lock.release()
        return data

    def reset(self) -> None:
        """Reset the internal data and restart collection."""
        self._data_lock.acquire()
        self._data = pd.DataFrame()
        self._data_lock.release()
        log.info(f"Subscribed DataFrame {hash(self._data)} was reset successfully.")

    def _housekeeping(self) -> None:
        """Keep internal data short by only keeping last rows as specified in self.keep_data_rows."""
        self._data_lock.acquire()
        self._data = self._data.drop(index=self._data.index[: -self.keep_data_rows])
        self._data_lock.release()

    def close(self) -> None:
        """This is just here to satisfy the interface, not needed in this case."""
        pass
