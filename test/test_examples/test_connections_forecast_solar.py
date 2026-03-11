import pandas as pd
import pytest

from examples.connections.read_series_forecastsolar import read_series as ex_read_forecast_solar
from test.utilities.vcr.forecast_solar import _scrub_request, _scrub_response, custom_matcher


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


@pytest.mark.block_network
@pytest.mark.vcr
def test_example_read_forecast_solar():
    data = ex_read_forecast_solar()

    assert isinstance(data, pd.DataFrame)
    assert set(data.columns) == {"Forecastsolar Node"}
    assert data.shape == (97, 1)
