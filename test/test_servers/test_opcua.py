from pathlib import Path

import asyncua as opcua
import pytest

from eta_nexus.nodes import Node
from eta_nexus.servers import OpcuaServer
from eta_nexus.servers.loaders.opcua_server_loader import load_opcua_servers_from_config

nodes = (
    {
        "name": "Serv.NodeName",
        "port": 4840,
        "protocol": "opcua",
        "opc_id": "ns=6;s=.Some_Namespace.NodeFloat",
        "dtype": "float",
    },
    {
        "name": "Serv.NodeName2",
        "port": 4840,
        "protocol": "opcua",
        "opc_id": "ns=6;s=.Some_Namespace.NodeInt",
        "dtype": "int",
    },
    {
        "name": "Serv.NodeName2",
        "port": 4840,
        "protocol": "opcua",
        "opc_id": "ns=6;s=.Some_Namespace.NodeStr",
        "dtype": "str",
    },
)


@pytest.fixture(scope="module")
def local_nodes(config_host_ip):
    _nodes = []
    for node in nodes:
        _nodes.extend(Node.from_dict({**node, "ip": config_host_ip}))

    return _nodes


def test_init():
    try:
        server = OpcuaServer(5, ip="127.0.0.1")
        assert server._server.aio_obj.bserver._server._serving is True  # Check session can be created
    finally:
        server.stop()

    # Check session is closed
    assert server._server.aio_obj.bserver._server._serving is False


def test_init_with():
    with OpcuaServer(5, ip="127.0.0.1") as server:
        assert server._server.aio_obj.bserver._server._serving is True  # Check session can be created

    # Check session is closed
    assert server._server.aio_obj.bserver._server._serving is False


class TestServerOperations:
    @pytest.fixture(scope="class")
    def server(self, config_host_ip):
        with OpcuaServer(5, ip=config_host_ip) as server:
            yield server

    def test_active(self, server: OpcuaServer):
        assert server.active is True

    def test_get_invalid_node(self, server: OpcuaServer):
        with pytest.raises(
            opcua.ua.uaerrors.BadNodeIdUnknown, match="The node id refers to a node that does not exist"
        ):
            server._server.get_node("s=something").get_value()

    def test_create_nodes(self, server: OpcuaServer, local_nodes):
        server.create_nodes(local_nodes)

        for node in local_nodes:
            server._server.get_node(node.opc_id).get_value()

    def test_create_node_with_missing_dot(self, server: OpcuaServer, local_nodes):
        node = local_nodes[0]
        missing_node = Node(
            node.name, node.url, node.protocol, usr=node.usr, pwd=node.pwd, opc_id="ns=6;s=thermal_power"
        )
        server.create_nodes({missing_node})

        for _ in local_nodes:
            server._server.get_node(missing_node.opc_id).get_value()

    values = ((0, 1.5), (1, 5), (2, "something"))

    @pytest.mark.parametrize(("index", "value"), values)
    def test_write_node(self, server: OpcuaServer, local_nodes, index, value):
        server.create_nodes({local_nodes[index]})
        server.write({local_nodes[index]: value})

        assert server._server.get_node(local_nodes[index].opc_id).get_value() == value

    @pytest.mark.parametrize(("index", "expected"), values)
    def test_read_node(self, server: OpcuaServer, local_nodes, index, expected):
        server.create_nodes({local_nodes[index]})
        server.write({local_nodes[index]: expected})
        val = server.read(local_nodes[index])

        assert val.iloc[0, 0] == expected
        assert val.columns[0] == local_nodes[index].name

    def test_delete_nodes(self, server: OpcuaServer, local_nodes):
        server.create_nodes(local_nodes)
        server.delete_nodes(local_nodes)

        with pytest.raises(RuntimeError, match=".*BadNodeIdUnknown.*"):
            server.read(local_nodes)


class TestOpcuaServerFromConfigFile:
    """
    Tests loading OPCUA Servers from connection manager yaml file.
    """

    @pytest.fixture(scope="class", params=["yaml", "toml", "json"])
    def servers_from_config(self, request):
        extension = request.param
        config_path = f"./test/resources/connection_manager/config.{extension}"
        assert Path(config_path).exists(), f"{config_path} does not exist."

        servers = load_opcua_servers_from_config(config_path)
        yield servers

        # Cleanup after tests
        for s in servers:
            s.stop()

    def test_servers_started(self, servers_from_config):
        for s in servers_from_config:
            assert s.active is True

    def test_servers_have_nodes(self, servers_from_config):
        """
        Verify that nodes configured in yaml are created and can be read from.
        """
        for s in servers_from_config:
            try:
                val_df = s.read()
                assert not val_df.empty, "No variables found in server; s.read() returned empty DataFrame."
            except Exception as e:
                raise AssertionError(f"Failed to read from server {s.url}. Error: {e}") from e

    @pytest.mark.parametrize(("index", "value"), [(0, 3.14), (1, 42), (2, "new_str_val")])
    def test_write_node(self, servers_from_config, index, value):
        for s in servers_from_config:
            s.write({s.nodes[index]: value})
            actual = s._server.get_node(s.nodes[index].opc_id).get_value()
            assert actual == value, f"Expected {value}, got {actual}"

    @pytest.mark.parametrize(("index", "expected"), [(0, 3.14), (1, 42), (2, "new_str_val")])
    def test_read_node(self, servers_from_config, index, expected):
        for s in servers_from_config:
            s.write({s.nodes[index]: expected})
            val_df = s.read(s.nodes[index])
            assert val_df.iloc[0, 0] == expected
            assert val_df.columns[0] == s.nodes[index].name

    def test_delete_nodes(self, servers_from_config):
        for s in servers_from_config:
            s.delete_nodes(s.nodes)
            with pytest.raises(RuntimeError, match=".*BadNodeIdUnknown.*"):
                s.read(s.nodes)
