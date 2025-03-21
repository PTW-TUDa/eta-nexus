from datetime import datetime

import pandas as pd

from eta_connect.connectors import ENTSOEConnection
from eta_connect.connectors.node import NodeEntsoE


def main() -> None:
    read_series()


def read_series() -> pd.DataFrame:
    # --begin_entsoe_doc_example--
    # Define your ENTSO-E Token
    entsoe_token = ""

    # Check out NodeEntsoE documentation for endpoint and bidding zone information
    node = NodeEntsoE(
        "CH1.Elek_U.L1-N",
        "https://web-api.tp.entsoe.eu/",
        "entsoe",
        endpoint="Price",
        bidding_zone="DEU-LUX",
    )

    # start connection from one or multiple nodes
    server = ENTSOEConnection.from_node(node, api_token=entsoe_token)

    # Define time interval as datetime values
    from_datetime = datetime.strptime("2022-02-15T13:18:12", "%Y-%m-%dT%H:%M:%S")
    to_datetime = datetime.strptime("2022-02-15T14:00:00", "%Y-%m-%dT%H:%M:%S")

    # read_series will request data from specified connection and time interval
    # The DataFrame will have index with time delta of the specified interval in seconds
    if isinstance(server, ENTSOEConnection):
        result = server.read_series(from_time=from_datetime, to_time=to_datetime, interval=1)
    else:
        raise TypeError("The connection must be an ENTSOEConnection, to be able to call read_series.")
    # --end_entsoe_doc_example--

    return result


if __name__ == "__main__":
    main()
