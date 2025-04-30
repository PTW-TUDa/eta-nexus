import pytest

from eta_nexus import json_import
from eta_nexus.connection_manager import ConnectionManager
from eta_nexus.nodes import Node
from eta_nexus.servers import OpcuaServer


@pytest.fixture
def nodes_from_config(config_connection_manager, config_host_ip):
    config = json_import(config_connection_manager["file"])

    # Combine config for nodes with server config
    for n in config["system"][0]["nodes"]:
        server = config["system"][0]["servers"][n["server"]]
        if "usr" in server and "pwd" in server:
            n["url"] = f"https://{server['usr']}:{server['pwd']}@{config_host_ip}:4840"
        else:
            n["url"] = f"https://{config_host_ip}:4840"
        n["protocol"] = server["protocol"]

    return Node.from_dict(config["system"][0]["nodes"])


@pytest.fixture
def setup_connection_manager(config_connection_manager, nodes_from_config, config_host_ip):
    server = OpcuaServer(6)
    server.create_nodes(nodes_from_config)
    server.allow_remote_admin(allow=True)

    config = json_import(config_connection_manager["file"])
    config["system"][0]["servers"]["glt"]["url"] = f"{config_host_ip}:4840"

    connection = ConnectionManager.from_dict(**config)

    connection.step({"CHP.u": 0})
    connection.deactivate()
    yield connection
    server.stop()


read_values = (
    {
        "CHP.opti_mode": True,
        "CHP.control_mode": True,
        "CHP.control_value": True,
        "CHP.op_request": False,
    },
)


@pytest.mark.parametrize(("values"), read_values)
def test_read(setup_connection_manager, values):
    connection = setup_connection_manager
    result = connection.read(*values.keys())

    assert result == values


read_write_values = (
    (
        {
            "CHP.opti_mode": True,
            "CHP.op_request": True,
            "CHP.control_mode": True,
            "CHP.control_value": True,
            "CHP.control_mode_opti": 1,
            "CHP.control_value_opti": 70,
        }
    ),
    (
        {
            "CHP.opti_mode": False,
            "CHP.op_request": False,
            "CHP.control_mode": False,
            "CHP.control_value": False,
            "CHP.control_mode_opti": 0,
            "CHP.control_value_opti": 0,
        }
    ),
)


@pytest.mark.parametrize(("values"), read_write_values)
def test_read_write(setup_connection_manager, values):
    connection = setup_connection_manager
    connection.write(values)

    result = connection.read(*values.keys())

    assert result == values


def test_set_activate_and_deactivate(setup_connection_manager):
    connection = setup_connection_manager

    result = connection.step({"u": 0.7})
    assert result == {"CHP.power_elek": 0, "CHP.operation": False, "CHP.control_value_opti": 70}

    result = connection.read("op_request")
    assert result == {"CHP.op_request": True}

    result = connection.step({"u": 0.3})
    assert result == {"CHP.power_elek": 0, "CHP.operation": False, "CHP.control_value_opti": 30}

    result = connection.read("op_request")
    assert result == {"CHP.op_request": False}


def test_close(setup_connection_manager):
    connection = setup_connection_manager

    connection.write(read_write_values[0])

    connection.close()
    result = connection.read(*read_write_values[0].keys())

    assert result == read_write_values[1]
