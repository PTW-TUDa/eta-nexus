import pathlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import requests_cache
from lxml import etree

from eta_connect.connectors import ENTSOEConnection, Node
from eta_connect.connectors.entso_e import _ConnectionConfiguration
from eta_connect.util import dict_search, round_timestamp

ENTSOE_TOKEN = ""


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
    if ENTSOE_TOKEN == "":
        monkeypatch.setattr(requests_cache.CachedSession, "post", Postable(config_entsoe["path"]))


multiple_nodes_expected = [
    ((create_node("Price", "name1"), create_node("Price", "name2")), 2),
    ((create_node("ActualGenerationPerType", "Node1"), create_node("ActualGenerationPerType", "Node2")), 19),
]


def test_entsoe_price_ahead():
    node = create_node("Price")

    server = ENTSOEConnection.from_node(node, api_token=ENTSOE_TOKEN)

    from_datetime = datetime.strptime("2022-02-15T13:18:12", "%Y-%m-%dT%H:%M:%S")
    to_datetime = datetime.strptime("2022-02-15T14:15:31", "%Y-%m-%dT%H:%M:%S")

    res = server.read_series(from_time=from_datetime, to_time=to_datetime)
    assert isinstance(res, pd.DataFrame)
    assert isinstance(res.columns, pd.MultiIndex)
    assert isinstance(res.index, pd.DatetimeIndex)
    assert node.name in res.columns.get_level_values(0)[0]


def test_entsoe_actual_generation_per_type():
    node = create_node("ActualGenerationPerType")

    server = ENTSOEConnection.from_node(node, api_token=ENTSOE_TOKEN)

    from_datetime = datetime.strptime("2022-02-15T13:18:12", "%Y-%m-%dT%H:%M:%S")
    to_datetime = datetime.strptime("2022-02-15T14:00:00", "%Y-%m-%dT%H:%M:%S")

    res = server.read_series(from_time=from_datetime, to_time=to_datetime)
    assert isinstance(res, pd.DataFrame)
    assert isinstance(res.columns, pd.MultiIndex)
    assert isinstance(res.index, pd.DatetimeIndex)
    assert node.name in res.columns.get_level_values(0)[0]


def test_entsoe_timezone():
    node = create_node("Price", "Node1")

    server = ENTSOEConnection.from_node(node, api_token=ENTSOE_TOKEN)

    from_datetime = datetime(2022, 2, 15, 13, 18, 12, tzinfo=timezone.utc)
    to_datetime = datetime(2022, 2, 15, 14, 15, 31, tzinfo=timezone.utc)
    res = server.read_series(from_time=from_datetime, to_time=to_datetime)
    # Compare with correct reference values from entso-e
    assert res.iloc[0, 0] == 126.93
    assert res.iloc[-1, 0] == 158.61
    assert res.iloc[0, 1] == 149.28
    assert res.iloc[-1, 1] == 157.27

    from_datetime = datetime(2022, 2, 15, 13, 18, 12, tzinfo=timezone(timedelta(hours=-12)))  # 16.02 01:18:12 UTC
    to_datetime = datetime(2022, 2, 15, 14, 15, 31, tzinfo=timezone(timedelta(hours=-12)))  # 16.02 02:15:31 UTC
    res = server.read_series(from_time=from_datetime, to_time=to_datetime)
    # Compare with correct reference values from entso-e
    assert res.iloc[0, 0] == 71.91
    assert res.iloc[-1, 0] == 83.85
    assert res.iloc[0, 1] == 99.45
    assert res.iloc[-1, 1] == 106.67


@pytest.mark.parametrize(("nodes", "number_of_columns_per_node"), multiple_nodes_expected)
def test_multiple_nodes(nodes, number_of_columns_per_node):
    "Check if multiple nodes return a dataframe with all nodes concatenated"

    from_datetime = datetime.strptime("2022-02-15T13:18:12", "%Y-%m-%dT%H:%M:%S")
    to_datetime = datetime.strptime("2022-02-15T14:15:31", "%Y-%m-%dT%H:%M:%S")

    server = ENTSOEConnection.from_node(nodes, api_token=ENTSOE_TOKEN)
    res = server.read_series(from_time=from_datetime, to_time=to_datetime)

    assert isinstance(res, pd.DataFrame)
    assert isinstance(res.columns, pd.MultiIndex)
    assert isinstance(res.index, pd.DatetimeIndex)
    assert number_of_columns_per_node * len(nodes) == res.shape[1]


@pytest.mark.parametrize("interval", [1, 2, 3])
def test_interval(interval):
    """Considering interval of one second, should return
    the number of seconds between from_time and to_time
    """
    node = create_node("Price")

    server = ENTSOEConnection.from_node(node, api_token=ENTSOE_TOKEN)

    from_datetime = datetime.strptime("2022-02-15T13:18:12", "%Y-%m-%dT%H:%M:%S")
    to_datetime = datetime.strptime("2022-02-15T14:15:31", "%Y-%m-%dT%H:%M:%S")

    res = server.read_series(from_time=from_datetime, to_time=to_datetime, interval=interval)
    number_of_resolutions = len(res.columns.levels[1])

    total_timestamps = (
        round_timestamp(to_datetime, interval) - round_timestamp(from_datetime, interval)
    ).total_seconds() // interval + 1
    assert total_timestamps * number_of_resolutions == res.shape[0] * res.shape[1]


@pytest.mark.parametrize("end_time", ["2022-02-15T23:30:00", "2022-02-16T23:00:00", "2022-02-16T22:59:00"])
def test_multiple_days(end_time):
    """Entsoe delivers multiple days in different TimeSeries-tags.
    Check if these timeseries are concatenated correctly.
    """
    interval = 900
    node = create_node("Price")

    server = ENTSOEConnection.from_node(node, api_token=ENTSOE_TOKEN)

    from_datetime = datetime.strptime("2022-02-15T13:18:12", "%Y-%m-%dT%H:%M:%S")
    to_datetime = datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S")

    res = server.read_series(from_time=from_datetime, to_time=to_datetime, interval=interval)
    number_of_resolutions = len(res.columns.levels[1])

    total_timestamps = (
        round_timestamp(to_datetime, interval) - round_timestamp(from_datetime, interval)
    ).total_seconds() // interval + 1
    assert total_timestamps * number_of_resolutions == res.shape[0] * res.shape[1]


class MockResponse(requests_cache.CachedResponse):
    def __init__(self, endpoint: str, path: pathlib.Path):
        super().__init__()
        self.status_code = 200
        self.endpoint = endpoint
        self.path = path

    @property
    def content(self):
        with pathlib.Path(self.path / f"{self.endpoint}_sample.xml").open() as f:
            return f.read().encode()


class Postable:
    def __init__(self, path):
        self.path = path

    def __call__(self, url, data, headers, **kwargs):
        parser = etree.XMLParser(load_dtd=False, ns_clean=True, remove_pis=True)
        e_msg = etree.XML(data, parser)
        ns = e_msg.nsmap

        endpoint_code = (
            e_msg.find(".//AttributeInstanceComponent", namespaces=ns).find("attributeValue", namespaces=ns).text
        )
        doc_types = _ConnectionConfiguration().doc_types

        endpoint = dict_search(doc_types, endpoint_code)

        return MockResponse(endpoint, self.path)
