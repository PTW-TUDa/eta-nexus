from __future__ import annotations

from abc import ABC, abstractmethod
from logging import getLogger
from typing import TYPE_CHECKING, Generic, TypeVar

import pandas as pd
from wetterdienst import Settings
from wetterdienst.provider.dwd.mosmix.api import DwdMosmixRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Any

    from wetterdienst.core.timeseries.result import StationsResult

    from eta_nexus.util.type_annotations import Nodes, TimeStep

from eta_nexus.connections.connection import Connection, SeriesReadable
from eta_nexus.nodes.wetterdienst_node import (
    WetterdienstNode,
    WetterdienstObservationNode,
    WetterdienstPredictionNode,
)

log = getLogger(__name__)

WN = TypeVar("WN", bound=WetterdienstNode)


class WetterdienstConnection(Generic[WN], Connection[WN], SeriesReadable[WN], ABC):
    """The WetterdienstConnection class is a connection to the Wetterdienst API for retrieving weather data.
    This class is an abstract base class and should not be used directly. Instead, use the subclasses
    :class:`WetterdienstObservationConnection` and :class:`WetterdienstPredictionConnection`.

    :param url: The base URL of the Wetterdienst API
    :param nodes: Nodes to select in connection
    :param settings: Wetterdienst settings object
    """

    def __init__(
        self,
        *,
        nodes: Nodes[WN] | None = None,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        self.settings = Settings(settings=settings)
        self.settings.ts_skip_empty = True
        self.settings.ts_si_units = False
        self.settings.ts_humanize = True
        super().__init__("https://opendata.dwd.de/", nodes=nodes)  # dummy url

    @classmethod
    def _from_node(cls, node: WN, **kwargs: Any) -> WetterdienstConnection:
        """Initialize the connection object from an wetterdienst protocol node object.

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
        nodes: WN | Nodes[WN] | None = None,
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

    def retrieve_stations(self, node: WetterdienstNode, request: DwdObservationRequest) -> pd.DataFrame:
        """Retrieve stations from the Wetterdienst API and return the values as a pandas DataFrame
        Stations are filtered by the node's station_id or latlon and number_of_stations.

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
    WetterdienstConnection[WetterdienstObservationNode], protocol="wetterdienst_observation"
):
    """The WetterdienstObservationConnection class is a connection to the Wetterdienst API
    for retrieving weather observation data. Data can only be read with
    :func:`~wetterdienst.WetterdienstObservationConnection.read_series`.
    """

    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: WetterdienstObservationNode | Nodes[WetterdienstObservationNode] | None = None,
        interval: TimeStep = 60,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Read weather observation data from the Wetterdienst API for the given nodes and time interval.

        :param from_time: Start time for the data retrieval
        :param to_time: End time for the data retrieval
        :param nodes: Single node or list/set of nodes to read data from
        :param interval: Time interval between data points in seconds
        :return: Pandas DataFrame containing the data read from the connection
        """
        from_time, to_time, nodes, interval = super()._preprocess_series_context(
            from_time, to_time, nodes, interval, **kwargs
        )

        def _read_node(node: WetterdienstObservationNode) -> pd.Dataframe:
            # Get the resolution for the node from the interval
            resolution = WetterdienstObservationNode.convert_interval_to_resolution(node.interval)
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
        result = pd.concat([_read_node(node) for node in nodes], axis=1, sort=False)

        # Convert the data to the requested interval
        return result.asfreq(interval, method="ffill").ffill()


class WetterdienstPredictionConnection(
    WetterdienstConnection[WetterdienstPredictionNode], protocol="wetterdienst_prediction"
):
    """The WetterdienstPredictionConnection class is a connection to the Wetterdienst API
    for retrieving weather prediction data (MOSMIX). Data can only be read with
    :func:`~wetterdienst.WetterdienstPredictionConnection.read_series`.
    """

    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: WetterdienstPredictionNode | Nodes[WetterdienstPredictionNode] | None = None,
        interval: TimeStep = 0,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Read weather prediction data from the Wetterdienst API for the given nodes.
        The interval parameter is not used for prediction data, as predictions are always given hourly.

        :param from_time: Start time for the data retrieval
        :param to_time: End time for the data retrieval
        :param nodes: Single node or list/set of nodes to read data from
        :param interval: - Not used for prediction data
        :return: Pandas DataFrame containing the data read from the connection
        """
        from_time, to_time, nodes, interval = super()._preprocess_series_context(
            from_time, to_time, nodes, interval, **kwargs
        )

        def _read_node(node: WetterdienstPredictionNode) -> pd.Dataframe:
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
        return pd.concat([_read_node(node) for node in nodes], axis=1, sort=False)
