import pandas as pd

from eta_nexus.nodes import EmonioNode


def connection_manager_from_dict(url: str) -> dict[str, float]:
    # --connection_manager--
    from eta_nexus import ConnectionManager

    config = {
        "system": [
            {
                "name": "emonio",
                "servers": {"ac_supply": {"url": url, "protocol": "emonio"}},
                "nodes": [
                    {"name": "V_RMS", "server": "ac_supply"},
                    {"name": "I_RMS", "server": "ac_supply", "phase": "a"},
                ],
            }
        ]
    }
    # Create the connection object with classmethod from_dict
    connection = ConnectionManager.from_dict(1, 10, **config)

    # Read the values of the nodes we defined in the dictionary
    return connection.read("V_RMS", "I_RMS")
    # --connection_manager--


def emonio_manual(url: str) -> pd.DataFrame:
    # --emonio--
    from eta_nexus.connections import EmonioConnection

    voltage_node = EmonioNode("V_RMS", url, "emonio")
    current_node = EmonioNode("I_RMS", url, "emonio", phase="a")

    # Initialize the connection object with both nodes
    connection = EmonioConnection.from_node([voltage_node, current_node])

    # Read values of selected nodes
    return connection.read()
    # --emonio--


def modbus_manual(url: str) -> pd.DataFrame:
    # --modbus--
    from eta_nexus.connections import ModbusConnection
    from eta_nexus.connections.emonio_connection import ModbusNodeFactory

    factory = ModbusNodeFactory(url)

    # V_RMS for all phases
    voltage_node = factory.get_default_node("Spannung", 300)
    # I_RMS for phase a
    current_node = factory.get_default_node("Strom", 2)

    connection = ModbusConnection.from_node([voltage_node, current_node])

    if isinstance(connection, ModbusConnection):
        result = connection.read()
    else:
        raise TypeError("The connection must be an ModbusConnection.")
    # --modbus--
    return result
