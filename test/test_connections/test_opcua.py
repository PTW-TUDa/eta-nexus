import asyncio
import datetime

import pandas as pd
import pytest

from eta_nexus.connections import OpcuaConnection
from eta_nexus.nodes import Node
from eta_nexus.servers import OpcuaServer
from eta_nexus.subhandlers import DFSubHandler
from test.conftest import stop_execution

init_tests = (
    (("opc.tcp://someurl:48050", None, None), {}, {"url": "opc.tcp://someurl:48050"}),
    (
        ("opc.tcp://someurl:48050", "someuser", "somepassword"),
        {},
        {"url": "opc.tcp://someurl:48050", "usr": "someuser", "pwd": "somepassword"},
    ),
    (
        ("opc.tcp://usr:pwd@someurl:48050", "someuser", "somepassword"),
        {},
        {"url": "opc.tcp://someurl:48050", "usr": "someuser", "pwd": "somepassword"},
    ),
    (("opc.tcp://usr:pwd@someurl:48050",), {}, {"url": "opc.tcp://someurl:48050", "usr": "usr", "pwd": "pwd"}),
    (
        ("opc.tcp://usr:pwd@someurl:48050",),
        {
            "nodes": (
                Node(
                    "Serv.NodeName",
                    "opc.tcp://someurl:48050",
                    "opcua",
                    usr="auser",
                    pwd="apassword",
                    opc_id="ns=6;s=.Test_Namespace.Node.Drehzahl",
                ),
            )
        },
        {"url": "opc.tcp://someurl:48050", "usr": "usr", "pwd": "pwd"},
    ),
    (
        ("opc.tcp://someurl:48050",),
        {
            "nodes": (
                Node(
                    "Serv.NodeName",
                    "opc.tcp://someurl:48050",
                    "opcua",
                    usr="auser",
                    pwd="apassword",
                    opc_id="ns=6;s=.Test_Namespace.Node.Drehzahl",
                ),
            )
        },
        {"url": "opc.tcp://someurl:48050", "usr": "auser", "pwd": "apassword"},
    ),
)


@pytest.mark.parametrize(("args", "kwargs", "expected"), init_tests)
def test_init(args, kwargs, expected):
    connection = OpcuaConnection(*args, **kwargs)

    for key, value in expected.items():
        assert getattr(connection, key) == value


init_nodes = (
    (
        Node(
            "Serv.NodeName",
            "opc.tcp://someurl:48050",
            "opcua",
            usr="auser",
            pwd="apassword",
            opc_id="ns=6;s=.Test_Namespace.Node.Drehzahl",
        ),
        {},
        {"url": "opc.tcp://someurl:48050", "usr": "auser", "pwd": "apassword"},
    ),
    (
        Node(
            "Serv.NodeName",
            "opc.tcp://someurl:48050",
            "opcua",
            usr="auser",
            pwd="apassword",
            opc_id="ns=6;s=.Test_Namespace.Node.Drehzahl",
        ),
        {"usr": "another", "pwd": "pwd"},
        {"url": "opc.tcp://someurl:48050", "usr": "auser", "pwd": "apassword"},
    ),
    (
        Node(
            "Serv.NodeName",
            "opc.tcp://someurl:48050",
            "opcua",
            opc_id="ns=6;s=.Test_Namespace.Node.Drehzahl",
        ),
        {"usr": "another", "pwd": "pwd"},
        {"url": "opc.tcp://someurl:48050", "usr": "another", "pwd": "pwd"},
    ),
)


@pytest.mark.parametrize(("node", "kwargs", "expected"), init_nodes)
def test_init_fromnodes(node, kwargs, expected):
    connection = OpcuaConnection.from_node(node, **kwargs)

    for key, value in expected.items():
        assert getattr(connection, key) == value


