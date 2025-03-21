from __future__ import annotations

from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING

import pandas as pd

from eta_connect.connectors.base_classes import Connection, SubscriptionHandler
from eta_connect.connectors.modbus import ModbusConnection
from eta_connect.connectors.node import NodeEmonio, NodeModbus

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from eta_connect.type_hints import Nodes, TimeStep

log = getLogger(__name__)


class EmonioConnection(Connection[NodeEmonio], protocol="emonio"):
    """
    Thin wrapper class for the Emonio that uses a modbus TCP Connection.
    Internally the Emonio nodes are converted to modbus nodes with
    fixed parameters, expect for the name, url and channel.
    If nodes have specified a phase, the connection will check if the phase is connected.
    Additionally, the connection will check for Emonio errors and warnings (max. every minute).

    When creating a :class:`~node.NodeEmonio` the :attr:`~node.NodeEmonio.parameter` (and resulting modbus channel)
    is set by the name of the node (case insensitive).
    See `Available Emonio Nodes` for for possible parameter names.
    Alternatively, the :attr:`~node.NodeEmonio.address` (modbus channel) can be set manually.

    The phase is set by the :attr:`~node.NodeEmonio.phase` attribute of the node.
    Possible values are ``a``, ``b``, ``c`` or ``abc``, with ``abc`` being the default.
    """

    def __init__(self, url: str, *, nodes: Nodes[NodeEmonio] | None = None, check_error: bool = True) -> None:
        """
        Initialize the Emonio connection.

        :param url: URL of the Emonio.
        :param nodes: List of nodes to connect to.
        :param check_error: Setting to check for errors and warnings.
        """
        self.nodes_factory = NodeModbusFactory(url)
        # The actual (Modbus) connection which will be used for reading
        self._connection = ModbusConnection(url=url)
        # Dictionary to keep track of the connected phases
        self._phases_connected: dict[str, bool] = self._get_phases_status()

        self.check_error = check_error
        self._last_error_check = datetime.now() - timedelta(minutes=1)
        self.check_warnings_and_errors()

        # This calls self._validate_nodes(nodes) and checks phases and errors/warnings
        super().__init__(url, nodes=nodes)

    @classmethod
    def _from_node(cls, node: NodeEmonio, **kwargs: Any) -> EmonioConnection:
        """
        Create an Emonio connection from a single node.

        :param node: The node to connect to.
        :return: The Emonio connection.
        """
        return super()._from_node(node)

    def read(self, nodes: NodeEmonio | Nodes[NodeEmonio] | None = None) -> pd.DataFrame:
        """
        Read the values of the selected nodes.
        If nodes is None, all previously selected nodes will be read.

        :param nodes: Single node or list/set of nodes to read from.
        :return: Dataframe with the read values.
        """

        _nodes: set[NodeEmonio] = self._validate_nodes(nodes)
        return self._connection.read(self._prepare_modbus_nodes(_nodes))

    def write(self, values: Mapping[NodeEmonio, Any]) -> None:
        """
        .. warning::
           Not implemented: Writing to Emonio nodes is not supported.
        """
        raise NotImplementedError("Writing to Emonio nodes is not supported")

    def subscribe(
        self, handler: SubscriptionHandler, nodes: NodeEmonio | Nodes[NodeEmonio] | None = None, interval: TimeStep = 1
    ) -> None:
        """
        Subscribe to the selected nodes. The Modbus connection does all the handling.

        :param handler: The handler to subscribe.
        :param nodes: Single node or list/set of nodes to subscribe to.
        :param interval: The interval in seconds to read the values.
        """

        _nodes: set[NodeEmonio] = self._validate_nodes(nodes)
        self._connection.subscribe(handler, self._prepare_modbus_nodes(_nodes), interval)

    def close_sub(self) -> None:
        """Close the subscription of the modus connection."""
        self._connection.close_sub()

    def _prepare_modbus_nodes(self, nodes: Nodes[NodeEmonio]) -> list[NodeModbus]:
        """
        Convert the Emonio nodes to modbus nodes with fixed parameters.
        The wordorder is little because the Emonio uses zero based word indexing.
        All values are 32 bit float holding registers.

        :param nodes: List of Emonio nodes.
        :return: List of modbus nodes (will return empty list when no nodes are passed).
        """
        return [self.nodes_factory.get_default_node(node.name, node.address) for node in nodes]

    def _validate_nodes(self, nodes: NodeEmonio | Nodes[NodeEmonio] | None) -> set[NodeEmonio]:
        """
        Validate the nodes and return the set of nodes.
        If nodes is none, return the previously selected nodes.

        :param nodes: List of nodes to validate.
        :return: Set of nodes.
        """
        _nodes: set[NodeEmonio] = super()._validate_nodes(nodes)
        if self.check_error:
            self.check_warnings_and_errors()
        # Check if the phases of the nodes are connected
        self._check_phases(_nodes)
        return _nodes

    def _get_phases_status(self) -> dict[str, bool]:
        """
        Get connection information about the phases of the Emonio.
        The status is read from the discrete input registers of the Emonio.
        """

        nodes = [self.nodes_factory.get_discrete_input_node(phase, i) for i, phase in enumerate(["a", "b", "c"])]
        # Read the status of the phases from the Emonio
        result = self._connection.read(nodes)
        # Convert the result to a dictionary
        result = result.iloc[0].to_dict()
        log.debug("Connected phases: %s", result)
        return result

    def _check_phases(self, nodes: Nodes[NodeEmonio]) -> None:
        """
        Check the connection status of the Emonio phases.

        :param nodes: List of nodes to check.
        """

        for node in nodes:
            phase = node.phase
            if phase == "abc":
                continue
            if not self._phases_connected[phase]:
                raise ValueError(f"Phase '{phase}' is not connected.")

    def check_warnings_and_errors(self) -> None:
        """
        Calls the error and warning check if the last check was more than a minute ago.
        """
        now = datetime.now()
        if self._last_error_check is None:
            pass
        elif now - self._last_error_check < timedelta(minutes=1):
            return
        self._last_error_check = now
        self._check_warnings_and_errors()

    def _check_warnings_and_errors(self) -> None:
        """
        Check the Emonio for errors and warnings.
        This is done by reading the error and warning bits from the Emonio.
        If an error bit is set, a ValueError is raised.
        If a warning bit is set, a warning is logged.
        """
        error_node = self.nodes_factory.get_warnings_errors_node("Error", 1000)
        warning_node = self.nodes_factory.get_warnings_errors_node("Warning", 1001)

        result = self._connection.read([error_node, warning_node])

        # Check binary if corresponding error/warning bit is set
        for name, value in result.items():
            # Convert the value to a binary string and reverse it
            for i, bit in enumerate(bin(value.iloc[0])[:1:-1]):
                if bit == "1":
                    # chr(97) = "a", chr(98) = "b", ...
                    msg = (
                        f"{name} bit '{chr(97 + i)}' is set. "
                        f"See https://wiki.emonio.de/de/Emonio_P3 for more information."
                    )
                    if name == "Warning":
                        log.warning(msg)
                    else:
                        log.error(msg)
                        raise ValueError(msg)


