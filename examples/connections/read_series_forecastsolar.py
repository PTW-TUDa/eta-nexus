from datetime import datetime, timedelta

import pandas as pd

from eta_nexus.connections import ForecastsolarConnection
from eta_nexus.nodes import ForecastsolarNode


def main() -> None:
    read_series()


def read_series(api_token: str | None = None) -> pd.DataFrame:
    # --begin_forecast_solar_doc_example1--
    # ------------------------------
    # Simple node (API key optional):
    # ------------------------------
    node_simple = ForecastsolarNode(
        name="Forecastsolar Node",
        url="https://api.forecast.solar",
        protocol="forecast_solar",
        latitude=51.15,
        longitude=10.45,
        declination=20,
        azimuth=0,
        kwp=12.34,
    )

    # Create an instance of the ForecastsolarConnection class
    conn_simple = ForecastsolarConnection(api_token=api_token)

    # Use the read method of the ForecastsolarConnection instance to get an estimation
    # The read method takes a node as an argument, here represented by node_simple
    return conn_simple.read(node_simple)
    # --end_forecast_solar_doc_example1--


def read_series_multiple_planes(api_token: str) -> pd.DataFrame:
    # --begin_forecast_solar_doc_example2--
    # ------------------------------
    # Node with api key and multiple planes:
    # ------------------------------
    node_eta = ForecastsolarNode(
        name="Forecastsolar Node",
        url="https://api.forecast.solar",
        protocol="forecast_solar",
        latitude=49.86381,
        longitude=8.68105,
        declination=[14, 10, 10],
        azimuth=[90, -90, 90],
        kwp=[23.31, 23.31, 23.31],
    )

    # Create a connection instance from the node_eta using the from_node method
    conn_eta = ForecastsolarConnection.from_node(node_eta, api_token=api_token)

    if isinstance(conn_eta, ForecastsolarConnection):
        # Get a series of estimations for a specified time interval
        estimation = conn_eta.read_series(
            from_time=datetime(2024, 5, 7), to_time=datetime(2024, 5, 8), interval=timedelta(minutes=15)
        )
    else:
        raise TypeError("The connection must be a ForecastsolarConnection, to be able to call read_series.")
    # --end_forecast_solar_doc_example2--
    return estimation


if __name__ == "__main__":
    main()
