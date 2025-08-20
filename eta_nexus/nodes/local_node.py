from __future__ import annotations

from typing import TYPE_CHECKING

from eta_nexus.nodes.node import Node

if TYPE_CHECKING:
    from typing import Any


class LocalNode(Node, protocol="local"):
    """LocalNode (no specific protocol), useful for example to manually provide data to subscription handlers."""

    def __attrs_post_init__(self) -> None:
        """Ensure username and password are processed correctly."""
        super().__attrs_post_init__()

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> LocalNode:
        """Create a local node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: LocalNode object.
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)
        try:
            return cls(name, url, "local", usr=usr, pwd=pwd, interval=interval)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}") from e
