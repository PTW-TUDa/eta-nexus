import json
import pathlib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
import requests
import requests_cache
from attrs import validators

from eta_nexus.connections import ForecastsolarConnection
from eta_nexus.nodes import ForecastsolarNode, Node
from test.utilities.requests.forecast_solar_request import request


# Sample node
@pytest.fixture
def forecast_solar_nodes(config_forecast_solar: dict[str, str]) -> dict[str, ForecastsolarNode]:
    return {
        "node": ForecastsolarNode(
            name="node_forecast_solar1",
            url=config_forecast_solar["url"],
            protocol="forecast_solar",
            endpoint="estimate",
            latitude=51.15,
            longitude=10.45,
            declination=20,
            azimuth=0,
            kwp=12.34,
        ),
        "node2": ForecastsolarNode(
            name="node_forecast_solar2",
            url=config_forecast_solar["url"],
            protocol="forecast_solar",
            latitude=51.15,
            longitude=10.45,
            declination=20,
            azimuth=0,
            kwp=12.34,
        ),
        "node3": ForecastsolarNode(
            name="node_forecast_solar3",
            url=config_forecast_solar["url"],
            protocol="forecast_solar",
            latitude=51.15,
            longitude=10.45,
            declination=20,
            azimuth=0,
            kwp=12.34,
        ),
        "node4": ForecastsolarNode(
            name="node_forecast_solar3",
            url=config_forecast_solar["url"],
            protocol="forecast_solar",
            api_key="A1B2C3D4E5F6G7H8",
            latitude=49.86381,
            longitude=8.68105,
            declination=[14, 10, 10],
            azimuth=[90, -90, 90],
            kwp=[23.31, 23.31, 23.31],
        ),
    }


@pytest.fixture
def _local_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests_cache.CachedSession, "request", request)


@pytest.fixture
def connection():
    with ForecastsolarConnection() as connection:
        yield connection


def test_node_from_dict():
    nodes = ForecastsolarNode.from_dict(
        [
            {
                "name": "node_forecast_solar1",
                "ip": "",
                "protocol": "forecast_solar",
                "endpoint": "estimate",
                "latitude": 51.15,
                "longitude": 10.45,
                "declination": 20,
                "azimuth": 0,
                "kwp": 12.34,
            },
            {
                "name": "node_forecast_solar2",
                "ip": "",
                "protocol": "forecast_solar",
                "latitude": 51.15,
                "longitude": 10.45,
                "declination": 20,
                "azimuth": 0,
                "kwp": 12.34,
            },
        ]
    )

    for node in nodes:
        assert node.endpoint == "estimate", (
            "Invalid endpoint for the forecastsolar.api, default endpoint is 'estimate'."
        )


@pytest.mark.usefixtures("_local_requests")
def test_raw_connection(connection: ForecastsolarConnection):
    get_url = connection._baseurl + "/help"

    result = connection._raw_request("GET", get_url)

    assert result.status_code == 200, "Connection failed"


@pytest.mark.disable_logging
@pytest.mark.xfail(reason="This test is expected to fail due to rate limiting")
def test_check_route():
    # Check if URL params location and plane are valid
    node = ForecastsolarNode.from_dict(
        {
            "name": "node_forecast_solar1",
            "ip": "",
            "protocol": "forecast_solar",
            "endpoint": "estimate",
            "latitude": 51.15,
            "longitude": 10.45,
            "declination": 20,
            "azimuth": 0,
            "kwp": 12.34,
        }
    )[0]

    assert ForecastsolarConnection.route_valid(node)

    with validators.disabled():
        invalid_node = node.evolve(latitude=91)  # latitude invalid
        assert not ForecastsolarConnection.route_valid(invalid_node)


@pytest.mark.usefixtures("_local_requests")
def test_read(forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection):
    nodes = [forecast_solar_nodes["node"], forecast_solar_nodes["node2"]]
    result = connection.read(nodes)

    assert isinstance(result, pd.DataFrame)
    assert result.shape == (1, 2), "The result has the wrong size of data"