init_ids = (
    (
        (["ns=6;s=.Some_Namespace.Node1", "ns=6;s=.Test_Namespace.Node2"], "opc.tcp://127.0.0.1:4840"),
        {"url": "opc.tcp://127.0.0.1:4840"},
    ),
    (
        (
            ["ns=6;s=.Some_Namespace.Node1", "ns=6;s=.Test_Namespace.Node2"],
            "opc.tcp://127.0.0.1:4840",
            "user",
            "password",
        ),
        {"url": "opc.tcp://127.0.0.1:4840", "usr": "user", "pwd": "password"},
    ),
)


@pytest.mark.parametrize(("args", "expected"), init_ids)
def test_init_fromids(args, expected):
    connection = OpcuaConnection.from_ids(*args)

    for key, value in expected.items():
        assert getattr(connection, key) == value


init_fail = (
    (
        ("opc.tcp://someurl:48050",),
        {
            "nodes": (
                Node(
                    "Serv.NodeName",
                    "opc.tcp://someotherurl:48050",
                    "opcua",
                    opc_id="ns=6;s=.Test_Namespace.Node.Drehzahl",
                ),
            )
        },
        "Some nodes to read from/write to must be specified",
    ),
    (
        ("someurl:48050",),
        {},
        "Given URL is not a valid OPC url",
    ),
)


@pytest.mark.parametrize(("args", "kwargs", "expected"), init_fail)
def test_init_fail(args, kwargs, expected):
    with pytest.raises(ValueError, match=expected):
        OpcuaConnection(*args, **kwargs)


read = (
    (
        (
            Node(
                "Serv.NodeName",
                "opc.tcp://127.0.0.1:4840",
                "opcua",
                opc_id="ns=6;s=.Some_Namespace.Node1",
            ),
        ),
        pd.DataFrame(data={"Serv.NodeName": 2858.00000}, index=[datetime.datetime.now()]),
    ),
    (
        (
            Node(
                "Serv.NodeName",
                "opc.tcp://127.0.0.1:4840",
                "opcua",
                opc_id="ns=6;s=.Some_Namespace.Node1",
            ),
            Node(
                "Serv.NodeName2",
                "opc.tcp://127.0.0.1:4840",
                "opcua",
                opc_id="ns=6;s=.Some_Namespace.Node1",
            ),
        ),
        pd.DataFrame(data={"Serv.NodeName": 2858.00000, "Serv.NodeName2": 2858.00000}, index=[datetime.datetime.now()]),
    ),
    (
        (
            Node(
                "Serv.NodeName",
                "opc.tcp://127.0.0.1:4840",
                "opcua",
                opc_id="ns=6;s=.Some_Namespace.Node1",
            ),
            Node(
                "Serv.NodeName2",
                "opc.tcp://10.10.0.1:4840",
                "opcua",
                opc_id="ns=6;s=.Some_Namespace.Node1",
            ),
        ),
        pd.DataFrame(data={"Serv.NodeName": 2858.00000}, index=[datetime.datetime.now()]),
    ),
)

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
        "name": "Serv.NodeName4",
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


