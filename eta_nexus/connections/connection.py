"""Connection base class and protocols for the ETA Nexus framework."""

from __future__ import annotations

import concurrent.futures
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING, Any, Generic, Protocol, cast, overload, runtime_checkable

import pandas as pd
from attr import field
from dateutil import tz
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError, RequestException, Timeout
from typing_extensions import deprecated
from urllib3.util.retry import Retry

from eta_nexus.nodes.node import Node
from eta_nexus.subscription_handlers.subscription_handler import SubscriptionHandler
from eta_nexus.util import ensure_timezone, round_timestamp, url_parse
from eta_nexus.util.type_annotations import N, N_contra

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from logging import Logger
    from typing import Any, ClassVar
    from urllib.parse import ParseResult

    from pandas._typing import ArrayLike
    from requests.auth import AuthBase
    from requests_cache import AnyResponse, CachedSession

    from eta_nexus.subscription_handlers import SubscriptionHandler
    from eta_nexus.util.type_annotations import Nodes, Self, TimeStep


@runtime_checkable
class StatusReadable(Protocol, Generic[N_contra]):
    """Non-data Protocol for Connections with the ability to read data."""

    @abstractmethod
    def read(self, nodes: N_contra | Nodes[N_contra] | None = None) -> pd.DataFrame:
        """Reads current value from each Node in nodes. Uses selected_nodes if no nodes are passed.

        :param nodes: Single Node or Sequence/Set of Nodes to read from.
        :return: Pandas DataFrame with read values.
        """


@runtime_checkable
class StatusWritable(Protocol, Generic[N]):
    """Non-data Protocol for Connections with the ability to write data."""

    @abstractmethod
    def write(self, values: Mapping[N, Any]) -> None:
        """Writes given values to nodes
        :param values: Mapping(e.g. Dict) of Nodes and respective values to write {node: value}.
        """


@runtime_checkable
class StatusSubscribable(Protocol, Generic[N_contra]):
    """Non-data Protocol for Connections with the ability to subscribe to data."""

    @abstractmethod
    def subscribe(
        self,
        handler: SubscriptionHandler,
        nodes: N_contra | Nodes[N_contra] | None = None,
        request_frequency: TimeStep = 1,
    ) -> None:
        """Subscribes to nodes and calls handler when new data is available. If the connection protocol doesn't
           implement subscriptions natively, this method polls the nodes with the given frequency. Uses
           subscription_nodes if no nodes are passed.

        :param nodes: Single Node or Sequence/Set of nodes to subscribe to.
        :param handler: A SubscriptionHandler object
        :param request_frequency: Time period between two requests. Interpreted as seconds if Numeric is given.
            Technically no frequency!
        """

    @abstractmethod
    def close_sub(self) -> None:
        """Closes an open subscription. This should gracefully handle non-existent subscriptions."""


