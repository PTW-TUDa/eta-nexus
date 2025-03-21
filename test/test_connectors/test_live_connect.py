import pytest

from eta_connect import json_import
from eta_connect.connectors import LiveConnect, Node
from eta_connect.servers import OpcUaServer


@pytest.fixture
def nodes_from_config(config_live_connect, config_host_ip):
    config = json_import(config_live_connect["file"])

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
def setup_live_connect(config_live_connect, nodes_from_config, config_host_ip):
    server = OpcUaServer(6)
    server.create_nodes(nodes_from_config)
    server.allow_remote_admin(True)

    config = json_import(config_live_connect["file"])
    config["system"][0]["servers"]["glt"]["url"] = f"{config_host_ip}:4840"

    connector = LiveConnect.from_dict(**config)

    connector.step({"CHP.u": 0})
    connector.deactivate()
    yield connector
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
def test_read(setup_live_connect, values):
    connector = setup_live_connect
    result = connector.read(*values.keys())

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
def test_read_write(setup_live_connect, values):
    connector = setup_live_connect
    connector.write(values)

    result = connector.read(*values.keys())

    assert result == values


def test_set_activate_and_deactivate(setup_live_connect):
    connector = setup_live_connect

    result = connector.step({"u": 0.7})
    assert result == {"CHP.power_elek": 0, "CHP.operation": False, "CHP.control_value_opti": 70}

    result = connector.read("op_request")
    assert result == {"CHP.op_request": True}

    result = connector.step({"u": 0.3})
    assert result == {"CHP.power_elek": 0, "CHP.operation": False, "CHP.control_value_opti": 30}

    result = connector.read("op_request")
    assert result == {"CHP.op_request": False}


def test_close(setup_live_connect):
    connector = setup_live_connect

    connector.write(read_write_values[0])

    connector.close()
    result = connector.read(*read_write_values[0].keys())

    assert result == read_write_values[1]