@pytest.mark.usefixtures("_local_requests")
def test_read_series(forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection):
    nodes = [forecast_solar_nodes["node"], forecast_solar_nodes["node2"]]

    start = datetime(2024, 9, 18, 12, 0)
    end = start + timedelta(days=4)
    interval = timedelta(minutes=15)

    res = connection.read_series(
        start,
        end,
        nodes,
        interval,
    )

    assert isinstance(res, pd.DataFrame)
    assert res.shape == (385, 2), "The result has the wrong size of data"
    assert connection._api_token == "None", "The api_key is not set correctly"


@pytest.mark.usefixtures("_local_requests")
def test_read_data_types(forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection):
    start = datetime(2024, 9, 18, 12, 0)
    end = start + timedelta(days=4)
    interval = timedelta(minutes=15)

    data_types = ["watts", "watthours", "watthours/period", "watthours/day"]

    # Test single node with different data types
    node = forecast_solar_nodes["node"]
    for data_type in data_types:
        evolved_node = node.evolve(data=data_type)
        res = connection.read_series(start, end, evolved_node, interval)
        assert res.attrs["name"] == data_type, f"Data type '{data_type}' is not correctly processed"

    # Test multiple nodes with default data type fallback to "watts"
    nodes = [node.evolve(data=data_type) for data_type in data_types]
    res = connection.read_series(start, end, nodes, interval)
    assert res.attrs["name"] == "watts", (
        "Default data type 'watts' is not correctly processed for multiple specifications"
    )

    # Test multiple nodes with explicit data type "watthours"
    nodes = [node.evolve(data="watthours") for node in forecast_solar_nodes.values()]
    res = connection.read_series(start, end, nodes, interval)
    assert res.attrs["name"] == "watthours", "Data type 'watthours' is not correctly processed for multiple nodes"


@pytest.mark.usefixtures("_local_requests")
def test_read_multiple_nodes(forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection):
    api_key = "A1B2C3D4E5F6G7H8"
    n = forecast_solar_nodes["node"].evolve(api_key=api_key)
    nodes = [n]
    nodes.append(n.evolve(declination=30, azimuth=90, kwp=10))
    nodes.append(n.evolve(declination=10, azimuth=60, kwp=40))
    nodes.append(n.evolve(latitude=37.6, longitude=-116.8))

    # Range of possible values for query parameters (except horizon)
    query_params = {
        "no_sun": (0, 1),
        "damping_morning": (0.0, 0.33, 0.99),
        "damping_evening": (0.0, 0.33, 0.99),
        "inverter": (10, 1000),
        "actual": (0, 100, 1000),
    }
    # Create nodes with different query parameters
    for k, v in query_params.items():
        for val in v:
            kwargs = {k: val}
            nodes.append(n.evolve(**kwargs))

    start = datetime(2024, 9, 18, 12, 0)
    end = start + timedelta(hours=2)
    interval = timedelta(minutes=1)

    result = connection.read_series(start, end, nodes, interval)
    assert isinstance(result, pd.DataFrame)
    assert len(result.columns) == len(nodes), "The result has the wrong number of columns"


@pytest.mark.usefixtures("_local_requests")
def test_connection_from_node(forecast_solar_nodes: dict[str, Node]):
    # Test connection from node
    nodes = [forecast_solar_nodes["node3"], forecast_solar_nodes["node4"]]
    start = datetime(2024, 9, 18, 12, 0)
    end = start + timedelta(hours=2)
    interval = timedelta(minutes=1)

    connection = ForecastsolarConnection.from_node(nodes)
    result = connection.read_series(start, end, nodes, interval)

    assert connection._baseurl is not None, "Base URL is empty"
    assert result.shape == (121, 2)


