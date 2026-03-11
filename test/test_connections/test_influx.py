from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import eta_nexus.connections.influx_connection as influx_mod
from eta_nexus.nodes.influx_node import InfluxNode


class FakeClient:
    def __init__(self, host, token, database):
        self.host = host
        self.token = token
        self.database = database
        self.queries = []
        self.writes = []

    def query(self, *, query, language, mode, database=None):
        self.queries.append({"query": query, "language": language, "mode": mode, "database": database})
        if query.startswith("LATEST:"):
            _, table, fields_csv = query.split(":")
            fields = fields_csv.split(",") if fields_csv else []
            row = {"time": pd.Timestamp("2024-01-01T00:00:00Z")}
            row.update(dict.fromkeys(fields, 1))
            return pd.DataFrame([row])

        if query.startswith("SERIES:"):
            payload = query[len("SERIES:") :]
            table, fields_csv, _rest = payload.split(":", 2)
            fields = fields_csv.split(",") if fields_csv else []
            times = pd.date_range("2024-01-01T00:00:00Z", periods=3, freq="1h")
            frame = pd.DataFrame({"time": times})
            for f in fields:
                frame[f] = range(len(times))
            return frame

        return pd.DataFrame(columns=["time"])

    def write(self, *, database, record, data_frame_measurement_name):
        self.writes.append(
            {
                "database": database,
                "measurement": data_frame_measurement_name,
                "index_name": getattr(record.index, "name", None),
                "columns": list(record.columns),
                "shape": record.shape,
            }
        )


@pytest.fixture(autouse=True)
def patch_client_and_sql_builders(monkeypatch):
    monkeypatch.setattr(influx_mod, "InfluxDBClient3", FakeClient, raising=True)
    calls = {"latest": [], "series": []}

    def fake_latest(table, fields):
        calls["latest"].append((table, tuple(fields)))
        return f"LATEST:{table}:{','.join(fields)}"

    def fake_series(table, fields, start, end):
        assert start.endswith("Z")
        assert end.endswith("Z")
        calls["series"].append((table, tuple(fields), start, end))
        return f"SERIES:{table}:{','.join(fields)}:{start}:{end}"

    monkeypatch.setattr(influx_mod, "build_latest_select", fake_latest, raising=True)
    monkeypatch.setattr(influx_mod, "build_series_select", fake_series, raising=True)
    return calls


@pytest.fixture
def env_token(monkeypatch):
    monkeypatch.setenv("INFLUXDB3_AUTH_TOKEN", "ENV")


@pytest.fixture
def two_nodes_same_table():
    n1 = InfluxNode("temp_c", "localhost:8086", "influx", database="db1", table="home")
    n2 = InfluxNode("humidity", "localhost:8086", "influx", database="db1", table="home")
    return n1, n2


@pytest.fixture
def two_nodes_diff_tables():
    n1 = InfluxNode("temp_c", "localhost:8086", "influx", database="db1", table="home")
    n2 = InfluxNode("humidity", "localhost:8086", "influx", database="db1", table="home2")
    return n1, n2


# token resolution (ENV first, then pwd)
def test_token_from_env_if_no_kwarg(monkeypatch, two_nodes_same_table):
    monkeypatch.setenv("INFLUXDB3_AUTH_TOKEN", "ENV")
    n1, n2 = two_nodes_same_table
    conn = influx_mod.InfluxConnection.from_node({n1, n2})
    assert conn._client.token == "ENV"


def test_token_falls_back_to_pwd(monkeypatch, two_nodes_same_table):
    monkeypatch.delenv("INFLUXDB3_AUTH_TOKEN", raising=False)
    n1, n2 = two_nodes_same_table
    conn = influx_mod.InfluxConnection.from_node({n1, n2}, pwd="PWD")
    assert conn._client.token == "PWD"


# database resolution
def test_database_from_node_if_not_passed(env_token, two_nodes_same_table):
    n1, n2 = two_nodes_same_table
    conn = influx_mod.InfluxConnection.from_node({n1, n2})
    assert conn.database == "db1"
    assert conn._client.database == "db1"


def test_database_required_if_no_nodes_and_no_env(monkeypatch):
    monkeypatch.delenv("INFLUXDB_DB", raising=False)
    monkeypatch.delenv("INFLUXDB3_AUTH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Database must be provided"):
        influx_mod.InfluxConnection(url="localhost:8086")  # type: ignore[arg-type]


