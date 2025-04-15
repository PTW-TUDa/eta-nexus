from __future__ import annotations

from asyncio import sleep as async_sleep
from datetime import datetime
from time import sleep
from typing import TYPE_CHECKING

from eta_nexus.util import ensure_timezone

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any, Final

    import pandas as pd

    from eta_nexus.nodes import Node
    from eta_nexus.util.type_annotations import TimeStep


class RetryWaiter:
    """Helper class which keeps track of waiting time before retrying a connection."""

    VALUES: Final[list[int]] = [0, 1, 3, 5, 5, 10, 20, 30, 40, 60]

    def __init__(self) -> None:
        self.counter = 0

    def tried(self) -> None:
        """Register a retry with the RetryWaiter."""
        self.counter += 1

    def success(self) -> None:
        """Register a successful connection with the RetryWaiter."""
        self.counter = 0

    @property
    def wait_time(self) -> int:
        """Return the time to wait for."""
        if self.counter >= len(self.VALUES) - 1:
            return self.VALUES[-1]
        return self.VALUES[self.counter]

    def wait(self) -> None:
        """Wait/sleep synchronously."""
        sleep(self.wait_time)

    async def wait_async(self) -> None:
        """Wait/sleep asynchronously - must be awaited."""
        await async_sleep(self.wait_time)


class IntervalChecker:
    """Class for the subscription interval checking."""

    def __init__(self) -> None:
        #: Dictionary that stores the value and the time for checking changes and the time interval
        self.node_latest_values: dict[Node, list] = {}

        #: :py:func:`eta_nexus.util.ensure_timezone`
        self._assert_tz_awareness = ensure_timezone

    def push(
        self,
        node: Node,
        value: Any | pd.Series | Sequence[Any],
        timestamp: datetime | pd.DatetimeIndex | TimeStep | None = None,
    ) -> None:
        """Push value and time in dictionary for a node. If the value doesn't change compared to the previous
        timestamp, the push is skipped.

        :param node: Node to check.
        :param value: Value from the subscription.
        :param timestamp: Time of the incoming value of the node.
        """
        if node in self.node_latest_values:
            if value != self.node_latest_values[node][0]:
                self.node_latest_values[node] = [value, timestamp]
        elif node.interval is not None:
            self.node_latest_values[node] = [value, timestamp]

    def check_interval_connection(self) -> bool | None:
        """Check the interval between old and new value. If no interval has been defined, the check interval is skipped.

        :return: Boolean for the interval check.
        """
        # Get the current time to compare the interval
        time = self._assert_tz_awareness(datetime.now())

        if len(self.node_latest_values) > 0:
            for node in self.node_latest_values:
                _time_since_last_check = (
                    (time - self.node_latest_values[node][1]).total_seconds()
                    if node in self.node_latest_values
                    else None
                )
                if node in self.node_latest_values and _time_since_last_check is not None:
                    if _time_since_last_check <= float(node.interval):  # type: ignore[arg-type]
                        _changed_within_interval = True
                    else:
                        _changed_within_interval = False
                        break
                else:
                    _changed_within_interval = True
        else:
            _changed_within_interval = True

        return _changed_within_interval
