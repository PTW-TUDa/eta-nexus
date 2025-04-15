import asyncio

import pandas as pd
import pytest

from eta_nexus.connections import ModbusConnection
from eta_nexus.nodes import Node
from eta_nexus.servers import ModbusServer
from eta_nexus.subhandlers import DFSubHandler
from test.conftest import stop_execution

init_tests = (
    (("modbus.tcp://someurl:48050", None, None), {}, {"url": "modbus.tcp://someurl:48050"}),
    (
        ("modbus.tcp://someurl:48050", "someuser", "somepassword"),
        {},
        {"url": "modbus.tcp://someurl:48050", "usr": "someuser", "pwd": "somepassword"},
    ),
    (
        ("modbus.tcp://usr:pwd@someurl:48050", "someuser", "somepassword"),
        {},
        {"url": "modbus.tcp://someurl:48050", "usr": "someuser", "pwd": "somepassword"},
    ),
    (("modbus.tcp://usr:pwd@someurl:48050",), {}, {"url": "modbus.tcp://someurl:48050", "usr": "usr", "pwd": "pwd"}),
    (
        ("modbus.tcp://usr:pwd@someurl:48050",),
        {
            "nodes": (
                Node(
                    "Serv.NodeName",
                    "modbus.tcp://someurl:48050",
                    "modbus",
                    usr="auser",
                    pwd="apassword",
                    mb_register="holding",
                    mb_channel=5000,
                    mb_byteorder="big",
                ),
            )
        },
        {"url": "modbus.tcp://someurl:48050", "usr": "usr", "pwd": "pwd"},
    ),
    (
        ("modbus.tcp://someurl:48050",),
        {
            "nodes": (
                Node(
                    "Serv.NodeName",
                    "modbus.tcp://someurl:48050",
                    "modbus",
                    usr="auser",
                    pwd="apassword",
                    mb_register="holding",
                    mb_channel=5000,
                    mb_byteorder="big",
                ),
            )
        },
        {"url": "modbus.tcp://someurl:48050", "usr": "auser", "pwd": "apassword"},
    ),
)


@pytest.mark.parametrize(("args", "kwargs", "expected"), init_tests)
def test_init(args, kwargs, expected):
    connection = ModbusConnection(*args, **kwargs)

    for key, value in expected.items():
        assert getattr(connection, key) == value


init_nodes = (
    (
        Node(
            "Serv.NodeName",
            "modbus.tcp://someurl:48050",
            "modbus",
            usr="auser",
            pwd="apassword",
            mb_register="holding",
            mb_channel=5000,
            mb_byteorder="big",
        ),
        {},
        {"url": "modbus.tcp://someurl:48050", "usr": "auser", "pwd": "apassword"},
    ),
    (
        Node(
            "Serv.NodeName",
            "modbus.tcp://someurl:48050",
            "modbus",
            usr="auser",
            pwd="apassword",
            mb_register="holding",
            mb_channel=5000,
            mb_byteorder="big",
        ),
        {"usr": "another", "pwd": "pwd"},
        {"url": "modbus.tcp://someurl:48050", "usr": "auser", "pwd": "apassword"},
    ),
    (
        Node(
            "Serv.NodeName",
            "modbus.tcp://someurl:48050",
            "modbus",
            mb_register="holding",
            mb_channel=5000,
            mb_byteorder="big",
        ),
        {"usr": "another", "pwd": "pwd"},
        {"url": "modbus.tcp://someurl:48050", "usr": "another", "pwd": "pwd"},
    ),
)


@pytest.mark.parametrize(("node", "kwargs", "expected"), init_nodes)
def test_init_fromnodes(node, kwargs, expected):
    connection = ModbusConnection.from_node(node, **kwargs)

    for key, value in expected.items():
        assert getattr(connection, key) == value


init_fail = (
    (
        ("opc.tcp://someurl:48050",),
        {
            "nodes": (
                Node(
                    "Serv.NodeName",
                    "modbus.tcp://someotherurl:48050",
                    "modbus",
                    mb_channel=3861,
                    mb_register="Holding",
                    mb_slave=32,
                    mb_byteorder="little",
                ),
            )
        },
        "Some nodes to read from/write to must be specified",
    ),
    (
        ("someurl:48050",),
        {},
        "Given URL is not a valid Modbus url",
    ),
)


@pytest.mark.parametrize(("args", "kwargs", "expected"), init_fail)
def test_init_fail(args, kwargs, expected):
    with pytest.raises(ValueError, match=expected):
        ModbusConnection(*args, **kwargs)


def test_modbus_connection_fail():
    """Test modbus failures"""
    node = Node(
        "Serv.NodeName",
        "modbus.tcp://10.0.0.1:502",
        "modbus",
        mb_channel=3861,
        mb_register="Holding",
        mb_slave=32,
        mb_byteorder="big",
    )
    server_fail = ModbusConnection(node.url)

    with pytest.raises(ConnectionError, match="Could not establish connection"):
        server_fail.read(node)


