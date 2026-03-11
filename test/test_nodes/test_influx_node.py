import pytest

from eta_nexus.nodes.influx_node import InfluxNode


def test_from_dict_minimal_ok():
    node = InfluxNode._from_dict(
        {
            "name": "temperature",
            "url": "localhost:8086",
            "protocol": "influx",
            "database": "db1",
            "table": "home",
        }
    )
    assert node.database == "db1"
    assert node.table == "home"
    # field is alias of name
    assert node.field == "temperature"
    # url normalized with default scheme from Node
    assert "localhost:8086" in node.url


def test_from_dict_with_field_overrides_name():
    node = InfluxNode._from_dict(
        {
            "name": "ignored",
            "field": "temp_c",
            "url": "localhost:8086",
            "protocol": "influx",
            "database": "db1",
            "table": "home",
        }
    )
    assert node.name == "temp_c"
    assert node.field == "temp_c"


def test_from_dict_missing_database_raises():
    with pytest.raises(KeyError):
        InfluxNode._from_dict({"name": "x", "url": "localhost:8086", "protocol": "influx", "table": "t"})


def test_url_username_password_are_parsed():
    node = InfluxNode(
        "x",
        "https://user:pass@localhost:8086",
        "influx",
        database="db1",
        table="t",
    )
    # credentials parsed into separate fields
    assert node.usr == "user"
    assert node.pwd == "pass"
    # URL is sanitized (no credentials, no "@")
    assert node.url == "https://localhost:8086"
    assert "@" not in node.url


def test_connection_identifier_includes_database():
    a = InfluxNode("a", "localhost:8086", "influx", database="db1", table="t")
    b = InfluxNode("b", "localhost:8086", "influx", database="db2", table="t")
    # The identifier uses netloc + _extra_equality_key (database), so these differ
    assert a.connection_identifier() != b.connection_identifier()
