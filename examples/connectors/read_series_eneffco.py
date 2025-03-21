from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from eta_connect.connectors import EnEffCoConnection

if TYPE_CHECKING:
    import pandas as pd


def main() -> None:
    read_series()


def read_series() -> pd.DataFrame:
    # --main--
    # Create the connection object
    connection = EnEffCoConnection.from_ids(
        ["CH1.Elek_U.L1-N", "Pu3.425.ThHy_Q"],
        url="https://someurl.com/",
        usr="username",
        pwd="password",
        api_token="your_server_auth_token",
    )

    # Read series data within a specified time interval
    from_time = datetime.fromisoformat("2019-01-01 00:00:00")
    to_time = datetime.fromisoformat("2019-01-02 00:00:00")
    return connection.read_series(from_time, to_time, interval=900)
    # --main--


if __name__ == "__main__":
    main()
