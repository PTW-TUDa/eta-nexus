import asyncio
import pathlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pytest

from eta_connect.nodes import Node
from eta_connect.subhandlers import CsvSubHandler, DFSubHandler, SubscriptionHandler

sample_series = pd.Series(
    data=[1, 2, 3], index=pd.DatetimeIndex(["2020-11-05 10:00:00", "2020-11-05 10:00:01.1", "2020-11-05 10:00:01.7"])
)
sample_series2 = pd.Series(
    data=[1, 2, 3], index=pd.DatetimeIndex(["2020-11-05 10:00:0.4", "2020-11-05 10:00:01.2", "2020-11-05 10:00:01.5"])
)

sample_series_nan = pd.Series(
    data=[1, np.nan, np.nan],
    index=pd.DatetimeIndex(["2020-11-05 10:00:0.4", "2020-11-05 10:00:01.2", "2020-11-05 10:00:01.5"]),
)


@pytest.fixture(scope="module")
def test_node():
    return Node(name="FirstNode", url="", protocol="local")


@pytest.fixture(scope="module")
def test_node2():
    return Node(name="SecondNode", url="", protocol="local")


async def push_values(handler: SubscriptionHandler, test_node, test_node2):
    for num in range(6):
        idx = num // 2 if num > 1 else 0
        if num % 2 == 0:
            handler.push(test_node, sample_series.to_numpy()[idx], sample_series.index[idx])
        else:
            handler.push(test_node2, sample_series2.to_numpy()[idx], sample_series2.index[idx])
    handler.close()


class TestCSVSubHandler:
    def test_push_timeseries_to_csv(self, temp_dir, test_node, test_node2):
        file = temp_dir / "csv_test_output.csv"
        handler = CsvSubHandler(file, 0.5)

        executor = ThreadPoolExecutor(max_workers=3)
        loop = asyncio.get_event_loop()
        loop.set_default_executor(executor)
        loop.run_until_complete(push_values(handler, test_node, test_node2))
        executor.shutdown()

        with pathlib.Path(file).open("r") as f:
            read_values = pd.read_csv(f)
            read_values = read_values.set_index("Timestamp")
            check_values = pd.DataFrame(
                columns=["FirstNode", "SecondNode"],
                index=[
                    "2020-11-05 10:00:00.000000",
                    "2020-11-05 10:00:00.500000",
                    "2020-11-05 10:00:01.500000",
                    "2020-11-05 10:00:02.000000",
                ],
                data=[[1, np.nan], [1, 1], [2, 3], [3, 3]],
            )
            check_values.index.name = "Timestamp"

            assert all(read_values == check_values)


class TestDFSubHandler:
    @pytest.mark.parametrize(("value", "timestamp"), [(sample_series.to_numpy(), sample_series.index)])
    def test_push_timeseries_to_df(self, value, timestamp, test_node):
        """Test pushing a Series all at once"""
        handler = DFSubHandler(write_interval=1)
        handler.push(test_node, value, timestamp)
        data = handler.data

        assert (data["FirstNode"].to_numpy() == value).all()

    def test_housekeeping(self, test_node):
        """Test keeping the internal data of DFSubHandler short"""
        keep_data_rows = 2
        handler = DFSubHandler(write_interval=1, size_limit=keep_data_rows)
        handler.push(test_node, sample_series.values, sample_series.index)

        assert len(handler.data) <= keep_data_rows

    def test_get_latest(self, test_node):
        handler = DFSubHandler(write_interval=1)
        handler.push(test_node, sample_series.values, sample_series.index)
        data = handler.get_latest()

        assert (data.to_numpy() == sample_series.to_numpy()[-1]).all()

    def test_auto_fillna(self, test_node, test_node2):
        # First test default behavior: nans are filled
        handler = DFSubHandler(write_interval=0.25)  # Double the write interval to fill gaps with nans

        # Push a value at time index[0] from node2, because there is no previous value for node2 to fill with
        handler.push(test_node2, sample_series.to_numpy()[0], sample_series.index[0])
        asyncio.get_event_loop().run_until_complete(push_values(handler, test_node, test_node2))

        assert handler.data.notna().all().all()

        # Next test auto_fillna = False
        handler = DFSubHandler(write_interval=0.25, auto_fillna=False)
        asyncio.get_event_loop().run_until_complete(push_values(handler, test_node, test_node2))

        assert handler.data.isna().any().any()