@runtime_checkable
class SeriesReadable(Protocol, Generic[N_contra]):
    """Non-data Protocol for Connections with the ability to read historic data."""

    @abstractmethod
    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: N_contra | Nodes[N_contra] | None = None,
        interval: TimeStep = 1,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Reads time series data for each Node in nodes. Retrieves values for the partly open time interval
            [from_time, to_time), adhering to the specified value-to-value distance given as resolution.
            Uses selected_nodes if no nodes are passed. Will apply the same resolution to all nodes.

        :param interval: Start and end of timeseries, treated as partly open interval[from_time, to_time).
        :param nodes: Single Node or Sequence/Set of nodes to read values from.
        :param resolution: Time between timeseries' values. Interpreted as seconds if Numeric is given.
        :param kwargs: Additional Subclass arguments.
        :return: pandas.DataFrame containing the timeseries read from the connection.
        """


@runtime_checkable
class SeriesWritable(Protocol, Generic[N]):
    """Non-data Protocol for Connections with the ability to write historic (time series) data."""

    @overload
    def write_series(
        self,
        values: Mapping[N, pd.Series],
        *,
        allow_overwrite: bool = True,
        **kwargs: Any,
    ) -> None: ...

    @overload
    def write_series(
        self,
        values: pd.DataFrame,
        *,
        allow_overwrite: bool = True,
        **kwargs: Any,
    ) -> None: ...

    def write_series(
        self,
        values: Mapping[N, pd.Series] | pd.DataFrame,
        *,
        allow_overwrite: bool = True,
        **kwargs: Any,
    ) -> None:
        """Writes time series data for the given nodes.

        Accepts either
          - a mapping from Node -> pandas.Series (index must be datetime-like; series values are samples), or
          - a pandas.DataFrame with a datetime-like index and one column per Node (column names must match node.name).

        Implementations may round/align timestamps to node-specific intervals and should ensure timezone
        awareness consistent with the Connection utilities.

        :param values: Mapping of nodes to Series, or a DataFrame with datetime-like index.
        :param allow_overwrite: If True, upsert points at identical timestamps; if False, avoid overwriting.
        :param kwargs: Additional subclass arguments.
        """


@runtime_checkable
class SeriesSubscribable(Protocol, Generic[N_contra]):
    """Non-data Protocol for Connections with the ability to subscribe to historic data."""

    @abstractmethod
    def subscribe_series(
        self,
        handler: SubscriptionHandler,
        req_interval: TimeStep,
        offset: TimeStep | None = None,
        nodes: N_contra | Nodes[N_contra] | None = None,
        interval: TimeStep = 1,
        data_interval: TimeStep = 1,
        **kwargs: Any,
    ) -> None:
        """Subscribes to nodes and calls handler when new data is available. Retrieves values for the partly open time
           interval [now + offset, now + offset + data_duration), adhering to the specified value-to-value distance
           given as resolution. If the connection protocol doesn't implement subscriptions natively, this method polls
           the nodes with the given requesty_frequency. Uses subscription_nodes if no nodes are passed. Will apply the
           same resolution to all nodes.

        :param handler: A SubscriptionHandler object
        :param data_duration: Duration of returned timeseries interval.
        :param offset: Offset between time of request and start of returned timeseries. Can be negative.
        :param nodes: Single Node or Sequence/Set of nodes to subscribe to.
        :param request_frequency: Time period between two requests. Interpreted as seconds if Numeric is given.
            Technically no frequency!
        :param resolution: Time between timeseries' values. Interpreted as seconds if Numeric is given.
        :param **kwargs: Subclass arguments
        """

    @abstractmethod
    def close_sub(self) -> None:
        """Closes an open subscription. This should gracefully handle non-existent subscriptions."""


class Connection(Generic[N], ABC):
    """Common connection interface class.

    The URL (netloc) may contain the username and password. (schema://username:password@hostname:port/path)
    In this case, the parameters usr and pwd are not required. BUT the keyword parameters of the function will
    take precedence over username and password configured in the url.

    :param url: Netloc of the server to connect to.
    :param usr: Username for login to server.
    :param pwd: Password for login to server.
    :param nodes: List of nodes to select as a standard case.
    """

    logger: Logger

    _registry: ClassVar[dict[str, type[Connection]]] = {}
    _PROTOCOL: ClassVar[str] = field(repr=False, eq=False, order=False)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Store subclass definitions to instantiate based on protocol."""
        protocol = kwargs.pop("protocol", None)
        if protocol:
            cls._PROTOCOL = protocol
            cls._registry[protocol] = cls

        return super().__init_subclass__(**kwargs)

    def __init__(
        self, url: str, usr: str | None = None, pwd: str | None = None, *, nodes: Nodes[N] | None = None
    ) -> None:
        #: URL of the server to connect to
        self.url_parsed: ParseResult
        #: Username for login to server
        self.usr: str | None
        #: Password for login to server
        self.pwd: str | None
        self.url_parsed, self.usr, self.pwd = url_parse(url)

        if nodes is not None:
            #: Preselected nodes which will be used for reading and writing, if no other nodes are specified
            self.selected_nodes = self._validate_nodes(nodes)
        else:
            self.selected_nodes = set()

        # Get username and password either from the arguments, from the parsed URL string or from a Node object
        node = next(iter(self.selected_nodes)) if len(self.selected_nodes) > 0 else None

        def validate_and_set(attribute: str, value: str | Any, node_value: str | None) -> None:
            """If attribute is not already set, set it to value or node_value if value is None."""
            if value is not None:
                if not isinstance(value, str):
                    raise TypeError(f"{attribute.capitalize()} should be a string value.")
                setattr(self, attribute, value)
            elif getattr(self, attribute) is None and node_value is not None:
                setattr(self, attribute, node_value)

        validate_and_set("usr", usr, node.usr if node else None)
        validate_and_set("pwd", pwd, node.pwd if node else None)

        #: Store local time zone
        self._local_tz = tz.tzlocal()
        #: :py:func:`eta_nexus.util.round_timestamp`
        self._round_timestamp = round_timestamp
        #: :py:func:`eta_nexus.util.ensure_timezone`
        self._assert_tz_awareness = ensure_timezone

        self.exc: BaseException | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Connection):
            return False
        return (self.url_parsed.netloc, self._extra_equality_key()) == (
            other.url_parsed.netloc,
            other._extra_equality_key(),
        )

    def __hash__(self) -> int:
        return hash((self.url_parsed.netloc, self._extra_equality_key()))

    def _extra_equality_key(self) -> Any | None:
        """Additional attributes that are relevant for deciding if nodes belong to a connection.
        Override this in case extra keys are necessary, don't forget to also set this in the node class.
        Enforce presence of attributes used in this method!
        """
        return None

    @classmethod
    def from_node(cls, node: Nodes[N] | N, usr: str | None = None, pwd: str | None = None, **kwargs: Any) -> Self:
        """Will return a single connection for an enumerable of nodes with the same url netloc.

        Initialize the connection object from a node object. When a list of Node objects is provided,
        from_node checks if all nodes match the same connection; it throws an error if they don't.
        A node matches a connection if it has the same url netloc.

        :param node: Node to initialize from.
        :param kwargs: Other arguments are ignored.
        :raises: ValueError: if not all nodes match the same connection.
        :return: Connection object
        """
        nodes = {node} if not isinstance(node, Iterable) else set(node)
        # Check if all nodes belong to the same connection
        if len({_node.connection_identifier() for _node in nodes}) != 1:
            raise ValueError("Nodes must all have the same netloc to be used with the same connection.")

        for index, _node in enumerate(nodes):
            # Instantiate connection from the first node
            if index == 0:
                # set the username and password
                usr = _node.usr or usr
                pwd = _node.pwd or pwd
                connection_cls = cls._registry[_node.protocol]
                connection = cast("Self", connection_cls._from_node(_node, usr=usr, pwd=pwd, **kwargs))
            # Add node to existing connection
            else:
                connection.selected_nodes.add(_node)

        return connection

    @classmethod
    def from_nodes(cls, nodes: Nodes[N], **kwargs: Any) -> dict[str, Connection[N]]:
        """Returns a dictionary of connections for nodes with the same url netloc.

        This method handles different Connections, unlike from_node().
        The keys of the dictionary are the netlocs of the nodes and
        each connection contains the nodes with the same netloc.
        (Uses from_node to initialize connections from nodes.).

        :param nodes: List of nodes to initialize from.
        :param kwargs: Other arguments are ignored.
        :return: Dictionary of Connection objects with the netloc as key.
        """
        connections: dict[str, Connection[N]] = {}

        for node in nodes:
            connection_id = str(node.connection_identifier())

            # If we already have a connection for this URL, add the node to connection
            if connection_id in connections:
                connections[connection_id].selected_nodes.add(node)
                continue  # Skip creating a new connection

            connections[connection_id] = cls.from_node(node, **kwargs)

        return connections

    @classmethod
    @abstractmethod
    def _from_node(cls, node: N, **kwargs: Any) -> Self:
        """Initialize the object from a node with corresponding protocol.

        :return: Initialized connection object.
        """
        if not isinstance(node, Node):
            raise TypeError("Node must be a Node object.")
        if node.protocol != cls._PROTOCOL:
            raise ValueError(
                f"Tried to initialize {cls.__name__} from a node "
                f"that does not specify {cls._PROTOCOL} as its protocol: {node.name}."
            )
        return cls(url=node.url, nodes=[node], **kwargs)

    @property
    def url(self) -> str:
        return self.url_parsed.geturl()

    def _validate_nodes(self, nodes: N | Nodes[N] | None) -> set[N]:
        """Make sure that nodes are a Set of nodes and that all nodes correspond to the connection.

        :param nodes: Single node or list/set of nodes to validate.
        :return: Set of valid node objects for this connection.
        """
        if nodes is None:
            _nodes = self.selected_nodes
        else:
            nodes = {nodes} if not isinstance(nodes, Iterable) else nodes
            # If not using preselected nodes from self.selected_nodes, check if nodes correspond to the connection
            _nodes = {
                node
                for node in nodes
                if (
                    node.protocol == self._PROTOCOL
                    and node.url_parsed.netloc == self.url_parsed.netloc
                    and node._extra_equality_key() == self._extra_equality_key()
                )
            }

        # Make sure that some nodes remain after the checks and raise an error if there are none.
        if len(_nodes) == 0:
            raise ValueError(
                f"Some nodes to read from/write to must be specified. If nodes were specified, they do not "
                f"match the connection {self.url}"
            )

        return _nodes

    def _preprocess_series_context(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: N | Nodes[N] | None = None,
        interval: TimeStep = 1,
        **kwargs: Any,
    ) -> tuple[datetime, datetime, set[N], timedelta]:
        """Preprocesses the series context to ensure it is ready for reading.
        This method validates the nodes, ensures the time interval is a timedelta, and rounds the timestamps
        to the nearest interval. It also checks that the timezones of from_time and to_time are the same.

        :param from_time: The start time of the series.
        :param to_time: The end time of the series.
        :param nodes: The nodes to read from.
        :param interval: The time interval for the series.
        :return: A tuple containing the processed from_time, to_time, nodes, and interval.
        """
        nodes = self._validate_nodes(nodes)

        interval = interval if isinstance(interval, timedelta) else timedelta(seconds=interval)

        from_time = round_timestamp(from_time, interval.total_seconds(), method="floor", ensure_tz=True)
        to_time = round_timestamp(to_time, interval.total_seconds(), method="ceil", ensure_tz=True)

        if from_time.tzinfo != to_time.tzinfo:
            log = getLogger(self.__module__)
            log.warning(
                f"Timezone of from_time and to_time are different. Using from_time timezone: {from_time.tzinfo}"
            )
        return (from_time, to_time, nodes, interval)


