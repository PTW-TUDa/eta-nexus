from __future__ import annotations

from abc import ABC, abstractmethod
from logging import getLogger
from typing import TYPE_CHECKING, Generic, TypeVar

import pandas as pd
from wetterdienst import Settings
from wetterdienst.provider.dwd.mosmix.api import DwdMosmixRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from wetterdienst.core.timeseries.result import StationsResult

    from eta_connect.type_hints import Nodes, TimeStep

from datetime import datetime, timedelta

from eta_connect.connectors.node import (
    NodeWetterdienst,
    NodeWetterdienstObservation,
    NodeWetterdienstPrediction,
)

from .base_classes import SeriesConnection, SubscriptionHandler

log = getLogger(__name__)

NW = TypeVar("NW", bound=NodeWetterdienst)


class WetterdienstConnection(Generic[NW], SeriesConnection[NW], ABC):
    """
    The WetterdienstConnection class is a connector to the Wetterdienst API for retrieving weather data.
    This class is an abstract base class and should not be used directly. Instead, use the subclasses
    :class:`WetterdienstObservationConnection` and :class:`WetterdienstPredictionConnection`.

    :param url: The base URL of the Wetterdienst API
    :param nodes: Nodes to select in connection
    :param settings: Wetterdienst settings object
    """

    def __init__(
        self,
        *,
        nodes: Nodes[NW] | None = None,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        self.settings = Settings(settings=settings)
        self.settings.ts_skip_empty = True
        self.settings.ts_si_units = False
        self.settings.ts_humanize = True
        super().__init__("https://opendata.dwd.de/", nodes=nodes)  # dummy url

    @classmethod
    def _from_node(cls, node: NW, **kwargs: Any) -> WetterdienstConnection:
        """Initialize the connection object from an wetterdienst protocol node object

        :param node: Node to initialize from
        :param kwargs: Extra keyword arguments
        """
        settings = kwargs.get("settings")
        return super()._from_node(node, settings=settings)

    @abstractmethod
    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: NW | Nodes[NW] | None = None,
        interval: TimeStep = 60,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Abstract base method for read_series(). Is fully implemented in
        :func:`~wetterdienst.WetterdienstObservationConnection.read_series` and
        :func:`~wetterdienst.WetterdienstPredictionConnection.read_series`.

        :param nodes: Single node or list/set of nodes to read values from.
        :param from_time: Starting time to begin reading (included in output).
        :param to_time: Time to stop reading at (not included in output).
        :param interval: interval between time steps. It is interpreted as seconds if given as integer.
        :param kwargs: additional argument list, to be defined by subclasses.
        :return: pandas.DataFrame containing the data read from the connection.
        """
        if from_time.tzinfo != to_time.tzinfo:
            log.warning(
                f"Timezone of from_time and to_time are different. Using from_time timezone: {from_time.tzinfo}"
            )

    def read(self, nodes: NW | Nodes[NW] | None = None) -> pd.DataFrame:
        """
        .. warning::
            Cannot read single values from the Wetterdienst API. Use read_series instead

        :param nodes: Single node or list/set of nodes to read values from
        :return: Pandas DataFrame containing the data read from the connection
        """
        raise NotImplementedError("Cannot read single values from the Wetterdienst API. Use read_series instead")

    def write(self, values: Mapping[NW, Any], time_interval: timedelta | None = None) -> None:
        """
        .. warning::
            Cannot write to the Wetterdienst API.

        :param values: Dictionary of nodes and data to write. {node: value}
        :param time_interval: Interval between datapoints, default 1s
        """
        raise NotImplementedError("Cannot write to the Wetterdienst API.")

    def subscribe(
        self, handler: SubscriptionHandler, nodes: NW | Nodes[NW] | None = None, interval: TimeStep = 1
    ) -> None:
        """Subscribe to nodes and call handler when new data is available. This will return only the
        last available values.

        :param handler: SubscriptionHandler object with a push method that accepts node, value pairs
        :param interval: interval for receiving new data. It is interpreted as seconds when given as an integer.
        :param nodes: Single node or list/set of nodes to subscribe to
        """
        raise NotImplementedError("Cannot subscribe to data from the Wetterdienst API.")

    def subscribe_series(
        self,
        handler: SubscriptionHandler,
        req_interval: TimeStep,
        offset: TimeStep | None = None,
        nodes: NW | Nodes[NW] | None = None,
        interval: TimeStep = 1,
        data_interval: TimeStep = 1,
        **kwargs: Any,
    ) -> None:
        """
        .. warning::
            Not implemented: Cannot subscribe to data from the Wetterdienst API.

        :param handler: SubscriptionHandler object with a push method that accepts node, value pairs
        :param req_interval: Duration covered by requested data (time interval). Interpreted as seconds if given as int
        :param offset: Offset from datetime.now from which to start requesting data (time interval).
                       Interpreted as seconds if given as int. Use negative values to go to past timestamps.
        :param data_interval: Time interval between values in returned data. Interpreted as seconds if given as int.
        :param interval: interval (between requests) for receiving new data.
                         It it interpreted as seconds when given as an integer.
        :param nodes: Single node or list/set of nodes to subscribe to
        """
        raise NotImplementedError("Cannot subscribe to data from the Wetterdienst API.")

    def close_sub(self) -> None:
        """
        .. warning::
            Not implemented: Cannot subscribe to data from the the Wetterdienst API.
        """
        raise NotImplementedError("Cannot subscribe to data from the the Wetterdienst API.")

    def retrieve_stations(self, node: NodeWetterdienst, request: DwdObservationRequest) -> pd.DataFrame:
        """
        Retrieve stations from the Wetterdienst API and return the values as a pandas DataFrame
        Stations are filtered by the node's station_id or latlon and number_of_stations

        :param node: Node to retrieve stations for
        :param request: Wetterdienst request object, containing the station data
        """
        # Retrieve stations. If station_id is provided, use it, otherwise use latlon to get nearest stations
        stations: StationsResult
        if node.station_id is not None:
            stations = request.filter_by_station_id(node.station_id)
        else:
            stations = request.filter_by_rank(node.latlon, rank=node.number_of_stations)

        # Convert to pandas and pivot values so date is the index and
        # node names combined with the station_id are the columns
        result_df: pd.DataFrame = stations.values.all().df.to_pandas()  # noqa: PD011 (stations is not a dataframe)
        result_df = result_df.pivot_table(values="value", columns=("parameter", "station_id"), index="date")

        # Rename the columns to the node names
        result_df = result_df.rename({node.parameter.lower(): node.name}, axis="columns")
        return result_df.rename_axis(("Name", "station_id"), axis="columns")


class WetterdienstObservationConnection(
    WetterdienstConnection[NodeWetterdienstObservation], protocol="wetterdienst_observation"
):
    """
    The WetterdienstObservationConnection class is a connector to the Wetterdienst API
    for retrieving weather observation data. Data can only be read with
    :func:`~wetterdienst.WetterdienstObservationConnection.read_series`.
    """

    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: NodeWetterdienstObservation | Nodes[NodeWetterdienstObservation] | None = None,
        interval: TimeStep = 60,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Read weather observation data from the Wetterdienst API for the given nodes and time interval

        :param from_time: Start time for the data retrieval
        :param to_time: End time for the data retrieval
        :param nodes: Single node or list/set of nodes to read data from
        :param interval: Time interval between data points in seconds
        :return: Pandas DataFrame containing the data read from the connection
        """

        super().read_series(from_time, to_time, nodes, interval)
        nodes = self._validate_nodes(nodes)
        interval = interval if isinstance(interval, timedelta) else timedelta(seconds=interval)

        def _read_node(node: NodeWetterdienstObservation) -> pd.Dataframe:
            # Get the resolution for the node from the interval
            resolution = NodeWetterdienstObservation.convert_interval_to_resolution(node.interval)
            # Create a request object for the node
            request: DwdObservationRequest = DwdObservationRequest(
                parameter=node.parameter,
                resolution=resolution,
                start_date=from_time,
                end_date=to_time,
                settings=self.settings,
            )
            return self.retrieve_stations(node, request)

        # We can't use a ThreadPoolExecutor here, as the Wetterdienst library uses asyncio.
        # As a result, we have to call the _read_node method directly, which causes type errors.
        results = []
        for node in nodes:
            results.append(_read_node(node))
        result = pd.concat(results, axis=1, sort=False)

        # Convert the data to the requested interval
        return result.asfreq(interval, method="ffill").ffill()


class WetterdienstPredictionConnection(
    WetterdienstConnection[NodeWetterdienstPrediction], protocol="wetterdienst_prediction"
):
    """
    The WetterdienstPredictionConnection class is a connector to the Wetterdienst API
    for retrieving weather prediction data (MOSMIX). Data can only be read with
    :func:`~wetterdienst.WetterdienstPredictionConnection.read_series`.
    """

    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: NodeWetterdienstPrediction | Nodes[NodeWetterdienstPrediction] | None = None,
        interval: TimeStep = 0,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Read weather prediction data from the Wetterdienst API for the given nodes.
        The interval parameter is not used for prediction data, as predictions are always given hourly.

        :param from_time: Start time for the data retrieval
        :param to_time: End time for the data retrieval
        :param nodes: Single node or list/set of nodes to read data from
        :param interval: - Not used for prediction data
        :return: Pandas DataFrame containing the data read from the connection
        """

        super().read_series(from_time, to_time, nodes, interval)
        nodes = self._validate_nodes(nodes)

        def _read_node(node: NodeWetterdienstPrediction) -> pd.Dataframe:
            request = DwdMosmixRequest(
                parameter=node.parameter,
                mosmix_type=node.mosmix_type,
                start_date=from_time,
                end_date=to_time,
                settings=self.settings,
            )
            return self.retrieve_stations(node, request)

        # We can't use a ThreadPoolExecutor here, as the Wetterdienst library uses asyncio.
        # As a result, we have to call the _read_node method directly, which causes type errors.
        results = []
        for node in nodes:
            results.append(_read_node(node))
        return pd.concat(results, axis=1, sort=False)
