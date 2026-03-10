import pandas as pd
import pytest

from examples.connections.read_series_smard import read_series as ex_read_smard


@pytest.mark.block_network
@pytest.mark.vcr
def test_example_read_smard():
    data = ex_read_smard()

    assert isinstance(data, pd.DataFrame)
    assert set(data.columns) == {"Solar_Generation_DE"}
    assert len(data) > 0