@deprecated("Use `Connection` and the appropriate protocols instead.")
class SeriesConnection(
    StatusReadable[N],
    StatusWritable[N],
    StatusSubscribable[N],
    SeriesReadable[N],
    SeriesWritable[N],
    SeriesSubscribable[N],
    Connection[N],
    ABC,
):
    """Connection object for protocols with the ability to provide access to timeseries data.

    :param url: URL of the server to connect to.
    """


class RESTConnection(Connection[N], ABC):
    """
    RESTConnection is an abstract base class for managing RESTful API connections in the ETA Nexus framework.
    It extends the `Connection` class and provides standardized functionality for handling HTTP requests,
    managing API tokens, and session management. This class is designed to reduce boilerplate code and
    streamline the integration of new REST-based connections.

    Key Features:
    - Centralized HTTP request handling with consistent error management and logging.
    - Lazy-loaded session management using a cached session.
    - API token retrieval from environment variables based on the connection protocol name.
    - Abstract methods for session initialization and node-specific data reading.
    - Authentication abstraction for subclasses to define custom authentication mechanisms.

    Subclasses should implement the `_initialize_session` method to define session initialization logic
    and the `_read_node` method to handle node-specific data reading.

    :param url: URL of the REST API endpoint.
    :param usr: Username for authentication (optional).
    :param pwd: Password for authentication (optional).
    :param nodes: List of nodes to connect to (optional).
    :param retry_total: Total number of retries for failed HTTP requests (default: 3).
    :param retry_backoff_factor: Backoff factor for retries (default: 1s-> e.g. 1s, 2s, 4s for 3 retries).
    """

    def __init__(
        self,
        url: str,
        usr: str | None = None,
        pwd: str | None = None,
        *,
        nodes: Nodes[N] | None = None,
        retry_total: int = 3,
        retry_backoff_factor: float = 1.0,
    ) -> None:
        super().__init__(url, usr, pwd, nodes=nodes)
        self._retry_total = retry_total
        self._retry_backoff_factor = retry_backoff_factor

    @property
    def _api_token(self) -> str | None:
        """Return the API token from the environment variable if set."""
        token = os.getenv(self._PROTOCOL.upper() + "_API_TOKEN")
        if token is None:
            self.logger.warning(
                f"[{self._PROTOCOL.capitalize()}] {self._PROTOCOL.upper()}_API_TOKEN not found in environment."
            )
        return token

    @property
    def session(self) -> CachedSession:
        "Return the cached session."
        if not hasattr(self, "_cached_session"):
            session = self._initialize_session()
            retry_strategy = Retry(
                total=self._retry_total,  # Number of total retries
                connect=self._retry_total,  # Retry on connect timeouts
                read=self._retry_total,  # Retry on read timeouts
                status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],  # Methods to retry
                backoff_factor=self._retry_backoff_factor,
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self._cached_session = session
        return self._cached_session

    @property
    def authentication(self) -> None | AuthBase:
        """Return the authentication method for the API."""
        return None

    @abstractmethod
    def _initialize_session(self) -> CachedSession:
        "Initialize the cached session and return it."

    def _raw_request(
        self, method: str, url: str, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> AnyResponse | None:
        """Send a raw HTTP request to the REST API.

        :param method: HTTP method to use (e.g., GET, POST).
        :param url: URL of the API endpoint.
        :return: Response object from the requests library.
        """
        kwargs.setdefault("timeout", 10)
        try:
            response = self.session.request(method, url, params=params, auth=self.authentication, **kwargs)
            response.raise_for_status()
        except HTTPError:  # Bad Response (4xx, 5xx after retries exhausted)
            self.logger.exception(f"[{self._PROTOCOL.capitalize()}] Request failed:")
            return None
        except Timeout:  # Timeout errors (after retries exhausted)
            self.logger.exception(
                f"[{self._PROTOCOL.capitalize()}] Request timed out after {kwargs.get('timeout', 10)}s"
            )
            return None
        except RequestException:  # Other errors (ConnectionError, SSLError, etc.)
            self.logger.exception(f"[{self._PROTOCOL.capitalize()}] Request error occurred")
            return None
        else:
            return response

    @abstractmethod
    def _parse_response(self, json_data: dict[Any, Any]) -> tuple[pd.DatetimeIndex, ArrayLike]:
        """Parse the JSON data from the REST API into a DataFrame.

        :param json_data: JSON data from the API response.
        :return: Tuple of (timestamps, values) where:
            - timestamps: DatetimeIndex to use as the DataFrame index. Must be timezone-aware.
            - values: Array-like data for the DataFrame. If a pd.Series is returned,
                    its index MUST match the timestamps to avoid NaN values from
                    misalignment. For other array-like types (list, tuple, ndarray),
                    the values will be automatically aligned with timestamps.
        """

    @abstractmethod
    def read_node(
        self,
        node: N,
        from_time: datetime,
        to_time: datetime,
        interval: timedelta,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Read data from a REST API endpoint.

        :param node: Node to read data from.
        :param from_time: Start of the time series (timezone-aware).
        :param to_time: End of the time series (timezone-aware).
        :param interval: Time interval between data points.
        :param kwargs: Additional subclass-specific arguments.
        :return: DataFrame containing the data read from the API.
        """
        raise NotImplementedError(
            "Subclasses must implement read_node to define how data is read from a REST API endpoint for a given node."
        )

    def _read_node(self, node: N, url: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Read data from a REST API endpoint.

        :param node: Node to read data from.
        :return: DataFrame containing the data read from the API.
        """
        empty_df = pd.DataFrame(columns=[node.name], index=pd.DatetimeIndex([], name="Time (with timezone)"))
        response = self._raw_request("GET", url, params=params)
        if response is None:
            self.logger.warning(f"[{self._PROTOCOL}] No response from {url} for node {node.name}")
            return empty_df
        # Process the data into a DataFrame
        try:
            json_data = response.json()
            timestamps, node_values = self._parse_response(json_data)
            node_data_frame = pd.DataFrame(
                data=node_values,
                index=timestamps.tz_convert(self._local_tz),
                columns=[node.name],
                dtype="float64",
            )
            node_data_frame.index.name = "Time (with timezone)"
        except (KeyError, ValueError, AttributeError, TypeError):
            self.logger.exception(f"[{self._PROTOCOL}] Failed to process data for node {node.name}")
            return empty_df
        else:
            return node_data_frame

    def _get_data(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: N | Nodes[N] | None = None,
        interval: TimeStep = 60,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Get data from the REST API for the specified nodes and time interval.

        :param from_time: Start of the time series, treated as partly open interval [from_time, to_time).
        :param to_time: End of the time series, treated as partly open interval [from_time, to_time).
        :param nodes: Single node or list/set of nodes to read values from.
        :param interval: Time between time series' values. Interpreted as seconds if Numeric is given.
        :param kwargs: Additional subclass arguments.
        """
        from_time, to_time, nodes, interval = super()._preprocess_series_context(
            from_time, to_time, nodes, interval, **kwargs
        )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = executor.map(lambda node: self.read_node(node, from_time, to_time, interval, **kwargs), nodes)

        # Filter out empty or all-NA DataFrames
        filtered_results = [df for df in results if not df.empty and not df.isna().all().all()]

        if not filtered_results:
            self.logger.warning(f"[{self._PROTOCOL.capitalize()}] No valid data retrieved from any node.")
            col_names = [node.name for node in nodes]
            if not col_names:
                col_names = ["__placeholder__"]
            return pd.DataFrame(columns=col_names)

        return pd.concat(filtered_results, axis=1, sort=False)