def test_database_from_env_when_no_nodes(monkeypatch):
    monkeypatch.setenv("INFLUXDB_DB", "env_db")
    monkeypatch.setenv("INFLUXDB3_AUTH_TOKEN", "ENV")
    conn = influx_mod.InfluxConnection(url="localhost:8086")  # type: ignore[arg-type]
    assert conn.database == "env_db"
    assert conn._client.database == "env_db"


# read / read_series
def test_read_groups_by_table_and_returns_columns(two_nodes_diff_tables, patch_client_and_sql_builders, env_token):
    n1, n2 = two_nodes_diff_tables
    conn = influx_mod.InfluxConnection.from_node({n1, n2})

    result_frame = conn.read({n1, n2})
    assert set(result_frame.columns) == {"temp_c", "humidity"}
    assert "time" not in result_frame.columns
    assert len(patch_client_and_sql_builders["latest"]) == 2


def test_read_series_uses_utc_z_and_time_index(two_nodes_same_table, patch_client_and_sql_builders, env_token):
    n1, n2 = two_nodes_same_table
    conn = influx_mod.InfluxConnection.from_node({n1, n2})

    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2, minutes=59)
    series_frame = conn.read_series(start, end, {n1, n2})

    assert set(series_frame.columns) == {"temp_c", "humidity"}
    assert isinstance(series_frame.index, pd.DatetimeIndex)
    assert len(patch_client_and_sql_builders["series"]) == 1


# write (point-in-time)
def test_write_one_row_per_table(two_nodes_diff_tables, env_token):
    n1, n2 = two_nodes_diff_tables
    conn = influx_mod.InfluxConnection.from_node({n1, n2})
    conn.write({n1: 1.23, n2: 4.56})

    assert len(conn._client.writes) == 2
    mnames = {w["measurement"] for w in conn._client.writes}
    assert mnames == {"home", "home2"}
    for w in conn._client.writes:
        assert w["database"] == "db1"
        assert w["index_name"] == "time"
        assert w["shape"][0] == 1


def test_write_groups_columns_when_same_table(two_nodes_same_table, env_token):
    n1, n2 = two_nodes_same_table
    conn = influx_mod.InfluxConnection.from_node({n1, n2})
    conn.write({n1: 1.23, n2: 4.56})

    assert len(conn._client.writes) == 1
    w = conn._client.writes[0]
    assert w["measurement"] == "home"
    assert set(w["columns"]) == {"temp_c", "humidity"}


# write series
def test_write_series_mapping(two_nodes_same_table, env_token):
    n1, n2 = two_nodes_same_table
    conn = influx_mod.InfluxConnection.from_node({n1, n2})

    idx = pd.date_range("2024-01-01T00:00:00Z", periods=3, freq="1h")
    s1 = pd.Series([1, 2, 3], index=idx)
    s2 = pd.Series([10, 20, 30], index=idx)

    conn.write_series({n1: s1, n2: s2})
    assert len(conn._client.writes) == 1
    w = conn._client.writes[0]
    assert w["measurement"] == "home"
    assert set(w["columns"]) == {"temp_c", "humidity"}
    assert w["index_name"] == "time"
    assert w["shape"] == (3, 2)


def test_write_series_dataframe(two_nodes_same_table, env_token):
    n1, n2 = two_nodes_same_table
    conn = influx_mod.InfluxConnection.from_node({n1, n2})

    idx = pd.date_range("2024-01-01T00:00:00Z", periods=2, freq="1h")
    input_frame = pd.DataFrame({"temp_c": [1.1, 1.2], "humidity": [50, 55]}, index=idx)

    conn.write_series(input_frame)
    assert len(conn._client.writes) == 1
    w = conn._client.writes[0]
    assert w["measurement"] == "home"
    assert set(w["columns"]) == {"temp_c", "humidity"}
    assert w["shape"] == (2, 2)


def test_write_series_dataframe_unknown_column_raises(two_nodes_same_table, env_token):
    n1, n2 = two_nodes_same_table
    conn = influx_mod.InfluxConnection.from_node({n1, n2})

    idx = pd.date_range("2024-01-01T00:00:00Z", periods=1, freq="1h")
    bad_frame = pd.DataFrame({"unknown": [1]}, index=idx)

    with pytest.raises(ValueError, match="unknown|column"):
        conn.write_series(bad_frame)
