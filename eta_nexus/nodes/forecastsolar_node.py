from __future__ import annotations

import ast
import re
from logging import getLogger
from sys import maxsize
from typing import TYPE_CHECKING

import attrs
from attrs import (
    converters,
    field,
    validators as vld,
)

from eta_nexus import dict_get_any
from eta_nexus.nodes.node import Node, _dtype_converter

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from typing_extensions import TypeAlias


log = getLogger(__name__)


# Forecast.Solar API Node
def _convert_list(_type: TypeAlias) -> Callable:
    """Convert an optional list of values to a single value or a list of values.

    :param _type: type to convert the values to.
    :return: converter function.
    """

    def converter(value: Any) -> Any | list[Any]:
        try:
            if isinstance(value, str):
                value = ast.literal_eval(value)
            if isinstance(value, list):
                return [_type(val) for val in value]
            return _type(value)
        except ValueError as e:
            raise ValueError(f"Could not convert value to {_type} ({value}).") from e

    return converter


def _check_api_key(instance, attribute, value):  # type: ignore[no-untyped-def]
    """attrs validator to check if the API key is set."""
    if re.match(r"[A-Za-z0-9]{16}", value) is None:
        raise ValueError("'api_key' must be a 16 character long alphanumeric string.")


def _check_plane(_type: TypeAlias, lower: int, upper: int) -> Callable:
    """Return an attrs validator for plane related attributes (declination, azimuth, kwp).
    Checks if the value is between the lower and upper bounds.

    :param _type: type of the parameter
    :param lower: lower bound
    :param upper: upper bound
    """

    def validator(instance, attribute, value):  # type: ignore[no-untyped-def]
        value = value if isinstance(value, list) else [value]
        for val in value:
            if not isinstance(val, _type):
                raise ValueError(f"'{attribute.name}' must be of type {_type} ({(val, type(val))}).")
            if val < lower:
                raise ValueError(f"'{attribute.name}' must be >= {lower}: {val}.")
            if val > upper:
                raise ValueError(f"'{attribute.name}' must be <= {upper}: {val}.")

    return validator


def _check_horizon(instance, attribute, value):  # type: ignore[no-untyped-def]
    """attrs validator to check if horizon attribute corresponds to the API requirements."""
    if not isinstance(value, list) and value != 0:
        raise ValueError("'horizon' must be a list, 0 (To suppress horizon usage *at all*) or None")
    if len(value) < 4:
        raise ValueError("'horizon' must contain at least 4 values.")
    if 360 % len(value) != 0:
        raise ValueError("'horizon' must be set such that 360 / <your count of horizon values> is an integer.")
    if not all(isinstance(i, (int, float)) and 0 <= i <= 90 for i in value):
        raise ValueError("'horizon' values must be between 0 and 90.")


def _forecast_solar_transform(cls: attrs.AttrsInstance, fields: list[attrs.Attribute]) -> list[attrs.Attribute]:
    """Transform the fields of the Forecastsolar node class.

    :param fields: list of fields to transform.
    :return: transformed fields.
    """
    for _field in fields:
        # Skip fields from superclass and reset original kw_only value
        if _field.name in ["usr", "pwd", "interval", "dtype", "name", "url", "url_parsed", "protocol"]:
            if _field.name in ["name", "url", "url_parsed", "protocol"]:
                object.__setattr__(_field, "kw_only", False)
            continue

        # Unpack field's type hints and convert them appropriately
        types = tuple(map(_dtype_converter, _field.type.split(" | ")))  # type: ignore[union-attr]

        # Create and append type validator to existing validators
        _vlds = [vld.instance_of(tuple(filter(lambda x: x is not None, types)))]  # type: ignore
        if _field.validator:
            # If the field has a vld.and() validator, unpack it and append to the list
            _vlds.extend(
                [*_field.validator._validators]  # type: ignore
                if isinstance(_field.validator, type(vld.and_()))
                else [_field.validator]
            )
        all_validators = vld.and_(*_vlds)

        # If None in type hints, make the field optional
        if None in types:
            all_validators = vld.optional(all_validators)
            if _field.converter:
                object.__setattr__(_field, "converter", converters.optional(_field.converter))
            object.__setattr__(_field, "default", _field.default or None)
        object.__setattr__(_field, "validator", all_validators)

    return fields


attrs_args = {"kw_only": True, "field_transformer": _forecast_solar_transform}


