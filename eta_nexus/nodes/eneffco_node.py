from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from attrs import (
    field,
)

from eta_nexus.nodes.node import Node

if TYPE_CHECKING:
    from typing import Any

    from eta_nexus.util.type_annotations import Self


log = getLogger(__name__)


class EneffcoNode(Node, protocol="eneffco"):
    """Node for the Eneffco API."""

    #: Eneffco datapoint code / ID.
    eneffco_code: str = field(kw_only=True, converter=str)

    def __attrs_post_init__(self) -> None:
        """Ensure username and password are processed correctly."""
        super().__attrs_post_init__()

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> Self:
        """Create a Eneffco node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: EneffcoNode object.
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)
        try:
            code = cls._try_dict_get_any(dikt, "code", "eneffco_code")
        except KeyError as e:
            raise KeyError(
                f"The required parameter for the node configuration was not found (see log). The node {name} could "
                f"not load."
            ) from e

        try:
            return cls(name, url, "eneffco", usr=usr, pwd=pwd, eneffco_code=code, interval=interval)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e