nodes = (
    {
        "name": "Serv.NodeName",
        "protocol": "modbus",
        "mb_channel": 3200,
        "mb_register": "Holding",
        "mb_byteorder": "big",
        "dtype": "float",
    },
    {
        "name": "Serv.NodeName2",
        "protocol": "modbus",
        "mb_channel": 3232,
        "mb_register": "Holding",
        "mb_byteorder": "big",
        "dtype": "int",
    },
    {
        "name": "Serv.NodeName4",
        "protocol": "modbus",
        "mb_channel": 3264,
        "mb_register": "Holding",
        "mb_byteorder": "big",
        "mb_bitlength": 80,
        "dtype": "str",
    },
)


@pytest.fixture(scope="class")
def local_nodes(config_modbus_port, config_host_ip):
    _nodes = []
    for node in nodes:
        _nodes.extend(Node.from_dict({**node, "ip": config_host_ip, "port": config_modbus_port}))

    return _nodes


class TestConnectionOperations:
    @pytest.fixture(scope="class", autouse=True)
    def server(self, config_modbus_port, config_host_ip):
        with ModbusServer(ip=config_host_ip, port=config_modbus_port) as server:
            yield server

    @pytest.fixture(scope="class")
    def connection(self, local_nodes):
        return ModbusConnection.from_node(local_nodes)

    values = ((0, 1.5), (1, 5), (2, " something"))

    @pytest.mark.parametrize(("index", "value"), values)
    def test_write_node(self, server, connection, local_nodes, index, value):
        connection.write({local_nodes[index]: value})

        assert server.read(local_nodes[index]).iloc[0, 0] == value

    @pytest.mark.parametrize(("index", "expected"), values)
    def test_read_node(self, server, connection, local_nodes, index, expected):
        server.write({local_nodes[index]: expected})
        val = connection.read(local_nodes[index])

        assert val.iloc[0, 0] == expected
        assert val.columns[0] == local_nodes[index].name

    def test_read_fail_reg_addr(self, connection, local_nodes):
        n = local_nodes[0]
        fail_node = Node(
            n.name,
            n.url,
            n.protocol,
            mb_channel=129387192,
            mb_register=n.mb_register,
            mb_byteorder=n.mb_byteorder,
            mb_bit_length=n.mb_bit_length,
        )
        with pytest.raises(ValueError, match="reg_addr out of range"):
            connection.read(fail_node)


class TestConnectionOperationsLittleEndian:
    @pytest.fixture(scope="class")
    def local_nodes(self, config_modbus_port, config_host_ip):
        _nodes = []
        for node in nodes:
            _nodes.extend(
                Node.from_dict(
                    {
                        **node,
                        "ip": config_host_ip,
                        "port": config_modbus_port,
                        "mb_byteorder": "little",
                    }
                )
            )

        return _nodes

    @pytest.fixture(scope="class", autouse=True)
    def server(self, config_modbus_port, config_host_ip):
        with ModbusServer(ip=config_host_ip, big_endian=False, port=config_modbus_port) as server:
            yield server

    @pytest.fixture(scope="class")
    def connection(self, local_nodes):
        return ModbusConnection.from_node(local_nodes[0])

    values = ((0, 1.5), (1, 5), (2, " something"))

    @pytest.mark.parametrize(("index", "value"), values)
    def test_write_node(self, server, connection, local_nodes, index, value):
        connection.write({local_nodes[index]: value})

        assert server.read([local_nodes[index]]).iloc[0, 0] == value

    @pytest.mark.parametrize(("index", "expected"), values)
    def test_read_node(self, server, connection, local_nodes, index, expected):
        server.write({local_nodes[index]: expected})
        val = connection.read(local_nodes[index])

        assert val.iloc[0, 0] == expected
        assert val.columns[0] == local_nodes[index].name


