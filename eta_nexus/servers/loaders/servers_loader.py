from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import suppress
from logging import getLogger
from typing import Any, cast

from eta_nexus.nodes import Node
from eta_nexus.servers import ModbusServer, OpcuaServer
from eta_nexus.util.io_utils import load_config
from eta_nexus.util.utils import dict_get_any, url_parse

log = getLogger(__name__)


def _server_host_port_and_netloc(srv_cfg: Mapping[str, Any], protocol: str) -> tuple[str, int | None, str]:
    """Resolve server host, port and netloc (host:port) using shared utils."""

    cfg_dict = dict(srv_cfg)
    raw_url = str(dict_get_any(cfg_dict, "url", fail=False, default="") or "").strip()
    if raw_url in {"", "nan", "None"}:
        ip = dict_get_any(cfg_dict, "ip", fail=False, default=None)
        port = dict_get_any(cfg_dict, "port", fail=False, default=None)
        raw_url = f"{ip}:{port}" if ip and port else (str(ip) if ip else "")

    scheme = "opc.tcp" if protocol == "opcua" else ("modbus.tcp" if protocol == "modbus" else "")
    parsed, _, _ = url_parse(raw_url, scheme=scheme)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port

    if protocol == "opcua":
        override = os.getenv("ETA_NEXUS_TEST_OPCUA_PORT")
        if override:
            with suppress(ValueError):
                port = int(override)
    elif protocol == "modbus":
        override = os.getenv("ETA_NEXUS_TEST_MODBUS_PORT")
        if override:
            with suppress(ValueError):
                port = int(override)

    netloc = parsed.netloc if parsed.netloc else host if port is None else f"{host}:{port}"
    return host, port, netloc


def _extract_opc_namespace(nodes_cfg: Sequence[Mapping[str, Any]]) -> int | None:
    """Try to extract the OPC UA namespace index from the first node that defines an "opc_id"."""

    for node_cfg in nodes_cfg:
        opc_id = node_cfg.get("opc_id")
        if isinstance(opc_id, str) and opc_id.startswith("ns="):
            ns_part = opc_id.split(";", 1)[0]
            with suppress(IndexError, ValueError):
                return int(ns_part.split("=", 1)[1])
    return None


def _iter_system_configs(config: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    systems = config.get("system")
    if systems is None:
        yield dict(config)
        return

    if not isinstance(systems, Sequence) or isinstance(systems, (str, bytes)):
        raise TypeError("'system' must be a sequence of system configurations.")

    for system_cfg in systems:
        if not isinstance(system_cfg, Mapping):
            raise TypeError("Each entry in 'system' must be a mapping.")
        yield dict(system_cfg)


def from_config(*files: str | os.PathLike[str]) -> dict[str, Any]:
    """Load one or more config files and instantiate the configured servers."""

    main_config: dict[str, list[Mapping[str, Any]]] = {"system": []}

    for file_path in files:
        config = load_config(file_path)
        if not isinstance(config, Mapping):
            raise TypeError("Config file must define a dictionary of options.")
        main_config["system"].extend(list(_iter_system_configs(config)))

    return from_dict(**main_config)


def from_dict(**config: Any) -> dict[str, Any]:
    """Instantiate servers from a configuration dictionary compatible with ConnectionManager."""

    systems = config.get("system")
    if not isinstance(systems, Sequence) or isinstance(systems, (str, bytes)) or len(systems) < 1:
        raise KeyError("Could not find a valid 'system' section in the configuration")

    servers: dict[str, Any] = {}

    for system in systems:
        if not isinstance(system, Mapping):
            raise TypeError("Each system entry must be a mapping.")

        sys_name = system.get("name")
        if not isinstance(sys_name, str) or not sys_name:
            raise KeyError("Each system must define a non-empty 'name'.")

        sys_servers = system.get("servers", {})
        if not isinstance(sys_servers, Mapping):
            raise TypeError("'servers' must be a mapping of aliases to server configs.")

        sys_nodes = system.get("nodes", [])
        if not isinstance(sys_nodes, Sequence):
            raise TypeError("'nodes' must be a list of node configs.")

        nodes_by_alias: dict[str, list[Mapping[str, Any]]] = {}
        for node_cfg in sys_nodes:
            if isinstance(node_cfg, Mapping):
                alias = node_cfg.get("server")
                if isinstance(alias, str):
                    nodes_by_alias.setdefault(alias, []).append(dict(node_cfg))

        for alias, srv_cfg in sys_servers.items():
            if not isinstance(srv_cfg, Mapping):
                raise TypeError("Each server config must be a mapping.")

            srv_dict = dict(srv_cfg)
            protocol = str(dict_get_any(srv_dict, "protocol")).strip().lower()
            usr = dict_get_any(srv_dict, "usr", fail=False, default=None)
            pwd = dict_get_any(srv_dict, "pwd", "pw", fail=False, default=None)
            key = f"{sys_name}.{alias}"

            if protocol not in {"opcua", "modbus"}:
                log.warning("Skipping unsupported server protocol '%s' for '%s'", protocol, key)
                continue

            if protocol == "opcua":
                host, port, netloc = _server_host_port_and_netloc(srv_dict, protocol)
                namespace = _extract_opc_namespace(nodes_by_alias.get(alias, [])) or 2
                opc_server = OpcuaServer(namespace, ip=host, port=port or 4840)

                opc_nodes_cfg = nodes_by_alias.get(alias, [])
                if opc_nodes_cfg:
                    opc_nodes = Node.from_dict(
                        [
                            {
                                "name": f"{sys_name}.{node['name']}",
                                "url": netloc,
                                "protocol": protocol,
                                "usr": usr,
                                "pwd": pwd,
                                **{k: v for k, v in node.items() if k not in {"server", "name"}},
                            }
                            for node in opc_nodes_cfg
                        ]
                    )
                    try:
                        opc_server.create_nodes(opc_nodes)
                    except Exception:
                        log.exception("Failed to create OPC UA nodes for server '%s'", key)
                    else:
                        with suppress(AttributeError, TypeError):
                            cast("Any", opc_server).nodes = opc_nodes

                servers[key] = opc_server

            else:
                host, port, _ = _server_host_port_and_netloc(srv_dict, protocol)
                modbus_server = ModbusServer(ip=host, port=port or 502)
                servers[key] = modbus_server

    return servers
