"""Connection base class and protocols for the ETA Nexus framework."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, Protocol, cast, runtime_checkable

from attr import field
from dateutil import tz
from typing_extensions import deprecated

from eta_nexus.nodes.node import Node
from eta_nexus.subhandlers.subhandler import SubscriptionHandler
from eta_nexus.util import ensure_timezone, round_timestamp, url_parse
from eta_nexus.util.type_annotations import N, N_contra

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from typing import Any, ClassVar
    from urllib.parse import ParseResult

    import pandas as pd

    from eta_nexus.subhandlers import SubscriptionHandler
    from eta_nexus.util.type_annotations import Nodes, Self, TimeStep


@runtime_checkable
class Readable(Protocol, Generic[N_contra]):
    """Non-data Protocol for Connections with the ability to read data."""

    @abstractmethod
    def read(self, nodes: N_contra | Nodes[N_contra] | None = None) -> pd.DataFrame:
        """Reads current value from each Node in nodes. Uses selected_nodes if no nodes are passed.

        :param nodes: Single Node or Sequence/Set of Nodes to read from.
        :return: Pandas DataFrame with read values.
        """


@runtime_checkable
class Writable(Protocol, Generic[N]):
    """Non-data Protocol for Connections with the ability to write data."""

    @abstractmethod
    def write(self, values: Mapping[N, Any]) -> None:
        """Writes given values to nodes
        :param values: Mapping(e.g. Dict) of Nodes and respective values to write {node: value}.
        """


@runtime_checkable
class Subscribable(Protocol, Generic[N_contra]):
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
        self._url: ParseResult
        #: Username for login to server
        self.usr: str | None
        #: Password for login to server
        self.pwd: str | None
        self._url, self.usr, self.pwd = url_parse(url)

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
        # Check if all nodes have the same netloc
        if len({f"{_node.url_parsed.netloc}" for _node in nodes}) != 1:
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
            node_id = f"{node.url_parsed.netloc}"

            # If we already have a connection for this URL, add the node to connection
            if node_id in connections:
                connections[node_id].selected_nodes.add(node)
                continue  # Skip creating a new connection

            connections[node_id] = cls.from_node(node, **kwargs)

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
        return self._url.geturl()

    def _validate_nodes(self, nodes: N | Nodes[N] | None) -> set[N]:
        """Make sure that nodes are a Set of nodes and that all nodes correspond to the protocol and url
        of the connection.

        :param nodes: Single node or list/set of nodes to validate.
        :return: Set of valid node objects for this connection.
        """
        if nodes is None:
            _nodes = self.selected_nodes
        else:
            nodes = {nodes} if not isinstance(nodes, Iterable) else nodes
            # If not using preselected nodes from self.selected_nodes, check if nodes correspond to the connection
            _nodes = {
                node for node in nodes if node.protocol == self._PROTOCOL and node.url_parsed.netloc == self._url.netloc
            }

        # Make sure that some nodes remain after the checks and raise an error if there are none.
        if len(_nodes) == 0:
            raise ValueError(
                f"Some nodes to read from/write to must be specified. If nodes were specified, they do not "
                f"match the connection {self.url}"
            )

        return _nodes


@deprecated("Use `Connection` and the appropriate protocols instead.")
class SeriesConnection(
    Readable[N], Writable[N], Subscribable[N], SeriesReadable[N], SeriesSubscribable[N], Connection[N], ABC
):
    """Connection object for protocols with the ability to provide access to timeseries data.

    :param url: URL of the server to connect to.
    """
