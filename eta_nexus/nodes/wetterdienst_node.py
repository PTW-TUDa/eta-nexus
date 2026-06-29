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
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.mosmix.api import (
    DwdForecastDate,
    DwdMosmixRequest,
    DwdMosmixStationGroup,
)
from wetterdienst.provider.dwd.observation import DwdObservationMetadata

from eta_nexus.nodes.node import Node

if TYPE_CHECKING:
    from typing import Any

    from wetterdienst.model.request import ResolutionModel

log = getLogger(__name__)


class WetterdienstNode(Node):
    """Abstract Base Node for the Wetterdienst API.
    This class is not meant to be used directly, but to be subclassed by
    WetterdienstObservationNode and WetterdienstPredictionNode.
    """

    #: Parameter to read from wetterdienst (e.g HUMIDITY or TEMPERATURE_AIR_200)
    parameter: str = field(kw_only=True, converter=str.upper)

    #: The id of the weather station. Selects which station to query.
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
                f"https://wetterdienst.readthedocs.io/en/latest/data/parameters.html"
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
    For more information see:
    https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/observation/
    """

    #: Redeclare interval attribute, but don't allow it to be optional
    interval: str = field(
        converter=converters.optional(float),
        kw_only=True,
        repr=False,
        eq=False,
        order=False,
    )

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()
        resolution: str = self.convert_interval_to_resolution(self.interval)
        available_params = [param.name.lower() for dataset in DwdObservationMetadata[resolution] for param in dataset]

        # If the parameter is not available for the given resolution,
        # find all resolutions where it exists and raise a helpful error
        if self.parameter.lower() not in available_params:
            available_resolutions = []

            for res_model in DwdObservationMetadata:
                params = {param.name.lower() for dataset in res_model for param in dataset}

                if self.parameter.lower() in params:
                    available_resolutions.append(Resolution(res_model.name).name)

            if len(available_resolutions) == 0:
                raise ValueError(f"Parameter {self.parameter} is not a valid observation parameter.")

            raise ValueError(
                f"Parameter {self.parameter} is not valid for the given resolution. "
                f"Valid resolutions for parameter {self.parameter} are: "
                f"{available_resolutions}"
            )

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

    def find_dataset(self, resolution: str) -> str:
        """Find the dataset name for this node's parameter at the given resolution.

        Iterates over all datasets available at the given resolution and returns
        the name of the first dataset that contains a matching parameter.

        This method is especially useful when constructing :class:`DwdObservationRequest` objects,
        which require parameters in the format ``{resolution}/{dataset}`` or
        ``{resolution}/{dataset}/{parameter}``, where ``parameter`` corresponds to
        :attr:`~WetterdienstObservationNode.parameter`.

        :param resolution: The resolution string (e.g. ``"HOURLY"``, ``"DAILY"``) to search within.
        :return: The dataset name (e.g. ``"temperature_air"``) containing the parameter.
        :raises ValueError: If no dataset at the given resolution contains the parameter.
        """
        for dataset in DwdObservationMetadata[resolution]:
            for parameter in dataset:
                if parameter.name.lower() == self.parameter.lower():
                    return dataset.name

        raise ValueError(f"Resolution {resolution} does not provide a valid dataset for parameter {self.parameter} ")


class WetterdienstPredictionNode(WetterdienstNode, protocol="wetterdienst_prediction"):
    """Node for the Wetterdienst API to get MOSMIX predictions (new API).
    Mosmix is a forecast service of the DWD. It is available in two Versions: Mosmix Large and
    Mosmix Small. Mosmix-S comes with a set of 40 parameters and is published every hour while
    MOSMIX-L has a set of about 115 parameters and is released every 6 hours (3am, 9am, 3pm, 9pm).
    Both versions have a forecast limit of 240h
    For more information see: https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/mosmix/
    """

    #: Type of MOSMIX prediction ('SMALL' or 'LARGE')
    mosmix_type: str = field(
        kw_only=True,
        converter=str.upper,
        validator=vld.in_(("SMALL", "LARGE")),
    )

    #: Forecast issue time (default = latest run)
    #: DwdForecastdate is an enumeration, which points to different Mosmix dates.
    issue: str | DwdForecastDate | None = field(
        default=DwdForecastDate.LATEST,
        kw_only=True,
    )

    #: Station group (default = single stations)
    #: Decides whether to query a single station or all.
    station_group: str | DwdMosmixStationGroup = field(
        default=DwdMosmixStationGroup.SINGLE_STATIONS,
        kw_only=True,
    )

    def __attrs_post_init__(self) -> None:
        super().__attrs_post_init__()

        resolution: ResolutionModel = DwdMosmixRequest.metadata[Resolution.HOURLY.name.lower()]
        dataset = resolution[self.mosmix_type]
        available_params = [param.name for param in dataset if type(param) is not enum.EnumMeta]

        if self.parameter.lower() not in available_params:
            raise ValueError(
                f"Parameter {self.parameter} is not valid for the given resolution."
                f"Valid parameters for resolution {self.mosmix_type} can be found here:"
                f"https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/mosmix/hourly/"
            )

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> WetterdienstPredictionNode:
        name, _, _, _, _ = cls._read_dict_info(dikt)
        params = cls._get_params(dikt)

        return cls(
            name,
            "",
            "wetterdienst_prediction",
            mosmix_type=dikt.get("mosmix_type"),
            issue=dikt.get("issue", DwdForecastDate.LATEST),
            station_group=dikt.get(
                "station_group",
                DwdMosmixStationGroup.SINGLE_STATIONS,
            ),
            **params,
        )
