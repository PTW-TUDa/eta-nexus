import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest
from attrs import validators
from dateutil import tz

from eta_nexus.connections import ForecastsolarConnection
from eta_nexus.nodes import ForecastsolarNode
from test.utilities.vcr.forecast_solar import _scrub_request, _scrub_response, custom_matcher

DUMMY_API_TOKEN = "A1B2C3D4E5F6G7H8"


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
            name="node_forecast_solar4",
            url=config_forecast_solar["url"],
            protocol="forecast_solar",
            latitude=49.86381,
            longitude=8.68105,
            declination=[14, 10, 10],
            azimuth=[90, -90, 90],
            kwp=[23.31, 23.31, 23.31],
        ),
    }


@pytest.fixture
def connection(scope="module"):
    with ForecastsolarConnection() as connection:
        yield connection


@pytest.fixture
def api_token_in_environment():
    with patch.dict(os.environ, {"FORECAST_SOLAR_API_TOKEN": DUMMY_API_TOKEN}):
        yield DUMMY_API_TOKEN


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


def test_coordinate_rounding():
    node = ForecastsolarNode.from_dict(
        {
            "name": "node_forecast_solar_coordinates_rounding",
            "ip": "",
            "protocol": "forecast_solar",
            "endpoint": "estimate",
            "latitude": "51.151324",
            "longitude": 10.00006,
            "declination": 20,
            "azimuth": 0,
            "kwp": 12.34,
        }
    )[0]

    assert node.latitude == 51.1513
    assert node.longitude == 10.0001


def test_api_key_from_environment(forecast_solar_nodes, api_token_in_environment):
    connection = ForecastsolarConnection.from_node(forecast_solar_nodes["node2"])

    assert connection._api_token == api_token_in_environment, "API Token was not taken from environment!"


def test_api_key_from_keyword(forecast_solar_nodes, api_token_in_environment):
    connection = ForecastsolarConnection.from_node(forecast_solar_nodes["node"], api_token="A9B9C9D9E9F9G9H9")
    assert connection._api_token == "A9B9C9D9E9F9G9H9", (
        "Keyword argument '_api_token' does not overwrite environment variable!"
    )


def test_no_api_key_in_environment(forecast_solar_nodes, monkeypatch):
    # Check that key is None if env-variable is not set.
    monkeypatch.delenv("FORECAST_SOLAR_API_TOKEN", raising=False)
    connection = ForecastsolarConnection.from_node(forecast_solar_nodes["node3"])
    assert connection._api_token is None


@pytest.mark.live
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


@pytest.mark.cache_enabled
def test_cached_responses(forecast_solar_nodes: dict[str, ForecastsolarNode], caplog: pytest.LogCaptureFixture):
    # Test connection from node
    node = forecast_solar_nodes["node"]
    connection: ForecastsolarConnection = ForecastsolarConnection.from_node(node)

    url, query_params = node.url, node._query_params
    for i in range(10):
        response = connection._raw_request("GET", url, params=query_params, headers=connection._headers)
        if i == 0 and response is None and "429" in caplog.text:
            pytest.skip("Rate limit reached")
        elif i != 0:
            assert response.from_cache is True


def pytest_recording_configure(config, vcr):
    """Register the custom matcher using pytest-recording hook."""
    vcr.register_matcher("api_cleaned_uri", custom_matcher)
    vcr.match_on = ["api_cleaned_uri"]


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "allow_playback_repeats": True,
        "before_record_request": _scrub_request,
        "before_record_response": _scrub_response,
    }


@pytest.fixture(autouse=True)
def assert_all_vcr_responses_used(vcr, record_mode):
    yield
    if vcr is not None and record_mode == "none":
        unused_responses = [index + 1 for index in range(len(vcr)) if vcr.play_counts[index] == 0]
        assert not unused_responses, f"Unused VCR responses: {unused_responses}"


