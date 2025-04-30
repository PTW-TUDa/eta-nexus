"""The OPC UA module provides utilities for the flexible creation of OPC UA connections."""

from __future__ import annotations

import asyncio
import concurrent.futures
import socket
from concurrent.futures import (
    CancelledError as ConCancelledError,
    TimeoutError as ConTimeoutError,
)
from contextlib import contextmanager
from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING

import asyncua.sync
import pandas as pd

# TODO: add async import: from asyncua import Client as asyncClient
# https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-utility/-/issues/270
from asyncua import ua

# TODO: add async import: from asyncua.common.subscription import Subscription as asyncSubscription
# https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-utility/-/issues/270
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256

# Synchronous imports
from asyncua.sync import Client, Subscription
from asyncua.ua import SecurityPolicy, uaerrors

from eta_nexus.connections.connection_utils import IntervalChecker, RetryWaiter
from eta_nexus.nodes import OpcuaNode
from eta_nexus.util import KeyCertPair, Suppressor

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence
    from typing import Any

    from eta_nexus.subhandlers import SubscriptionHandler

    # Sync import
    # Async import
    # TODO: add async import: from asyncua import Node as asyncSyncOpcNode
    # https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-utility/-/issues/270
    from eta_nexus.util.type_annotations import Nodes, TimeStep


from .base_classes import Connection

log = getLogger(__name__)


