from __future__ import annotations

import socket
from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING

# Async import
import asyncua.sync
import pandas as pd
from asyncua import ua  # , Server as asyncServer

# Sync import
from asyncua.sync import Server, ThreadLoopNotRunning
from asyncua.ua import uaerrors

from eta_connect import ensure_timezone, url_parse
from eta_connect.connectors.node import NodeOpcUa

if TYPE_CHECKING:
    import types
    from collections.abc import Mapping
    from typing import Any

    # Sync import
    from asyncua.sync import SyncNode as SyncOpcNode
    from typing_extensions import Self

    # Async import
    # TODO: add async import: from asyncua import Node as asyncSyncOpcNode
    # https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-utility/-/issues/270
    from eta_connect.type_hints import Nodes

log = getLogger(__name__)


class OpcUaServer:
    """Provides an OPC UA server with a number of specified nodes. Each node can contain single values or arrays.

    :param namespace: Namespace of the OPC UA Server.
    :param ip: IP Address to listen on (default: None).
    :param port: Port to listen on (default: 4840).
    """

    def __init__(self, namespace: str | int, ip: str | None = None, port: int = 4840) -> None:
        #: URL of the OPC UA Server.
        self.url: str
        if ip is None:
            try:
                host = socket.gethostbyname(socket.gethostname())
            except socket.gaierror:
                host = "127.0.0.1"
            self.url = f"opc.tcp://{host}:{port}"
        else:
            self.url = f"opc.tcp://{ip}:{port}"
        log.info(f"Server Address is {self.url}")

        self._url, _, _ = url_parse(self.url)

        self._server: Server = Server()
        self._server.set_endpoint(self.url)

        self.idx: int = self._server.register_namespace(str(namespace))  #: idx: Namespace of the OPC UA _server
        log.debug(f'Server Namespace set to "{namespace}"')

        self._server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        self._server.set_server_name("ETA Utility OPC UA Server")
        self._server.start()

    def write(self, values: Mapping[NodeOpcUa, Any]) -> None:
        """Write some values directly to the OPC UA server.

        :param values: Dictionary of data to write {node.name: value}.
        """

        nodes = self._validate_nodes(set(values.keys()))

        for node in nodes:
            var = self._server.get_node(node.opc_id)
            try:
                opc_type = var.read_data_type_as_variant_type()
            except asyncua.sync.ThreadLoopNotRunning as e:
                raise ConnectionError(f"Server {self} is not running.") from e
            var.write_value(ua.Variant(values[node], opc_type))

    def read(self, nodes: NodeOpcUa | Nodes[NodeOpcUa] | None = None) -> pd.DataFrame:
        """
        Read some manually selected values directly from the OPC UA server.

        :param nodes: Single node or list/set of nodes to read from.
        :return: pandas.DataFrame containing current values of the OPC UA-variables.
        :raises RuntimeError: When an error occurs during reading.
        """
        _nodes = self._validate_nodes(nodes)

        _dikt = {}
        for node in _nodes:
            try:
                opcua_variable = self._server.get_node(node.opc_id)
                value = opcua_variable.read_value()
                _dikt[node.name] = [value]
            except uaerrors.BadNodeIdUnknown as e:
                raise RuntimeError(
                    f"The node id ({node.opc_id}) refers to a node that does not exist in the server address space "
                    f"{self.url}. (BadNodeIdUnknown)"
                ) from e

        return pd.DataFrame(_dikt, index=[ensure_timezone(datetime.now())])

    def create_nodes(self, nodes: Nodes[NodeOpcUa]) -> None:
        """Create nodes on the server from a list of nodes. This will try to create the entire node path.

        :param nodes: List or set of nodes to create.
        """

        def create_object(parent: SyncOpcNode, opc_name: str, opc_path_str: str, opc_id: str) -> SyncOpcNode:
            children: list[SyncOpcNode] = asyncua.sync._to_sync(parent.tloop, parent.get_children())
            for child in children:
                ident = child.nodeid.Identifier
                if isinstance(ident, str) and ident.strip() == opc_path_str:
                    return child
            return asyncua.sync._to_sync(parent.tloop, parent.add_object(opc_id, opc_name))

        _nodes = self._validate_nodes(nodes)

        for node in _nodes:
            try:
                split_path = node.opc_path_str.split(".")  # type: ignore
                # If the path starts with a dot, the dot belongs to the root node and is not a separator
                if node.opc_path_str.startswith("."):  # type: ignore
                    split_path = node.opc_path_str.rsplit(".", maxsplit=len(split_path) - 2)  # type: ignore

                # Create SyncNode from asyncNode
                last_obj = asyncua.sync._to_sync(self._server.tloop, self._server.aio_obj.get_objects_node())
                for i in range(len(split_path) - 1):
                    _opc_name = split_path[i].strip(" .")
                    _opc_path_str = ".".join(split_path[: i + 1])
                    _opc_id = f"ns={node.opc_ns};s={_opc_path_str}"

                    last_obj = create_object(last_obj, _opc_name, _opc_path_str, _opc_id)

                init_val: Any
                if not hasattr(node, "dtype"):
                    init_val = 0.0
                elif node.dtype is int:
                    init_val = 0
                elif node.dtype is bool:
                    init_val = False
                elif node.dtype is str:
                    init_val = ""
                else:
                    init_val = 0.0

                last_obj.add_variable(node.opc_id, node.opc_name, init_val)
                log.debug(f"OPC UA Node created: {node.opc_id}")
            except uaerrors.BadNodeIdExists:
                log.warning(f"Node with NodeId : {node.opc_id} could not be created. It already exists.")
            except RuntimeError as e:
                raise ConnectionError(str(e)) from e

    def delete_nodes(self, nodes: Nodes[NodeOpcUa]) -> None:
        """Delete the given nodes and their parents (if the parents do not have other children).

        :param nodes: List or set of nodes to be deleted.
        """

        def delete_node_parents(node: SyncOpcNode, depth: int = 20) -> None:
            parents = node.get_references(direction=ua.BrowseDirection.Inverse)
            if not node.get_children():
                node.delete(delete_references=True)
                log.info(f"Deleted Node {node.nodeid} from server {self.url}.")
            else:
                log.info(f"Node {node.nodeid} on server {self.url} has remaining children and was not deleted.")
            for parent in parents:
                if depth > 0:
                    delete_node_parents(self._server.get_node(parent.NodeId), depth=depth - 1)

        nodes = self._validate_nodes(nodes)

        for node in nodes:
            delete_node_parents(self._server.get_node(node.opc_id))

    def start(self) -> None:
        """Restart the server after it was stopped."""
        self._server.start()

    def stop(self) -> None:
        """This should always be called, when the server is not needed anymore. It stops the server."""
        try:
            self._server.stop()
        except AttributeError:
            # Occurs only if server did not exist and can be ignored.
            pass
        except ThreadLoopNotRunning:
            # Occurs only if server was already stopped (and therefore the ThreadLoop as well) and can be ignored.
            pass

    @property
    def active(self) -> bool:
        return self._server.aio_obj.bserver._server._serving

    def allow_remote_admin(self, allow: bool) -> None:
        """Allow remote administration of the server.

        :param allow: Set to true to enable remote administration of the server.
        """
        self._server.aio_obj.allow_remote_admin(allow)

    def _validate_nodes(self, nodes: NodeOpcUa | Nodes[NodeOpcUa] | None) -> set[NodeOpcUa]:
        """Make sure that nodes are a Set of nodes and that all nodes correspond to the protocol and url
        of the connection.

        :param nodes: Sequence of Node objects to validate.
        :return: Set of valid Node objects for this connection.
        """
        _nodes = None

        if nodes:
            # If not using preselected nodes from self.selected_nodes, check if nodes correspond to the connection
            nodes = {nodes} if isinstance(nodes, NodeOpcUa) else nodes
            _nodes = {
                node for node in nodes if isinstance(node, NodeOpcUa) and node.url_parsed.hostname == self._url.hostname
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
