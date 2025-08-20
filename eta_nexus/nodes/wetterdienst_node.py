from __future__ import annotations

import enum
from datetime import timedelta
from logging import getLogger
from typing import TYPE_CHECKING

from attrs import (
    converters,
    field,
    validators as vld,
)
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.provider.dwd.mosmix.api import DwdMosmixParameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationParameter,
    DwdObservationResolution,
)

from eta_nexus.nodes.node import Node

if TYPE_CHECKING:
    from typing import Any


log = getLogger(__name__)


class WetterdienstNode(Node):
    """Abstract Base Node for the Wetterdienst API.
    This class is not meant to be used directly, but to be subclassed by
    WetterdienstObservationNode and WetterdienstPredictionNode.
    """

    #: Parameter to read from wetterdienst (e.g HUMIDITY or TEMPERATURE_AIR_200)
    parameter: str = field(kw_only=True, converter=str.upper)

    #: The id of the weather station
    station_id: str | None = field(default=None, kw_only=True)
    #: latitude and longitude (not necessarily a weather station)
    latlon: str | None = field(default=None, kw_only=True)
    #: Number of stations to be used for the query
    number_of_stations: int | None = field(default=None, kw_only=True)

    def __attrs_post_init__(self) -> None:
        """Ensure that all required parameters are present."""
        # Set same default URL for all Wetterdienst nodes
        object.__setattr__(self, "url", "https://opendata.dwd.de")
        super().__attrs_post_init__()
        if self.station_id is None and (self.latlon is None or self.number_of_stations is None):
            raise ValueError(
                "The required parameter 'station_id' or 'latlon' and 'number_of_stations' for the node configuration "
                "was not found. The node could not load."
            )
        parameters = [item.name for item in Parameter]
        if self.parameter not in parameters:
            raise ValueError(
                f"Parameter {self.parameter} is not valid. Valid parameters can be found here:"
                f"https://wetterdienst.readthedocs.io/en/latest/data/parameters/"
            )

    @classmethod
    def _get_params(cls, dikt: dict[str, Any]) -> dict[str, Any]:
        """Get the common parameters for a Wetterdienst node.

        :param dikt: dictionary with node information.
        :return: dict with: parameter, station_id, latlon, number_of_stations
        """
        return {
            "parameter": dikt.get("parameter"),
            "station_id": dikt.get("station_id"),
            "latlon": dikt.get("latlon"),
            "number_of_stations": dikt.get("number_of_stations"),
        }


class WetterdienstObservationNode(WetterdienstNode, protocol="wetterdienst_observation"):
    """Node for the Wetterdienst API to get weather observations.
    For more information see: https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/observation/.
    """

    #: Redeclare interval attribute, but don't allow it to be optional
    interval: str = field(converter=converters.optional(float), kw_only=True, repr=False, eq=False, order=False)

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        resolution = self.convert_interval_to_resolution(self.interval)
        # Sort out the parameters by resolution
        available_params = DwdObservationParameter[resolution]
        available_params = [param.name for param in available_params if type(param) is not enum.EnumMeta]

        # If the parameter is not in the available parameters for the resolution, generate a list
        # of available resolutions for the parameter and raise an error
        if self.parameter not in available_params:
            available_resolutions = []
            for resolution in DwdObservationResolution:
                params = DwdObservationParameter[resolution.name]  # type: ignore[attr-defined]
                if self.parameter in [param.name for param in params if type(param) is not enum.EnumMeta]:
                    available_resolutions.append(resolution.name)  # type: ignore[attr-defined]
            if len(available_resolutions) == 0:
                raise ValueError(f"Parameter {self.parameter} is not a valid observation parameter.")
            raise ValueError(
                f"Parameter {self.parameter} is not valid for the given resolution. "
                f"Valid resolutions for parameter {self.parameter} are: "
                f"{available_resolutions}"
            )

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> WetterdienstObservationNode:
        """Create a WetterdienstObservationNode from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: WetterdienstObservationNode object.
        """
        name, _, _, _, interval = cls._read_dict_info(dikt)
        params = cls._get_params(dikt)
        try:
            return cls(name, "", "wetterdienst_observation", interval=interval, **params)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e

    @staticmethod
    def convert_interval_to_resolution(interval: int | str | timedelta) -> str:
        resolutions = {
            60: "MINUTE_1",
            300: "MINUTE_5",
            600: "MINUTE_10",
            3600: "HOURLY",
            28800: "SUBDAILY",  # not 8h intervals, measured at 7am, 2pm, 9pm
            86400: "DAILY",
            2592000: "MONTHLY",
            31536000: "ANNUAL",
        }
        interval = int(interval.total_seconds()) if isinstance(interval, timedelta) else int(interval)
        if interval not in resolutions:
            raise ValueError(f"Interval {interval} not supported. Must be one of {list(resolutions.keys())}")
        return resolutions[interval]


class WetterdienstPredictionNode(WetterdienstNode, protocol="wetterdienst_prediction"):
    """Node for the Wetterdienst API to get weather predictions.
    For more information see: https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/mosmix/.
    """

    #: Type of the MOSMIX prediction. Either 'SMALL' or 'LARGE'
    mosmix_type: str = field(kw_only=True, converter=str.upper, validator=vld.in_(("SMALL", "LARGE")))

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        # Sort out the parameters by resolution
        params = DwdMosmixParameter[self.mosmix_type]
        # Create list of available parameters, enums are excluded because they are datasets
        available_params = [param.name for param in params if type(param) is not enum.EnumMeta]

        if self.parameter not in available_params:
            raise ValueError(
                f"Parameter {self.parameter} is not valid for the given resolution."
                f"Valid parameters for resolution {self.mosmix_type} can be found here:"
                f"https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/mosmix/hourly/"
            )

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> WetterdienstPredictionNode:
        """Create a WetterdienstPredictionNode from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: WetterdienstPredictionNode object.
        """
        name, _, _, _, _ = cls._read_dict_info(dikt)
        params = cls._get_params(dikt)
        mosmix_type = dikt.get("mosmix_type")
        try:
            return cls(name, "", "wetterdienst_prediction", mosmix_type=mosmix_type, **params)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e