class OpcuaConnection(Connection[OpcuaNode], protocol="opcua"):
    """The OPC UA Connection class allows reading and writing from and to OPC UA servers. Additionally,
    it implements a subscription method, which reads continuously in a specified interval.

    :param url: URL of the OPC UA Server.
    :param usr: Username in OPC UA for login.
    :param pwd: Password in OPC UA for login.
    :param nodes: List of nodes to use for all operations.
    """

    def __init__(
        self,
        url: str,
        usr: str | None = None,
        pwd: str | None = None,
        *,
        nodes: Nodes[OpcuaNode] | None = None,
        key_cert: KeyCertPair | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(url, usr, pwd, nodes=nodes)

        if self._url.scheme != "opc.tcp":
            raise ValueError("Given URL is not a valid OPC url (scheme: opc.tcp).")

        self.connection: Client
        self._connected = False
        self._retry = RetryWaiter()
        self._retry_interval_checker = RetryWaiter()
        self._conn_check_interval = 1

        self._sub: Subscription
        self._subbed_nodes: list[int] = []
        self._sub_task: asyncio.Task
        self._subscription_open: bool = False
        self._subscription_nodes: set[OpcuaNode] = set()

        self.connection_interval_checker = IntervalChecker()

        self._key_cert: KeyCertPair | None = key_cert
        self._try_secure_connect = True

    @classmethod
    def _from_node(
        cls, node: OpcuaNode, usr: str | None = None, pwd: str | None = None, **kwargs: Any
    ) -> OpcuaConnection:
        """Initialize the connection object from an Opcua protocol Node object.

        :param node: Node to initialize from.
        :param usr: Username to use.
        :param pwd: Password to use.
        :param kwargs: Other arguments are ignored.
        :return: OpcuaConnection object.
        """
        key_cert = kwargs.get("key_cert")

        return super()._from_node(node, usr=usr, pwd=pwd, key_cert=key_cert)

    @classmethod
    def from_ids(
        cls,
        ids: Sequence[str],
        url: str,
        usr: str | None = None,
        pwd: str | None = None,
    ) -> OpcuaConnection:
        """Initialize the connection object from an OPC UA protocol through the node IDs.

        :param ids: Identification of the Node.
        :param url: URL for  connection.
        :param usr: Username in OPC UA for login.
        :param pwd: Password in OPC UA for login.
        :return: OpcuaConnection object.
        """
        nodes = [OpcuaNode(name=opc_id, usr=usr, pwd=pwd, url=url, protocol="opcua", opc_id=opc_id) for opc_id in ids]
        return cls(nodes[0].url, usr, pwd, nodes=nodes)

    def read(self, nodes: OpcuaNode | Nodes[OpcuaNode] | None = None) -> pd.DataFrame:
        """Read some manually selected values from OPC UA capable controller.

        :param nodes: Single node or list/set of nodes to read from.
        :return: pandas.DataFrame containing current values of the OPC UA-variables.
        :raises ConnectionError: When an error occurs during reading.
        """
        _nodes = self._validate_nodes(nodes)

        def read_node(node: OpcuaNode) -> dict[str, list]:
            try:
                opcua_variable = self.connection.get_node(node.opc_id)
                value = opcua_variable.read_value()
                if node.dtype is not None:
                    try:
                        value = node.dtype(value)
                    except ValueError as e:
                        raise ConnectionError(
                            f"Failed to typecast value '{value}' at {node.name} to {node.dtype.__name__}."
                        ) from e
            except uaerrors.BadNodeIdUnknown:
                raise ConnectionError(
                    f"The node id ({node.opc_id}) refers to a node that does not exist in the server address space "
                    f"{self.url}. (BadNodeIdUnknown)"
                ) from None
            except RuntimeError as e:
                raise ConnectionError(str(e)) from e
            else:
                return {node.name: [value]}

        values: dict[str, list] = {}
        with self._connection(), concurrent.futures.ThreadPoolExecutor() as executor:
            results = executor.map(read_node, _nodes)
        for result in results:
            values.update(result)

        return pd.DataFrame(values, index=[self._assert_tz_awareness(datetime.now())])

    def write(self, values: Mapping[OpcuaNode, Any]) -> None:
        """Writes some manually selected values on OPC UA capable controller.

        :param values: Dictionary of nodes and data to write {node: value}.
        :raises ConnectionError: When an error occurs during reading.
        """
        nodes = self._validate_nodes(set(values.keys()))

        with self._connection():
            for node in nodes:
                try:
                    opcua_variable = self.connection.get_node(node.opc_id)
                    opcua_variable_type = opcua_variable.read_data_type_as_variant_type()
                    value = node.dtype(values[node]) if node.dtype is not None else values[node]
                    opcua_variable.write_value(ua.DataValue(ua.Variant(value, opcua_variable_type)))
                except uaerrors.BadNodeIdUnknown as e:
                    raise ConnectionError(
                        f"The node id ({node.opc_id}) refers to a node that does not exist in the server address space "
                        f"{self.url}. (BadNodeIdUnknown)"
                    ) from e
                except RuntimeError as e:
                    raise ConnectionError(str(e)) from e

    def subscribe(
        self, handler: SubscriptionHandler, nodes: OpcuaNode | Nodes[OpcuaNode] | None = None, interval: TimeStep = 1
    ) -> None:
        """Subscribe to nodes and call handler when new data is available. Basic architecture of the subscription is
        the client- server communication via subscription notify. This function works asynchronously. Subscriptions
        must always be closed using the close_sub function (use try, finally!).

        :param nodes: Single node or list/set of nodes to subscribe to.
        :param handler: SubscriptionHandler object with a push method that accepts node, value pairs.
        :param interval: Interval for receiving new data. It is interpreted as seconds when given as an integer.
        """
        _nodes = self._validate_nodes(nodes)
        interval = interval if isinstance(interval, timedelta) else timedelta(seconds=interval)

        self._subscription_nodes.update(_nodes)

        if self._subscription_open:
            # Adding nodes to subscription is enough to include them in the query. Do not start an additional loop
            # if one already exists
            return

        self._subscription_open = True

        loop = asyncio.get_event_loop()
        self._sub_task = loop.create_task(
            self._subscription_loop(
                _OPCSubHandler(handler=handler, interval_check_handler=self.connection_interval_checker),
                float(interval.total_seconds()),
            )
        )

    async def _subscription_loop(self, handler: _OPCSubHandler, interval: float) -> None:
        """The subscription loop makes sure that the subscription is reset in case the server generates an error.

        :param handler: Handler object with a push function to receive data.
        :param interval: Interval for requesting data in seconds.
        """
        subscribed = False
        while self._subscription_open:
            try:
                if not self._connected:
                    await self._retry.wait_async()
                    try:
                        self._connect()
                    except ConnectionError:
                        log.error(f"Retrying to connect to {self.url}.")  # noqa: TRY400
                        continue

                elif self._connected and not subscribed:
                    try:
                        self._sub = self.connection.create_subscription(interval * 1000, handler)
                        subscribed = True
                    except RuntimeError:
                        subscribed = False
                        log.error(f"Unable to subscribe to server {self.url} - Retrying.")  # noqa: TRY400
                        self._disconnect()
                        continue

                    for node in self._subscription_nodes:
                        try:
                            handler.add_node(node.opc_id, node)  # type: ignore[arg-type]
                            self._subbed_nodes.append(
                                self._sub.subscribe_data_change(self.connection.get_node(node.opc_id))
                            )
                        except RuntimeError as e:
                            log.warning(f"Could not subscribe to node '{node.name}' on server {self.url}, error: {e}")

            except (ConnectionAbortedError, ConnectionResetError, TimeoutError, ConCancelledError, BaseException) as e:
                if isinstance(e, (ConnectionAbortedError, ConnectionResetError)):
                    msg = f"Subscription to the OPC UA server {self.url} is unexpectedly terminated."
                if isinstance(e, TimeoutError):
                    msg = f"OPC UA client for server {self.url} doesn't receive a response from the server."
                if isinstance(e, ConCancelledError):
                    msg = (
                        f"Connection to OPC UA-Server {self.url} was terminated "
                        "during connection establishment or maintenance."
                    )
                log.exception(f"Handling exception for server {self.url}.")
                if msg:
                    msg += " Trying to reconnect."
                    log.info(msg)
                subscribed = False
                self._connected = False

            # Exit point in case the connection operates normally.
            if not self._check_connection():
                # Push Nan for every node
                for node in self._subscription_nodes:
                    handler.handler.push(node=node, value=float("nan"), timestamp=datetime.now())
                subscribed = False
                self._connected = False
                self._disconnect()

            elif self._connected and subscribed:
                _changed_within_interval = self.connection_interval_checker.check_interval_connection()

                if not _changed_within_interval:
                    subscribed = False
                    self._connected = False
                    log.warning(
                        f"The subscription connection for {self.url} doesn't change the values "
                        "anymore. Trying to reconnect."
                    )
                    self._disconnect()
                    self._retry_interval_checker.tried()
                    await self._retry_interval_checker.wait_async()
                else:
                    self._retry_interval_checker.success()
                    await asyncio.sleep(self._conn_check_interval)

    def close_sub(self) -> None:
        """Close an open subscription."""
        self._subscription_open = False
        try:
            self._sub.unsubscribe(self._subbed_nodes)
        except AttributeError:
            pass
        except Exception:
            log.exception("Canceling OpcUA subscription failed.")
        finally:
            self._subbed_nodes = []

        try:
            self._sub_task.cancel()
            self._sub.delete()
        except (OSError, RuntimeError) as e:
            log.debug(f"Deleting subscription for server {self.url} failed.")
            log.debug(f"Server {self.url} returned error: {e}.")
        except (TimeoutError, ConTimeoutError):
            log.debug(f"Timeout occurred while trying to close the subscription to server {self.url}.")
        except AttributeError:
            # Occurs if the subscription did not exist and can be ignored.
            pass
        except asyncua.sync.ThreadLoopNotRunning:
            # Occurs if the subscription (and therefore the thread loop) was already closed and can be ignored.
            pass

        self._disconnect()

    def _connect(self) -> None:
        """Connect to server. This will try to securely connect using Basic256SHA256 method
        before trying an insecure connection.
        """
        if not hasattr(self, "connection"):
            # Do not reninitialize connection if it already exists
            self.connection = Client(self.url)
        self._connected = False
        if self.usr is not None:
            self.connection.set_user(self.usr)
        if self.pwd is not None:
            self.connection.set_password(self.pwd)
        self._retry.tried()

        def _connect_insecure() -> None:
            self.connection.aio_obj.security_policy = SecurityPolicy()
            self.connection.aio_obj.uaclient.set_security(self.connection.aio_obj.security_policy)
            self.connection.connect()

        def _connect_secure(key_cert: KeyCertPair) -> None:
            try:
                self.connection.set_security(SecurityPolicyBasic256Sha256, key_cert.cert_path, key_cert.key_path)
                with Suppressor():
                    self.connection.connect()
            except ua.uaerrors.BadSecurityPolicyRejected:
                self._try_secure_connect = False
                _connect_insecure()
            except ua.UaError as e:
                if "No matching endpoints" in str(e):
                    self._try_secure_connect = False
                    _connect_insecure()
                else:
                    raise
            except (TimeoutError, ConTimeoutError, asyncio.exceptions.TimeoutError) as e:
                self._try_secure_connect = False
                raise ConnectionError("Host timeout during secure connect") from e

        try:
            if self._key_cert is not None and self._try_secure_connect:
                _connect_secure(key_cert=self._key_cert)
            else:
                _connect_insecure()
        except (socket.herror, socket.gaierror) as e:
            raise ConnectionError(f"Host not found: {self.url}") from e
        except (TimeoutError, ConTimeoutError, asyncio.exceptions.TimeoutError) as e:
            raise ConnectionError(f"Host timeout: {self.url}") from e
        except ConCancelledError as e:
            raise ConnectionError(f"Connection cancelled by host: {self.url}") from e
        except (RuntimeError, ConnectionError) as e:
            raise ConnectionError(f"OPC Connection Error: {self.url}: {e!s}") from e
        else:
            log.debug(f"Connected to OPC UA server: {self.url}")
            self._connected = True
            self._retry.success()

    def _check_connection(self) -> bool:
        if self._connected:
            try:
                self.connection.get_node(ua.FourByteNodeId(ua.ObjectIds.Server_ServerStatus_State)).read_value()
            except AttributeError:
                self._connected = False
                log.debug(f"Connection to server {self.url} did not exist - connection check failed.")
            except Exception:
                self._connected = False
                log.error(f"Error while checking connection to server {self.url}.")  # noqa: TRY400
            else:
                self._connected = True

        if not self._connected:
            self._disconnect()

        return self._connected

    def _disconnect(self) -> None:
        """Disconnect from server."""
        self._connected = False
        try:
            self.connection.disconnect()
        except (ConCancelledError, ConnectionAbortedError):
            log.debug(f"Connection to {self.url} already closed by server.")
        except (OSError, RuntimeError) as e:
            log.debug(f"Closing connection to server {self.url} failed")
            log.debug(f"Connection to {self.url} returned an error while closing the connection: {e}")
        except AttributeError:
            log.debug(f"Connection to server {self.url} already closed.")

    @contextmanager
    def _connection(self) -> Generator:
        """Connect to the server and return a context manager that automatically disconnects when finished."""
        try:
            self._connect()
            yield None
        finally:
            self._disconnect()

    def _validate_nodes(self, nodes: OpcuaNode | Nodes[OpcuaNode] | None) -> set[OpcuaNode]:
        vnodes = super()._validate_nodes(nodes)
        _nodes = set()
        for node in vnodes:
            if isinstance(node, OpcuaNode):
                _nodes.add(node)

        return _nodes


class _OPCSubHandler:
    """Wrapper for the OPC UA subscription. Enables the subscription to use the standardized eta_nexus subscription
    format.

    :param handler: *eta_nexus* style subscription handler.
    """

    def __init__(self, handler: SubscriptionHandler, interval_check_handler: IntervalChecker) -> None:
        self.handler = handler
        self._sub_nodes: dict[str | int, OpcuaNode] = {}
        self._node_interval_to_check = interval_check_handler

    def add_node(self, opc_id: str | int, node: OpcuaNode) -> None:
        """Add a node to the subscription. This is necessary to translate between formats."""
        self._sub_nodes[opc_id] = node

    def datachange_notification(self, node: OpcuaNode, val: Any, data: Any) -> None:
        """datachange_notification is called whenever subscribed input data is received via OPC UA. This pushes data
        to the actual eta_nexus subscription handler.

        :param node: Node Object, which was subscribed to and which has sent an updated value.
        :param val: New value of OPC UA node.
        :param data: Raw data of OPC UA (not used).
        """
        _time = self.handler._assert_tz_awareness(datetime.now())

        self.handler.push(self._sub_nodes[str(node)], val, _time)
        self._node_interval_to_check.push(node=self._sub_nodes[str(node)], value=val, timestamp=_time)

    def status_change_notification(self, status: ua.StatusChangeNotification) -> None:
        pass

    def event_notification(self, event: ua.EventNotificationList) -> None:
        pass
