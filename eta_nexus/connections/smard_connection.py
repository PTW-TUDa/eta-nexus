from __future__ import annotations

from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from requests_cache import CachedSession

from eta_nexus.connections.connection import RESTConnection, SeriesReadable, StatusReadable
from eta_nexus.nodes import SmardNode

if TYPE_CHECKING:
    from typing import Any

    from pandas._typing import ArrayLike

    from eta_nexus.util.type_annotations import Nodes, TimeStep


class SmardConnection(
    RESTConnection[SmardNode],
    StatusReadable[SmardNode],
    SeriesReadable[SmardNode],
    protocol="smard",
):
    """Connection to SMARD (Bundesnetzagentur Strommarktdaten) API.

    Provides access to German electricity market data including power generation by source,
    consumption, market prices, and generation forecasts. No authentication required.

    :param url: Base URL (default: https://smard.api.proxy.bund.dev/app)
    :param nodes: Nodes to select in connection

    For detailed documentation including available filters, regions, time resolutions, and usage examples,
    see :ref:`smard_connection`.
    """

    logger = getLogger(__name__)

    def __init__(
        self,
        url: str = "https://smard.api.proxy.bund.dev/app",
        *,
        nodes: Nodes[SmardNode] | None = None,
    ) -> None:
        # No authentication needed for SMARD API
        super().__init__(url, None, None, nodes=nodes)

    def _initialize_session(self) -> CachedSession:
        """Initialize the cached request session.

        SMARD data is relatively static (historical data doesn't change),
        so we use aggressive caching.
        """
        self._cached_session = CachedSession(
            cache_name="eta_nexus/connections/requests_cache/smard_cache",
            expire_after=timedelta(hours=1),  # Cache for 1 hour
            allowable_codes=(200, 400, 404),
            use_cache_dir=True,
        )

        self._cached_session.headers.update(
            {
                "accept": "application/json",
            }
        )

        return self._cached_session

    @property
    def authentication(self) -> None:
        """No authentication required for SMARD API."""
        return None

    @classmethod
    def _from_node(
        cls,
        node: SmardNode,
        **kwargs: Any,
    ) -> SmardConnection:
        """Initialize connection from a node.

        :param node: SmardNode to initialize from
        :return: SmardConnection instance
        """
        return super()._from_node(node)

    def read(self, nodes: SmardNode | Nodes[SmardNode] | None = None) -> pd.DataFrame:
        """Read the latest available values from SMARD.

        Fetches the most recent data chunk for each node and returns the last
        available data point. Note that SMARD data has publication delay, so
        the "latest" value may be hours or days old depending on data type.

        :param nodes: Single node or list/set of nodes to read values from.
        :return: pandas.DataFrame containing the latest available values.
        """
        nodes = self._validate_nodes(nodes)
        results: list[pd.DataFrame] = []

        for node in nodes:
            # Get available chunk timestamps from index
            available_timestamps = self._get_available_timestamps(node)

            if not available_timestamps:
                self.logger.warning(f"[SMARD] No available data for {node.name}")
                continue

            # Get the most recent chunk (last timestamp in index)
            latest_chunk_ts = max(available_timestamps)

            # Build URL for the latest chunk
            request_url = (
                f"{self.url}/chart_data/{node.filter}/{node.region}/"
                f"{node.filter}_{node.region}_{node.resolution}_{latest_chunk_ts}.json"
            )

            # Fetch the chunk data
            chunk_data = super()._read_node(node, request_url)

            if not chunk_data.empty:
                # Return only the last row (most recent data point)
                results.append(chunk_data.iloc[[-1]])

        if not results:
            self.logger.warning("[SMARD] No data retrieved from any node")
            return pd.DataFrame(columns=[n.name for n in nodes])

        return pd.concat(results, axis=1)

    def _parse_response(self, json_data: dict[Any, Any]) -> tuple[pd.DatetimeIndex, ArrayLike]:
        """Parse SMARD API response into (timestamps, values).

        SMARD returns data as:
        {
          "series": [
            [timestamp_ms, value],
            [timestamp_ms, value],
            ...
          ]
        }

        :param json_data: JSON data from API
        :return: (DatetimeIndex, values) tuple
        """
        series = json_data.get("series", [])

        if not series:
            self.logger.warning("[SMARD] Empty series in response")
            return pd.DatetimeIndex([]), []

        # Split [timestamp, value] pairs
        timestamps_ms = [item[0] for item in series if item[0] is not None]
        values = [item[1] if item[1] is not None else np.nan for item in series]

        # Convert millisecond timestamps to datetime
        timestamps = pd.to_datetime(timestamps_ms, unit="ms", utc=True)

        return timestamps, values

    def _get_available_timestamps(
        self,
        node: SmardNode,
    ) -> list[int]:
        """Get available timestamps for a node from the index endpoint.

        :param node: Node to get timestamps for
        :return: List of available Unix timestamps (milliseconds)
        """
        # Build index URL
        index_url = f"{self.url}/chart_data/{node.filter}/{node.region}/index_{node.resolution}.json"

        response = self._raw_request("GET", index_url)
        if response is None:
            self.logger.warning(f"[SMARD] No response from index endpoint for {node.name}")
            return []

        try:
            data = response.json()
            timestamps = data.get("timestamps", [])
            return [ts for ts in timestamps if ts is not None]
        except (ValueError, KeyError):
            self.logger.exception("[SMARD] Failed to parse index response")
            return []

    def _datetime_to_timestamp_ms(self, dt: datetime) -> int:
        """Convert datetime to Unix timestamp in milliseconds.

        :param dt: Datetime to convert
        :return: Unix timestamp in milliseconds
        """
        return int(dt.timestamp() * 1000)

    def _find_closest_timestamp(
        self,
        target_ms: int,
        available_timestamps: list[int],
        direction: str = "before",
    ) -> int | None:
        """Find closest available timestamp to target.

        :param target_ms: Target timestamp in milliseconds
        :param available_timestamps: List of available timestamps
        :param direction: 'before' (<=) or 'after' (>=)
        :return: Closest timestamp or None
        """
        if not available_timestamps:
            return None

        if direction == "before":
            # Find largest timestamp <= target
            valid = [ts for ts in available_timestamps if ts <= target_ms]
            return max(valid) if valid else None
        # Find smallest timestamp >= target
        valid = [ts for ts in available_timestamps if ts >= target_ms]
        return min(valid) if valid else None

    def read_node(
        self,
        node: SmardNode,
        from_time: datetime,
        to_time: datetime,
        interval: timedelta,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Read data for a single SMARD node.

        Due to SMARD API design, we need to:
        1. Get available timestamps from index endpoint
        2. Find appropriate starting timestamp for our time range
        3. Request time series data from that timestamp

        :param node: Node to read from
        :param from_time: Start of the time series (timezone-aware).
        :param to_time: End of the time series (timezone-aware).
        :param interval: Time interval for resampling (currently unused, data returned at native resolution).
        :param kwargs: Additional arguments (currently unused).
        :return: DataFrame with node data
        """

        # Get available timestamps
        available_timestamps = self._get_available_timestamps(node)

        if not available_timestamps:
            self.logger.warning(f"[SMARD] No available timestamps for {node.name}")
            return pd.DataFrame(columns=[node.name], index=pd.DatetimeIndex([], name="Time (with timezone)"))

        # Find appropriate start timestamp
        from_time_ms = self._datetime_to_timestamp_ms(from_time)
        start_timestamp = self._find_closest_timestamp(from_time_ms, available_timestamps, direction="before")

        if start_timestamp is None:
            self.logger.warning(f"[SMARD] No data available before {from_time} for {node.name}")
            return pd.DataFrame(columns=[node.name], index=pd.DatetimeIndex([], name="Time (with timezone)"))

        # Build time series URL (note the duplicate parameters - API design quirk)
        request_url = (
            f"{self.url}/chart_data/{node.filter}/{node.region}/"
            f"{node.filter}_{node.region}_{node.resolution}_{start_timestamp}.json"
        )

        # Delegate to base class for actual request and DataFrame creation
        result = super()._read_node(node, request_url)

        # Filter to requested time range
        if not result.empty:
            result = result.loc[from_time:to_time]  # type: ignore[misc]

        return result

    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: SmardNode | Nodes[SmardNode] | None = None,
        interval: TimeStep = 60,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Read time series data for multiple SMARD nodes."""
        return self._get_data(from_time, to_time, nodes, interval, **kwargs)
