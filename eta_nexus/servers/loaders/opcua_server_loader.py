from pathlib import Path

from eta_nexus.nodes import OpcuaNode
from eta_nexus.servers import OpcuaServer
from eta_nexus.util.io_utils import load_config


def load_opcua_servers_from_config(config_path: str) -> list[OpcuaServer]:
    """
    Load and instantiate OPC UA servers from a configuration file.

    Supported config shapes (both are normalized internally):
         {
           "servers": [
             {
               "namespace": "Factory",
               "ip": "127.0.0.1", "port": 4840,
               "ns_index": 2,  # optional, default 2
               "nodes": [
                 {"name": "Temperature", "path": "Factory.Line1.T", "datatype": "float"},
                 ...
               ]
             }, ...
           ]
         }

         {
           "system": [
             {
               "name": "CHP",
               "servers": {
                 "glt": {"url": "127.0.0.1:4840", "protocol": "opcua", "usr": "...", "pwd": "..."}
               },
               "nodes": [
                 {"name": "power_elek", "server": "glt",
                  "opc_id": "ns=6;s=...", "dtype": "float"},
                 ...
               ]
             }
           ]
         }

    Normalization rules:
      - Endpoint: prefer `url`/`endpoint` (with or without `opc.tcp://`); otherwise compose from `ip` + `port`.
      - If only `url` is provided, it is parsed into `ip` and `port`.
      - NodeId: prefer explicit `opc_id`; else derive from `path` using `ns_index` (default 2):
        `ns={ns_index};s=.{{path}}`.
      - DType aliases are mapped case-insensitively (e.g., double→float, boolean→bool, uint16→int).

    Returns:
      List[OpcuaServer] with nodes created and attached.
    """
    path = Path(config_path)
    config = load_config(path)

    servers = []
    raw_servers = _extract_servers(config)

    for s in raw_servers:
        namespace = s.get("namespace") or s.get("name") or "default"
        ip = s.get("ip")
        port = s.get("port", 4840)

        server = OpcuaServer(namespace=namespace, ip=ip, port=port)

        nodes_conf = s.get("nodes", [])
        nodes = []
        for node_conf in nodes_conf:
            node = OpcuaNode(
                name=node_conf["name"],
                url=server.url,
                protocol="opcua",
                opc_id=node_conf["opc_id"],
                dtype=_map_dtype(str(node_conf.get("dtype", "float"))),
            )
            nodes.append(node)

        if nodes:
            server.create_nodes(nodes)
            server.nodes = nodes

        servers.append(server)

    return servers


