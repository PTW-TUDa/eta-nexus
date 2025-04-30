"""Connection base classes (Connection, SeriesConnection, StateConnection)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, Generic

from attr import field
from dateutil import tz

from eta_nexus.nodes.node import Node
from eta_nexus.subhandlers import SubscriptionHandler
from eta_nexus.util import ensure_timezone, round_timestamp, url_parse
from eta_nexus.util.type_annotations import N

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from typing import Any, ClassVar
    from urllib.parse import ParseResult

    import pandas as pd
    from typing_extensions import Self

    from eta_nexus.subhandlers import SubscriptionHandler
    from eta_nexus.util.type_annotations import Nodes, TimeStep


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
    def from_node(
        cls, node: Nodes[Node] | Node, usr: str | None = None, pwd: str | None = None, **kwargs: Any
    ) -> Connection:
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
                connection = cls._registry[_node.protocol]._from_node(_node, usr=usr, pwd=pwd, **kwargs)
            # Add node to existing connection
            else:
                connection.selected_nodes.add(_node)

        return connection

    @classmethod
    def from_nodes(cls, nodes: Nodes[Node], **kwargs: Any) -> dict[str, Connection[Node]]:
        """Returns a dictionary of connections for nodes with the same url netloc.

        This method handles different Connections, unlike from_node().
        The keys of the dictionary are the netlocs of the nodes and
        each connection contains the nodes with the same netloc.
        (Uses from_node to initialize connections from nodes.).

        :param nodes: List of nodes to initialize from.
        :param kwargs: Other arguments are ignored.
        :return: Dictionary of Connection objects with the netloc as key.
        """
        connections: dict[str, Connection] = {}

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

    @abstractmethod
    def read(self, nodes: N | Nodes[N] | None = None) -> pd.DataFrame:
        """Read data from nodes.

        :param nodes: Single node or list/set of nodes to read from.
        :return: Pandas DataFrame with resulting values.
        """

    @abstractmethod
    def write(self, values: Mapping[N, Any]) -> None:
        """Write data to a list of nodes.

        :param values: Dictionary of nodes and data to write {node: value}.
        """

    @abstractmethod
    def subscribe(
        self, handler: SubscriptionHandler, nodes: N | Nodes[N] | None = None, interval: TimeStep = 1
    ) -> None:
        """Subscribe to nodes and call handler when new data is available.

        :param nodes: Single node or list/set of nodes to subscribe to.
        :param handler: Function to be called upon receiving new values, must accept attributes: node, val.
        :param interval: Interval for receiving new data. Interpreted as seconds when given as integer.
        """

    @abstractmethod
    def close_sub(self) -> None:
        """Close an open subscription. This should gracefully handle non-existent subscriptions."""

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


class SeriesConnection(Connection[N], ABC):
    """Connection object for protocols with the ability to provide access to timeseries data.

    :param url: URL of the server to connect to.
    """

    def __init__(
        self, url: str, usr: str | None = None, pwd: str | None = None, *, nodes: Nodes[N] | None = None
    ) -> None:
        super().__init__(url=url, usr=usr, pwd=pwd, nodes=nodes)

    @abstractmethod
    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: N | Nodes[N] | None = None,
        interval: TimeStep = 1,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Read time series data from the connection, within a specified time interval (from_time until to_time).

        :param nodes: Single node or list/set of nodes to read values from.
        :param from_time: Starting time to begin reading (included in output).
        :param to_time: Time to stop reading at (not included in output).
        :param interval: interval between time steps. It is interpreted as seconds if given as integer.
        :param kwargs: additional argument list, to be defined by subclasses.
        :return: pandas.DataFrame containing the data read from the connection.
        """

    def subscribe_series(
        self,
        handler: SubscriptionHandler,
        req_interval: TimeStep,
        offset: TimeStep | None = None,
        nodes: N | Nodes[N] | None = None,
        interval: TimeStep = 1,
        data_interval: TimeStep = 1,
        **kwargs: Any,
    ) -> None:
        """Subscribe to nodes and call handler when new data is available. This will always return a series of values.
        If nodes with different intervals should be subscribed, multiple connection objects are needed.

        :param handler: SubscriptionHandler object with a push method that accepts node, value pairs.
        :param req_interval: Duration covered by requested data (time interval). Interpreted as seconds if given as int
        :param offset: Offset from datetime.now from which to start requesting data (time interval).
            Interpreted as seconds if given as int. Use negative values to go to past timestamps.
        :param data_interval: Time interval between values in returned data. Interpreted as seconds if given as int.
        :param interval: interval (between requests) for receiving new data. It is interpreted as seconds
            when given as an integer.
        :param nodes: Single node or list/set of nodes to subscribe to.
        :param kwargs: Any additional arguments required by subclasses.
        """
