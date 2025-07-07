from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from requests.exceptions import HTTPError

from eta_nexus.connections import (
    EneffcoConnection,
    EntsoeConnection,
    ForecastsolarConnection,
)
from eta_nexus.nodes import (
    EntsoeNode,
    ForecastsolarNode,
)


def test_forecastsolar_invalid_token_real_http_error(caplog):
    node = ForecastsolarNode(
        name="Forecastsolar Node",
        url="https://api.forecast.solar",
        protocol="forecast_solar",
        api_key="A1B2C3D4E5F6G7H8",
        latitude=49.86381,
        longitude=8.68105,
        declination=[14],
        azimuth=[90],
        kwp=[23.31],
    )

    conn = ForecastsolarConnection.from_node(node)

    result = conn.read_series(
        from_time=datetime(2024, 5, 7), to_time=datetime(2024, 5, 7, 1), interval=timedelta(minutes=15)
    )
    assert result is not None
    assert "401" in caplog.text


def test_entsoe_http_error_handled(monkeypatch, caplog):
    monkeypatch.setenv("ENTSOE_API_TOKEN", "A1B2C3D4E5F6G7H8")

    node = EntsoeNode(
        name="test",
        url="https://web-api.tp.entsoe.eu/",
        protocol="entsoe",
        endpoint="Price",
        bidding_zone="DEU-LUX",
    )

    conn = EntsoeConnection.from_node(node)

    with caplog.at_level("ERROR"):
        result = conn.read_series(
            from_time=datetime(2024, 5, 1),
            to_time=datetime(2024, 5, 2),
            interval=900,
        )

    assert result is not None
    assert any("HTTPError" in message for message in caplog.messages)


def test_eneffco_json_error_handled(monkeypatch, caplog):
    monkeypatch.setenv("ENEFFCO_API_TOKEN", "A1B2C3D4E5F6G7H8")

    conn = EneffcoConnection.from_ids(
        ["CH1.Elek_U.L1-N", "Pu3.425.ThHy_Q"],
        url="https://someurl.com/",
        usr="wronguser",
        pwd="wrongpass",
    )

    from_time = datetime(2024, 5, 1)
    to_time = datetime(2024, 5, 2)

    with caplog.at_level("ERROR"):
        result = conn.read_series(from_time, to_time)

    assert result is not None
    assert any("JSON parse error" in msg or "Failed to parse JSON" in msg for msg in caplog.messages)


def test_eneffco_http_error_handled(monkeypatch, caplog):
    monkeypatch.setenv("ENEFFCO_API_TOKEN", "A1B2C3D4E5F6G7H8")

    conn = EneffcoConnection.from_ids(
        ["CH1.Elek_U.L1-N"],
        url="https://eneffco.fake",
        usr="test",
        pwd="wrongpass",
    )

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = HTTPError("401 Client Error: Unauthorized")
    mock_response.status_code = 401

    with patch.object(conn._session, "request", return_value=mock_response):
        with caplog.at_level("WARNING"):
            result = conn.read_series(datetime(2024, 5, 1), datetime(2024, 5, 2))

        assert result is not None
        assert any("401 Client Error" in msg for msg in caplog.messages)