class TestConnectionSubscriptions:
    values = {
        "Serv.NodeName": (1.5, 2, 2.5, 1, 1.1, 3.4, 6.5, 7.1),
        "Serv.NodeName2": (5, 3, 4, 2, 3, 6, 3, 2),
        "Serv.NodeName4": (
            " something",
            " thething1",
            " another23",
            " someother",
            " different",
            " 112389223",
            " 285746384",
            " 327338574",
        ),
    }

    @pytest.fixture(scope="class", autouse=True)
    def server(self, local_nodes, config_modbus_port, config_host_ip):
        with ModbusServer(ip=config_host_ip, port=config_modbus_port) as server:
            yield server

    async def write_loop(self, server, local_nodes, values):
        await asyncio.sleep(0.5)
        for i in range(len(values["Serv.NodeName"])):
            server.write({node: values[node.name][i] for node in local_nodes})
            await asyncio.sleep(0.5)

    def test_subscribe(self, local_nodes, server):
        connection = ModbusConnection.from_node(local_nodes, usr="admin", pwd="0")
        handler = DFSubHandler(write_interval=0.5)
        connection.subscribe(handler, interval=0.5)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.write_loop(server, local_nodes, self.values))

        # How many values are allowed to be missing in the dataframe
        max_missing_values = 2

        # Remove NaN values and round to 3 decimal places
        data = handler.data.dropna().round(3)

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
    def _write_nodes_interrupt(self, server, local_nodes):
        async def write_loop(server, local_nodes, values):
            i = 0
            while True:
                if i == 3:
                    server.stop()
                elif 3 < i < 6:
                    pass
                elif i == 6:
                    server.start()
                else:
                    server.write(
                        {node: values[node.name][i % len(values[local_nodes[0].name])] for node in local_nodes}
                    )

                # Index should fall back to one if the number of provided values is exceeded.
                i += 1
                await asyncio.sleep(1)

        asyncio.get_event_loop().create_task(write_loop(server, local_nodes, self.values))

    @pytest.mark.usefixtures("_write_nodes_interrupt")
    def test_subscribe_interrupted(self, local_nodes, caplog):
        connection = ModbusConnection.from_node(local_nodes, usr="admin", pwd="0")
        handler = DFSubHandler(write_interval=1)
        connection.subscribe(handler, interval=1)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(stop_execution(25))
        connection.close_sub()

        for node, values in self.values.items():
            # Check whether Dataframe contains NaN
            assert pd.isna(handler.data[node]).any()

            # Don't check floating point values in this case because it is hard to deal with precision problems here.
            if handler.data[node].dtype == "float":
                continue
            assert set(handler.data[node].dropna()) <= set(values)

        # Check if connection was actually interrupted during the test.
        messages_found = 0
        for message in caplog.messages:
            if "ModbusError 4 at modbus" in message or "Could not establish connection to host" in message:
                messages_found += 1

        assert messages_found >= 2, "Error while interrupting the connection, test could not be executed reliably."


nodes_interval_to_check = (
    {
        "name": "Serv.NodeName",
        "protocol": "modbus",
        "mb_channel": 3200,
        "mb_register": "Holding",
        "mb_byteorder": "big",
        "dtype": "float",
        "interval": 2,
    },
    {
        "name": "Serv.NodeName2",
        "protocol": "modbus",
        "mb_channel": 3232,
        "mb_register": "Holding",
        "mb_byteorder": "big",
        "dtype": "int",
        "interval": 2,
    },
    {
        "name": "Serv.NodeName4",
        "protocol": "modbus",
        "mb_channel": 3264,
        "mb_register": "Holding",
        "mb_byteorder": "big",
        "mb_bitlength": 80,
        "dtype": "str",
        "interval": 2,
    },
)


@pytest.fixture(scope="class")
def local_nodes_interval_checking(config_modbus_port, config_host_ip):
    _nodes = []
    for node in nodes_interval_to_check:
        _nodes.extend(Node.from_dict({**node, "ip": config_host_ip, "port": config_modbus_port}))

    return _nodes


class TestConnectionSubscriptionsIntervalChecker:
    values = {
        "Serv.NodeName": (1.5, 2, 4.5),
        "Serv.NodeName2": (5, 3, 6),
        "Serv.NodeName4": (
            " something",
            " thething1",
            " another23",
        ),
    }

    @pytest.fixture(scope="class", autouse=True)
    def server(self, local_nodes_interval_checking, config_modbus_port, config_host_ip):
        with ModbusServer(ip=config_host_ip, port=config_modbus_port) as server:
            yield server

    @pytest.fixture
    def _write_nodes_interval_checking(self, server, local_nodes_interval_checking):
        async def write_loop(server, local_nodes_interval_checking, values):
            i = 0
            while True:
                if i <= 3:
                    server.write({node: values[node.name][0] for node in local_nodes_interval_checking})
                else:
                    server.write({node: values[node.name][1] for node in local_nodes_interval_checking})

                i += 1
                await asyncio.sleep(1)

        asyncio.get_event_loop().create_task(write_loop(server, local_nodes_interval_checking, self.values))

    @pytest.mark.usefixtures("_write_nodes_interval_checking")
    def test_subscribe_interval_checking(self, local_nodes_interval_checking, caplog):
        connection = ModbusConnection.from_node(local_nodes_interval_checking, usr="admin", pwd="0")
        handler = DFSubHandler(write_interval=1)
        connection.subscribe(handler, interval=1)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(stop_execution(10))
        connection.close_sub()

        for node, values in self.values.items():
            # Don't check floating point values in this case because it is hard to deal with precision problems here.
            if handler.data[node].dtype == "float":
                continue
            assert set(handler.data[node]) <= set(values)

        # Check if interval checker was actually raised a warning message during the test.
        messages_found = 0
        for message in caplog.messages:
            if "The subscription connection for" in message:
                messages_found += 1

        assert messages_found >= 3, "Error while testing the interval checker, test could not be executed reliably."
