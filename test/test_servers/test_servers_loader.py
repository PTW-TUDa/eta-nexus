import os
from contextlib import suppress
from pathlib import Path

import pytest

from eta_nexus.nodes import Node
from eta_nexus.servers import ModbusServer, OpcuaServer
from eta_nexus.servers.loaders.servers_loader import from_config
from eta_nexus.util.io_utils import load_config


def test_mixed_from_single_config_full():
    """Ensure a mixed config instantiates both servers and round-trips their nodes."""
    cfg_path = Path("./test/resources/connection_manager/config_mixed.yaml")
    assert cfg_path.exists()

    os.environ["ETA_NEXUS_TEST_OPCUA_PORT"] = "4854"
    os.environ["ETA_NEXUS_TEST_MODBUS_PORT"] = "5064"
    servers = from_config(cfg_path)
    try:
        # Both servers should be created and active
        assert "MIX.glt" in servers
        assert "MIX.mb1" in servers
        opc = servers["MIX.glt"]
        mb = servers["MIX.mb1"]
        assert isinstance(opc, OpcuaServer)
        assert opc.active is True
        assert isinstance(mb, ModbusServer)
        assert mb.active is True

        # Build nodes from the same config for both protocols
        cfg = load_config(cfg_path)
        nodes_cfg = cfg["system"][0]["nodes"]
        opc_netloc = opc._url.netloc
        mb_netloc = mb._url.netloc

        opc_nodes = Node.from_dict(
            [
                {
                    "name": f"MIX.{n['name']}",
                    "url": opc_netloc,
                    "protocol": "opcua",
                    **{k: v for k, v in n.items() if k not in {"server", "name"}},
                }
                for n in nodes_cfg
                if n.get("server") == "glt"
            ]
        )

        mb_nodes = Node.from_dict(
            [
                {
                    "name": f"MIX.{n['name']}",
                    "url": mb_netloc,
                    "protocol": "modbus",
                    **{k: v for k, v in n.items() if k not in {"server", "name"}},
                    "mb_byteorder": "big",
                }
                for n in nodes_cfg
                if n.get("server") == "mb1"
            ]
        )

        # OPC UA write/read/delete
        by_base = {n.name.split(".", 1)[1]: n for n in opc_nodes}
        # Ensure required basenames exist
        assert {"NodeFloat", "NodeInt", "NodeStr"}.issubset(set(by_base.keys()))
        float_node = by_base["NodeFloat"]
        int_node = by_base["NodeInt"]
        str_node = by_base["NodeStr"]
        opc.write({float_node: 2.5, int_node: 11, str_node: "abc"})
        opc_df = opc.read({float_node, int_node, str_node})
        assert opc_df[float_node.name].iloc[0] == pytest.approx(2.5)
        assert opc_df[int_node.name].iloc[0] == 11
        assert opc_df[str_node.name].iloc[0] == "abc"
        opc.delete_nodes({float_node, int_node, str_node})
        with pytest.raises(RuntimeError, match=".*BadNodeIdUnknown.*"):
            opc.read({float_node, int_node, str_node})

        # Modbus write/read
        mb_by_base = {n.name.split(".", 1)[1]: n for n in mb_nodes}
        values_by_base = {
            "int_val": 21,
            "float_val": 6.28,
            "str_val": "xyz",
            "coil1": [True],
            "coil4": [True, False, True, False],
        }
        assert set(values_by_base.keys()).issubset(mb_by_base.keys())
        mb.write({mb_by_base[k]: v for k, v in values_by_base.items()})
        for base, val in values_by_base.items():
            name = f"MIX.{base}"
            node = mb_by_base[base]
            res = mb.read(node)
            if isinstance(val, str):
                assert res[name].iloc[0] == val
            elif getattr(node, "mb_register", "") in ("coils", "discrete_input"):
                if len(val) > 1:
                    for idx, _ in enumerate(val):
                        assert res[f"{name}_{idx}"].iloc[0] == val[idx]
                else:
                    assert res[name].iloc[0] == val
            else:
                assert res[name].iloc[0] == pytest.approx(val)
    finally:
        for server in servers.values():
            with suppress(Exception):
                server.stop()
        os.environ.pop("ETA_NEXUS_TEST_OPCUA_PORT", None)
        os.environ.pop("ETA_NEXUS_TEST_MODBUS_PORT", None)
