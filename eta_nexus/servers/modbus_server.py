from __future__ import annotations

import socket
from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING

import pandas as pd
from pyModbusTCP.server import ModbusServer as BaseModbusServer

from eta_nexus import ensure_timezone, url_parse
from eta_nexus.nodes.modbus_node import ModbusNode, bitarray_to_registers

if TYPE_CHECKING:
    import types
    from collections.abc import Mapping
    from typing import Any

    from typing_extensions import Self

    from eta_nexus.util.type_annotations import Nodes

log = getLogger(__name__)


class ModbusServer:
    """Provides a Modbus server with a number of specified nodes.

    When building a data structure make sure to consider the following. Numbers (integers and flaots) will be
    stored depending on the byte_length setting of the Modbus node. This is 2 by default and means that
    each number will take up 16 bits. This affects, how many "channels" are needed for each number. You
    have to ensure not to overwrite parts of a number by leaving enough channels after the start of a number empty.

    :param ip: IP Address to listen on (default: None).
    :param port: Port to listen on (default: 502).
    """

    def __init__(self, ip: str | None = None, port: int = 502) -> None:
        #: URL of the Modbus Server.
        self.url: str
        if ip is None:
            try:
                host = socket.gethostbyname(socket.gethostname())
            except socket.gaierror:
                host = "127.0.0.1"
            self.url = f"modbus.tcp://{host}:{port}"
        else:
            self.url = f"modbus.tcp://{ip}:{port}"
        log.info(f"Server Address is {self.url}")

        self._url, _, _ = url_parse(self.url)

        self._server: BaseModbusServer = BaseModbusServer(self._url.hostname, self._url.port, no_block=True)
        self.start()

    def write(self, values: Mapping[ModbusNode, Any]) -> None:
        """Write some values directly to the Modbus server. This function supports writing int, float and
        string objects. If you have another object, convert it to bytes before writing.

        :param values: Dictionary of data to write {node.name: value}.
        """
        nodes = self._validate_nodes(set(values.keys()))
        srv_info = BaseModbusServer.ServerInfo()

        for node in nodes:
            bits = node.encode_bits(values[node]) if not isinstance(values[node], list) else values[node]

            if node.mb_register == "coils":
                self._server.data_hdl.write_coils(node.mb_channel, bits, srv_info)
            elif node.mb_register == "holding":
                bits = bitarray_to_registers(bits)
                # If the wordorder is little, the bits have to be reversed.
                if node.mb_wordorder == "little":
                    bits = bits[::-1]
                self._server.data_hdl.write_h_regs(node.mb_channel, bits, srv_info)

    def read(self, nodes: ModbusNode | Nodes[ModbusNode] | None = None) -> pd.DataFrame:
        """Read some manually selected values directly from the Modbusserver.

        :param nodes: Single node or list/set of nodes to read from.
        :return: pandas.DataFrame containing current values of the Modbus-variables.
        :raises RuntimeError: When an error occurs during reading.
        """
        _nodes = self._validate_nodes(nodes)
        srv_info = BaseModbusServer.ServerInfo()

        results = {}

        for node in _nodes:
            if node.mb_register == "holding":
                val = self._server.data_hdl.read_h_regs(node.mb_channel, node.mb_bit_length // 16, srv_info)
            elif node.mb_register == "coils":
                val = self._server.data_hdl.read_coils(node.mb_channel, node.mb_bit_length, srv_info)
            elif node.mb_register == "discrete_input":
                val = self._server.data_hdl.read_d_inputs(node.mb_channel, node.mb_bit_length, srv_info)
            elif node.mb_register == "input":
                val = self._server.data_hdl.read_i_regs(node.mb_channel, node.mb_bit_length // 16, srv_info)
            else:
                raise ValueError(f"The specified register type is not supported: {node.mb_register}")

            if val.ok and (node.mb_register in ("holding", "input")):
                results[node.name] = node.decode_modbus_value(val.data)
            elif val.ok and isinstance(val.data, list):
                if len(val.data) > 1:
                    for idx, value in enumerate(val.data):
                        results[f"{node.name}_{idx}"] = value
                else:
                    results[node.name] = val.data[0]
            elif val.ok:
                results[node.name] = val.data
            else:
                raise RuntimeError("Could not decode bits from ModbusServer.")

        return pd.DataFrame(results, index=[ensure_timezone(datetime.now())])

    def start(self) -> None:
        """Restart the server after it was stopped."""
        self._server.start()

    def stop(self) -> None:
        """This should always be called, when the server is not needed anymore. It stops the server."""
        self._server.stop()

    @property
    def active(self) -> bool:
        return self._server.is_run

    def _validate_nodes(self, nodes: ModbusNode | Nodes[ModbusNode] | None) -> set[ModbusNode]:
        """Make sure that nodes are a Set of nodes and that all nodes correspond to the protocol and url
        of the connection.

        :param nodes: Sequence of Node objects to validate.
        :return: Set of valid Node objects for this connection.
        """
        _nodes = None

        if nodes:
            # If not using preselected nodes from self.selected_nodes, check if nodes correspond to the connection
            nodes = {nodes} if isinstance(nodes, ModbusNode) else nodes
            _nodes = {
                node
                for node in nodes
                if isinstance(node, ModbusNode) and node.url_parsed.hostname == self._url.hostname
            }

        # Make sure that some nodes remain after the checks and raise an error if there are none.
        if not _nodes or len(_nodes) == 0:
            raise ValueError(
                f"Some nodes to read from/write to must be specified. If nodes were specified, they do not "
                f"match the connection {self.url}"
            )

        return _nodes

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None
    ) -> None:
        self.stop()
