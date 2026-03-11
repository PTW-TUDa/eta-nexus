from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from eta_nexus.connections import SmardConnection
from eta_nexus.nodes import SmardNode

# Mark all tests in this module to use pytest-recording (VCR.py) for recording and playing HTTP interactions
pytestmark = [pytest.mark.vcr, pytest.mark.block_network]


@pytest.fixture
def solar_node():
    """Create a test node for solar power."""
    return SmardNode(
        name="solar_test",
        url="https://smard.api.proxy.bund.dev/app",
        protocol="smard",
        filter=4068,  # Photovoltaik
        region="DE",
        resolution="hour",
    )


@pytest.fixture
def solar_node_daily():
    """Create a test node for solar power with daily resolution."""
    return SmardNode(
        name="solar_daily",
        url="https://smard.api.proxy.bund.dev/app",
        protocol="smard",
        filter=4068,  # Photovoltaik
        region="DE",
        resolution="day",
    )


@pytest.fixture
def connection(solar_node: SmardNode):
    """Create a test connection."""
    return SmardConnection.from_node(solar_node)


def test_node_creation():
    """Test SmardNode creation with different parameters."""
    # Test with filter ID
    node1 = SmardNode(
        name="solar",
        url="https://smard.api.proxy.bund.dev/app",
        protocol="smard",
        filter=4068,
        region="DE",
    )
    assert node1.filter == 4068
    assert node1.resolution == "quarterhour"  # default

    # Test with different resolution
    node2 = SmardNode(
        name="wind",
        url="https://smard.api.proxy.bund.dev/app",
        protocol="smard",
        filter=4067,
        region="50Hertz",
        resolution="quarterhour",
    )
    assert node2.resolution == "quarterhour"


def test_node_validation():
    """Test node validation."""
    # Invalid filter
    with pytest.raises(ValueError, match="Invalid filter"):
        SmardNode(
            name="invalid",
            url="https://smard.api.proxy.bund.dev/app",
            protocol="smard",
            filter=99999,
            region="DE",
        )

    # Invalid region
    with pytest.raises(ValueError, match="'region' must be in"):
        SmardNode(
            name="invalid",
            url="https://smard.api.proxy.bund.dev/app",
            protocol="smard",
            filter=4068,
            region="INVALID",
        )

    # Invalid resolution
    with pytest.raises(ValueError, match="'resolution' must be in"):
        SmardNode(
            name="invalid",
            url="https://smard.api.proxy.bund.dev/app",
            protocol="smard",
            filter=4068,
            region="DE",
            resolution="invalid",
        )


def test_node_from_dict():
    """Test creating node from dictionary."""
    config = {
        "name": "solar_de",
        "url": "https://smard.api.proxy.bund.dev/app",
        "protocol": "smard",
        "filter": "solar",  # Test string filter name
        "region": "DE",
        "resolution": "hour",
    }

    node = SmardNode._from_dict(config)
    assert node.name == "solar_de"
    assert node.filter == 4068
    assert node.region == "DE"


def test_connection_initialization(connection: SmardConnection):
    """Test connection creation."""
    assert connection.url == "https://smard.api.proxy.bund.dev/app"
    assert len(connection.selected_nodes) == 1
    assert connection.authentication is None  # No auth needed


def test_read_latest_value(solar_node_daily: SmardNode):
    """Test read() method returns the latest available value."""
    conn = SmardConnection.from_node(solar_node_daily)

    result = conn.read()

    assert isinstance(result, pd.DataFrame)
    assert result.shape == (1, 1)  # Single row, single column
    assert solar_node_daily.name in result.columns
    assert result.index.name == "Time (with timezone)"
    assert result.index.tzinfo is not None  # Timezone aware
    # Should have exactly one data point (the latest)
    assert len(result) == 1


def test_read_series_integration(connection: SmardConnection, solar_node: SmardNode):
    """Integration test: Read actual data from SMARD API."""
    # Request last 2 days of data
    to_time = datetime(2025, 11, 11, 14, 19, 0, tzinfo=timezone.utc)
    from_time = to_time - timedelta(days=2)

    result = connection.read_series(
        from_time=from_time,
        to_time=to_time,
        nodes=solar_node,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.shape == (8, 1)
    assert solar_node.name in result.columns
    assert result.index.name == "Time (with timezone)"
    assert len(result) > 0
    assert result.index.tzinfo is not None  # Timezone aware


def test_multiple_nodes_integration():
    """Integration test: Read multiple generation sources."""
    # Create nodes for solar and wind
    nodes = [
        SmardNode(
            name="solar",
            url="https://smard.api.proxy.bund.dev/app",
            protocol="smard",
            filter=4068,
            region="DE",
            resolution="day",
        ),
        SmardNode(
            name="wind_onshore",
            url="https://smard.api.proxy.bund.dev/app",
            protocol="smard",
            filter=4067,
            region="DE",
            resolution="day",
        ),
    ]

    conn = SmardConnection(nodes=nodes)

    # Request last week
    to_time = datetime(2025, 11, 11, 14, 19, 0, tzinfo=timezone.utc)
    from_time = to_time - timedelta(days=7)

    result = conn.read_series(
        from_time=from_time,
        to_time=to_time,
        nodes=nodes,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.shape == (7, 2)
    assert set(result.columns) == {"solar", "wind_onshore"}
    assert len(result) == 7  # 7 days


def test_get_filter_name():
    """Test filter name lookup utility."""
    assert SmardNode.get_filter_name(4068) == "solar"
    assert SmardNode.get_filter_name(4067) == "wind_onshore"
    assert SmardNode.get_filter_name(99999) is None
