from datetime import datetime, timedelta, timezone

import pandas as pd

from eta_nexus.connections import SmardConnection
from eta_nexus.nodes import SmardNode


def main() -> None:
    read_series()


def read_series() -> pd.DataFrame:
    # --begin_smard_doc_example--

    # Construct a node with the necessary information to request data from the SMARD API
    # SMARD provides German electricity market data from Bundesnetzagentur
    node = SmardNode(
        name="Solar_Generation_DE",
        url="https://smard.api.proxy.bund.dev/app",
        protocol="smard",
        filter=4068,  # Solar power generation (can also use string name "solar")
        region="DE",  # Germany
        resolution="hour",  # Available: 'quarterhour', 'hour', 'day', 'week', 'month', 'year'
    )

    # Start connection from one or multiple nodes
    # The Connection class can be used for initializing the connection
    connection = SmardConnection.from_node(node)

    # Define time interval as datetime values
    # SMARD has data from 2015 onwards
    to_datetime = datetime(2025, 11, 11, 14, 19, 0, tzinfo=timezone.utc)
    from_datetime = to_datetime - timedelta(days=2)

    # read_series will request data from specified connection and time interval
    # The DataFrame will have index with time delta of the specified interval in seconds
    # If a node has a different interval than the requested interval, the data will be resampled.
    if isinstance(connection, SmardConnection):
        result = connection.read_series(from_time=from_datetime, to_time=to_datetime, interval=3600)
    else:
        raise TypeError("The connection must be a SmardConnection, to be able to call read_series.")

    # Check out the SmardConnection documentation for more information about:
    # - Available filters (solar, wind, nuclear, prices, etc.)
    # - Regions (DE, AT, LU, and German control zones)
    # - Time resolutions
    # --end_smard_doc_example--

    return result


if __name__ == "__main__":
    main()
