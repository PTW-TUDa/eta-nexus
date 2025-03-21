"""
This module provides a read-only REST API connector to the forecast.solar API.

You can obtain an estimate of solar production for a specific location, defined by latitude and longitude,
and a specific plane orientation, defined by declination and azimuth, based on the installed module power.

Supported endpoints include: "Estimate", "Historic", and "Clearsky":

**Estimate Solar Production**
The `estimate` endpoint provides the forecast for today and the upcoming days, depending on the account model.

**Historic Solar Production**
The `historic` endpoint calculates the average solar production for a given day based on historical weather data,
excluding current weather conditions.

**Clear Sky Solar Production**
The `clearsky` endpoint calculates the theoretically possible solar production assuming no cloud cover.

For more information, visit the `forecast.solar API documentation <https://doc.forecast.solar/start>`_.

"""

from __future__ import annotations

import concurrent.futures
import traceback
from collections.abc import Mapping
from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import requests
from requests_cache import DO_NOT_CACHE, CachedSession

from eta_connect.connectors.node import NodeForecastSolar
from eta_connect.timeseries import df_interpolate
from eta_connect.util import round_timestamp

from .base_classes import SeriesConnection, SubscriptionHandler

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, Callable, ClassVar

    from typing_extensions import Self

    from eta_connect.type_hints import Nodes, TimeStep


log = getLogger(__name__)