class TestPremiumConnectionOperations:
    def test_multiple_planes_require_api_token(self, forecast_solar_nodes, monkeypatch):
        monkeypatch.delenv("FORECAST_SOLAR_API_TOKEN", raising=False)
        node = forecast_solar_nodes["node4"]

        assert node.url == (
            "https://api.forecast.solar/estimate/watts/49.8638/8.6811/14/90/23.31/10/-90/23.31/10/90/23.31"
        )
        with pytest.raises(ValueError, match="valid API key is needed for multiple planes"):
            ForecastsolarConnection.from_node(node)

        connection = ForecastsolarConnection.from_node(node, api_token=DUMMY_API_TOKEN)
        assert isinstance(connection, ForecastsolarConnection)
        assert connection.selected_nodes == {node}
        assert connection._api_token == DUMMY_API_TOKEN

    @pytest.mark.block_network
    @pytest.mark.vcr(before_record_request=_scrub_request, before_record_response=_scrub_response)
    def test_read_multiple_planes(self, forecast_solar_nodes):
        node = forecast_solar_nodes["node4"]
        connection = ForecastsolarConnection.from_node(
            node, api_token=os.environ.get("FORECAST_SOLAR_API_TOKEN") or DUMMY_API_TOKEN
        )

        start = datetime(2026, 8, 4, 10, 0)
        result = connection.read_series(start, start + timedelta(hours=2), interval=timedelta(minutes=15))

        assert list(result.columns) == [node.name]
        assert not result.empty
        assert (result[node.name] > 0).any()


@pytest.mark.block_network
@pytest.mark.vcr(before_record_request=_scrub_request, before_record_response=_scrub_response)
class TestPublicConnectionOperations:
    def test_raw_connection(self, connection: ForecastsolarConnection):
        get_url = connection._baseurl + "/help"

        result = connection._raw_request("GET", get_url)

        assert result.status_code == 200, "Connection failed"

    def test_read(self, forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection):
        result = connection.read(forecast_solar_nodes["node"])

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (1, 1), "The result has the wrong size of data"

    def test_read_series(self, forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection):
        start = datetime(2024, 9, 18, 12, 0)
        end = start + timedelta(days=4)
        interval = timedelta(minutes=15)

        res = connection.read_series(
            start,
            end,
            forecast_solar_nodes["node"],
            interval,
        )

        assert isinstance(res, pd.DataFrame)
        assert res.index.tzinfo == tz.tzlocal(), "The index should be timezone aware"
        assert res.shape == (385, 1), "The result has the wrong size of data"

    def test_select_data_keeps_datetime_index_for_utc_bounds(self, connection: ForecastsolarConnection):
        index = pd.date_range("2026-02-17 07:00", periods=3, freq="1h", tz=connection._local_tz)
        values = pd.DataFrame({"pv": [0.0, 1.0, 2.0]}, index=index)

        selected, _ = connection._select_data(
            values,
            datetime(2026, 2, 17, 6, tzinfo=UTC),
            datetime(2026, 2, 17, 8, tzinfo=UTC),
        )

        assert isinstance(selected.index, pd.DatetimeIndex)
        assert selected.index.tz == connection._local_tz

    def test_read_data_types(
        self, forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection
    ):
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
            assert res.shape in [(385, 1), (5, 1)], f"Data shape for data type '{data_type}' is incorrect"

    def test_read_multiple_nodes(
        self, forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection
    ):
        n = forecast_solar_nodes["node"]
        nodes = [
            n,
            n.evolve(name="node_forecast_solar2", declination=30, azimuth=90, kwp=10),
            n.evolve(name="node_forecast_solar3", latitude=37.6, longitude=-116.8),
        ]

        start = datetime(2024, 9, 18, 12, 0)
        end = start + timedelta(hours=2)
        interval = timedelta(minutes=1)

        result = connection.read_series(start, end, nodes, interval)

        assert isinstance(result, pd.DataFrame)
        assert len(result.columns) == len(nodes), "The result has the wrong number of columns"
        assert result.shape == (121, len(nodes)), "The result has the wrong size of data"

    def test_connection_from_node(self, forecast_solar_nodes: dict[str, ForecastsolarNode], monkeypatch):
        monkeypatch.delenv("FORECAST_SOLAR_API_TOKEN", raising=False)
        node = forecast_solar_nodes["node3"]
        connection = ForecastsolarConnection.from_node(node)

        assert isinstance(connection, ForecastsolarConnection)
        assert connection.selected_nodes == {node}

        start = datetime(2026, 8, 4, 10, 0)
        result = connection.read_series(start, start + timedelta(hours=2), interval=timedelta(minutes=15))

        assert list(result.columns) == [node.name]
        assert not result.empty
        assert (result[node.name] > 0).any()

    def test_watt_functions(
        self, forecast_solar_nodes: dict[str, ForecastsolarNode], connection: ForecastsolarConnection
    ):
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
