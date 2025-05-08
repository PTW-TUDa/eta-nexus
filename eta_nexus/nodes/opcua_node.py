from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from attrs import (
    converters,
    field,
    validators as vld,
)

from eta_nexus.nodes.node import Node
from eta_nexus.nodes.node_utils import _lower_str, _strip_str
from eta_nexus.util import dict_get_any

if TYPE_CHECKING:
    from typing import Any

    from typing_extensions import Self


log = getLogger(__name__)


class OpcuaNode(Node, protocol="opcua"):
    """Node for the OPC UA protocol."""

    #: Node ID of the OPC UA Node.
    opc_id: str | None = field(default=None, kw_only=True, converter=converters.optional(_strip_str))
    #: Path to the OPC UA node.
    opc_path_str: str | None = field(
        default=None, kw_only=True, converter=converters.optional(_strip_str), repr=False, eq=False, order=False
    )
    #: Namespace of the OPC UA Node.
    opc_ns: int | None = field(default=None, kw_only=True, converter=converters.optional(_lower_str))

    # Additional fields which will be determined automatically
    #: Type of the OPC UA Node ID Specification.
    opc_id_type: str = field(
        init=False, converter=str, validator=vld.in_(("i", "s")), repr=False, eq=False, order=False
    )
    #: Name of the OPC UA Node.
    opc_name: str = field(init=False, repr=False, eq=False, order=False, converter=str)
    #: Path to the OPC UA node in list representation. Nodes in this list can be used to access any
    #: parent objects.

    def __attrs_post_init__(self) -> None:
        """Add default port to the URL and convert mb_byteorder values."""
        super().__attrs_post_init__()

        # Set port to default 4840 if it was not explicitly specified
        if not isinstance(self.url_parsed.port, int):
            url = self.url_parsed._replace(netloc=f"{self.url_parsed.hostname}:4840")
            object.__setattr__(self, "url", url.geturl())
            object.__setattr__(self, "url_parsed", url)

        # Determine, which values to use for initialization and set values
        if self.opc_id is not None:
            try:
                parts = self.opc_id.split(";")
            except ValueError as e:
                raise ValueError(
                    f"When specifying opc_id, make sure it follows the format ns=2;s=.path (got {self.opc_id})."
                ) from e
            for part in parts:
                try:
                    key, val = part.split("=")
                except ValueError as e:
                    raise ValueError(
                        f"When specifying opc_id, make sure it follows the format ns=2;s=.path (got {self.opc_id})."
                    ) from e

                if key.strip().lower() == "ns":
                    object.__setattr__(self, "opc_ns", int(val))
                else:
                    object.__setattr__(self, "opc_id_type", key.strip().lower())
                    object.__setattr__(self, "opc_path_str", val.strip())

            object.__setattr__(self, "opc_id", f"ns={self.opc_ns};{self.opc_id_type}={self.opc_path_str}")

        elif self.opc_path_str is not None and self.opc_ns is not None:
            object.__setattr__(self, "opc_id_type", "s")
            object.__setattr__(self, "opc_id", f"ns={self.opc_ns};s={self.opc_path_str}")
        else:
            raise ValueError("Specify opc_id or opc_path_str and ns for OPC UA nodes.")

        # Determine the name of the opc node
        object.__setattr__(self, "opc_name", self.opc_path_str.split(".")[-1])  # type: ignore[union-attr]

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> Self:
        """Create an opcua node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: OpcuaNode object.
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)

        opc_id = dict_get_any(dikt, "opc_id", "identifier", "identifier", fail=False)
        dtype = dict_get_any(dikt, "dtype", "datentyp", fail=False)

        if opc_id is None:
            opc_ns = dict_get_any(dikt, "opc_ns", "namespace", "ns", fail=False)
            opc_path_str = dict_get_any(dikt, "opc_path", "path", fail=False)
            try:
                return cls(
                    name,
                    url,
                    "opcua",
                    usr=usr,
                    pwd=pwd,
                    opc_ns=opc_ns,
                    opc_path_str=opc_path_str,
                    dtype=dtype,
                    interval=interval,
                )
            except (TypeError, AttributeError) as e:
                raise TypeError(
                    f"Could not convert all types for node {name}. Either the 'node_id' or the 'opc_ns' "
                    f"and 'opc_path' must be specified."
                ) from e
        else:
            try:
                return cls(name, url, "opcua", usr=usr, pwd=pwd, opc_id=opc_id, dtype=dtype, interval=interval)
            except (TypeError, AttributeError) as e:
                raise TypeError(
                    f"Could not convert all types for node {name}. Either the 'node_id' or the 'opc_ns' "
                    f"and 'opc_path' must be specified."
                ) from e

    def evolve(self, **kwargs: Any) -> Self:
        """Returns a new node instance
        by copying the current node and changing only specified keyword arguments.

        This allows for seamless node instantiation with only a few changes.

        Adjusted attributes handling according to OpcuaNode instantiation logic as in '__attrs_post_init__'.

        :param kwargs: Keyword arguments to change.
        :return: New instance of the node.
        """
        # Ensure that opc_id is not set if opc_ns and opc_path_str are set, to avoid postprocessing conflicts
        if kwargs.get("opc_id") is not None or self.opc_id is not None:
            kwargs["opc_ns"] = None
            kwargs["opc_path_str"] = None
        else:
            kwargs["opc_ns"] = str(kwargs.get("opc_ns", self.opc_ns))

        return super().evolve(**kwargs)
