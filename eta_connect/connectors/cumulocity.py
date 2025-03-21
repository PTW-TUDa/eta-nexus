from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import json
from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import requests

from eta_connect.connectors.node import NodeCumulocity

if TYPE_CHECKING:
    from typing import Any

    from eta_connect.type_hints import Nodes, TimeStep

from .base_classes import SeriesConnection, SubscriptionHandler

log = getLogger(__name__)


class CumulocityConnection(SeriesConnection[NodeCumulocity], protocol="cumulocity"):
    """
    CumulocityConnection is a class to download and upload multiple features from and to the Cumulocity database as
    timeseries.

    :param url: URL of the server without scheme (https://).
    :param usr: Username in Cumulocity for login.
    :param pwd: Password in Cumulocity for login.
    :param tenant: Cumulocity tenant.
    :param nodes: Nodes to select in connection.
    """

    def __init__(
        self, url: str, usr: str | None, pwd: str | None, *, tenant: str, nodes: Nodes[NodeCumulocity] | None = None
    ) -> None:
        self._tenant = tenant

        super().__init__(url, usr, pwd, nodes=nodes)

        if self.usr is None:
            raise ValueError("Username must be provided for the Cumulocity connector.")
        if self.pwd is None:
            raise ValueError("Password must be provided for the Cumulocity connector.")

        self._node_ids: pd.DataFrame | None = None
        self._node_ids_raw: pd.DataFrame | None = None

        self._sub: asyncio.Task | None = None
        self._subscription_nodes: set[NodeCumulocity] = set()
        self._subscription_open: bool = False

    @classmethod
    def _from_node(
        cls, node: NodeCumulocity, usr: str | None = None, pwd: str | None = None, **kwargs: Any
    ) -> CumulocityConnection:
        """Initialize the connection object from an Cumulocity protocol node object

        :param node: Node to initialize from.
        :param usr: Username for Cumulocity login.
        :param pwd: Password for Cumulocity login.
        :param kwargs: Keyword arguments for API authentication, where "tenant" is required
        :return: CumulocityConnection object.
        """

        if "tenant" not in kwargs:
            raise AttributeError("Keyword parameter 'tenant' is missing.")
        tenant = kwargs["tenant"]

        return super()._from_node(node, usr=usr, pwd=pwd, tenant=tenant)

    def read(self, nodes: NodeCumulocity | Nodes[NodeCumulocity] | None = None) -> pd.DataFrame:
        """Download current value from the Cumulocity Database

        :param nodes: Single node or list/set of nodes to read values from.
        :return: pandas.DataFrame containing the data read from the connection.
        """
        nodes = self._validate_nodes(nodes)
        base_time = 1  # minutes
        the_time = datetime.now()
        value = self.read_series(the_time - timedelta(minutes=base_time), the_time, nodes, base_time)
        return value[-1:]

    def write(  # type: ignore
        self,
        values: pd.Series[datetime, Any],
        measurement_type: str,
        unit: str,
        nodes: Nodes[NodeCumulocity] | None = None,
    ) -> None:
        """Write values to the cumulocity Database

        :param values: Pandas Series containing the data. Make sure the index is a Datetimeindex.
                        If fragment is not specified for node,
                        make sure the pd.Series has name since it will be used as replacement.
        :param measurement_type: The type of the measurement to be written.
        :param unit: The unit of the values.
        :param nodes: List of nodes to write values to.
        """
        headers = self.get_auth_header()
        nodes = self._validate_nodes(nodes)

        # convert numpy values to native paython values since numpy values are not json serializable
        def myconverter(obj: Any) -> Any:
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, datetime):
                return obj.__str__()
            return None

        # iterate over nodes
        for node in nodes:
            request_url = f"{node.url}/measurement/measurements"

            # iterate over values to upload
            for idx in values.index:
                fragment_name = node.fragment if node.fragment != "" else values.name

                payload = {
                    "source": {"id": node.device_id},
                    "time": datetime.fromisoformat(str(idx)).isoformat(),
                    "type": measurement_type,
                    node.measurement: {fragment_name: {"unit": unit, "value": values[idx]}},
                }

                # upload values
                response = self._raw_request(
                    "POST", request_url, headers, data=json.dumps(payload, default=myconverter)
                )
                log.info(response.text)

    def subscribe(
        self,
        handler: SubscriptionHandler,
        nodes: NodeCumulocity | Nodes[NodeCumulocity] | None = None,
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
        nodes: NodeCumulocity | Nodes[NodeCumulocity] | None = None,
        interval: TimeStep | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Download timeseries data from the Cumulocity Database

        :param nodes: Single node or list/set of nodes to read values from.
        :param from_time: Starting time to begin reading.
        :param to_time: Time to stop reading at.
        :param interval: Interval between time steps.
                        It is interpreted as seconds if given as integer (ignored by this connector).
        :param kwargs: Other parameters (ignored by this connector).
        :return: Pandas DataFrame containing the data read from the connection.
        """

        nodes = self._validate_nodes(nodes)

        # specify read function for ThreadpoolExecutor
        def read_node(node: NodeCumulocity) -> pd.DataFrame:
            request_url = (
                f"{node.url}/measurement/measurements"
                f"?dateFrom={self.timestr_from_datetime(from_time)}"
                f"&dateTo={self.timestr_from_datetime(to_time)}"
                f"&source={node.device_id}"
                f"&valueFragmentSeries={node.fragment}&pageSize=2000"
            )

            headers = self.get_auth_header()

            data_list = []

            # Sequentially retrieve the data from cumulocity database
            while True:
                response = self._raw_request("GET", request_url, headers).json()

                data_tmp = pd.DataFrame(
                    data=(
                        r[node.measurement][node.fragment]["value"]
                        for r in response["measurements"]
                        if node.measurement in r and node.fragment in r[node.measurement]
                    ),
                    index=pd.to_datetime(
                        [
                            r["time"]
                            for r in response["measurements"]
                            if node.measurement in r and node.fragment in r[node.measurement]
                        ],
                        utc=True,
                        format="%Y-%m-%dT%H:%M:%S.%fZ",
                    ),
                    columns=[node.name],
                    dtype="float64",
                )
                data_list.append(data_tmp)

                # Stopping criteria for data collection
                if data_tmp.empty or "next" not in response:
                    data = pd.concat(data_list)
                    break
                request_url = response["next"]

            data.index.name = "Time (with timezone)"
            return data

        # parallelize download from multiple nodes
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = executor.map(read_node, nodes)

        return pd.concat(results, axis=1, sort=False)

    def subscribe_series(
        self,
        handler: SubscriptionHandler,
        req_interval: TimeStep,
        offset: TimeStep | None = None,
        nodes: NodeCumulocity | Nodes[NodeCumulocity] | None = None,
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

    @staticmethod
    def create_device(url: str, username: str, password: str, tenant: str, device_name: str) -> None:
        """Create a cumulocity device.

        :param url: URL of the server without scheme (https://).
        :param usr: Username in Cumulocity for login.
        :param pwd: Password in Cumulocity for login.
        :param tenant: Cumulocity tenant.
        :param device_name: Name of the to be created device.
        """
        auth_header = str(base64.b64encode(bytes(f"{tenant}/{username}:{password}", encoding="utf-8")), "utf-8")
        headers = {"Authorization": f"Basic {auth_header}"}

        payload = {
            "name": device_name,
            "c8y_IsDevice": {},
        }

        request_url = f"{url}/inventory/managedObjects"

        response = CumulocityConnection._raw_request("POST", request_url, headers=headers, data=json.dumps(payload))
        log.info(response.text)

    @staticmethod
    def get_measurement_ids_by_device(url: str, username: str, password: str, tenant: str, device_id: str) -> list:
        """Returns a list of all measurement IDs that the specified device holds.

        :param url: URL of the server without scheme (https://).
        :param usr: Username in Cumulocity for login.
        :param pwd: Password in Cumulocity for login.
        :param tenant: Cumulocity tenant.
        :param device_id: ID of the device to retrieve the measurement IDs from.
        """
        auth_header = str(base64.b64encode(bytes(f"{tenant}/{username}:{password}", encoding="utf-8")), "utf-8")
        headers = {"Authorization": f"Basic {auth_header}"}

        request_url = f"{url}/measurement/measurements?source={device_id}&pageSize=2000"

        data_list = []

        # Sequentially collect all measuremnt IDs from device
        while True:
            response = CumulocityConnection._raw_request("GET", request_url, headers=headers).json()
            for r in response["measurements"]:
                if r["id"] not in data_list:
                    data_list.append(r["id"])
            if "next" not in response or response["measurements"] == []:
                break
            request_url = response["next"]

        return data_list

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
            from_time = datetime.now() + offset
            while self._subscription_open:
                to_time = datetime.now() + offset + req_interval

                values = self.read_series(from_time, to_time, self._subscription_nodes, interval=data_interval)

                for node in self._subscription_nodes:
                    handler.push(node, values[node.name])

                from_time = to_time

                await asyncio.sleep(interval.total_seconds())
        except BaseException as e:
            self.exc = e

    def timestr_from_datetime(self, dt: datetime) -> str:
        """Create an Cumulocity compatible time string.

        :param dt: Datetime object to convert to string.
        :return: Cumulocity compatible time string.
        """

        return dt.isoformat() + "Z"

    @staticmethod
    def _raw_request(method: str, endpoint: str, headers: dict, **kwargs: Any) -> requests.Response:
        """Perform Cumulocity request and handle possibly resulting errors.

        :param method: HTTP request method.
        :param endpoint: Endpoint for the request (server URI is added automatically).
        :param kwargs: Additional arguments for the request.
        """
        response = requests.request(method, endpoint, headers=headers, verify=False, **kwargs)

        # Check for request errors
        if response.status_code not in [
            200,
            201,
            204,
        ]:  # Status 200 for GET requests, 204 for POST requests
            error = f"Cumulocity Error {response.status_code}"
            if hasattr(response, "text") and "message" in response.json():
                error = f"{error}: {response.json()['message']}"
            elif response.status_code == 401:
                error = f"{error}: Authentication has failed, or credentials were required but not provided."
            elif response.status_code == 403:
                error = f"{error}: You are not authorized to access the API."
            elif response.status_code == 404:
                error = f"{error}: Endpoint not found '{endpoint!s}'"
            elif response.status_code == 500:
                error = f"{error}: Internal error: request could not be processed."
            elif response.status_code == 503:
                error = f"{error}: Server is unavailable"

            raise ConnectionError(error)

        return response

    def _validate_nodes(self, nodes: NodeCumulocity | Nodes[NodeCumulocity] | None) -> set[NodeCumulocity]:  # type: ignore
        vnodes = super()._validate_nodes(nodes)
        _nodes = set()
        for node in vnodes:
            if isinstance(node, NodeCumulocity):
                _nodes.add(node)

        return _nodes

    def get_auth_header(self) -> dict:
        auth_header = str(
            base64.b64encode(bytes(f"{self._tenant}/{self.usr}:{self.pwd}", encoding="utf-8")),
            "utf-8",
        )
        return {"Authorization": f"Basic {auth_header}"}
