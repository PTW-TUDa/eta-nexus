from __future__ import annotations

import re

import pandas as pd
import pytest

from eta_nexus.nodes import Node

fail_nodes = (
    (
        {
            "name": "Serv.NodeName",
            "url": "modbus.tcp://10.0.0.1:502",
            "protocol": "modbus",
            "mb_channel": 3861,
            "mb_register": "Holding",
            "mb_slave": 32,
            "mb_byteorder": "someendian",
        },
        "'mb_byteorder' must be in",
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "10.0.0.1:502",
            "protocol": "opcua",
        },
        "Specify opc_id or opc_path_str",
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "10.0.0.1:502",
            "protocol": "something",
        },
        "Specified an unsupported protocol",
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "10.0.0.1:502",
            "protocol": "opcua",
            "opc_id": "somestring",
        },
        "When specifying opc_id, make sure it follows the format ns=2;s=.path",
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "10.0.0.1:502",
            "protocol": "opcua",
            "opc_id": "ns=2;somestring",
        },
        "When specifying opc_id, make sure it follows the format ns=2;s=.path",
    ),
    (  # wetterdienst
        {
            "name": "Serv.NodeName",
            "url": "",
            "protocol": "wetterdienst_observation",
            "parameter": "foo-bar",
            "station_id": "0",
            "interval": "60",
        },
        "Parameter FOO-BAR is not valid. Valid parameters can be found here:"
        "https://wetterdienst.readthedocs.io/en/latest/data/parameters/",
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "",
            "protocol": "wetterdienst_observation",
            "parameter": "HUMIDITY",
            "interval": "60",
        },
        "The required parameter 'station_id' or 'latlon' and 'number_of_stations' for the node configuration "
        "was not found. The node could not load.",
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "",
            "protocol": "wetterdienst_observation",
            "parameter": "temperature_air_mean_2m",
            "station_id": "0",
            "interval": "60",
        },
        re.escape(
            "Parameter TEMPERATURE_AIR_MEAN_2M is not valid for the given resolution. "
            "Valid resolutions for parameter TEMPERATURE_AIR_MEAN_2M are: "
            "['MINUTE_10', 'HOURLY', 'SUBDAILY', 'DAILY', 'MONTHLY', 'ANNUAL']"
        ),
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "",
            "protocol": "wetterdienst_observation",
            "parameter": "temperature_air_mean_2m",
            "station_id": "0",
            "interval": "200",
        },
        re.escape("Interval 200 not supported. Must be one of [60, 300, 600, 3600, 28800, 86400, 2592000, 31536000]"),
    ),
    (
        {
            "name": "Serv.Name1",
            "url": "",
            "protocol": "emonio",
        },
        "Parameter for node Serv.Name1 not found, name is not valid.",
    ),
    (
        {"name": "Serv.Name1", "url": "", "protocol": "emonio", "address": 13},
        "Address 13 for node Serv.Name1 is not valid.",
    ),
    (
        {
            "name": "Serv.Spannung Max",
            "url": "",
            "protocol": "emonio",
        },
        "Phase must be set for MIN/MAX values",
    ),
    # Forecast.Solar
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "api_key": "InvalidKEy",
            "endpoint": "estimate",
            "latitude": "0",
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": 0.0,
        },
        re.escape("'api_key' must be a 16 character long alphanumeric string."),
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "endpoint": "sun.core",
            "latitude": "0",
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": 0,
        },
        re.escape("'endpoint' must be in ('estimate', 'history', 'clearsky') (got 'sun.core')"),
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "endpoint": "estimate",
            "data": "all",
            "latitude": "0",
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": 0,
        },
        re.escape("'data' must be in ('watts', 'watthours', 'watthours/period', 'watthours/day') (got 'all')"),
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "latitude": "0",
            "longitude": -200,
            "declination": 0,
            "azimuth": 0,
            "kwp": 0.0,
        },
        "'longitude' must be >= -180: -200",
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "endpoint": "estimate",
            "latitude": "0",
            "longitude": 0,
            "declination": [0, 1, 2],
            "azimuth": [0, 1, 2],
            "kwp": [0.0, 0.1, 0.4],
        },
        "Valid API key is needed for multiple planes",
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "api_key": "InvalidKEy",
            "endpoint": "estimate",
            "latitude": "0",
            "longitude": 0,
            "declination": [0, 1, 2],
            "azimuth": [0, 1, 2],
            "kwp": [0.0, 0.1, 0.4],
        },
        re.escape("'api_key' must be a 16 character long alphanumeric string."),
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "api_key": "A1B2C3D4E5F6G7H8",  # Test Key
            "latitude": "0",
            "longitude": 0,
            "declination": [0, 1, 2],
            "azimuth": [0, 2],
            "kwp": [0.0, 0.1, 0.4],
        },
        "'declination', 'azimuth' and 'kwp' must be passed for all planes",
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "endpoint": "estimate",
            "latitude": "0",
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": "-200",
        },
        re.escape("'kwp' must be >= 0: -200.0"),
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "latitude": "0",
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": "0",
            "horizon": 1,
        },
        re.escape("'horizon' must be a list, 0 (To suppress horizon usage *at all*) or None"),
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "latitude": "0",
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": "0",
            "horizon": [1, 2, 3],
        },
        re.escape("'horizon' must contain at least 4 values."),
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "latitude": "0",
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": "0",
            "horizon": [1, 2, 3, 4, 5, 6, 7],
        },
        re.escape("'horizon' must be set such that 360 / <your count of horizon values> is an integer."),
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "latitude": "0",
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": "0",
            "horizon": [1, 2, 3, 4, 5, 100],
        },
        re.escape("'horizon' values must be between 0 and 90."),
    ),
)


