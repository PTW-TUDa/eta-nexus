from __future__ import annotations

from typing import TYPE_CHECKING

from eta_nexus.connections import ModbusConnection
from eta_nexus.nodes import ModbusNode
from eta_nexus.subscription_handlers import DFSubscriptionHandler

if TYPE_CHECKING:
    import pandas as pd


def read_modbus() -> pd.DataFrame:
    # --begin_modbus_doc_read--
    # Create a node describing a single Modbus data point.
    # The default Modbus port (502) is added automatically if it is not part of the URL.
    node = ModbusNode(
        name="Power",
        url="modbus.tcp://10.0.0.1:502",
        protocol="modbus",
        mb_register="holding",  # one of: input, discrete_input, coils, holding
        mb_channel=3200,  # address of the value
        mb_byteorder="big",  # byteorder of the returned value (big or little)
        mb_bit_length=32,  # length of the value in bits (multiple of 16)
        dtype="float",  # python type to decode the raw registers into
    )

    # Create a connection from one or multiple nodes.
    # from_node returns the connection that matches the node's host and protocol.
    connection = ModbusConnection.from_node(node)

    if not isinstance(connection, ModbusConnection):
        raise TypeError("The connection must be a ModbusConnection to call read.")

    # Read the current value of the node. The result is a pandas.DataFrame with the
    # node name as column and the read time as index.
    return connection.read(node)
    # --end_modbus_doc_read--


def write_modbus() -> None:
    # --begin_modbus_doc_write--
    # Only the 'coils' and 'holding' registers can be written to.
    node = ModbusNode(
        name="Setpoint",
        url="modbus.tcp://10.0.0.1:502",
        protocol="modbus",
        mb_register="holding",
        mb_channel=3232,
        mb_byteorder="big",
        dtype="int",
    )

    connection = ModbusConnection.from_node(node)

    if not isinstance(connection, ModbusConnection):
        raise TypeError("The connection must be a ModbusConnection to call write.")

    # Write a value by passing a mapping of {node: value}.
    connection.write({node: 5})
    # --end_modbus_doc_write--


def subscribe_modbus() -> pd.DataFrame:
    # --begin_modbus_doc_subscribe--
    # Multiple nodes on the same server can be combined into a single connection.
    power = ModbusNode(
        name="Power",
        url="modbus.tcp://10.0.0.1:502",
        protocol="modbus",
        mb_register="holding",
        mb_channel=3200,
        mb_byteorder="big",
        dtype="float",
    )
    temperature = ModbusNode(
        name="Temperature",
        url="modbus.tcp://10.0.0.1:502",
        protocol="modbus",
        mb_register="input",
        mb_channel=3232,
        mb_byteorder="big",
        dtype="float",
    )

    connection = ModbusConnection.from_node([power, temperature])

    if not isinstance(connection, ModbusConnection):
        raise TypeError("The connection must be a ModbusConnection to subscribe.")

    # A subscription handler receives the values read in regular intervals.
    # The DFSubscriptionHandler stores them in a pandas.DataFrame.
    handler = DFSubscriptionHandler(write_interval=1)
    connection.subscribe(handler, interval=1)

    # ... let the subscription run, then close it again.
    connection.close_sub()

    return handler.data
    # --end_modbus_doc_subscribe--


def main() -> None:
    read_modbus()


if __name__ == "__main__":
    main()