class NodeModbusFactory:
    """
    The NodeModbusFactory is a factory class that creates NodeModbus objects
    with fixed parameters, expect: name, url and mb_channel.

    Has to be initialized with the url of the Emonio.

    It's a helper class for the EmonioConnection to create its modbus nodes.
    It also can be used to manually create a NodeModbus object, which has to be read with a ModbusConnection.
    (not recommended, use the EmonioConnection instead)
    """

    def __init__(self, url: str):
        common = {"url": url, "protocol": "modbus", "mb_byteorder": "big"}
        self.default_params = {
            **common,
            "mb_wordorder": "little",
            "mb_register": "holding",
            "dtype": "float",
            "mb_bit_length": 32,
        }
        self.discrete_input_params = {
            **common,
            "mb_register": "discrete_input",
            "dtype": "bool",
            "mb_bit_length": 1,
        }
        self.warnings_errors_params = {
            **common,
            "mb_register": "holding",
            "dtype": "int",
            "mb_bit_length": 16,
        }

    def __return_nodes(self, name: str, channel: int, params: dict[str, Any]) -> NodeModbus:
        return NodeModbus(name=name, **params, mb_channel=channel)

    def get_default_node(self, name: str, channel: int) -> NodeModbus:
        """
        Create a modbus node for reading Emonio values.

        :param name: Name of the node.
        :param channel: Modbus channel of the node. (Emonio address)

        """
        return self.__return_nodes(name, channel, self.default_params)

    def get_discrete_input_node(self, name: str, channel: int) -> NodeModbus:
        """
        Create a modbus node for reading the connection status of the Emonio phases.

        :param name: Name of the node.
        :param channel: Modbus channel of the node. (Emonio address)
        """
        return self.__return_nodes(name, channel, self.discrete_input_params)

    def get_warnings_errors_node(self, name: str, channel: int) -> NodeModbus:
        """
        Create a modbus node for reading the error and warning registers of the Emonio.

        :param name: Name of the node.
        :param channel: Modbus channel of the node. (Emonio address)
        """
        return self.__return_nodes(name, channel, self.warnings_errors_params)
