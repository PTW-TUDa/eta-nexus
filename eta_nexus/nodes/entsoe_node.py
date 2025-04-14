from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from attrs import (
    field,
)

from eta_nexus.nodes.node import Node

if TYPE_CHECKING:
    from typing import Any


log = getLogger(__name__)


class EntsoeNode(Node, protocol="entsoe"):
    """Node for the EntsoE API (see `ENTSO-E Transparency Platform API
    <https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html>`_).

    .. list-table:: **Available endpoint**
        :widths: 25 35
        :header-rows: 1

        * - Endpoint
          - Description
        * - ActualGenerationPerType
          - Actual Generation Per Energy Type
        * - Price
          - Price day ahead

    Currently, there is only two endpoints available, due to the parameter managing required by the API documentation.
    The other possible endpoints are listed in

    `eta_nexus.connections.entso_e._ConnectionConfiguration._doc_types`

    .. list-table:: **Main bidding zone**
        :widths: 15 25
        :header-rows: 1

        * - Bidding Zone
          - Description
        * - DEU-LUX
          - Deutschland-Luxemburg

    The other possible bidding zones are listed in

    `eta_nexus.connections.entso_e._ConnectionConfiguration._bidding_zones`

    """

    #: REST endpoint.
    endpoint: str = field(kw_only=True, converter=str)
    #: Bidding zone.
    bidding_zone: str = field(kw_only=True, converter=str)

    def __attrs_post_init__(self) -> None:
        """Ensure username and password are processed correctly."""
        super().__attrs_post_init__()

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> EntsoeNode:
        """Create an EntsoE node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: EntsoeNode object.
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)

        try:
            endpoint = cls._try_dict_get_any(dikt, "endpoint")
            bidding_zone = cls._try_dict_get_any(dikt, "bidding zone", "bidding_zone", "zone")
        except KeyError as e:
            raise KeyError(
                f"The required parameter for the node configuration was not found (see log). The node {name} could "
                f"not load."
            ) from e

        try:
            return cls(
                name, url, "entsoe", usr=usr, pwd=pwd, endpoint=endpoint, bidding_zone=bidding_zone, interval=interval
            )
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e
