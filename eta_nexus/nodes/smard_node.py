from __future__ import annotations

from typing import TYPE_CHECKING, Final

from attrs import field, validators

from eta_nexus.nodes import Node

if TYPE_CHECKING:
    from typing import Any


# Filter constants as documented in API
POWER_GENERATION_FILTERS: Final[dict[str, int]] = {
    "lignite": 1223,
    "nuclear": 1224,
    "wind_offshore": 1225,
    "hydro": 1226,
    "other_conventional": 1227,
    "other_renewable": 1228,
    "biomass": 4066,
    "wind_onshore": 4067,
    "solar": 4068,
    "hard_coal": 4069,
    "pumped_storage_generation": 4070,
    "natural_gas": 4071,
}

POWER_CONSUMPTION_FILTERS: Final[dict[str, int]] = {
    "total_load": 410,
    "residual_load": 4359,
    "pumped_storage_consumption": 4387,
}

MARKET_PRICE_FILTERS: Final[dict[str, int]] = {
    "de_lu": 4169,
    "neighbors_de_lu": 5078,
    "belgium": 4996,
    "norway_2": 4997,
    "austria": 4170,
    # Add more as needed
}

FORECAST_FILTERS: Final[dict[str, int]] = {
    "offshore_forecast": 3791,
    "onshore_forecast": 123,
    "solar_forecast": 125,
    "other_forecast": 715,
    "wind_solar_forecast": 5097,
    "total_forecast": 122,
}

# All filters combined
ALL_FILTERS: Final[dict[str, int]] = {
    **POWER_GENERATION_FILTERS,
    **POWER_CONSUMPTION_FILTERS,
    **MARKET_PRICE_FILTERS,
    **FORECAST_FILTERS,
}

VALID_REGIONS: Final[tuple[str, ...]] = (
    "DE",
    "AT",
    "LU",
    "DE-LU",
    "DE-AT-LU",
    "50Hertz",
    "Amprion",
    "TenneT",
    "TransnetBW",
    "APG",
    "Creos",
)

VALID_RESOLUTIONS: Final[tuple[str, ...]] = ("quarterhour", "hour", "day", "week", "month", "year")


class SmardNode(Node, protocol="smard"):
    """Node for SMARD (Bundesnetzagentur Strommarktdaten) API.

    Provides access to German electricity market data including:
    - Power generation by source
    - Power consumption
    - Market prices
    - Generation forecasts

    :param filter: Data filter ID or name (e.g., 'solar', 1223, 'total_load')
    :param region: Region code (e.g., 'DE', '50Hertz', 'AT')
    :param resolution: Time resolution ('hour', 'quarterhour', 'day', etc.)
    """

    # Required: Identifies what data to retrieve
    filter: int = field(kw_only=True)
    region: str = field(kw_only=True, converter=str, validator=validators.in_(VALID_REGIONS))
    resolution: str = field(
        default="quarterhour", kw_only=True, converter=str, validator=validators.in_(VALID_RESOLUTIONS)
    )

    @filter.validator  # type: ignore[attr-defined]
    def _validate_filter(self, attribute, value: int) -> None:  # type: ignore[no-untyped-def]
        """Validate filter is a known filter ID."""
        if value not in ALL_FILTERS.values():
            valid_filters = ", ".join(f"{k}={v}" for k, v in list(ALL_FILTERS.items())[:5])
            raise ValueError(
                f"Invalid filter {value}. Must be one of the documented filter IDs. Examples: {valid_filters}..."
            )

    def __attrs_post_init__(self) -> None:
        """Post-initialization validation."""
        super().__attrs_post_init__()

        # Validate region compatibility with filter
        # (Some filters may not be available for all regions)
        if self.region in ("AT", "LU") and self.filter in POWER_CONSUMPTION_FILTERS.values():
            raise ValueError(
                f"Power consumption filters not available for region {self.region}. Use 'DE' or German control zones."
            )

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> SmardNode:
        """Create node from dictionary (for config files).

        :param dikt: Dictionary with node configuration
        :return: SmardNode instance
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)

        # Extract SMARD-specific parameters
        try:
            # Accept filter as int or string name
            filter_raw = cls._try_dict_get_any(dikt, "filter", "filter_id")
            if isinstance(filter_raw, str):
                # Try to parse as int first (for numeric strings like "4068")
                try:
                    filter_id = int(filter_raw)
                except ValueError as err:
                    # Not a number, try as filter name
                    filter_id_or_none = ALL_FILTERS.get(filter_raw.lower())
                    if filter_id_or_none is None:
                        raise ValueError(f"Unknown filter name: {filter_raw}") from err
                    filter_id = filter_id_or_none
            else:
                filter_id = int(filter_raw)

            region = cls._try_dict_get_any(dikt, "region", "area")
        except KeyError as e:
            raise KeyError(f"Required parameter missing for node {name}: {e}") from e

        # Optional parameters
        resolution = dikt.get("resolution", "hour")

        try:
            return cls(
                name=name,
                url=url or "https://smard.api.proxy.bund.dev/app",
                protocol="smard",
                usr=usr,
                pwd=pwd,
                interval=interval,
                filter=filter_id,
                region=region,
                resolution=resolution,
            )
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not create node {name}: {e}") from e

    @staticmethod
    def get_filter_name(filter_id: int) -> str | None:
        """Get human-readable name for a filter ID.

        :param filter_id: Filter ID
        :return: Filter name or None if unknown
        """
        for name, fid in ALL_FILTERS.items():
            if fid == filter_id:
                return name
        return None