@pytest.mark.usefixtures("_local_requests")
def test_watt_functions(forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection):
    # Test watt processing functions
    start_time = "2024-11-11 07:30:00"
    end_time = "2024-11-11 16:15:00"
    freq = "15min"

    index = pd.date_range(start=start_time, end=end_time, freq=freq, tz="tzlocal()")
    sample_data = [
        70.28282828282829,
        142.0,
        261.0,
        382.0,
        514.0,
        650.0,
        797.0,
        978.0,
        1164.0,
        1288.0,
        1317.0,
        1304.0,
        1311.0,
        1351.0,
        1414.0,
        1469.0,
        1521.0,
        1560.0,
        1576.0,
        1590.0,
        1597.0,
        1592.0,
        1573.0,
        1544.0,
        1514.0,
        1485.0,
        1447.0,
        1402.0,
        1353.0,
        1297.0,
        1223.0,
        1149.0,
        1062.0,
        976.0,
        876.0,
        654.0,
    ]
    result = pd.DataFrame(sample_data, index=index)
    result.attrs["name"] = "watts"

    # Calculate watt_hours_period, watt_hours and combine the data
    watt_hours_period = ForecastsolarConnection.calculate_watt_hours_period(result)
    watt_hours = ForecastsolarConnection.cumulative_watt_hours_per_day(watt_hours_period)
    sum_watt_hours = ForecastsolarConnection.summarize_watt_hours_per_day(watt_hours_period)
    assert watt_hours_period.attrs["name"] == "watthours/period"
    assert watt_hours.attrs["name"] == "watthours"
    assert sum_watt_hours.attrs["name"] == "watthours/day"
    assert watt_hours.equals(ForecastsolarConnection.cumulative_watt_hours_per_day(result, from_unit="watts"))
    assert sum_watt_hours.equals(ForecastsolarConnection.summarize_watt_hours_per_day(result, from_unit="watts"))
    with pytest.raises(ValueError, match="Invalid unit:"):
        ForecastsolarConnection.cumulative_watt_hours_per_day(result, from_unit="watthours")
    with pytest.raises(ValueError, match="Invalid unit:"):
        ForecastsolarConnection.summarize_watt_hours_per_day(result, from_unit="watthours")


@pytest.mark.usefixtures("_local_requests")
def test_watt_processing(connection: ForecastsolarConnection, forecast_solar_nodes: dict[str, Node]):
    node = forecast_solar_nodes["node"].evolve(latitude=49, longitude=8)
    start = datetime(2024, 11, 11, 7, 30)
    end = start + timedelta(days=6) + timedelta(hours=9)
    interval = timedelta(minutes=15)
    result = connection.read_series(start, end, node, interval)
    assert result.attrs["name"] == "watts", "Data type 'watts' is not correctly processed"

    # Load expected response
    sample_dir = pathlib.Path(__file__).parent.parent / "utilities/requests"
    with (sample_dir / "forecast_solar_full_data.json").open() as f:
        exp_response = json.load(f)

    # Convert expected response to DataFrame
    exp_hours_day = pd.Series(exp_response.pop("watt_hours_day"))
    exp_response = pd.DataFrame(exp_response)
    exp_response.index = pd.to_datetime(exp_response.index).tz_convert(connection._local_tz)

    # Calculate watt_hours_period, watt_hours and combine the data
    watt_hours_period = connection.calculate_watt_hours_period(result)
    watt_hours = connection.cumulative_watt_hours_per_day(watt_hours_period)
    combined_watt_data = pd.concat([result, watt_hours_period, watt_hours], axis=1)

    # Check if the data is close to the expected response
    tolerance = 0.05
    joined_data = combined_watt_data.align(exp_response, join="inner", axis=0)
    is_close_matrix = np.isclose(*joined_data, rtol=tolerance)  # boolean matrix of close values
    assert np.mean(is_close_matrix) > 0.95, "Too many values differ significantly from the expected response"

    # Check if the watt_hours_day is close to the expected response
    watt_hours_day = connection.summarize_watt_hours_per_day(watt_hours_period)
    assert np.allclose(watt_hours_day[node.name], exp_hours_day, rtol=tolerance)


def test_cached_responses(forecast_solar_nodes: dict[str, Node]):
    # Test connection from node
    node = forecast_solar_nodes["node"]
    connection: ForecastsolarConnection = ForecastsolarConnection.from_node(node)

    url, query_params = node.url, node._query_params
    for i in range(10):
        try:
            response = connection._raw_request("GET", url, params=query_params, headers=connection._headers)
            if i != 0:
                assert response.from_cache is True
        except requests.exceptions.HTTPError as e:
            if i == 0 and e.response.status_code == 429:
                pytest.skip("Rate limit reached")