@pytest.mark.parametrize(("node_data", "error"), fail_nodes)
def test_node_init_failures(node_data: dict[str, str], error: str):
    with pytest.raises(ValueError, match=error):
        Node(**node_data)


@pytest.mark.parametrize(("node_data", "error"), fail_nodes)
def test_node_dict_init_failures(node_data: dict[str, str], error: str):
    with pytest.raises(ValueError, match=error):
        Node.from_dict(node_data)


nodes = (
    (
        {
            "name": "Serv.NodeName",
            "url": "modbus.tcp://10.0.0.1:502",
            "protocol": "modbus",
            "mb_channel": 3861,
            "mb_register": "Holding",
            "mb_slave": 32,
            "mb_byteorder": "BigEndian",
        },
        {
            "name": "Serv.NodeName",
            "url": "modbus.tcp://10.0.0.1:502",
            "protocol": "modbus",
            "mb_channel": 3861,
            "mb_register": "holding",
            "mb_slave": 32,
            "mb_byteorder": "big",
        },
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "opc.tcp://10.0.0.1:48050",
            "protocol": "opcua",
            "opc_id": "ns=6;s=.Some_Namespace.Node1",
        },
        {
            "name": "Serv.NodeName",
            "url": "opc.tcp://10.0.0.1:48050",
            "protocol": "opcua",
            "opc_id": "ns=6;s=.Some_Namespace.Node1",
        },
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "eneffco",
            "eneffco_code": "A_Code",
        },
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "eneffco",
            "eneffco_code": "A_Code",
        },
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "entsoe",
            "endpoint": "Price",
            "bidding_zone": "DE-LU-AT",
        },
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "entsoe",
            "endpoint": "Price",
            "bidding_zone": "DE-LU-AT",
        },
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "10.0.0.1:502",
            "protocol": "modbus",
            "mb_channel": 3861,
            "mb_register": "Holding",
            "mb_slave": 32,
            "mb_byteorder": "big",
        },
        {"url": "modbus.tcp://10.0.0.1:502"},
    ),
    (
        {"name": "Serv.NodeName", "url": "10.0.0.1", "protocol": "opcua", "opc_id": "ns=6;s=.Some_Namespace.Node1"},
        {"url": "opc.tcp://10.0.0.1:4840"},
    ),
    (
        {"name": "Serv.NodeName", "url": "some_url.de/path", "protocol": "eneffco", "eneffco_code": "A_Code"},
        {"url": "https://some_url.de/path"},
    ),
    ({"name": "Serv.NodeName", "url": None, "protocol": "eneffco", "eneffco_code": "A_Code"}, {"url": ""}),
    (
        {"name": "Serv.NodeName", "url": None, "protocol": "local"},
        {"name": "Serv.NodeName", "url": "", "protocol": "local"},
    ),
    (
        {"name": "Serv.NodeName", "url": "", "protocol": "local"},
        {"name": "Serv.NodeName", "url": "", "protocol": "local"},
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "someone:password@some_url.de/path1",
            "protocol": "eneffco",
            "eneffco_code": "A_Code",
        },
        {"url": "https://some_url.de/path1", "usr": "someone", "pwd": "password"},
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "http://someone:password@some_url.de/path",
            "usr": "someoneelse",
            "pwd": "anotherpwd",
            "protocol": "eneffco",
            "eneffco_code": "A_Code",
        },
        {"url": "http://some_url.de/path", "usr": "someoneelse", "pwd": "anotherpwd"},
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "some_url.de/path",
            "usr": "someperson",
            "pwd": "somepwd",
            "protocol": "eneffco",
            "eneffco_code": "A_Code",
        },
        {"url": "https://some_url.de/path", "usr": "someperson", "pwd": "somepwd"},
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "some_url.de/path",
            "protocol": "opcua",
            "opc_id": "NS=4;S=.Some_Namespace.Node3",
        },
        {"protocol": "opcua", "opc_id": "ns=4;s=.Some_Namespace.Node3"},
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "some_url.de/path",
            "protocol": "opcua",
            "opc_id": "NS=4;S=.Some_Namespace.Node3",
            "interval": "42",
        },
        {"protocol": "opcua", "opc_id": "ns=4;s=.Some_Namespace.Node3", "interval": 42},
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "some_url.de/path",
            "usr": "someperson",
            "pwd": "somepwd",
            "protocol": "eneffco",
            "eneffco_code": "A_Code",
            "interval": 42,
        },
        {"url": "https://some_url.de/path", "usr": "someperson", "protocol": "eneffco", "interval": 42},
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "10.0.0.1:502",
            "protocol": "modbus",
            "mb_channel": 3861,
            "mb_register": "Holding",
            "mb_slave": 32,
            "mb_byteorder": "big",
            "interval": "42",
        },
        {
            "url": "modbus.tcp://10.0.0.1:502",
            "interval": 42,
            "mb_slave": 32,
        },
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "entsoe",
            "interval": "42",
            "endpoint": "Price",
            "bidding_zone": "DE-LU-AT",
        },
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "entsoe",
            "interval": 42,
        },
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "wetterdienst_observation",
            "parameter": "temperature_air_mean_2m",
            "interval": "3600",
            "station_id": "00917",
        },
        {
            "url": "https://opendata.dwd.de",
            "parameter": "TEMPERATURE_AIR_MEAN_2M",
            "interval": 3600,
            "station_id": "00917",
        },
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "wetterdienst_prediction",
            "parameter": "temperature_air_mean_2m",
            "mosmix_type": "SMALL",
            "station_id": "K2596",
        },
        {
            "url": "https://opendata.dwd.de",
            "parameter": "TEMPERATURE_AIR_MEAN_2M",
            "mosmix_type": "SMALL",
            "station_id": "K2596",
        },
    ),
    (  # emonio
        {
            "name": "Serv.Spannung",
            "url": "https://some_url.de/path",
            "protocol": "emonio",
        },
        {
            "name": "Serv.Spannung",
            "address": 300,
        },
    ),
    (
        {
            "name": "Serv.Spannung MAX",
            "url": "https://some_url.de/path",
            "protocol": "emonio",
            "phase": "a",
        },
        {
            "name": "Serv.Spannung MAX",
            "address": 22,
            "phase": "a",
        },
    ),
    (
        {
            "name": "Serv.Temperature",
            "url": "https://some_url.de/path",
            "protocol": "emonio",
            "phase": "a",
        },
        {
            "name": "Serv.Temperature",
            "address": 500,
        },
    ),
    (
        {
            "name": "Serv.Temperature",
            "url": "https://some_url.de/path",
            "protocol": "emonio",
            "phase": "a",
        },
        {
            "name": "Serv.Temperature",
            "address": 500,
        },
    ),
    (
        {
            "name": "Serv.NodeName",
            "url": "https://some_url.de/path",
            "protocol": "emonio",
            "phase": "a",
            "address": 310,
        },
        {
            "name": "Serv.NodeName",
            "address": 310,
        },
    ),
    (
        {"name": "Serv.NodeName", "url": None, "interval": 42, "protocol": "local"},
        {
            "name": "Serv.NodeName",
            "interval": 42,
        },
    ),
    # Forecast.Solar
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "api_key": "A1B2C3D4E5F6G7H8",
            "endpoint": "clearsky",
            "latitude": "0",
            "longitude": "0",
            "declination": "0",
            "azimuth": 0.0,
            "kwp": "0",
        },
        {
            "name": "Serv.SolarForecast",
            "url": "https://api.forecast.solar/A1B2C3D4E5F6G7H8/clearsky/watts/0/0/0/0/0.0",
            "protocol": "forecast_solar",
            "api_key": "A1B2C3D4E5F6G7H8",
            "endpoint": "clearsky",
            "data": "watts",
            "latitude": 0,
            "longitude": 0,
            "declination": 0,
            "azimuth": 0,
            "kwp": 0.0,
        },
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "api_key": "A1B2C3D4E5F6G7H8",
            "latitude": 9,
            "longitude": 8,
            "declination": [0, 1, 2],
            "azimuth": [0, 1, 2],
            "kwp": [0, 1, 2],
        },
        {
            "name": "Serv.SolarForecast",
            "url": "https://api.forecast.solar/A1B2C3D4E5F6G7H8/estimate/watts/9/8/0/0/0.0/1/1/1.0/2/2/2.0",
            "api_key": "A1B2C3D4E5F6G7H8",
            "protocol": "forecast_solar",
            "endpoint": "estimate",
            "latitude": 9,
            "longitude": 8,
            "declination": [0, 1, 2],
            "azimuth": [0, 1, 2],
            "kwp": [0.0, 1.0, 2.0],
        },
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "endpoint": "estimate",
            "data": "watts",
            "latitude": 9,
            "longitude": 8,
            "declination": 1,
            "azimuth": 2,
            "kwp": 3,
        },
        {
            "name": "Serv.SolarForecast",
            "url": "https://api.forecast.solar/estimate/watts/9/8/1/2/3.0",
            "protocol": "forecast_solar",
            "endpoint": "estimate",
            "data": "watts",
            "latitude": 9,
            "longitude": 8,
            "declination": 1,
            "azimuth": 2,
            "kwp": 3.0,
        },
    ),
    (
        {
            "name": "Serv.SolarForecast",
            "url": "",
            "protocol": "forecast_solar",
            "api_key": "A1B2C3D4E5F6G7H8",
            "endpoint": "history",
            "latitude": 9,
            "longitude": 8,
            "declination": [0, 1, 2],
            "azimuth": [0, 1, 2],
            "kwp": [0, 1, 2],
        },
        {
            "name": "Serv.SolarForecast",
            "url": "https://api.forecast.solar/A1B2C3D4E5F6G7H8/history/watts/9/8/0/0/0.0/1/1/1.0/2/2/2.0",
            "api_key": "A1B2C3D4E5F6G7H8",
            "protocol": "forecast_solar",
            "endpoint": "history",
            "data": "watts",
            "latitude": 9,
            "longitude": 8,
            "declination": [0, 1, 2],
            "azimuth": [0, 1, 2],
            "kwp": [0.0, 1.0, 2.0],
        },
    ),
)