class ForecastSolarConnection(SeriesConnection[NodeForecastSolar], protocol="forecast_solar"):
    """
    ForecastSolarConnection is a class to download and upload multiple features from and to the Forecast.Solar database
    as timeseries.

    :param url: URL of the server with scheme (https://).
    :param usr: Not needed for Forecast.Solar.
    :param pwd: Not needed for Forecast.Solar.
    :param api_key: Token for API authentication.
    :param nodes: Nodes to select in connection.
    """

    _baseurl: ClassVar[str] = "https://api.forecast.solar"
    _time_format: ClassVar[str] = "%Y-%m-%dT%H:%M:%SZ"
    _headers: ClassVar[dict[str, str]] = {"Content-Type": "application/json"}

    def __init__(
        self,
        url: str = _baseurl,
        *,
        api_key: str = "None",
        url_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        nodes: Nodes[NodeForecastSolar] | None = None,
    ) -> None:
        super().__init__(url, None, None, nodes=nodes)

        #: Url parameters for the forecast.Solar api
        self.url_params: dict[str, Any] | None = url_params
        #: Query parameters for the forecast.Solar api
        self.query_params: dict[str, Any] | None = query_params
        #: Key to use the Forecast.Solar api. If API key is none, only the public functions are usable.
        self._api_key: str = api_key
        #: Cached session to handle the requests
        self._session: CachedSession = CachedSession(
            cache_name="eta_connect/connectors/requests_cache/forecast_solar_cache",
            urls_expire_after={
                "https://api.forecast.solar*": 900,  # 15 minutes
                "*": DO_NOT_CACHE,  # Don't cache other URLs
            },
            allowable_codes=(200, 400, 401, 403),
            use_cache_dir=True,
        )

    @classmethod
    def _from_node(cls, node: NodeForecastSolar, **kwargs: Any) -> ForecastSolarConnection:
        """Initialize the connection object from a Forecast.Solar protocol node object

        :param node: Node to initialize from.
        :param kwargs: Keyword arguments for API authentication, where "api_key" is required
        :return: ForecastSolarConnection object.
        """
        api_key = kwargs.get("api_key", "None")

        return super()._from_node(node, api_key=api_key)

    def _read_node(self, node: NodeForecastSolar, **kwargs: Any) -> pd.DataFrame:
        """Download data from the Forecast.Solar Database.

        :param node: Node to read values from.
        :return: pandas.DataFrame containing the data read from the connection.
        """
        url, query_params = node.url, node._query_params
        query_params["time"] = "utc"

        raw_response = self._raw_request("GET", url, params=query_params, headers=self._headers, **kwargs)
        response = raw_response.json()

        timestamps = pd.to_datetime(list(response["result"].keys()))
        watts = response["result"].values()

        data = pd.DataFrame(
            data=watts,
            index=timestamps.tz_convert(self._local_tz),
            dtype="float64",
        )
        data.index.name = "Time (with timezone)"
        data.columns = [node.name]

        return data

    def _select_data(
        self, results: pd.DataFrame, from_time: pd.Timestamp | None = None, to_time: pd.Timestamp | None = None
    ) -> tuple[pd.DataFrame, pd.Timestamp]:
        """Forecast.solar api returns the data for the whole day. Select data only for the time interval.

        :param nodes: pandas.DataFrame containing the raw data read from the connection.
        :param from_time: Starting time to begin reading (included in output).
        :param to_time: Time to stop reading at (included in output).
        :return: pandas.DataFrame containing the selected data read from the connection and the current timestamp.
        """
        now = pd.Timestamp.now().tz_localize(self._local_tz)

        previous_time = from_time if isinstance(from_time, pd.Timestamp) else now
        next_time = to_time if isinstance(to_time, pd.Timestamp) else previous_time
        previous_time = previous_time.floor("15min")
        next_time = next_time.ceil("15min")

        if previous_time not in results:
            results.loc[previous_time] = 0

        if next_time not in results:
            results.loc[next_time] = 0

        results = results.sort_index()

        return results.loc[previous_time:next_time], now

    def _process_watts(self, values: pd.DataFrame, nodes: set[NodeForecastSolar]) -> pd.DataFrame:
        """Process the watt values from the Forecast.Solar API.

        :param values: DataFrame containing the raw data read from the connection.
        :param nodes: List of nodes to read values from.
        :return: DataFrame containing the processed data read from the connection.
        """
        # Determine the data type to use, defaulting to "watts" if inconsistent
        if not nodes:
            raise ValueError("The set of nodes is empty")

        values.attrs["name"] = "watts"
        iterator = iter(nodes)
        first_node = next(iterator)
        data = first_node.data

        if any(node.data != data for node in iterator):
            data = "watts"
            log.warning("Multiple data types specified. Falling back to default data type: watts")

        # Define the actions for each data type
        actions: dict[str, Callable] = {
            "watts": lambda v: v,
            "watthours/period": self.calculate_watt_hours_period,
            "watthours": lambda v: self.cumulative_watt_hours_per_day(v, from_unit="watts"),
            "watthours/day": lambda v: self.summarize_watt_hours_per_day(v, from_unit="watts"),
        }

        return actions[data](values)

    def _get_data(
        self,
        nodes: set[NodeForecastSolar],
        from_time: pd.Timestamp | None = None,
        to_time: pd.Timestamp | None = None,
    ) -> tuple[pd.DataFrame, pd.Timestamp]:
        """Return forecast data from the Forecast.Solar Database.

        :param nodes: List of nodes to read values from.
        :return: pandas.DataFrame containing the data read from the connection.
        """
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = executor.map(self._read_node, nodes)

        # Filter out empty or all-NA DataFrames
        filtered_results = [df for df in results if not df.empty and not df.isna().all().all()]

        # Concatenate the filtered DataFrames
        values = pd.concat(filtered_results, axis=1, sort=False)
        return self._select_data(values, from_time, to_time)

    def read(self, nodes: NodeForecastSolar | Nodes[NodeForecastSolar] | None = None) -> pd.DataFrame:
        """Return solar forecast for the current time

        :param nodes: Single node or list/set of nodes to read values from.
        :return: Pandas DataFrame containing the data read from the connection.
        """
        nodes = self._validate_nodes(nodes)
        values, now = self._get_data(nodes)

        # Insert the current timestamp _now and sort the index column to finish with the linear interpolation method
        values.loc[now] = np.nan
        values = values.sort_index()
        values = values.interpolate(method="linear").loc[[now]]

        return self._process_watts(values, nodes)

    def write(self, values: Mapping[NodeForecastSolar, Any]) -> None:
        """
        .. warning::
            Cannot read single values from the Forecast.Solar API. Use read_series instead

        :raises NotImplementedError:
        """
        raise NotImplementedError("Write is not implemented for Forecast.Solar.")

    def subscribe(
        self,
        handler: SubscriptionHandler,
        nodes: NodeForecastSolar | Nodes[NodeForecastSolar] | None = None,
        interval: TimeStep = 1,
    ) -> None:
        """
        .. warning::
            Cannot read single values from the Forecast.Solar API. Use read_series instead

        :raises NotImplementedError:
        """
        raise NotImplementedError("Subscribe is not implemented for Forecast.Solar.")

    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: NodeForecastSolar | Nodes[NodeForecastSolar] | None = None,
        interval: TimeStep = 1,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Return a time series of forecast data from the Forecast.Solar Database.

        :param nodes: Single node or list/set of nodes to read values from.
        :param from_time: Starting time to begin reading (included in output).
        :param to_time: Time to stop reading at (not included in output).
        :param interval: Interval between time steps. It is interpreted as seconds if given as integer.
        :param kwargs: Other parameters (ignored by this connector).
        :return: Pandas DataFrame containing the data read from the connection.
        """
        _interval = interval if isinstance(interval, timedelta) else timedelta(seconds=interval)

        from_time = pd.Timestamp(round_timestamp(from_time, _interval.total_seconds())).tz_convert(self._local_tz)
        to_time = pd.Timestamp(round_timestamp(to_time, _interval.total_seconds())).tz_convert(self._local_tz)

        nodes = self._validate_nodes(nodes)
        values, _ = self._get_data(nodes, from_time, to_time)
        values = df_interpolate(values, _interval).loc[from_time:to_time]  # type: ignore # mypy doesn't recognize DatetimeIndex
        return self._process_watts(values, nodes)

    def subscribe_series(
        self,
        handler: SubscriptionHandler,
        req_interval: TimeStep,
        offset: TimeStep | None = None,
        nodes: NodeForecastSolar | Nodes[NodeForecastSolar] | None = None,
        interval: TimeStep = 1,
        data_interval: TimeStep = 1,
        **kwargs: Any,
    ) -> None:
        """
        .. warning::
            Cannot read single values from the Forecast.Solar  API. Use read_series instead

        :raises NotImplementedError:
        """
        raise NotImplementedError("Subscribe series is not implemented for Forecast.Solar.")

    def close_sub(self) -> None:
        """
        .. warning::
            Cannot read single values from the Forecast.Solar  API. Use read_series instead

        :raises NotImplementedError:
        """
        raise NotImplementedError("Close subscription is not implemented for Forecast.Solar.")

    async def _subscription_loop(
        self,
        handler: SubscriptionHandler,
        interval: TimeStep,
        req_interval: TimeStep,
        offset: TimeStep,
        data_interval: TimeStep,
    ) -> None:
        """
        .. warning::
            Cannot read single values from the Forecast.Solar  API. Use read_series instead

        :raises NotImplementedError:
        """
        raise NotImplementedError("Subscription loop is not implemented for Forecast.Solar.")

    def timestr_from_datetime(self, dt: datetime) -> str:
        """Create an Forecast.Solar compatible time string.

        :param dt: Datetime object to convert to string.
        :return: Forecast.Solar compatible time string.
        """

        return dt.isoformat(sep="T", timespec="seconds").replace(":", "%3A").replace("+", "%2B")

    def _raw_request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Perform Forecast.Solar request and handle possibly resulting errors.

        :param method: HTTP request method.
        :param endpoint: Endpoint for the request (server URI is added automatically).
        :param kwargs: Additional arguments for the request.
        """
        if self._api_key != "None":
            log.info("The api_key is None and only the public functions are available of the forecastsolar.api.")

        kwargs.setdefault("timeout", 10)
        response = self._session.request(method, url, **kwargs)
        # Check for request errors
        response.raise_for_status()

        return response

    @classmethod
    def route_valid(cls, nodes: Nodes, **kwargs: Any) -> bool:
        """Check if node routes make up a valid route, by using the Forecast.Solar API's check endpoint.

        :param nodes: List of nodes to check.
        :return: Boolean if the nodes are on the same route.
        """
        conn = ForecastSolarConnection()
        nodes = conn._validate_nodes(nodes)

        def _build_url(node: NodeForecastSolar) -> list[str]:
            """Build the URL for a node's route validation."""
            base_url = f"https://api.forecast.solar/check/{node.latitude}/{node.longitude}"
            if isinstance(node.declination, list):
                return [f"{base_url}/{d}/{a}/{k}" for d, a, k in zip(node.declination, node.azimuth, node.kwp)]  # type: ignore [arg-type]
            return [f"{base_url}/{node.declination}/{node.azimuth}/{node.kwp}"]

        def validate_node_routes(node: NodeForecastSolar) -> bool:
            """Validate all routes for a node."""
            urls = _build_url(node)
            for url in urls:
                try:
                    conn._raw_request("GET", url, headers=conn._headers, **kwargs)
                except requests.exceptions.HTTPError as e:
                    log.error(f"Route of node: {node.name} could not be verified: {e}")
                    return False
            return True

        # Validate each node's routes
        return all(validate_node_routes(node) for node in nodes)

    @staticmethod
    def calculate_watt_hours_period(watt_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates watt hours for each period based on the average watts between consecutive rows.

        :param df: DataFrame with indices representing time intervals and columns representing node's watt estimates
        :return: DataFrame with the watt-hour-period estimates for each interval
        """
        # Calculate the time difference in hours between consecutive indices
        time_diff_hours = watt_df.index.to_series().diff().dt.total_seconds().div(3600).fillna(0)

        # Calculate the mean power output between consecutive rows for all columns
        mean_watts = watt_df.add(watt_df.shift(1)).div(2)

        # Calculate watt-hours for the period using the mean power and the time difference
        watt_hours_df = mean_watts.multiply(time_diff_hours, axis=0)
        watt_hours_df.attrs["name"] = "watthours/period"

        return watt_hours_df.fillna(0).round(3)  # Replace NaN values (the first row will have NaN) with 0

    @staticmethod
    def cumulative_watt_hours_per_day(watt_hours_df: pd.DataFrame, from_unit: str = "watthours/period") -> pd.DataFrame:
        """
        Calculates the cumulative watt-hours throughout each day for each panel.

        :param watt_hours_df: df with indices representing time intervals and columns containing watt-hour estimates.
        :param from_unit: Unit of the input DataFrame. Default is "watthours/period".
        :return: DataFrame with cumulative watt-hours per day for each panel, rounded to three decimal places.
        """
        if from_unit == "watts":
            watt_hours_df = ForecastSolarConnection.calculate_watt_hours_period(watt_hours_df)
        elif from_unit != "watthours/period":
            raise ValueError(f"Invalid unit: {from_unit}")

        # Group by date and calculate cumulative sum within each group
        cumulative_watt_hours_df = watt_hours_df.groupby(watt_hours_df.index.date).cumsum()

        # Reset the index to original DateTimeIndex
        cumulative_watt_hours_df.index = watt_hours_df.index
        cumulative_watt_hours_df.attrs["name"] = "watthours"

        return cumulative_watt_hours_df.round(3)

    @staticmethod
    def summarize_watt_hours_per_day(watt_hours_df: pd.DataFrame, from_unit: str = "watthours/period") -> pd.DataFrame:
        """
        Sums the watt-hours over each day for each panel.

        :param watt_hours_df: df with indices representing time intervals and columns containing watt-hour estimates.
        :param from_unit: Unit of the input DataFrame. Default is "watthours/period".
        :return: DataFrame with total watt-hours per day for each panel, rounded to three decimal places.
        """
        if from_unit == "watts":
            watt_hours_df = ForecastSolarConnection.calculate_watt_hours_period(watt_hours_df)
        elif from_unit != "watthours/period":
            raise ValueError(f"Invalid unit: {from_unit}")

        # Resample the data to daily frequency, summing the watt-hours
        daily_watt_hours_df = watt_hours_df.resample("D").sum()
        daily_watt_hours_df.attrs["name"] = "watthours/day"

        return daily_watt_hours_df.round(3)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc_type is not None:
            traceback.print_exception(exc_type, exc_value, tb)
            return False
        try:
            self._session.close()
        except Exception as e:
            log.error(f"Error closing the connection: {e}")
        return True

    def __del__(self) -> None:
        try:
            self._session.close()
        finally:
            pass
