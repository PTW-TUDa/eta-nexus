from eta_nexus.nodes import OpcuaNode
from eta_nexus.nodes.node_utils import _dtype_converter
from eta_nexus.servers import OpcuaServer
from eta_nexus.util.io_utils import load_config
from eta_nexus.util.utils import dict_get_any, url_parse


def load_opcua_servers_from_config(config_path: str) -> list[OpcuaServer]:
    """
    Load and instantiate OPC UA servers from a configuration file.

    Supported config shape (normalized internally):
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
      - NodeId must be provided as `opc_id`.
      - DType aliases are mapped case-insensitively via `_dtype_converter`.

    Returns:
      List[OpcuaServer] with nodes created and attached.
    """

    config = load_config(config_path)

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
                dtype=_dtype_converter(str(node_conf.get("dtype", "float"))) or float,
            )
            nodes.append(node)

        if nodes:
            server.create_nodes(nodes)
            server.nodes = nodes

        servers.append(server)

    return servers


def _resolve_ip_port_from_url(url: str) -> tuple[str | None, int | None]:
    """Resolve host and port from a URL using shared util; default port 4840."""
    _url, _usr, _pwd = url_parse(url, scheme="opc.tcp")
    host = _url.hostname
    port = _url.port if _url.port is not None else 4840
    return host, port


def _extract_servers(config: dict) -> list[dict]:
    """Normalize supported config shapes into a list of standardized servers."""
    systems_obj = config.get("system")
    if systems_obj is None:
        return []
    return _extract_from_system(systems_obj)


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
                url = dict_get_any(srv_val, "url", "endpoint", fail=False, default=None)
                if url:
                    ip, port = _resolve_ip_port_from_url(str(url))
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
