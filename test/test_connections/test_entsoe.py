import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import requests_cache

from eta_nexus.connections import EntsoeConnection
from eta_nexus.nodes import Node
from eta_nexus.util import round_timestamp
from test.utilities.requests.entsoe_request import mock_get

USE_API_TOKEN = False


def create_node(endpoint: str, name: str = "Node1") -> Node:
    return Node(
        name,
        "https://web-api.tp.entsoe.eu/",
        "entsoe",
        endpoint=endpoint,
        bidding_zone="DEU-LUX",
    )


@pytest.fixture(autouse=True)
def _local_requests(monkeypatch, config_entsoe):
    if USE_API_TOKEN:
        return
    monkeypatch.setattr(requests_cache.CachedSession, "get", mock_get(config_entsoe["path"]))
    os.environ["ENTSOE_API_TOKEN"] = ""


@pytest.fixture
def connection():
    return EntsoeConnection()


@pytest.mark.parametrize("endpoint", ["Price", "ActualGenerationPerType"])
def test_entsoe_endpoint(connection: EntsoeConnection, endpoint: str):
    node = create_node(endpoint)
    from_datetime = datetime(2022, 2, 15, 13, 18, 12)
    to_datetime = datetime(2022, 2, 15, 14, 15, 31)
    res = connection.read_series(nodes=node, from_time=from_datetime, to_time=to_datetime)
    assert isinstance(res, pd.DataFrame)
    assert isinstance(res.columns, pd.MultiIndex)
    assert isinstance(res.index, pd.DatetimeIndex)
    assert node.name in res.columns.get_level_values(0)[0]


def test_entsoe_timezone(connection: EntsoeConnection):
    node = create_node("Price")

    from_datetime = datetime(2022, 2, 15, 13, 18, 12, tzinfo=timezone.utc)
    to_datetime = datetime(2022, 2, 15, 14, 15, 31, tzinfo=timezone.utc)
    res = connection.read_series(nodes=node, from_time=from_datetime, to_time=to_datetime)
    # Compare with correct reference values from entso-e
    assert res.iloc[0, 0] == 126.93
    assert res.iloc[-1, 0] == 158.61
    assert res.iloc[0, 1] == 149.28
    assert res.iloc[-1, 1] == 157.27

    from_datetime = from_datetime.replace(tzinfo=timezone(timedelta(hours=-12)))  # 16.02 01:18:12 UTC
    to_datetime = to_datetime.replace(tzinfo=timezone(timedelta(hours=-12)))  # 16.02 02:15:31 UTC
    res = connection.read_series(nodes=node, from_time=from_datetime, to_time=to_datetime)
    # Compare with correct reference values from entso-e
    assert res.iloc[0, 0] == 71.91
    assert res.iloc[-1, 0] == 83.85
    assert res.iloc[0, 1] == 99.45
    assert res.iloc[-1, 1] == 106.67


multiple_nodes_expected = [
    ((create_node("Price", "name1"), create_node("Price", "name2")), 2),
    ((create_node("ActualGenerationPerType", "Node1"), create_node("ActualGenerationPerType", "Node2")), 19),
]


@pytest.mark.parametrize(("nodes", "number_of_columns_per_node"), multiple_nodes_expected)
def test_multiple_nodes(connection, nodes, number_of_columns_per_node):
    "Check if multiple nodes return a dataframe with all nodes concatenated"

    from_datetime = datetime(2022, 2, 15, 13, 18, 12)
    to_datetime = datetime(2022, 2, 15, 14, 15, 31)
    res = connection.read_series(nodes=nodes, from_time=from_datetime, to_time=to_datetime)

    assert isinstance(res, pd.DataFrame)
    assert isinstance(res.columns, pd.MultiIndex)
    assert isinstance(res.index, pd.DatetimeIndex)
    assert number_of_columns_per_node * len(nodes) == res.shape[1]


@pytest.mark.parametrize("interval", [1, 2, 3])
def test_interval(connection: EntsoeConnection, interval):
    """Considering interval of one second, should return
    the number of seconds between from_time and to_time
    """
    node = create_node("Price")
    from_datetime = datetime(2022, 2, 15, 13, 18, 12)
    to_datetime = datetime(2022, 2, 15, 14, 15, 31)
    res = connection.read_series(nodes=node, from_time=from_datetime, to_time=to_datetime, interval=interval)

    number_of_resolutions = len(res.columns.levels[1])
    total_timestamps = (
        round_timestamp(to_datetime, interval) - round_timestamp(from_datetime, interval)
    ).total_seconds() // interval + 1
    assert total_timestamps * number_of_resolutions == res.shape[0] * res.shape[1]


@pytest.mark.parametrize("end_time", ["2022-02-15T23:30:00", "2022-02-16T23:00:00", "2022-02-16T22:59:00"])
def test_multiple_days(connection, end_time):
    """Entsoe delivers multiple days in different TimeSeries-tags.
    Check if these timeseries are concatenated correctly.
    """
    interval = 900
    node = create_node("Price")
    from_datetime = datetime.strptime("2022-02-15T13:18:12", "%Y-%m-%dT%H:%M:%S")
    to_datetime = datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S")
    res = connection.read_series(nodes=node, from_time=from_datetime, to_time=to_datetime, interval=interval)

    number_of_resolutions = len(res.columns.levels[1])
    total_timestamps = (
        round_timestamp(to_datetime, interval) - round_timestamp(from_datetime, interval)
    ).total_seconds() // interval + 1
    assert total_timestamps * number_of_resolutions == res.shape[0] * res.shape[1]
