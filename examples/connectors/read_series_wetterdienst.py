from datetime import datetime

import pandas as pd

from eta_connect.connectors import WetterdienstConnection
from eta_connect.connectors.node import NodeWetterdienst


def main() -> None:
    read_series()


def read_series() -> pd.DataFrame:
    # --begin_wetterdienst_doc_example--

    # Construct a node with the necessary information to request data from the Wetterdienst API
    node = (
        NodeWetterdienst(
            "Temperature_Darmstadt",
            "https://opendata.dwd.de",
            "wetterdienst_observation",
            parameter="TEMPERATURE_AIR_MEAN_200",
            station_id="00917",  # Darmstadt observation station ID
            interval=600,  # 10 minutes interval
        ),
    )

    # start connection from one or multiple nodes
    # The 'Connection' class can be used for initializing the connection
    connection = WetterdienstConnection.from_node(node)

    # Define time interval as datetime values
    from_datetime = datetime(2024, 1, 16, 12, 00)
    to_datetime = datetime(2024, 1, 16, 18, 00)

    # read_series will request data from specified connection and time interval
    # The DataFrame will have index with time delta of the specified interval in seconds
    # If a node  has a different interval than the requested interval, the data will be resampled.
    if isinstance(connection, WetterdienstConnection):
        result = connection.read_series(from_time=from_datetime, to_time=to_datetime, interval=1200)
    else:
        raise TypeError("The connection must be an WetterdienstConnection, to be able to call read_series.")
    # Check out the WetterdienstConnection documentation for more information
    # https://wetterdienst.readthedocs.io/en/latest/data/introduction.html
    # --end_wetterdienst_doc_example--

    return result


if __name__ == "__main__":
    main()
