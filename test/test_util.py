import json
import logging
import pathlib
from datetime import datetime, timezone

import pytest
from dateutil import tz

from eta_connect.util import (
    SelfsignedKeyCertPair,
    dict_search,
    get_logger,
    json_import,
    log_add_filehandler,
    round_timestamp,
)


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

    assert "No filename specified for filehandler. Using default filename eta_connect" in caplog.text
    assert "eta_connect" in log.handlers[-1].baseFilename

    logging.shutdown()
    pathlib.Path(log.handlers[-1].baseFilename).unlink()
    log.handlers.clear()


def test_log_name_deprecation_warning():
    msg = "The 'name' argument is deprecated and will be removed in future versions."
    with pytest.warns(DeprecationWarning, match=msg):
        log = get_logger(name="test")
    # Remove actions of get_logger()
    log.propagate = True
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

    result = round_timestamp(dt, interval, False).isoformat(sep="T", timespec="seconds")

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


def test_remove_comments_json():
    with pathlib.Path(pathlib.Path(__file__).parent / "resources/remove_comments/removed_comments.json").open() as f:
        control = json.load(f)

    assert json_import(pathlib.Path(__file__).parent / "resources/remove_comments/with_comments.json") == control


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
    with pytest.raises(ValueError, match=r".*Country name must be a 2 character country code"):
        SelfsignedKeyCertPair(
            common_name="opc_client",
            country="DEUTSCHLAND",
            province="HESSEN",
            city="Darmstadt",
            organization="TU Darmstadt",
        )
