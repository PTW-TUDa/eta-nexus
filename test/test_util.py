import json
import logging
import pathlib
import textwrap
from datetime import datetime, timezone

import pytest
from dateutil import tz

from eta_nexus.util import (
    SelfsignedKeyCertPair,
    dict_search,
    load_config,
    log_add_filehandler,
    round_timestamp,
)


def test_from_config(config_connection_manager):
    file = pathlib.Path(config_connection_manager["file"])

    config_json = load_config(file.with_suffix(".json"))
    config_toml = load_config(file.with_suffix(".toml"))
    config_yaml = load_config(file.with_suffix(".yaml"))

    assert config_json == config_toml == config_yaml


def test_load_config_respects_explicit_extension(tmp_path: pathlib.Path):
    """
    If a path with an extension is given, load that file ONLY,
    even if siblings with other extensions exist.
    """

    (tmp_path / "config.json").write_text(json.dumps({"a": 2}))
    (tmp_path / "config.toml").write_text("a = 3")
    (tmp_path / "config.yaml").write_text("a: 1")

    out = load_config(tmp_path / "config.yaml")
    assert out == {"a": 1}


def test_load_config_without_extension_searches_known_types(tmp_path: pathlib.Path):
    """
    If no extension is provided, the loader should search known extensions.
    Here we only create TOML to make the behavior unambiguous.
    """
    (tmp_path / "config.toml").write_text("a = 42")

    out = load_config(tmp_path / "config")  # no suffix
    assert out == {"a": 42}


def test_load_config_unsupported_extension_raises(tmp_path: pathlib.Path):
    (tmp_path / "settings.ini").write_text("[section]\na=1\n")
    with pytest.raises(ValueError, match=r"(?i)(unsupported|unknown).*(ext|extension|file type)"):
        load_config(tmp_path / "settings.ini")


def test_load_config_non_mapping_raises(tmp_path: pathlib.Path):
    # YAML list instead of dict
    (tmp_path / "list.yaml").write_text(
        textwrap.dedent("""\
        - 1
        - 2
    """)
    )
    with pytest.raises(TypeError, match="dict"):
        load_config(tmp_path / "list.yaml")


def test_log_file_handler():
    log_path = pathlib.Path("test_log.log")
    log = log_add_filehandler(log_path, level=3)
    log.info("Info")
    log.error("Error")

    with log_path.open() as f:
        log_content = f.read()

    assert "Info" not in log_content
    assert "Error" in log_content

    logging.shutdown()
    log.handlers.clear()
    log_path.unlink()


def test_log_file_handler_no_path(caplog):
    log = log_add_filehandler(None, level=3)

    assert "No filename specified for filehandler. Using default filename eta_nexus" in caplog.text
    assert "eta_nexus" in log.handlers[-1].baseFilename

    logging.shutdown()
    pathlib.Path(log.handlers[-1].baseFilename).unlink()
    log.handlers.clear()


@pytest.mark.parametrize(
    ("datetime_str", "interval", "expected"),
    [
        ("2016-01-01T02:02:02", 1, "2016-01-01T02:02:02"),
        ("2016-01-01T02:02:02", 60, "2016-01-01T02:03:00"),
        ("2016-01-01T02:02:00", 60, "2016-01-01T02:02:00"),
        ("2016-01-01T02:02:02", 60 * 60, "2016-01-01T03:00:00"),
        ("2016-01-01T02:00:00", 60 * 60, "2016-01-01T02:00:00"),
    ],
)
def test_round_timestamp(datetime_str, interval, expected):
    dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")

    result = round_timestamp(dt, interval, ensure_tz=False).isoformat(sep="T", timespec="seconds")

    assert result == expected


@pytest.mark.parametrize(
    ("datetime_str", "interval", "timezone", "expected", "expected_timezone"),
    [
        ("2016-01-01T02:02:02", 1, None, "2016-01-01T02:02:02", tz.tzlocal()),
        ("2016-01-01T02:02:02", 1, timezone.utc, "2016-01-01T02:02:02", timezone.utc),
        ("2016-01-01T02:02:02", 60, timezone.utc, "2016-01-01T02:03:00", timezone.utc),
        ("2016-01-01T02:02:02", 60 * 60, timezone.utc, "2016-01-01T03:00:00", timezone.utc),
    ],
)
def test_round_timestamp_with_timezone(datetime_str, interval, timezone, expected, expected_timezone):
    """Check if datetime object has the correct timezone after rounding"""
    dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone)
    dt_expected = datetime.strptime(expected, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=expected_timezone)

    result = round_timestamp(dt, interval)

    assert result == dt_expected


def test_dict_search():
    assert dict_search({"key": "value"}, "value") == "key"


def test_dict_search_fail():
    with pytest.raises(ValueError, match=r".*not specified in specified dictionary"):
        dict_search({}, "value")


def test_selfsignedkeycertpair_empty():
    with SelfsignedKeyCertPair("opc_client").tempfiles() as tempfiles:
        assert tempfiles is not None


def test_selfsignedkeycertpair():
    keycert_pair = SelfsignedKeyCertPair(
        common_name="opc_client",
        country="DE",
        province="HE",
        city="Darmstadt",
        organization="TU Darmstadt",
    )
    with keycert_pair.tempfiles() as tempfiles:
        assert tempfiles is not None


def test_selfsignedkeycertpair_fail():
    # with pytest.raises(ValueError, match=r".*length must be >= 2 and <= 2, but it*"):
    with pytest.raises(ValueError, match=r".*Country name must be a 2 character country code*"):
        SelfsignedKeyCertPair(
            common_name="opc_client",
            country="DEUTSCHLAND",
            province="HESSEN",
            city="Darmstadt",
            organization="TU Darmstadt",
        )