class ForecastsolarNode(Node, protocol="forecast_solar", attrs_args=attrs_args):
    """Node for using the Forecast.Solar API.

    Mandatory parameters are:
    * The location of the forecast solar plane(s): **latitude**, **longitude**,
    * Plane parameters: **declination**, **azimuth** and **kwp**.

    Additionally **api_key** must be set for endpoints other than 'estimate',
    multiple planes or if requests capacity is exceeded.

    For multiple planes, the parameters shall be passed as lists of the same length
    (e.g. [0, 30], [180, 180], [5, 5]).

    By default, data is queried as 'watts'. Other options are 'watthours', 'watthours/period' and 'watthours/day'.
    Either set the **data** parameter or call the appropriate method afterwards of
    :class:'eta_nexus.connections.forecast_solar.ForecastsolarConnection'.
    """

    # URL PARAMETERS
    # ----------------

    #: API key for the Forecast.Solar API; string
    api_key: str | None = field(repr=False, converter=str, validator=_check_api_key, metadata={"QUERY_PARAM": False})
    #: Endpoint in (estimate, history, clearsky), defaults to estimate; string
    endpoint: str = field(
        default="estimate",
        converter=str,
        validator=vld.in_(("estimate", "history", "clearsky")),
        metadata={"QUERY_PARAM": False},
    )
    #: What data to query, i.e. only 'watts', 'watthours', 'watthours/period' or 'watthours/day'; string
    data: str = field(
        default="watts",
        converter=str,
        validator=vld.in_(("watts", "watthours", "watthours/period", "watthours/day")),
        metadata={"QUERY_PARAM": False},
    )
    #: Latitude of plane location, -90 (south) … 90 (north); handled with a precision of 0.0001 or abt. 10 m
    latitude: int = field(converter=int, validator=[vld.ge(-90), vld.le(90)], metadata={"QUERY_PARAM": False})
    #: Longitude of plane location, -180 (west) … 180 (east); handled with a precision of 0.0001 or abt. 10 m
    longitude: int = field(converter=int, validator=[vld.ge(-180), vld.le(180)], metadata={"QUERY_PARAM": False})
    #: Plane declination, 0 (horizontal) … 90 (vertical) - always in relation to earth's surface; integer
    declination: int | list[int] = field(
        converter=_convert_list(int),
        validator=_check_plane(int, 0, 90),
        metadata={"QUERY_PARAM": False},
        eq=False,  # Exclude from __hash__
    )
    #: Plane azimuth, -180 … 180 (-180 = north, -90 = east, 0 = south, 90 = west, 180 = north); integer
    azimuth: int | list[int] = field(
        converter=_convert_list(int),
        validator=_check_plane(int, -180, 180),
        metadata={"QUERY_PARAM": False},
        eq=False,  # Exclude from __hash__
    )
    #: Installed modules power of plane in kilo watt; float
    kwp: float | list[float] = field(
        converter=_convert_list(float),
        validator=_check_plane(float, 0, maxsize),
        metadata={"QUERY_PARAM": False},
        eq=False,  # Exclude from __hash__
    )

    # QUERY PARAMETERS
    # ----------------
    #: Format of timestamps in the response, see API doc for values; string
    #: Forecast for full day or only sunrise to sunset, 0|1 (API defaults to 0); int
    no_sun: int | None = field(default=None, validator=vld.in_((0, 1)), metadata={"QUERY_PARAM": True})
    #: Damping factor for the morning (API defaults to 0.0)
    damping_morning: float | None = field(
        default=None, converter=float, validator=[vld.ge(0.0), vld.le(1.0)], metadata={"QUERY_PARAM": True}
    )
    #: Damping factor for the evening (API defaults to 0.0)
    damping_evening: float | None = field(
        default=None, converter=float, validator=[vld.ge(0.0), vld.le(1.0)], metadata={"QUERY_PARAM": True}
    )
    #: Horizon information; string, (comma-separated list of numerics) See API doc
    horizon: int | list[int] | None = field(
        default=None,
        converter=_convert_list(int),
        validator=_check_horizon,
        eq=False,
        metadata={"QUERY_PARAM": True},
    )  # Exclude from __hash__
    #: Maximum of inverter in kilowatts or kVA; float > 0
    inverter: float | None = field(default=None, converter=float, validator=vld.gt(0.0), metadata={"QUERY_PARAM": True})
    #: Actual production until now; float >= 0
    actual: float | None = field(default=None, converter=float, validator=vld.ge(0.0), metadata={"QUERY_PARAM": True})

    #: Url parameters for the API; dict
    _url_params: dict[str, Any] = field(init=False, repr=False, eq=False, order=False)
    #: Query parameters for the API; dict
    _query_params: dict[str, Any] = field(init=False, repr=False, eq=False, order=False)

    def __attrs_post_init__(self) -> None:
        """Process attributes after initialization."""
        if self.url not in [None, ""]:
            log.info("Passing 'url' to Forecastsolar node is not supported and will be ignored.")

        if not (isinstance(self.declination, int) and isinstance(self.azimuth, int) and isinstance(self.kwp, float)):
            if isinstance(self.declination, list) and isinstance(self.azimuth, list) and isinstance(self.kwp, list):
                if not len(self.declination) == len(self.azimuth) == len(self.kwp):
                    raise ValueError("'declination', 'azimuth' and 'kwp' must be passed for all planes")
                if self.api_key is None:
                    raise ValueError("Valid API key is needed for multiple planes")
            else:
                raise ValueError(
                    "'declination', 'azimuth' and 'kwp' must be passed either as lists or as single values."
                )

        if self.api_key is None and (self.endpoint not in ["estimate", "check"]):
            raise ValueError(f"Valid API key is needed for endpoint: {self.endpoint}")
        # Collect all url parameters and query parameters
        url_params = {}
        query_params = {}
        for _field in self.__attrs_attrs__:  # type: ignore[attr-defined]
            if _field.name is not None:
                if _field.metadata.get("QUERY_PARAM") is False:
                    url_params[_field.name] = getattr(self, _field.name)
                elif _field.metadata.get("QUERY_PARAM") is True:
                    query_params[_field.name] = getattr(self, _field.name)

        # Construct the URL
        url = self._build_url(url_params)

        object.__setattr__(self, "url", url)
        object.__setattr__(self, "_url_params", url_params)
        object.__setattr__(self, "_query_params", query_params)

        super().__attrs_post_init__()

    def _build_url(self, url_params: dict[str, Any]) -> str:
        """Build the URL for the Forecast Solar API.

        :param url_params: dictionary with URL parameters.
        :return: URL for the Forecast Solar API.
        """
        url = "https://api.forecast.solar"
        keys = ["endpoint", "latitude", "longitude"]

        # Check if the API key is set and add it to the URL
        if url_params["api_key"] is not None:
            keys.insert(0, "api_key")

        for key in keys:
            url += f"/{url_params[key]}"
            if key == "endpoint":
                url += "/watts"

        # Unpack plane parameters and add them to the URL
        if isinstance(url_params["declination"], list):
            url += "".join(
                f"/{d}/{a}/{k}" for d, a, k in zip(url_params["declination"], url_params["azimuth"], url_params["kwp"])
            )
        else:
            url += f"/{url_params['declination']}/{url_params['azimuth']}/{url_params['kwp']}"

        return url

    @classmethod
    def _get_params(cls, dikt: dict[str, Any]) -> dict[str, Any]:
        """Get the common parameters for a Forecast Solar node.

        :param dikt: dictionary with node information.
        :return: dict with: api_key, endpoint, latitude, longitude, declination, azimuth, kwp
        """
        attr_names = ForecastsolarNode.__annotations__.keys()
        discard_keys = ["api_key", "_url_params", "_query_params"]
        attributes = {key: dikt.get(key) for key in attr_names if key not in discard_keys}
        # return only non-"nan" values
        return {key: value for key, value in attributes.items() if str(value) not in ["None", "nan"]}

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> ForecastsolarNode:
        """Create a Forecast Solar node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: ForecastsolarNode object.
        """
        name, _, url, _, _ = cls._read_dict_info(dikt)

        params = cls._get_params(dikt)

        dict_key = str(dict_get_any(dikt, "api_key", "apikey", fail=False))
        if dict_key not in ["None", "nan"]:
            params["api_key"] = dict_key
        else:
            log.info(
                """'api_key' is None.
                Make sure to pass a valid API key to use the personal or the professional functions of forecastsolar.api
                otherwise the public functions are only available."""
            )

        # Convert lists given as strings to their literal values
        for key in ["declination", "azimuth", "kwp"]:
            if isinstance(params.get(key), str):
                try:
                    params[key] = ast.literal_eval(params[key])
                except (ValueError, SyntaxError):
                    raise ValueError(f"Invalid literal for parameter '{key}': {params[key]}") from None

        # Attempt to construct the class, handling potential type errors
        try:
            return cls(name, url, "forecast_solar", **params)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node '{name}':\n{e}") from e
