"""Utility functions for connecting to the EnEffCo database and reading data."""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import requests
from requests_cache import CachedSession

from eta_connect.connectors.node import NodeEnEffCo

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from eta_connect.type_hints import Nodes, TimeStep

from .base_classes import SeriesConnection, SubscriptionHandler

log = getLogger(__name__)


class EnEffCoConnection(SeriesConnection[NodeEnEffCo], protocol="eneffco"):
    """
    EnEffCoConnection is a class to download and upload multiple features from and to the EnEffCo database as
    timeseries.

    :param url: URL of the server with scheme (https://).
    :param usr: Username in EnEffco for login.
    :param pwd: Password in EnEffco for login.
    :param api_token: Token for API authentication.
    :param nodes: Nodes to select in connection.
    """

    API_PATH: str = "/API/v1.0"

    def __init__(
        self, url: str, usr: str | None, pwd: str | None, *, api_token: str, nodes: Nodes[NodeEnEffCo] | None = None
    ) -> None:
        url = url + self.API_PATH
        self._api_token: str = api_token
        super().__init__(url, usr, pwd, nodes=nodes)

        if self.usr is None:
            raise ValueError("Username must be provided for the EnEffCo connector.")
        if self.pwd is None:
            raise ValueError("Password must be provided for the EnEffCo connector.")

        self._node_ids: pd.DataFrame | None = None
        self._node_ids_raw: pd.DataFrame | None = None

        self._sub: asyncio.Task | None = None
        self._subscription_nodes: set[NodeEnEffCo] = set()
        self._subscription_open: bool = False
        self._session: CachedSession = CachedSession(
            cache_name="eta_connect/connectors/requests_cache/eneffco_cache",
            expire_after=timedelta(minutes=15),
            use_cache_dir=True,
        )

    @classmethod
    def _from_node(
        cls, node: NodeEnEffCo, usr: str | None = None, pwd: str | None = None, **kwargs: Any
    ) -> EnEffCoConnection:
        """Initialize the connection object from an EnEffCo protocol node object

        :param node: Node to initialize from.
        :param usr: Username to use.
        :param pwd: Password to use.
        :param kwargs: Keyword arguments for API authentication, where "api_token" is required
        :return: EnEffCoConnection object.
        """

        api_token = kwargs.get("api_token")
        if api_token is None:
            raise AttributeError("Keyword parameter 'api_token' is missing.")

        return super()._from_node(node, usr=usr, pwd=pwd, api_token=api_token)

    @classmethod
    def from_ids(cls, ids: Sequence[str], url: str, usr: str, pwd: str, api_token: str) -> EnEffCoConnection:
        """Initialize the connection object from an EnEffCo protocol through the node IDs

        :param ids: Identification of the Node.
        :param url: URL for EnEffco connection.
        :param usr: Username for EnEffCo login.
        :param pwd: Password for EnEffCo login.
        :param api_token: Token for API authentication.
        :return: EnEffCoConnection object.
        """
        nodes = [NodeEnEffCo(name=name, url=url, protocol="eneffco", eneffco_code=name) for name in ids]
        return cls(url=url, usr=usr, pwd=pwd, api_token=api_token, nodes=nodes)

    def read(self, nodes: NodeEnEffCo | Nodes[NodeEnEffCo] | None = None) -> pd.DataFrame:
        """Download current value from the EnEffCo Database

        :param nodes: Single node or list/set of nodes to read values from.
        :return: pandas.DataFrame containing the data read from the connection.
        """
        nodes = self._validate_nodes(nodes)
        base_time = 1  # seconds
        the_time = self._round_timestamp(datetime.now(), base_time).replace(tzinfo=None)
        return self.read_series(the_time - timedelta(seconds=base_time), the_time, nodes, base_time)

    def write(
        self, values: Mapping[NodeEnEffCo, Any] | pd.Series[datetime, Any], time_interval: timedelta | None = None
    ) -> None:
        """Writes some values to the EnEffCo Database

        :param values: Dictionary of nodes and data to write {node: value}.
        :param time_interval: Interval between datapoints (i.e. between "From" and "To" in EnEffCo Upload) (default 1s).
        """
        nodes = self._validate_nodes(list(values.keys()))

        if time_interval is None:
            time_interval = timedelta(seconds=1)

        for node in nodes:
            request_url = f"rawdatapoint/{self.id_from_code(node.eneffco_code, raw_datapoint=True)}/value"
            response = self._raw_request(
                "POST",
                request_url,
                data=self._prepare_raw_data(values[node], time_interval),
                headers={
                    "Content-Type": "application/json",
                    "cache-control": "no-cache",
                    "Postman-Token": self._api_token,
                },
                params={"comment": ""},
            )
            log.info(response.text)

    def _prepare_raw_data(
        self, data: Mapping[datetime, Any] | pd.Series[datetime, Any], time_interval: timedelta
    ) -> str:
        """Change the input format into a compatible format with EnEffCo and filter NaN values.

        :param data: Data to write to node {time: value}. Could be a dictionary or a pandas Series.
        :param time_interval: Interval between datapoints (i.e. between "From" and "To" in EnEffCo Upload).

        :return upload_data: String from dictionary in the format for the upload to EnEffCo.
        """

        if isinstance(data, (dict, pd.Series)):
            upload_data: dict[str, list[Any]] = {"Values": []}
            for time, val in data.items():
                # Only write values if they are not nan
                if not np.isnan(val):
                    aware_time = self._assert_tz_awareness(time).astimezone(timezone.utc)
                    upload_data["Values"].append(
                        {
                            "Value": float(val),
                            "From": aware_time.strftime("%Y-%m-%d %H:%M:%SZ"),
                            "To": (aware_time + time_interval).strftime("%Y-%m-%d %H:%M:%SZ"),
                        }
                    )

        else:
            raise ValueError("Unrecognized data format for EnEffCo upload. Provide dictionary or pandas series.")

        return str(upload_data)

    def read_info(self, nodes: NodeEnEffCo | Nodes[NodeEnEffCo] | None = None) -> pd.DataFrame:
        """Read additional datapoint information from Database.

        :param nodes: Single node or list/set of nodes values from.
        :return: pandas.DataFrame containing the data read from the connection.
        """

        nodes = self._validate_nodes(nodes)
        values = []

        for node in nodes:
            request_url = f"datapoint/{self.id_from_code(node.eneffco_code)}"
            response = self._raw_request("GET", request_url)
            values.append(pd.Series(response.json(), name=node.name))

        return pd.concat(values, axis=1)

    def subscribe(
        self,
        handler: SubscriptionHandler,
        nodes: NodeEnEffCo | Nodes[NodeEnEffCo] | None = None,
        interval: TimeStep = 1,
    ) -> None:
        """Subscribe to nodes and call handler when new data is available. This will return only the
        last available values.

        :param handler: SubscriptionHandler object with a push method that accepts node, value pairs.
        :param interval: Interval for receiving new data. It is interpreted as seconds when given as an integer.
        :param nodes: Single node or list/set of nodes to subscribe to.
        """
        self.subscribe_series(handler=handler, req_interval=1, nodes=nodes, interval=interval, data_interval=interval)

    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: NodeEnEffCo | Nodes[NodeEnEffCo] | None = None,
        interval: TimeStep = 1,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Download timeseries data from the EnEffCo Database

        :param nodes: Single node or list/set of nodes to read values from.
        :param from_time: Starting time to begin reading (included in output).
        :param to_time: Time to stop reading at (not included in output).
        :param interval: Interval between time steps. It is interpreted as seconds if given as integer.
        :param kwargs: Other parameters (ignored by this connector).
        :return: Pandas DataFrame containing the data read from the connection.
        """
        _interval = interval if isinstance(interval, timedelta) else timedelta(seconds=interval)

        nodes = self._validate_nodes(nodes)

        def read_node(node: NodeEnEffCo) -> pd.DataFrame:
            request_url = (
                f"datapoint/{self.id_from_code(node.eneffco_code)}/value?"
                f"from={self.timestr_from_datetime(from_time)}&"
                f"to={self.timestr_from_datetime(to_time)}&"
                f"timeInterval={int(_interval.total_seconds())!s}&"
                "includeNanValues=True"
            )
            response = self._raw_request("GET", request_url).json()

            data = pd.DataFrame(
                data=(r["Value"] for r in response),
                index=pd.to_datetime([r["From"] for r in response], utc=True, format="%Y-%m-%dT%H:%M:%SZ").tz_convert(
                    self._local_tz
                ),
                columns=[node.name],
                dtype="float64",
            )
            data.index.name = "Time (with timezone)"
            return data

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = executor.map(read_node, nodes)

        return pd.concat(results, axis=1, sort=False)

    def subscribe_series(
        self,
        handler: SubscriptionHandler,
        req_interval: TimeStep,
        offset: TimeStep | None = None,
        nodes: NodeEnEffCo | Nodes[NodeEnEffCo] | None = None,
        interval: TimeStep = 1,
        data_interval: TimeStep = 1,
        **kwargs: Any,
    ) -> None:
        """Subscribe to nodes and call handler when new data is available. This will always return a series of values.
        If nodes with different intervals should be subscribed, multiple connection objects are needed.

        :param handler: SubscriptionHandler object with a push method that accepts node, value pairs.
        :param req_interval: Duration covered by requested data (time interval). Interpreted as seconds if given as int.
        :param offset: Offset from datetime.now from which to start requesting data (time interval).
                       Interpreted as seconds if given as int. Use negative values to go to past timestamps.
        :param data_interval: Time interval between values in returned data. Interpreted as seconds if given as int.
        :param interval: interval (between requests) for receiving new data.
                         It is interpreted as seconds when given as an integer.
        :param nodes: Single node or list/set of nodes to subscribe to.
        :param kwargs: Other, ignored parameters.
        """

        nodes = self._validate_nodes(nodes)

        interval = interval if isinstance(interval, timedelta) else timedelta(seconds=interval)
        req_interval = req_interval if isinstance(req_interval, timedelta) else timedelta(seconds=req_interval)
        if offset is None:
            offset = -req_interval
        else:
            offset = offset if isinstance(offset, timedelta) else timedelta(seconds=offset)
        data_interval = data_interval if isinstance(data_interval, timedelta) else timedelta(seconds=data_interval)

        self._subscription_nodes.update(nodes)

        if self._subscription_open:
            # Adding nodes to subscription is enough to include them in the query. Do not start an additional loop
            # if one already exists
            return

        self._subscription_open = True
        loop = asyncio.get_event_loop()
        self._sub = loop.create_task(
            self._subscription_loop(
                handler,
                int(interval.total_seconds()),
                req_interval,
                offset,
                data_interval,
            )
        )

    def close_sub(self) -> None:
        """Close an open subscription."""
        self._subscription_open = False

        if self.exc:
            raise self.exc

        try:
            self._sub.cancel()  # type: ignore
        except Exception:
            pass

    async def _subscription_loop(
        self,
        handler: SubscriptionHandler,
        interval: TimeStep,
        req_interval: TimeStep,
        offset: TimeStep,
        data_interval: TimeStep,
    ) -> None:
        """The subscription loop handles requesting data from the server in the specified interval

        :param handler: Handler object with a push function to receive data.
        :param interval: Interval for requesting data in seconds.
        :param req_interval: Duration covered by the requested data.
        :param offset: Offset from datetime.now from which to start requesting data (time interval).
                       Use negative values to go to past timestamps.
        :param data_interval: Interval between data points.
        """
        interval = interval if isinstance(interval, timedelta) else timedelta(seconds=interval)
        req_interval = req_interval if isinstance(req_interval, timedelta) else timedelta(seconds=req_interval)
        data_interval = data_interval if isinstance(data_interval, timedelta) else timedelta(seconds=data_interval)
        offset = offset if isinstance(offset, timedelta) else timedelta(seconds=offset)

        try:
            while self._subscription_open:
                from_time = datetime.now() + offset
                to_time = from_time + req_interval

                values = self.read_series(from_time, to_time, self._subscription_nodes, interval=data_interval)
                for node in self._subscription_nodes:
                    handler.push(node, values[node.name])

                await asyncio.sleep(interval.total_seconds())
        except BaseException as e:
            self.exc = e

    def id_from_code(self, code: str, raw_datapoint: bool = False) -> str:
        """
        Function to get the raw EnEffCo ID corresponding to a specific (raw) datapoint

        :param code: Exact EnEffCo code.
        :param raw_datapoint: Returns raw datapoint ID.
        """

        # Only build lists of IDs if they are not available yet
        if self._node_ids is None:
            response = self._raw_request("GET", "/datapoint")
            self._node_ids = pd.DataFrame(data=response.json())

        if self._node_ids_raw is None:
            response = self._raw_request("GET", "/rawdatapoint")
            self._node_ids_raw = pd.DataFrame(data=response.json())

        def find_id(node_ids: pd.DataFrame) -> str:
            if len(node_ids.loc[node_ids["Code"] == code, "Id"]) <= 0:
                raise ValueError(f"Code {code} does not exist on server {self.url}.")
            return node_ids.loc[node_ids["Code"] == code, "Id"].to_numpy().item()

        return find_id(self._node_ids_raw) if raw_datapoint else find_id(self._node_ids)

    def timestr_from_datetime(self, dt: datetime) -> str:
        """Create an EnEffCo compatible time string.

        :param dt: Datetime object to convert to string.
        :return: EnEffCo compatible time string.
        """

        return dt.isoformat(sep="T", timespec="seconds").replace(":", "%3A").replace("+", "%2B")

    def _raw_request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        """Perform EnEffCo request and handle possibly resulting errors.

        :param method: HTTP request method.
        :param endpoint: Endpoint for the request (server URI is added automatically).
        :param kwargs: Additional arguments for the request.
        """
        assert self.usr is not None, "Make sure to specify a username before performing EnEffCo requests."
        assert self.pwd is not None, "Make sure to specify a password before performing EnEffCo requests."

        response = self._session.request(
            method, self.url + "/" + str(endpoint), auth=requests.auth.HTTPBasicAuth(self.usr, self.pwd), **kwargs
        )
        response.raise_for_status()

        return response

    def _validate_nodes(self, nodes: NodeEnEffCo | Nodes[NodeEnEffCo] | None) -> set[NodeEnEffCo]:  # type: ignore
        vnodes = super()._validate_nodes(nodes)
        _nodes = set()
        for node in vnodes:
            if isinstance(node, NodeEnEffCo):
                _nodes.add(node)

        return _nodes
