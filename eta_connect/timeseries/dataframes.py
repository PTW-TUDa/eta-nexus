"""Simple helpers for reading timeseries data from a csv file and getting slices or resampled data. This module
handles data using pandas dataframe objects.
"""

from __future__ import annotations

import operator as op
import warnings
from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from typing import Literal

    from eta_connect.util.type_annotations import FillMethod, TimeStep

log = getLogger(__name__)


def find_time_slice(
    time_begin: datetime,
    time_end: datetime | None = None,
    total_time: TimeStep | None = None,
    round_to_interval: TimeStep | None = None,
    random: bool | np.random.Generator = False,
) -> tuple[datetime, datetime]:
    """Return a (potentially random) slicing interval that can be used to slice a data frame.

    :param time_begin: Date and time of the beginning of the interval to slice from.
    :param time_end: Date and time of the ending of the interval to slice from.
    :param total_time: Specify the total time of the sliced interval. An integer will be interpreted as seconds.
                       If this argument is None, the complete interval between beginning and end will be returned.
    :param round_to_interval: Round times to a specified interval, this value is interpreted as seconds if given as
                              an int. Default is no rounding.
    :param random: If this value is true, or a random generator is supplied, it will be used to generate a
                   random slice of length total_time in the interval between time_begin and time_end.
    :return: Tuple of slice_begin time and slice_end time. Both times are datetime objects.
    """
    # Determine ending time and total time depending on what was supplied.
    if time_end is not None and total_time is None:
        total_time = time_end - time_begin
    elif total_time is not None:
        total_time = timedelta(seconds=total_time) if not isinstance(total_time, timedelta) else total_time
        time_end = time_begin + total_time if time_end is None else time_end
    else:
        raise ValueError("At least one of time_end and total_time must be specified to fully constrain the interval.")

    round_to_interval = (
        round_to_interval.total_seconds() if isinstance(round_to_interval, timedelta) else round_to_interval
    )

    # Determine the (possibly random) beginning time of the time slice and round it if necessary
    if random:
        if isinstance(random, bool):
            random = np.random.default_rng()
            log.info(
                "Using an unseeded random generator for time slicing. This will not produce deterministic results."
            )
        time_gap = max(0, (time_end - time_begin - total_time).total_seconds())
        if time_gap <= 0:
            log.warning(
                "Could not use random time sampling because the gap between the required starting and ending "
                "times is too small."
            )
        slice_begin = time_begin + timedelta(seconds=random.uniform() * time_gap)
    else:
        slice_begin = time_begin
    if round_to_interval is not None and round_to_interval > 0:
        slice_begin = datetime.fromtimestamp((slice_begin.timestamp() // round_to_interval) * round_to_interval)

    # Determine the ending time of the time slice and round it if necessary
    slice_end = slice_begin + total_time
    if round_to_interval is not None and round_to_interval > 0:
        slice_end = datetime.fromtimestamp((slice_end.timestamp() // round_to_interval) * round_to_interval)

    return slice_begin, slice_end


def df_time_slice(
    df: pd.DataFrame,
    time_begin: datetime,
    time_end: datetime | None = None,
    total_time: TimeStep | None = None,
    round_to_interval: TimeStep | None = None,
    random: bool | np.random.Generator = False,
) -> pd.DataFrame:
    """Return a data frame which has been sliced starting at time_begin and ending at time_end, from df.

    :param df: Original data frame to be sliced.
    :param time_begin: Date and time of the beginning of the interval to slice from.
    :param time_end: Date and time of the ending of the interval to slice from.
    :param total_time: Specify the total time of the sliced interval. An integer will be interpreted as seconds.
                       If this argument is None, the complete interval between beginning and end will be returned.
    :param round_to_interval: Round times to a specified interval, this value is interpreted as seconds if given as
                              an int. Default is no rounding.
    :param random: If this value is true, or a random generator is supplied, it will be used to generate a
                   random slice of length total_time in the interval between time_begin and time_end.
    :return: Sliced data frame.
    """

    slice_begin, slice_end = find_time_slice(time_begin, time_end, total_time, round_to_interval, random)
    return df[slice_begin:slice_end].copy()  # type: ignore


def df_resample(
    dataframe: pd.DataFrame, *periods_deltas: TimeStep, missing_data: FillMethod | None = None
) -> pd.DataFrame:
    """Resample the time index of a data frame. This method can be used for resampling in multiple different
    periods with multiple different deltas between single time entries.

    :param df: DataFrame for processing.
    :param periods_deltas: If one argument is specified, this will resample the data to the specified interval
                           in seconds. If more than one argument is specified, they will be interpreted as
                           (periods, interval) pairs. The first argument specifies a number of periods that should
                           be resampled, the second value specifies the interval that these periods should be
                           resampled to. A third argument would determine the next number of periods that should
                           be resampled to the interval specified by the fourth argument and so on.
    :param missing_data: Specify a method for handling missing data values. If this is not specified, missing
                         data will not be handled. Valid methods are: 'ffill', 'bfill', 'interpolate', 'asfreq'.
                         Default is 'asfreq'. 'fillna' is supported for backwards compatibility, but deprecated.
    :return: Resampled copy of the DataFrame.
    """
    # Set default value for missing_data
    missing_data = missing_data or "asfreq"
    if missing_data == "fillna":
        msg = "fillna is deprecated for parameter 'missing_data', use ffill instead."
        warnings.warn(msg, DeprecationWarning, stacklevel=2)
        missing_data = "ffill"

    valid_methods = ("ffill", "bfill", "interpolate", "asfreq")  # ref to FillMethod
    if missing_data not in valid_methods:
        raise ValueError(f"Invalid value for 'missing_data': {missing_data}. Valid values are: {valid_methods}")

    interpolation_method = op.methodcaller(missing_data)

    if not dataframe.index.is_unique:
        duplicates = dataframe.index.duplicated(keep="first")
        log.warning(f"Index has non-unique values. Dropping duplicates: {dataframe.index[duplicates].to_list()}.")
        dataframe = dataframe[~duplicates]

    _periods_deltas: list[int] = [int(t.total_seconds() if isinstance(t, timedelta) else t) for t in periods_deltas]

    if len(_periods_deltas) == 1:
        delta = _periods_deltas[0]
        new_df = (
            df_interpolate(dataframe, delta)  # interpolate needs an extra method for handling indices
            if missing_data == "interpolate"
            else interpolation_method(dataframe.resample(f"{int(delta)}s"))
        )
    else:
        period_delta = [(_periods_deltas[i], _periods_deltas[i + 1]) for i in range(0, len(_periods_deltas), 2)]
        total_periods: int = 0
        new_df = None
        for period, delta in period_delta:
            period_df = dataframe.iloc[total_periods : total_periods + period + 1]
            resampled_df = df_resample(period_df, delta, missing_data=missing_data)
            new_df = resampled_df if new_df is None else pd.concat((new_df, resampled_df))

            total_periods += period

    # Remove the duplicate value between periods
    new_df = new_df[~new_df.index.duplicated(keep="first")]

    if new_df.isna().to_numpy().any():
        log.warning(
            "Resampled Dataframe has missing values. Before using this data, ensure you deal with the missing values. "
            "For example, you could interpolate(), ffill() or dropna()."
        )

    return new_df


def df_interpolate(
    dataframe: pd.DataFrame, freq: TimeStep, limit_direction: Literal["both", "forward", "backward"] = "both"
) -> pd.DataFrame:
    """Interpolate missing values in a DataFrame with a specified frequency.
    Is able to handle unevenly spaced time series data.

    :param dataframe: DataFrame for interpolation.
    :param freq: Frequency of the resulting DataFrame.
    :param limit_direction: Direction in which to limit the
        interpolation. Defaults to "both".
    :return: Interpolated DataFrame.
    """
    if not dataframe.index.is_unique:
        log.warning(
            f"Index has non-unique values. Dropping duplicates: "
            f"{dataframe.index[dataframe.index.duplicated(keep='first')].to_list()}."
        )
        dataframe = dataframe[~dataframe.index.duplicated(keep="first")]

    freq_seconds: float | int = freq.total_seconds() if isinstance(freq, timedelta) else freq
    freq_str: str = str(int(freq_seconds)) + "s"

    old_index: pd.Index = dataframe.index
    start: pd.Timestamp = old_index.min().floor(freq_str)
    end: pd.Timestamp = old_index.max().ceil(freq_str)
    new_index: pd.Index = pd.date_range(start=start, end=end, freq=freq_str)
    tmp_index: pd.Index = old_index.union(new_index)

    df_reindexed: pd.DataFrame = dataframe.reindex(tmp_index)
    df_interpolated: pd.DataFrame = df_reindexed.interpolate(method="time", limit_direction=limit_direction)
    new_df: pd.DataFrame = df_interpolated.reindex(new_index)

    if new_df.iloc[0].isna().to_numpy().any():
        log.warning("The first value of the interpolated dataframe is NaN.")
    if new_df.iloc[-1].isna().to_numpy().any():
        log.warning("The last value of the interpolated dataframe is NaN.")

    return new_df