@pytest.mark.parametrize(("node_data", "expected"), nodes)
def test_node_init(node_data, expected):
    node = Node(**node_data)

    for key, val in expected.items():
        assert getattr(node, key) == val


nodes_from_dict = (
    *nodes,
    (
        {
            "name": "Serv.NodeName",
            "ip": "10.0.0.1",
            "port": 502,
            "protocol": "modbus",
            "mb_channel": 3861,
            "mb_register": "Holding",
            "mb_slave": 32,
            "mb_byteorder": "big",
        },
        {"url": "modbus.tcp://10.0.0.1:502"},
    ),
    (
        {
            "name": "Serv.NodeName",
            "ip": "10.0.0.1",
            "protocol": "opcua",
            "opc_id": "ns=6;s=.Some_Namespace.Node1",
        },
        {"url": "opc.tcp://10.0.0.1:4840"},
    ),
    (
        {
            "name": "Serv.NodeName",
            "ip": "123.123.217.12",
            "port": "321",
            "protocol": "eneffco",
            "eneffco_code": "A_Code",
        },
        {
            "url": "https://123.123.217.12:321",
        },
    ),
)


@pytest.mark.parametrize(("node_data", "expected"), nodes_from_dict)
def test_node_dict_init(node_data, expected):
    node = Node.from_dict(node_data)[0]

    for key, val in expected.items():
        assert getattr(node, key) == val