class TestConnectionOperations:
    @pytest.fixture(autouse=True)
    def server(self, config_host_ip):
        with OpcuaServer(5, ip=config_host_ip) as server:
            yield server

    @pytest.fixture(scope="class")
    def connection(self, local_nodes):
        connection: OpcuaConnection = OpcuaConnection.from_node(local_nodes, usr="admin", pwd="0")
        return connection

    values = ((0, 1.5), (1, 5), (2, "something"))

    @pytest.mark.parametrize(("index", "value"), values)
    def test_write_node(self, server: OpcuaServer, connection: OpcuaConnection, local_nodes, index, value):
        server.create_nodes(local_nodes)
        connection.write({local_nodes[index]: value})

        assert server.read(local_nodes[index]).iloc[0, 0] == value

    @pytest.mark.parametrize(("index", "expected"), values)
    def test_read_node(self, server: OpcuaServer, connection: OpcuaConnection, local_nodes, index, expected):
        server.create_nodes(local_nodes)
        server.write({local_nodes[index]: expected})
        val = connection.read(local_nodes[index])

        assert val.iloc[0, 0] == expected
        assert val.columns[0] == local_nodes[index].name

    def test_read_fail(self, server, connection: OpcuaConnection, local_nodes):
        n = local_nodes[0]
        server.create_nodes(local_nodes)
        fail_node = Node(n.name, n.url, n.protocol, usr=n.usr, pwd=n.pwd, opc_id="ns=6;s=AnotherNamespace.DoesNotExist")
        with pytest.raises(ConnectionError, match=".*BadNodeIdUnknown.*"):
            connection.read(fail_node)

    def test_login_fail_write(self, server, local_nodes):
        n = local_nodes[0]
        server.create_nodes(local_nodes)
        connection = OpcuaConnection.from_node(n, usr="another", pwd="something")
        with pytest.raises(ConnectionError, match=".*BadUserAccessDenied.*"):
            connection.write({n: 123})

    def test_login_fail_read(self, server: OpcuaServer, local_nodes):
        n = local_nodes[0]
        connection = OpcuaConnection.from_node(n, usr="another", pwd="something")

        # Create a new user manager that rejects all users
        from asyncua.server.user_managers import UserManager

        class BadUserManager(UserManager):
            # Reject all users and return None instead of a user object
            def get_user(self, iserver, username=None, password=None, certificate=None):
                return None

        # Set the user manager
        server._server.aio_obj.iserver.set_user_manager(user_manager=BadUserManager())

        with pytest.raises(ConnectionError, match=".*BadUserAccessDenied.*"):
            connection.read(n)


class TestConnectionSubscriptions:
    values = {
        "Serv.NodeName": (1.5, 2, 2.5, 1, 1.1, 3.4, 6.5, 7.1),
        "Serv.NodeName2": (5, 3, 4, 2, 3, 6, 3, 2),
        "Serv.NodeName4": ("something", "some1", "some2", "something else", "different", "1", "2", "3"),
    }

    @pytest.fixture(scope="class", autouse=True)
    def server(self, local_nodes, config_host_ip):
        with OpcuaServer(5, ip=config_host_ip) as server:
            server.create_nodes(local_nodes)
            yield server

    async def write_loop(self, server, local_nodes, values):
        await asyncio.sleep(0.5)
        for i in range(len(values["Serv.NodeName"])):
            server.write({node: values[node.name][i] for node in local_nodes})
            await asyncio.sleep(0.5)

    def test_subscribe(self, local_nodes, server):
        connection = OpcuaConnection.from_node(local_nodes, usr="admin", pwd="0")
        handler = DFSubHandler(write_interval=0.5)
        connection.subscribe(handler, interval=0.5)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.write_loop(server, local_nodes, self.values))

        # How many values are allowed to be missing in the dataframe
        max_missing_values = 2

        # Remove NaN
        data = handler.data.dropna()

        # Check if all values are in the dataframe
        for node, values in self.values.items():
            for value in values:
                try:
                    assert value in data[node].array
                except AssertionError:
                    max_missing_values -= 1
                    if max_missing_values < 0:
                        raise

        connection.close_sub()

    @pytest.fixture
    def _write_nodes_interrupt(self, server: OpcuaServer, local_nodes):
        async def write_loop(server: OpcuaServer, local_nodes, values):
            i = 0
            while True:
                if i == 3:
                    server.stop()
                elif 3 < i < 6:
                    pass
                elif i == 6:
                    server.start()
                else:
                    try:
                        server.write(
                            {node: values[node.name][i % len(values[local_nodes[0].name])] for node in local_nodes}
                        )
                    except ConnectionError:
                        pass

                # Index should fall back to one if the number of provided values is exceeded.
                i += 1
                await asyncio.sleep(1)

        asyncio.get_event_loop().create_task(write_loop(server, local_nodes, self.values))

    @pytest.mark.usefixtures("_write_nodes_interrupt")
    def test_subscribe_interrupted(self, local_nodes, caplog):
        connection: OpcuaConnection = OpcuaConnection.from_node(local_nodes, usr="admin", pwd="0")
        handler = DFSubHandler(write_interval=1)
        connection.subscribe(handler, interval=1)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(stop_execution(25))
        connection.close_sub()

        for node, values in self.values.items():
            # Check whether Dataframe contains NaN
            assert pd.isna(handler.data[node]).any()

            assert set(handler.data[node].dropna()) <= set(values)

        # Check if connection was actually interrupted during the test.
        messages_found = 0
        for message in caplog.messages:
            if "Error while checking connection" in message or "Retrying to connect to opc" in message:
                messages_found += 1

        assert messages_found >= 2, "Error while interrupting the connection, test could not be executed reliably."


