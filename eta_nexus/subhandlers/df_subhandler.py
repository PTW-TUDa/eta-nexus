from __future__ import annotations

import threading
from datetime import datetime
from logging import getLogger
from threading import Lock
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from eta_nexus.nodes import Node
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

    def __init__(self, write_interval: TimeStep = 1, size_limit: int = 100, *, auto_fillna: bool = True) -> None:
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
        with self._data_lock:
            if node.name not in self._data.columns:
                self._data[node.name] = pd.Series(dtype="object")

        def set_value(val: Any, ts: datetime, column: str) -> None:
            with self._data_lock:
                # Replace NaN with -inf to distinguish between the 'real' NaN and the 'fill' NaN
                if pd.isna(val):
                    val = -np.inf
                self._data.loc[ts, column] = val

        # Multiple values
        if not isinstance(value, (str, bytes)) and hasattr(value, "__len__"):
            series = self._convert_series(value, timestamp)
            # Push Series
            # Values are rounded to self.write_interval in _convert_series
            for _timestamp, _value in series.items():
                _timestamp = self._assert_tz_awareness(_timestamp)
                set_value(val=_value, ts=_timestamp, column=node.name)

        # Single value
        else:
            if not isinstance(timestamp, datetime) and timestamp is not None:
                raise ValueError("Timestamp must be a datetime object or None.")
            timestamp = self._round_timestamp(timestamp if timestamp is not None else datetime.now())
            set_value(val=value, ts=timestamp, column=node.name)

        # Housekeeping (Keep internal data short)
        self._housekeeping()

    def get_latest(self) -> pd.DataFrame | None:
        """Return a copy of the dataframe, this ensures they can be worked on freely. Returns None if data is empty."""
        with self._data_lock:
            if len(self._data.index) == 0:
                return None  # If no data in self._data, return None
        return self.data.iloc[[-1]]

    @property
    def data(self) -> pd.DataFrame:
        """This contains the interval dataframe and will return a copy of that."""
        with self._data_lock, pd.option_context("future.no_silent_downcasting", True):  # noqa: FBT003
            if self.auto_fillna:
                self._data = self._data.ffill(inplace=False)
            _data = self._data.replace(-np.inf, np.nan, inplace=False)
        return _data.convert_dtypes()

    def reset(self) -> None:
        """Reset the internal data and restart collection."""
        with self._data_lock:
            self._data = pd.DataFrame()
        log.info(f"Subscribed DataFrame {hash(self._data)} was reset successfully.")

    def _housekeeping(self) -> None:
        """Keep internal data short by only keeping last rows as specified in self.keep_data_rows."""
        with self._data_lock:
            self._data = self._data.drop(index=self._data.index[: -self.keep_data_rows])

    def close(self) -> None:
        """This is just here to satisfy the interface, not needed in this case."""