@pytest.mark.parametrize(("node_data", "expected"), nodes_from_dict)
def test_node_as_dict(node_data, expected):
    node = Node.from_dict(node_data)[0]
    node_dict = node.as_dict()

    for key, val in expected.items():
        assert node_dict.get(key) == val

    # Check for None filter
    node_dict_filtered = node.as_dict(filter_none=True)
    none_values = [key for key, val in node_dict.items() if val is None]

    for key in none_values:
        assert key not in node_dict_filtered


@pytest.mark.parametrize(("node_data", "expected"), nodes_from_dict)
def test_node_as_tuple(node_data, expected):
    node = Node.from_dict(node_data)[0]
    node_tuple = node.as_tuple()

    # For each expected value, check incrementally for representation in tuple,
    # making up for additional unexpected yet acceptable values
    for i, val in enumerate(tuple(expected.values())):
        j = i
        while val != node_tuple[j] and j < len(node_tuple):
            j += 1
        assert val == node_tuple[j], f"Expected {expected} node represented in {node_tuple}"

    # Check for None filter
    node_tuple_filtered = node.as_tuple(filter_none=True)
    none_values = [val for val in node_tuple if val is None]

    for key in none_values:
        assert key not in node_tuple_filtered


@pytest.mark.parametrize(("node_data", "expected"), nodes_from_dict)
def test_node_evolve(node_data, expected):
    parent = Node.from_dict(node_data)[0]
    child = parent.evolve(name="HelloWorld!")

    parent, child = parent.as_dict(), child.as_dict()

    assert child.pop("name") == "HelloWorld!" != parent.pop("name")
    assert child == parent


@pytest.fixture
def create_dictionary():
    nodes = []
    expected = []
    for item in nodes_from_dict:
        nodes.append(item[0])
        expected.append(item[1])

    return nodes, expected


@pytest.fixture
def create_excel(create_dictionary, temp_dir):
    nodes, expected = create_dictionary
    path = temp_dir / "excel_nodes.xlsx"
    pd.DataFrame(data=nodes).to_excel(path, sheet_name="Sheet1")
    return path, expected


def test_node_from_excel(create_excel):
    """Test reading nodes from Excel files and check some parameters of the resulting node objects"""
    path, expected = create_excel
    nodes = Node.from_excel(path, "Sheet1")

    assert len(nodes) == len(expected)

    for idx, item in enumerate(expected):
        for key, value in item.items():
            assert getattr(nodes[idx], key) == value, f"assert {nodes[idx]} == {item}"
