import asyncua as opcua
import pytest

from eta_connect.nodes import Node
from eta_connect.servers import OpcuaServer

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
