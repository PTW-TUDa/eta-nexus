"""Utilities for connecting to modbus servers"""

from __future__ import annotations

import asyncio
import socket
from contextlib import contextmanager
from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING

import pandas as pd
from pyModbusTCP import constants as mb_const
from pyModbusTCP.client import ModbusClient

from eta_connect.connectors.node import NodeModbus
from eta_connect.connectors.util import (
    IntervalChecker,
    RetryWaiter,
    bitarray_to_registers,
    decode_modbus_value,
    encode_bits,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping
    from typing import Any

    from eta_connect.type_hints import Nodes, TimeStep

from .base_classes import Connection, SubscriptionHandler

log = getLogger(__name__)


class ModbusConnection(Connection[NodeModbus], protocol="modbus"):
    """The Modbus Connection class allows reading and writing from and to Modbus servers and clients. Additionally,
    it implements a subscription service, which reads continuously in a specified interval.

    :param url: URL of the Modbus Server.
    :param usr: No login supported, only here to satisfy the interface
    :param pwd: No login supported, only here to satisfy the interface
    :param nodes: List of nodes to use for all operations.
    """

    def __init__(
        self, url: str, usr: str | None = None, pwd: str | None = None, *, nodes: Nodes[NodeModbus] | None = None
    ) -> None:
        super().__init__(url, usr, pwd, nodes=nodes)

        if self._url.scheme != "modbus.tcp":
            raise ValueError("Given URL is not a valid Modbus url (scheme: modbus.tcp)")

        self.connection: ModbusClient = ModbusClient(host=self._url.hostname, port=self._url.port, timeout=2)

        self._subscription_open: bool = False
        self._subscription_nodes: set[NodeModbus] = set()
        self._sub: asyncio.Task

        self._retry = RetryWaiter()
        self._retry_interval_checker = RetryWaiter()

        self._connection_interval_checker = IntervalChecker()

    @classmethod
    def _from_node(
        cls, node: NodeModbus, usr: str | None = None, pwd: str | None = None, **kwargs: Any
    ) -> ModbusConnection:
        """Initialize the connection object from a modubs protocol node object.

        :param node: Node to initialize from.
        :param usr: Username to use.
        :param pwd: Password to use.
        :param kwargs: Other arguments are ignored.
        :return: ModbusConnection object.
        """

        return super()._from_node(node, usr=usr, pwd=pwd)

    def read(self, nodes: NodeModbus | Nodes[NodeModbus] | None = None) -> pd.DataFrame:
        """Read some manually selected nodes from Modbus server.

        :param nodes: Single node or list/set of nodes to read from.
        :return: Dictionary containing current values of the Modbus variables.
        """
        _nodes = self._validate_nodes(nodes)

        values = {}

        with self._connection():
            results = {node: self._read_mb_value(node) for node in _nodes}

        for node, result in results.items():
            value = decode_modbus_value(result, node.mb_byteorder, node.dtype, node.mb_wordorder)
            values[node.name] = value

        return pd.DataFrame(values, index=[self._assert_tz_awareness(datetime.now())])

    def write(self, values: Mapping[NodeModbus, Any]) -> None:
        """Write some manually selected values on Modbus capable controller.

        .. warning::
            This is not implemented.

        :param values: Dictionary of nodes and data to write {node: value}.
        """
        nodes = self._validate_nodes(set(values.keys()))

        with self._connection():
            for node in nodes:
                if not isinstance(values[node], list):
                    bits = encode_bits(values[node], node.mb_byteorder, node.mb_bit_length, node.dtype)
                else:
                    bits = values[node]

                self._write_mb_value(node, bits)

    def subscribe(
        self, handler: SubscriptionHandler, nodes: NodeModbus | Nodes[NodeModbus] | None = None, interval: TimeStep = 1
    ) -> None:
        """Subscribe to nodes and call handler when new data is available. Basic architecture of the subscription is
        the client- server communication. This function works asynchronously.

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
        self._sub = loop.create_task(self._subscription_loop(handler, float(interval.total_seconds())))

    def close_sub(self) -> None:
        """Close the subscription."""
        self._subscription_open = False
        if self.exc:
            raise self.exc

        try:
            self._sub.cancel()
        except Exception:
            pass

        try:
            self.connection.close()
        except Exception:
            pass

    async def _subscription_loop(self, handler: SubscriptionHandler, interval: float) -> None:
        """The subscription loop handles requesting data from the server in the specified interval.

        :param handler: Handler object with a push function to receive data.
        :param interval: Interval for requesting data in seconds.
        """

        try:
            while self._subscription_open:
                try:
                    await self._retry.wait_async()
                    self._connect()
                except ConnectionError as e:
                    log.warning(str(e))
                    continue

                for node in self._subscription_nodes:
                    result = None
                    try:
                        result = self._read_mb_value(node)
                    except ValueError as e:
                        log.warning(str(e))
                    except ConnectionError:
                        handler.push(node, pd.NA, self._assert_tz_awareness(datetime.now()))
                        continue

                    if result is not None:
                        _result = decode_modbus_value(result, node.mb_byteorder, node.dtype, node.mb_wordorder)

                        time = self._assert_tz_awareness(datetime.now())

                        handler.push(node, _result, time)

                        self._connection_interval_checker.push(node=node, value=_result, timestamp=time)

                if self.connection.is_open:
                    _changed_within_interval = self._connection_interval_checker.check_interval_connection()

                    if not _changed_within_interval:
                        log.warning(
                            f"The subscription connection for {self.url} doesn't change the values "
                            "anymore. Trying to reconnect."
                        )
                        self._retry_interval_checker.tried()
                        await self._retry_interval_checker.wait_async()
                    else:
                        self._retry_interval_checker.success()
                        await asyncio.sleep(interval)
        except BaseException as e:
            self.exc = e

    def _read_mb_value(self, node: NodeModbus) -> list[int]:
        """Read raw value from modbus server. This function should not be used directly. It does not
        establish a connection or handle connection errors.
        """
        if not self.connection.is_open:
            raise ConnectionError(f"Could not establish connection to host {self.url}")

        self.connection.unit_id = node.mb_slave

        if node.mb_register == "holding":
            result = self.connection.read_holding_registers(node.mb_channel, node.mb_bit_length // 16)
        elif node.mb_register == "coils":
            result = self.connection.read_coils(node.mb_channel, node.mb_bit_length)
        elif node.mb_register == "discrete_input":
            result = self.connection.read_discrete_inputs(node.mb_channel, node.mb_bit_length)
        elif node.mb_register == "input":
            result = self.connection.read_input_registers(node.mb_channel, node.mb_bit_length // 16)
        else:
            raise ValueError(f"The specified register type for '{node.name}' is not supported: {node.mb_register}")

        if result is None:
            self._handle_mb_error()
        else:
            result = [int(x) for x in result]
        return result

    def _write_mb_value(self, node: NodeModbus, value: list[int]) -> None:
        """Write raw value to the modbus server. This function should not be used directly. It does not establish
        a connection or handle connection errors.
        """
        if not self.connection.is_open:
            raise ConnectionError(f"Could not establish connection to host {self.url}.")

        self.connection.unit_id = node.mb_slave

        if node.mb_register == "coils":
            success = self.connection.write_multiple_coils(node.mb_channel, value)
        elif node.mb_register == "holding":
            success = self.connection.write_multiple_registers(node.mb_channel, bitarray_to_registers(value))
        else:
            raise ValueError(f"The specified register type is not supported for writing: {node.mb_register}")

        if not success:
            raise ConnectionError(f"Could not write value to channel {node.mb_channel} on server: {self.url}.")

    def _connect(self) -> None:
        """Connect to server."""
        try:
            if not self.connection.is_open:
                self._retry.tried()
                if not self.connection.open():
                    raise ConnectionError(f"Could not establish connection to host {self.url}")
        except (socket.herror, socket.gaierror) as e:
            raise ConnectionError(f"Host not found: {self.url}") from e
        except socket.timeout as e:
            raise ConnectionError(f"Host timeout: {self.url}") from e
        except (RuntimeError, ConnectionError) as e:
            raise ConnectionError(f"Connection Error: {self.url}, Error: {e!s}") from e
        else:
            if self.connection.is_open:
                self._retry.success()
            else:
                raise ConnectionError(f"Could not establish connection to host {self.url}")

    def _disconnect(self) -> None:
        """Disconnect from server."""
        try:
            self.connection.close()
        except (OSError, RuntimeError) as e:
            log.error(f"Closing connection to server {self.url} failed")
            log.info(f"Connection to {self.url} returned error: {e}")
        except AttributeError:
            log.error(f"Connection to server {self.url} already closed.")

    @contextmanager
    def _connection(self) -> Generator:
        """Connect to the server and return a context manager that automatically disconnects when finished."""
        try:
            self._connect()
            yield None
        except ConnectionError as e:
            raise e
        finally:
            self._disconnect()

    def _handle_mb_error(self) -> None:
        error = self.connection.last_error
        exception = self.connection.last_except

        if error != mb_const.MB_NO_ERR:
            raise ConnectionError(f"ModbusError {error} at {self.url}: {self.connection.last_error_as_txt}")
        if exception != mb_const.EXP_NONE:
            raise ConnectionError(f"ModbusError {exception} at {self.url}: {self.connection.last_except_as_txt}")

        raise ConnectionError(f"Unknown ModbusError at {self.url}")

    def _validate_nodes(self, nodes: NodeModbus | Nodes[NodeModbus] | None) -> set[NodeModbus]:
        vnodes = super()._validate_nodes(nodes)
        _nodes = set()
        for node in vnodes:
            if isinstance(node, NodeModbus):
                _nodes.add(node)

        return _nodes
