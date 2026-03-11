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


class InfluxNode(Node, protocol="influx"):
    """Node for the InfluxDB module."""

    database: str = field(kw_only=True, converter=str)
    table: str = field(kw_only=True, converter=str)

    @property
    def field(self) -> str:
        """Alias for the underlying field/column name."""
        return self.name

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> Self:
        """Create a Influx node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: InfluxNode object.
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)
        try:
            database = cls._try_dict_get_any(dikt, "database")
            table = cls._try_dict_get_any(dikt, "table", "measurement")
        except KeyError as e:
            raise KeyError(
                f"The required parameter for the node configuration was not found (see log). The node {name} could "
                f"not load."
            ) from e

        if "field" in dikt and str(dikt["field"]).strip().lower() not in {"", "none", "nan"}:
            name = str(dikt["field"])

        try:
            return cls(name, url, "influx", usr=usr, pwd=pwd, database=database, table=table, interval=interval)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e

    def _extra_equality_key(self) -> Any | None:
        # Nodes from different databases must not be grouped into one connection
        return self.database
