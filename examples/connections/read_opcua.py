from __future__ import annotations

from typing import TYPE_CHECKING

from eta_nexus.connections import OpcuaConnection
from eta_nexus.nodes import OpcuaNode
from eta_nexus.subscription_handlers import DFSubscriptionHandler

if TYPE_CHECKING:
    import pandas as pd


def read_opcua() -> pd.DataFrame:
    # --begin_opcua_doc_read--
    # Identify a node by its full node id. Alternatively, a node can be identified by
    # namespace and path (opc_ns=6, opc_path_str=".Some_Namespace.Speed"), see write_opcua below.
    node = OpcuaNode(
        name="Speed",
        url="opc.tcp://10.0.0.1:4840",
        protocol="opcua",
        opc_id="ns=6;s=.Some_Namespace.Speed",
    )

    # Create a connection from the node. The default OPC UA port (4840) is added
    # automatically if it is not part of the URL.
    connection = OpcuaConnection.from_node(node)

    if not isinstance(connection, OpcuaConnection):
        raise TypeError("The connection must be an OpcuaConnection to call read.")

    # Read the current value. The result is a pandas.DataFrame with the node name
    # as column and the read time as index.
    return connection.read(node)
    # --end_opcua_doc_read--


def read_opcua_from_ids() -> pd.DataFrame:
    # --begin_opcua_doc_from_ids--
    # If you only need to read and do not want to create node objects yourself,
    # build the connection directly from a list of node ids.
    connection = OpcuaConnection.from_ids(
        ["ns=6;s=.Some_Namespace.Speed", "ns=6;s=.Some_Namespace.Power"],
        url="opc.tcp://10.0.0.1:4840",
        usr="admin",
        pwd="password",
    )

    return connection.read()
    # --end_opcua_doc_from_ids--


def write_opcua() -> None:
    # --begin_opcua_doc_write--
    # Here the node is identified by namespace and path instead of a full node id.
    node = OpcuaNode(
        name="Setpoint",
        url="opc.tcp://10.0.0.1:4840",
        protocol="opcua",
        opc_ns=6,
        opc_path_str=".Some_Namespace.Setpoint",
        usr="admin",
        pwd="password",
        dtype="int",
    )

    connection = OpcuaConnection.from_node(node)

    if not isinstance(connection, OpcuaConnection):
        raise TypeError("The connection must be an OpcuaConnection to call write.")

    # Write a value by passing a mapping of {node: value}.
    connection.write({node: 5})
    # --end_opcua_doc_write--


def subscribe_opcua() -> pd.DataFrame:
    # --begin_opcua_doc_subscribe--
    speed = OpcuaNode(
        name="Speed",
        url="opc.tcp://10.0.0.1:4840",
        protocol="opcua",
        opc_id="ns=6;s=.Some_Namespace.Speed",
        dtype="float",
    )
    power = OpcuaNode(
        name="Power",
        url="opc.tcp://10.0.0.1:4840",
        protocol="opcua",
        opc_id="ns=6;s=.Some_Namespace.Power",
        dtype="float",
    )

    connection = OpcuaConnection.from_node([speed, power])

    if not isinstance(connection, OpcuaConnection):
        raise TypeError("The connection must be an OpcuaConnection to subscribe.")

    # A subscription handler receives new values whenever the server reports a change.
    # The DFSubscriptionHandler stores them in a pandas.DataFrame.
    handler = DFSubscriptionHandler(write_interval=1)
    connection.subscribe(handler, interval=1)

    # ... let the subscription run, then close it again.
    connection.close_sub()

    return handler.data
    # --end_opcua_doc_subscribe--


def main() -> None:
    read_opcua()


if __name__ == "__main__":
    main()
