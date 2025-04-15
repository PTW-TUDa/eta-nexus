import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from eta_nexus.timeseries.dataframes import df_interpolate, df_resample

uneven_data = [100, 200, 0, 0, 300, 500]
uneven_index = pd.DatetimeIndex(
    [
        datetime(2024, 10, 18, 15, 3, 45),
        datetime(2024, 10, 18, 15, 8, 27),
        datetime(2024, 10, 18, 15, 15, 50),
        datetime(2024, 10, 18, 16, 15, 3),
        datetime(2024, 10, 18, 16, 23, 17),
        datetime(2024, 10, 18, 16, 28, 29),
    ]
)


@pytest.fixture
def uneven_dataframe() -> pd.DataFrame:
    return pd.DataFrame(data=uneven_data, index=uneven_index, columns=["Value"])


@pytest.fixture
def even_dataframe() -> pd.DataFrame:
    index = pd.date_range("1/1/2000", periods=6, freq="1h")
    return pd.Series([(i + 1) * 100 for i in range(6)], index=index, name="Value").to_frame()


class TestResample:
    def test_ffill_uneven_single(self, uneven_dataframe):
        df_resampled = df_resample(uneven_dataframe, 60, missing_data="ffill")
        values = df_resampled.round(2).to_numpy().flatten().tolist()

        diffs = [(uneven_index[i] - uneven_index[i - 1]).total_seconds() for i in range(1, len(uneven_index))]
        diffs[3] += 30  # hardcoded fix for 0
        ref_values = []
        for diff, value in zip(diffs, uneven_data, strict=False):
            ref_values.extend([float(value)] * round(diff / 60))
        assert values[1:] == ref_values

    def test_ffill_single(self, even_dataframe):
        df_resampled = df_resample(even_dataframe, 30 * 60, missing_data="ffill")
        values = df_resampled.round(2).to_numpy().flatten().tolist()

        ref_values = [100, 100, 200, 200, 300, 300, 400, 400, 500, 500, 600]
        assert values == ref_values

    def test_ffill_multiple(self, even_dataframe):
        pds = []
        ref_values = []
        for i in range(1, 6):
            pds.extend([1, 3600 // i])  # one period and frequency of i
            ref_values.extend([int(i * 100)] * i)  # 100, 200, 200, 300, 300, 300, ...
        ref_values.append(600)

        df_resampled = df_resample(even_dataframe, *pds, missing_data="ffill")

        assert df_resampled["Value"].to_list() == ref_values

    def test_duplicate_indices(self, even_dataframe: pd.DataFrame, caplog):
        duplicate_df = pd.concat([even_dataframe, even_dataframe.iloc[:1]])
        df_resample(duplicate_df, 60, missing_data="ffill")

        msg = f"Index has non-unique values. Dropping duplicates: {[duplicate_df.index[0]]}"
        assert msg in caplog.text

    def test_isna_warning(self, even_dataframe, caplog):
        even_dataframe.iloc[0] = np.nan
        df_resampled = df_resample(even_dataframe, 60, missing_data="ffill")
        assert df_resampled.isna().any().any()
        msg = (
            "Resampled Dataframe has missing values. Before using this data, ensure you deal with the missing values. "
            "For example, you could interpolate(), ffill() or dropna()."
        )
        assert msg in caplog.text

    def test_missing_data_default(self, even_dataframe):
        df_resampled = df_resample(even_dataframe, 30 * 60)
        assert df_resampled.isna().any().any()
        assert len(df_resampled) == 11
        assert (df_resampled.dropna()["Value"] == even_dataframe["Value"]).all()

    def test_invalid_missing_data(self, even_dataframe):
        msg = "Invalid value for 'missing_data': invalid. Valid values are: ('ffill', 'bfill', 'interpolate', 'asfreq')"
        with pytest.raises(ValueError, match=re.escape(msg)):
            df_resample(even_dataframe, 30 * 60, missing_data="invalid")


class TestInterpolate:
    def test_uneven_indices(self, uneven_dataframe):
        df_interpolated = df_interpolate(dataframe=uneven_dataframe, freq=timedelta(minutes=5))

        ref_values = [100, 126.6, 158.01, 22.57] + [0] * 12 + [180.36, 366.03, 500]
        assert (df_interpolated["Value"].round(2) == ref_values).all()

    @pytest.mark.parametrize(("limit_direction", "position"), [("forward", 0), ("backward", -1)])
    def test_limit_direction(self, limit_direction, position, uneven_dataframe):
        df_interpolated = df_interpolate(
            dataframe=uneven_dataframe, freq=timedelta(minutes=5), limit_direction=limit_direction
        )
        assert np.isnan(df_interpolated.iloc[position]["Value"])

    @pytest.fixture
    def zero_dataframe(self):
        """Mimic a ForecastSolar dataframe with zero values."""
        hours = 5
        index_1 = pd.date_range("1/1/2000", periods=hours, freq="h")  # 1. Jan
        index_2 = pd.date_range("1/2/2000", periods=hours, freq="h")  # 2. Jan
        index_1 = index_1.append(pd.DatetimeIndex([datetime(2000, 1, 1, 15, 43, 56), datetime(2000, 1, 1, 22, 2, 19)]))

        values = [i + 10 for i in range(hours)] + [0, 0] + [i + 10 + hours for i in range(hours)]

        return pd.DataFrame(data=values, index=index_1.append(index_2), columns=["Value"])

    def test_zero_fill(self, zero_dataframe):
        df_interpolated = df_interpolate(dataframe=zero_dataframe, freq=timedelta(hours=1))

        assert df_interpolated.index.is_unique

        zero_values = df_interpolated.iloc[16:23]  # 16 o'clock to 22 o'clock

        assert (zero_values["Value"] == 0).all()

    def test_duplicate_indices(self, even_dataframe: pd.DataFrame, caplog):
        duplicate_df = pd.concat([even_dataframe, even_dataframe.iloc[:1]])
        df_interpolate(duplicate_df, 60)

        msg = f"Index has non-unique values. Dropping duplicates: {[duplicate_df.index[0]]}"
        assert msg in caplog.text
