from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from eta_nexus.util.type_annotations import N, Nodes

from logging import getLogger
from typing import TYPE_CHECKING


def name_map_from_node_sequence(nodes: Nodes[N]) -> dict[str, N]:
    """Convert a Sequence/List of Nodes into a dictionary of nodes, identified by their name.

    .. warning ::

        Make sure that each node in nodes has a unique Name, otherwise this function will fail.

    :param nodes: Sequence of Node objects.
    :return: Dictionary of Node objects (format: {node.name: Node}).
    """
    if len({node.name for node in nodes}) != len([node.name for node in nodes]):
        raise ValueError("Not all node names are unique. Cannot safely convert to named dictionary.")

    return {node.name: node for node in nodes}


log = getLogger(__name__)


def _strip_str(value: str) -> str:
    """Convenience function to convert a string to its stripped version.

    :param value: String to convert.
    :return: Stripped string.
    """
    return value.strip()


def _lower_str(value: str) -> str:
    """Convenience function to convert a string to its stripped and lowercase version.

    :param value: String to convert.
    :return: Stripped and lowercase string.
    """
    return value.strip().lower()


def _dtype_converter(value: str) -> Callable | None:
    """Specify data type conversion functions (i.e. to convert modbus types to python).

    :param value: Data type string to convert to callable datatype converter.
    :return: Python datatype (callable).
    """
    _dtypes = {
        "boolean": bool,
        "bool": bool,
        "int": int,
        "uint32": int,
        "integer": int,
        "sbyte": int,
        "float": float,
        "double": float,
        "short": float,
        "string": str,
        "str": str,
        "bytes": bytes,
        "none": None,
        "list": list,
        "tuple": tuple,
        "dict": dict,
    }

    try:
        if value.startswith(("list", "tuple", "dict")):
            value = value.split("[")[0]
        dtype = _dtypes[_lower_str(value)]
    except KeyError:
        log.warning(
            f"The specified data type ({value}) is currently not available in the datatype map and will not be applied."
        )
        dtype = None

    return dtype