nodes_interval_to_check = (
    {
        "name": "Serv.NodeName",
        "port": 4840,
        "protocol": "opcua",
        "opc_id": "ns=6;s=.Some_Namespace.NodeFloat",
        "dtype": "float",
        "interval": 2,
    },
    {
        "name": "Serv.NodeName2",
        "port": 4840,
        "protocol": "opcua",
        "opc_id": "ns=6;s=.Some_Namespace.NodeInt",
        "dtype": "int",
        "interval": 2,
    },
    {
        "name": "Serv.NodeName4",
        "port": 4840,
        "protocol": "opcua",
        "opc_id": "ns=6;s=.Some_Namespace.NodeStr",
        "dtype": "str",
        "interval": 2,
    },
)


@pytest.fixture(scope="module")
def local_nodes_interval_checking(config_host_ip):
    _nodes = []
    for node in nodes_interval_to_check:
        _nodes.extend(Node.from_dict({**node, "ip": config_host_ip}))

    return _nodes


class TestConnectionSubscriptionsIntervalChecker:
    values = {
        "Serv.NodeName": (
            1.5,
            2,
            2.5,
        ),
        "Serv.NodeName2": (
            5,
            3,
            4,
        ),
        "Serv.NodeName4": (
            "something",
            "some1",
            "some2",
        ),
    }

    @pytest.fixture(scope="class", autouse=True)
    def server(self, local_nodes_interval_checking, config_host_ip):
        with OpcuaServer(5, ip=config_host_ip) as server:
            server.create_nodes(local_nodes_interval_checking)
            yield server

    @pytest.fixture
    def _write_nodes_interval_checking(self, server: OpcuaServer, local_nodes_interval_checking):
        async def write_loop(server: OpcuaServer, local_nodes_interval_checking, values):
            i = 0
            while True:
                if i <= 2:
                    try:
                        server.write({node: values[node.name][0] for node in local_nodes_interval_checking})
                    except ConnectionError:
                        pass
                else:
                    try:
                        server.write({node: values[node.name][1] for node in local_nodes_interval_checking})
                    except ConnectionError:
                        pass

                i += 1
                await asyncio.sleep(1)

        asyncio.get_event_loop().create_task(write_loop(server, local_nodes_interval_checking, self.values))

    @pytest.mark.usefixtures("_write_nodes_interval_checking")
    def test_subscribe_interval_checking(self, local_nodes_interval_checking, caplog):
        connection: OpcuaConnection = OpcuaConnection.from_node(local_nodes_interval_checking, usr="admin", pwd="0")
        handler = DFSubHandler(write_interval=1)
        connection.subscribe(handler, interval=1)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(stop_execution(10))
        connection.close_sub()

        for node, values in self.values.items():
            assert set(handler.data[node]) <= set(values)

        # Check if interval checker was actually raised a warning message during the test.
        messages_found = 0
        for message in caplog.messages:
            if "The subscription connection for" in message:
                messages_found += 1

        assert messages_found >= 3, "Error while testing the interval checker, test could not be executed reliably."
