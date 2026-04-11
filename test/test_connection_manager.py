from typing import Any

import pytest

from eta_nexus import json_import
from eta_nexus.connection_manager import ConnectionManager
from eta_nexus.nodes import Node
from eta_nexus.servers import OpcuaServer
from eta_nexus.util import load_config
from eta_nexus.util.type_annotations import Path, TimeStep


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
def opcua_test_server(nodes_from_config):
    with OpcuaServer(6, port=4840) as server:
        server.create_nodes(nodes_from_config)
        yield server


@pytest.fixture(scope="module")
def setup_connection_manager(opcua_test_server, config_connection_manager, nodes_from_config, config_host_ip):
    if not opcua_test_server.active:
        opcua_test_server.start()
    opcua_test_server.allow_remote_admin(allow=True)

    config = json_import(config_connection_manager["file"])
    config["system"][0]["servers"]["glt"]["url"] = f"{config_host_ip}:4840"

    connection = ConnectionManager.from_dict(**config)

    connection.step({"CHP.u": 0})
    connection.deactivate()
    yield connection
    opcua_test_server.stop()


def test_from_string_config(config_connection_manager, opcua_test_server, config_host_ip, monkeypatch):
    def _from_config_patched(
        *files: Path,
        step_size: TimeStep = 1,
        max_error_count: int = 10,
    ) -> ConnectionManager:
        """
        Patched version of ConnectionManager.from_config(). The patch replaces the OPCUA-Server URL
        specified in the config.json with the actual URL from the Test-Runtime.
        """
        main_config: dict[str, list[Any]] = {"system": []}
        for file_path in files:
            config = load_config(file_path)
            if not isinstance(config, dict):
                raise TypeError("Config file must define a dictionary of options.")
            if "system" in config:
                main_config["system"].extend(config["system"])
            else:
                main_config["system"].append(config)

        # Patching: Replace config Server URL with actual URL.
        main_config["system"][0]["servers"]["glt"]["url"] = f"{config_host_ip}:4840"

        return ConnectionManager.from_dict(**main_config, step_size=step_size, max_error_count=max_error_count)

    path = config_connection_manager["file"]
    # Monkey-Patch ConnectionManager config loading mechanism to adapt Server URL to current host
    monkeypatch.setattr(ConnectionManager, "from_config", _from_config_patched, raising=True)
    if not opcua_test_server.active:
        opcua_test_server.start()
    ConnectionManager.from_config(str(path))
    opcua_test_server.stop()


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


read_observe_values = (
    {
        "CHP.control_value_opti": 0.0,
        "CHP.operation": False,
        "CHP.power_elek": 0.0,
    },
)


@pytest.mark.parametrize(("values"), read_observe_values)
def test_read_default(setup_connection_manager, values):
    connection = setup_connection_manager
    result = connection.read()

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