def _map_dtype(dtype_str: str) -> type:
    """Map common (case-insensitive) dtype aliases to Python base types.

    Integer-like aliases → int; floating-point aliases → float; boolean → bool; string → str.
    Unknown types default to float (backward-compatible with previous behavior).
    """
    s = (dtype_str or "").strip().lower()
    int_aliases = {"int", "int8", "sbyte", "byte", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64"}
    float_aliases = {"float", "single", "double"}
    bool_aliases = {"bool", "boolean"}
    str_aliases = {"str", "string"}

    if s in int_aliases:
        return int
    if s in float_aliases:
        return float
    if s in bool_aliases:
        return bool
    if s in str_aliases:
        return str
    return float


def _extract_servers(config: dict) -> list[dict]:
    """Normalize supported config shapes into a list of standardized servers.

    Each returned server dict has: name, namespace, ip, port, nodes (list).
    Each node dict has: name, opc_id, dtype.
    """
    out: list[dict] = []

    servers_obj = config.get("servers")
    if isinstance(servers_obj, list):
        out.extend(_extract_from_legacy_list(servers_obj))
    elif isinstance(servers_obj, dict):
        out.extend(_extract_from_legacy_dict(servers_obj))

    systems_obj = config.get("system")
    if systems_obj is not None:
        out.extend(_extract_from_system(systems_obj))

    return out


def _extract_from_legacy_list(servers_obj: list) -> list[dict]:
    out: list[dict] = []
    for idx, s in enumerate(servers_obj):
        if not isinstance(s, dict):
            continue
        name = s.get("name") or f"server_{idx}"
        std = _standardize_legacy_server(s, fallback_name=name)
        if std:
            out.append(std)
    return out


def _extract_from_legacy_dict(servers_obj: dict) -> list[dict]:
    out: list[dict] = []
    for name, s in servers_obj.items():
        if not isinstance(s, dict):
            continue
        std = _standardize_legacy_server(s, fallback_name=name)
        if std:
            out.append(std)
    return out


def _standardize_legacy_server(s: dict, fallback_name: str) -> dict | None:
    name = s.get("name") or fallback_name
    namespace = s.get("namespace") or name
    ns_index = int(s.get("ns_index", 2))

    ip, port = None, s.get("port", 4840)
    url = s.get("url") or s.get("endpoint")
    if url:
        ip, port = _parse_url_to_ip_port(_ensure_opc_tcp(str(url)))
    else:
        ip = s.get("ip")
        port = s.get("port", 4840)

    nodes_in = s.get("nodes", []) or []
    nodes_out = []
    for n in nodes_in:
        std_n = _standardize_legacy_node(n, ns_index)
        if std_n:
            nodes_out.append(std_n)

    return {
        "name": name,
        "namespace": namespace,
        "ip": ip,
        "port": port,
        "nodes": nodes_out,
    }


def _standardize_legacy_node(n: dict, ns_index: int) -> dict | None:
    name_n = n.get("name")
    if not name_n:
        return None
    opc_id = n.get("opc_id")
    if not opc_id and n.get("path"):
        opc_id = f"ns={ns_index};s=.{n['path']}"
    if not opc_id:
        return None
    dtype = n.get("dtype", n.get("datatype", "float"))
    return {"name": name_n, "opc_id": opc_id, "dtype": dtype}


def _extract_from_system(systems_obj: dict | list) -> list[dict]:
    out: list[dict] = []
    systems = systems_obj if isinstance(systems_obj, list) else [systems_obj]
    for sys_entry in systems:
        if not isinstance(sys_entry, dict):
            continue
        sys_name = sys_entry.get("name") or "default"
        servers_obj = sys_entry.get("servers", {}) or {}
        nodes_all = sys_entry.get("nodes", []) or []

        mat_servers: dict[str, dict] = {}
        if isinstance(servers_obj, dict):
            for srv_key, srv_val in servers_obj.items():
                if not isinstance(srv_val, dict):
                    continue
                ip, port = None, srv_val.get("port", 4840)
                url = srv_val.get("url") or srv_val.get("endpoint")
                if url:
                    ip, port = _parse_url_to_ip_port(_ensure_opc_tcp(str(url)))
                else:
                    ip = srv_val.get("ip")
                    port = srv_val.get("port", 4840)
                mat_servers[srv_key] = {
                    "name": srv_key,
                    "namespace": sys_name,
                    "ip": ip,
                    "port": port,
                    "nodes": [],
                }

        for n in nodes_all:
            if not isinstance(n, dict):
                continue
            srv_ref = n.get("server")
            if srv_ref in mat_servers:
                name_n = n.get("name")
                opc_id = n.get("opc_id")
                if not (name_n and opc_id):
                    continue
                dtype = n.get("dtype", n.get("datatype", "float"))
                mat_servers[srv_ref]["nodes"].append({"name": name_n, "opc_id": opc_id, "dtype": dtype})

        out.extend(mat_servers.values())
    return out


def _parse_url_to_ip_port(url: str) -> tuple[str | None, int | None]:
    """Parse `opc.tcp://host:port` or `host:port` into (host, port).
    Returns (None, None) on failure.
    """
    s = (url or "").strip()
    if not s:
        return None, None
    if "://" in s:
        try:
            # split protocol
            s = s.split("://", 1)[1]
        except Exception:
            return None, None
    if ":" not in s:
        return s, 4840
    host, _, port_str = s.rpartition(":")
    try:
        return host, int(port_str)
    except Exception:
        return host or None, None


def _ensure_opc_tcp(url: str) -> str:
    """Ensure the URL has the `opc.tcp://` prefix; if missing, add it."""
    s = (url or "").strip()
    if not s:
        return s
    return s if s.startswith("opc.tcp://") else f"opc.tcp://{s}"
