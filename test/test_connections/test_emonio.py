import asyncio
from collections.abc import Generator

import pytest

from eta_nexus.connections.emonio_connection import EmonioConnection, ModbusNodeFactory
from eta_nexus.nodes import EmonioNode, Node
from eta_nexus.servers.modbus_server import ModbusServer
from eta_nexus.subhandlers import DFSubHandler

node_values = {
    "Serv.Spannung": 230,
    "Serv.Strom": 2,
    "Serv.Frequenz": 49.984005,
    "Serv.Watt": 460,
    "Serv.Temperature": 25,
}


@pytest.fixture(scope="module")
def local_nodes(config_modbus_port, config_host_ip):
    nodes = []
    for node in node_values:
        nodes.extend(
            EmonioNode.from_dict(
                {
                    "name": node,
                    "ip": config_host_ip,
                    "port": config_modbus_port,
                    "protocol": "emonio",
                    "dtype": "float",
                }
            )
        )
    return nodes


@pytest.fixture(scope="module")
def phase_node(config_modbus_port, config_host_ip):
    return EmonioNode.from_dict(
        {
            "name": "Serv.Spannung Max",
            "ip": config_host_ip,
            "port": config_modbus_port,
            "protocol": "emonio",
            "dtype": "float",
            "phase": "a",
        }
    )[0]


class TestConnectionOperations:
    @pytest.fixture(scope="class", autouse=True)
    def server(self, config_modbus_port, config_host_ip) -> Generator[ModbusServer, None, None]:
        with ModbusServer(ip=config_host_ip, port=config_modbus_port) as server:
            yield server

    @pytest.fixture(scope="class")
    def connection(self, local_nodes) -> EmonioConnection:
        return EmonioConnection.from_node(local_nodes)

    def test_read(self, server, connection):
        modbus_nodes = connection._prepare_modbus_nodes(connection.selected_nodes)
        # Write values to emulated emonio server
        server.write({node: node_values[node.name] for node in modbus_nodes})

        # Read values from emulated emonio server
        data = connection.read()

        # Assert received data, round to 6 decimal places
        data = data.round(6)
        for value_name, expected_value in node_values.items():
            assert value_name in data.columns
            assert data[value_name].to_numpy()[0] == expected_value

    async def write_loop(self, server, node, values):
        for i in range(len(values)):
            server.write({node: values[i]})
            await asyncio.sleep(0.9)

    def test_subscribe(self, server: ModbusServer, connection: EmonioConnection, local_nodes):
        voltage_node = connection._prepare_modbus_nodes(local_nodes[:1])[0]
        voltage_values = [299.5, 230, 230.001]

        handler = DFSubHandler()
        connection.subscribe(handler, interval=1)

        asyncio.get_event_loop().run_until_complete(self.write_loop(server, voltage_node, voltage_values))

        connection.close_sub()

        data = handler.data.round(3)
        assert (voltage_values == data["Serv.Spannung"].to_numpy()).all()

    def test_check_phase(self, connection, phase_node):
        # Set 'connected' for a at address 0 to 1 (True)
        connection._phases_connected = {"a": True, "b": False, "c": False}
        connection._check_phases({phase_node})

    def test_nodes_phase(self, server, phase_node):
        # Set 'connected' for a at address 0 to 1 (True)
        server._server.data_bank.set_discrete_inputs(0, [1])
        # Should not raise an error
        connection = EmonioConnection.from_node(phase_node)  # noqa: F841

    def test_node_phase_error(self, server, phase_node):
        # Set 'connected' for a at address 0 to 0 (False)
        server._server.data_bank.set_discrete_inputs(0, [0])
        expected_error_message = "Phase 'a' is not connected."
        with pytest.raises(ValueError, match=expected_error_message):
            connection = EmonioConnection.from_node(phase_node)  # noqa: F841

    def test_warning_checking(self, server, local_nodes, caplog):
        factory = ModbusNodeFactory(local_nodes[0].url)
        warning_node = factory.get_warnings_errors_node("warning_node", 1001)
        # Set warning bit to 1
        server.write({warning_node: 1})

        connection = EmonioConnection.from_node(local_nodes)
        connection.read()

    def test_error_warning_checking(self, server, local_nodes):
        factory = ModbusNodeFactory(local_nodes[0].url)
        error_node = factory.get_warnings_errors_node("error_node", 1000)
        # Set error bit to 1
        server.write({error_node: 1})

        msg = "Error bit 'a' is set. See https://wiki.emonio.de/de/Emonio_P3 for more information."
        with pytest.raises(ValueError, match=msg):
            connection = EmonioConnection.from_node(local_nodes)  # noqa: F841

        server.write({error_node: 0})  # Reset error bit

    test_nodes = (
        # single node
        (Node("Serv.Spannung", "", "emonio"), [300]),
        (Node("Serv.Spannung Max", "", "emonio", phase="a"), [22]),
        # multiple nodes
        (
            [
                Node("Serv.Spannung", "", "emonio"),
                Node("Serv.strom", "", "emonio"),
                Node("Serv.strom max", "", "emonio", phase="b"),
            ],
            [300, 302, 126],
        ),
    )

    @pytest.mark.parametrize(("nodes", "address"), test_nodes)
    def test_prepare_modbus_nodes(self, connection, nodes, address):
        if isinstance(nodes, Node):
            modbus_nodes = connection._prepare_modbus_nodes({nodes})
            assert len(modbus_nodes) == 1
        else:
            modbus_nodes = connection._prepare_modbus_nodes(nodes)
            assert len(modbus_nodes) == len(nodes)

        for i, node in enumerate(modbus_nodes):
            assert node.protocol == "modbus"
            assert node.mb_register == "holding"
            assert node.mb_byteorder == "big"
            assert node.mb_wordorder == "little"
            assert node.dtype == float
            assert node.mb_bit_length == 32
            assert node.mb_channel == address[i]
