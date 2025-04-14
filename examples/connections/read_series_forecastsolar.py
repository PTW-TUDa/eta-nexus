from datetime import datetime, timedelta

import pandas as pd


def main() -> None:
    read_series()


def read_series() -> pd.DataFrame:
    # --begin_forecast_solar_doc_example1--
    from eta_nexus.connections import ForecastsolarConnection
    from eta_nexus.nodes import ForecastsolarNode

    # ------------------------------
    # Simple node without API key:
    # ------------------------------
    node_simple = ForecastsolarNode(
        name="Forecastsolar Node",
        url="https://api.forecast.solar",
        protocol="forecast_solar",
        latitude=49.86381,
        longitude=8.68105,
        declination=14,
        azimuth=90,
        kwp=23.31,
    )

    # Create an instance of the ForecastsolarConnection class
    conn_simple = ForecastsolarConnection()

    # Use the read method of the ForecastsolarConnection instance to get an estimation
    # The read method takes a node as an argument, here represented by node_simple
    estimation = conn_simple.read(node_simple)

    # --end_forecast_solar_doc_example1--
    # --begin_forecast_solar_doc_example2--

    # ------------------------------
    # Node with api key and multiple planes:
    # ------------------------------
    node_eta = ForecastsolarNode(
        name="Forecastsolar Node",
        url="https://api.forecast.solar",
        protocol="forecast_solar",
        api_key="A1B2C3D4E5F6G7H8",  # Your API key
        latitude=49.86381,
        longitude=8.68105,
        declination=[14, 10, 10],
        azimuth=[90, -90, 90],
        kwp=[23.31, 23.31, 23.31],
    )

    # Create a connection instance from the node_eta using the from_node method
    conn_eta = ForecastsolarConnection.from_node(node_eta)

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
