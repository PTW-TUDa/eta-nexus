"""This module implements the node class, which is used to parametrize connections"""

from __future__ import annotations

import ast
import enum
import pathlib
import re
from collections.abc import Mapping
from datetime import timedelta
from logging import getLogger
from sys import maxsize
from typing import TYPE_CHECKING

import attrs
import pandas as pd
from attrs import (
    converters,
    define,
    field,
    validators as vld,
)
from typing_extensions import deprecated
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.provider.dwd.mosmix.api import DwdMosmixParameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationParameter,
    DwdObservationResolution,
)

from eta_connect import dict_get_any, url_parse

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any, ClassVar, Final
    from urllib.parse import ParseResult

    from typing_extensions import Self, TypeAlias

    from eta_connect.type_hints import Path

default_schemes = {
    "modbus": "modbus.tcp",
    "emonio": "modbus.tcp",
    "opcua": "opc.tcp",
    "eneffco": "https",
    "local": "https",
    "entsoe": "https",
    "cumulocity": "https",
    "wetterdienst_observation": "https",
    "wetterdienst_prediction": "https",
    "forecast_solar": "https",
}


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
        if value.startswith("list") or value.startswith("tuple") or value.startswith("dict"):
            value = value.split("[")[0]
        dtype = _dtypes[_lower_str(value)]
    except KeyError:
        log.warning(
            f"The specified data type ({value}) is currently not available in the datatype map and will not be applied."
        )
        dtype = None

    return dtype


class NodeMeta(type):
    """Metaclass to define all Node classes as frozen attr dataclasses."""

    def __new__(cls, name: str, bases: tuple, namespace: dict[str, Any], **kwargs: Any) -> NodeMeta:
        attrs_args = kwargs.pop("attrs_args", {})
        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)
        return define(frozen=True, slots=False, **attrs_args)(new_cls)


class Node(metaclass=NodeMeta):
    """The node objects represents a single variable. Valid keyword arguments depend on the protocol."""

    #: Name for the node.
    name: str = field(converter=_strip_str, eq=True)
    #: URL of the connection.
    url: str = field(eq=True, order=True)
    #: Parse result object of the URL (in case more post-processing is required).
    url_parsed: ParseResult = field(init=False, repr=False, eq=False, order=False)
    #: Protocol of the connection.
    protocol: str = field(repr=False, eq=False, order=False)
    #: Username for login to the connection (default: None).
    usr: str | None = field(default=None, kw_only=True, repr=False, eq=False, order=False)
    #: Password for login to the connection (default: None).
    pwd: str | None = field(default=None, kw_only=True, repr=False, eq=False, order=False)
    #: Interval
    interval: str | None = field(
        default=None, converter=converters.optional(float), kw_only=True, repr=False, eq=False, order=False
    )
    #: Data type of the node (for value conversion). Note that strings will be interpreted as utf-8 encoded. If you
    #: do not want this behaviour, use 'bytes'.
    dtype: Callable | None = field(
        default=None, converter=converters.optional(_dtype_converter), kw_only=True, repr=False, eq=False, order=False
    )

    _registry: ClassVar = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Store subclass definitions to instantiate based on protocol."""
        protocol = kwargs.pop("protocol", None)
        if protocol:
            cls._registry[protocol] = cls

        return super().__init_subclass__(**kwargs)

    def __new__(cls, name: str, url: str, protocol: str, *args: Any, **kwargs: Any) -> Self:
        """Create node object of correct subclass corresponding to protocol."""
        try:
            subclass = cls._registry[protocol]
        except KeyError as error:
            raise ValueError(f"Specified an unsupported protocol: {protocol}.") from error

        # Return the correct subclass for the specified protocol
        return object.__new__(subclass)

    def __attrs_post_init__(self) -> None:
        """Add post-processing to the url, username and password information. Username and password specified during
        class init take precedence.
        """
        url, usr, pwd = url_parse(self.url, scheme=default_schemes[self.protocol])

        if self.usr is None or str(self.usr) == "nan":
            object.__setattr__(self, "usr", usr)
        object.__setattr__(self, "usr", str(self.usr) if self.usr is not None else None)

        if self.pwd is None or str(self.pwd) == "nan":
            object.__setattr__(self, "pwd", pwd)
        object.__setattr__(self, "pwd", str(self.pwd) if self.pwd is not None else None)

        object.__setattr__(self, "url", url.geturl())
        object.__setattr__(self, "url_parsed", url)

    def evolve(self, **kwargs: Any) -> Node:
        """Returns a new node instance
        by copying the current node and changing only specified keyword arguments.

        This allows for seamless node instantiation with only a few changes.

        :param kwargs: Keyword arguments to change.
        :return: New instance of the node.
        """
        return attrs.evolve(self, **kwargs)  # type: ignore

    def as_dict(self, filter_none: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Return the attrs attribute values of node instance as a dict.

        :param filter_none: Filter none values, defaults to False
        :return: dict of attribute values
        """
        filter_func = self.__class__._filter_none(self) if filter_none else None
        return attrs.asdict(self, filter=filter_func, **kwargs)  # type: ignore

    def as_tuple(self, filter_none: bool = False, **kwargs: Any) -> tuple[Any, ...]:
        """Return the attrs attribute values of inst as a tuple.

        :param filter_none: Filter none values, defaults to False
        :return: tuple of attribute values
        """
        filter_func = self.__class__._filter_none(self) if filter_none else None
        return attrs.astuple(self, filter=filter_func, **kwargs)  # type: ignore

    @staticmethod
    def _filter_none(node: Node) -> Callable[[attrs.Attribute[Any], Any], bool]:
        """Return callable to filter none values, to be passed to attrs.asdict or attrs.astuple."""
        attributes = attrs.asdict(node)  # type: ignore
        non_values = {key: value for key, value in attributes.items() if value is None}
        return attrs.filters.exclude(*non_values.keys())

    @classmethod
    def from_dict(cls, dikt: Sequence[Mapping] | Mapping[str, Any], fail: bool = True) -> list[Self]:
        """Create nodes from a dictionary of node configurations. The configuration must specify the following
        fields for each node:

            * Code (or name), URL, Protocol (i.e. modbus or opcua or eneffco).
              The URL should be a complete network location identifier. Alternatively it is possible to specify the
              location in two fields: IP and Port. These should only contain the respective parts (as in only an IP
              address and only the port number).
              The IP-Address should always be given without scheme (https://).

        For local nodes no additional fields are required.

        For Modbus nodes the following additional fields are required:

            * ModbusRegisterType (or mb_register), ModbusSlave (or mb_slave), ModbusChannel (or mb_channel).

        For OPC UA nodes the following additional fields are required:

            * Identifier.

        For EnEffCo nodes the code field must be present.

        For EntsoE nodes the endpoint field must be present.

        :param dikt: Configuration dictionary.
        :param fail: Set this to false, if you would like to log errors instead of raising them.
        :return: List of Node objects.
        """

        nodes = []

        iter_ = [dikt] if isinstance(dikt, Mapping) else dikt
        for idx, lnode in enumerate(iter_):
            node = {k.strip().lower(): v for k, v in lnode.items()}

            try:
                protocol = cls._read_dict_protocol(node)
            except KeyError as e:
                text = f"Error reading node protocol in row {idx + 1}: {e}."
                if fail:
                    raise KeyError(text) from e
                log.error(text)
                continue

            try:
                node_class = cls._registry[protocol.strip().lower()]
            except KeyError as e:
                text = f"Specified an unsupported protocol in row {idx + 1}: {protocol}."
                if fail:
                    raise ValueError(text) from e
                log.error(text)
                continue

            try:
                nodes.append(node_class._from_dict(node))
            except (TypeError, KeyError) as e:
                text = f"Error while reading the configuration data for node in row {idx + 1}: {e}."
                if fail:
                    raise TypeError(text) from e
                log.error(text)

        return nodes

    @staticmethod
    def _read_dict_info(node: dict[str, Any]) -> tuple[str, str, str, str, int]:
        """Read general info about a node from a dictionary.

        :param node: dictionary containing node information.
        :return: name, pwd, url, usr of the node
        """
        # Read name first
        try:
            name = str(dict_get_any(node, "code", "name"))
            if name == "nan" or name is None:
                raise KeyError
        except KeyError as e:
            raise KeyError("Name or Code must be specified for all nodes in the dictionary.") from e
        # Find URL or IP and port
        if "url" in node and node["url"] is not None and str(node["url"]) not in {"nan", ""}:
            url = node["url"].strip()
        elif "ip" in node and node["ip"] is not None and str(node["ip"]) not in {"nan", ""}:
            _port = dict_get_any(node, "port", fail=False, default="")
            port = "" if _port in {None, ""} or str(_port) == "nan" else f":{int(_port)}"
            url = f"{dict_get_any(node, 'ip')}{port}"
        else:
            url = None
        usr = dict_get_any(node, "username", "user", "usr", fail=False)
        pwd = dict_get_any(node, "password", "pwd", "pw", fail=False)
        interval = dict_get_any(node, "interval", fail=False)
        return name, pwd, url, usr, interval

    @staticmethod
    def _read_dict_protocol(node: dict[str, Any]) -> str:
        try:
            protocol = str(dict_get_any(node, "protocol"))
            if protocol == "nan" or protocol is None:
                raise KeyError
        except KeyError as e:
            raise KeyError("Protocol must be specified for all nodes in the dictionary.") from e

        return protocol

    @staticmethod
    def _try_dict_get_any(dikt: dict[str, Any], *names: str) -> Any:
        """Get any of the specified items from the node, if any are available. The function will return
        the first value it finds, even if there are multiple matches.

        This function will output sensible error messages, when the values are not found.

        :param dikt: Dictionary of the node to get values from.
        :param names: Item names to look for.
        :return: Value from dictionary.
        """
        try:
            value = dict_get_any(dikt, *names, fail=True)
        except KeyError as e:
            log.error(f"For the node, the field '{names[0]}' must be specified or check the correct spelling.")
            raise KeyError(
                "The required parameter for the node configuration was not found (see log). "
                "Could not load config "
                "file. "
            ) from e

        return value

    @classmethod
    def from_excel(cls, path: Path, sheet_name: str, fail: bool = True) -> list[Self]:
        """
        Method to read out nodes from an Excel document. The document must specify the following fields:

            * Code, IP, Port, Protocol (modbus or opcua or eneffco).

        For Modbus nodes the following additional fields are required:

            * ModbusRegisterType, ModbusByte, ModbusChannel.

        For OPC UA nodes the following additional fields are required:

            * Identifier.

        For EnEffCo nodes the Code field must be present.

        The IP-Address should always be given without scheme (https://).

        :param path: Path to Excel document.
        :param sheet_name: name of Excel sheet, which will be read out.
        :param fail: Set this to false, if you would like to log errors instead of raising them.
        :return: List of Node objects.
        """

        file = path if isinstance(path, pathlib.Path) else pathlib.Path(path)
        input_ = pd.read_excel(file, sheet_name=sheet_name, dtype=str)

        return cls.from_dict(list(input_.to_dict("index").values()), fail)

    @classmethod
    def get_eneffco_nodes_from_codes(cls, code_list: Sequence[str], eneffco_url: str) -> list[Self]:
        """
        Utility function to retrieve Node objects from a list of EnEffCo Codes (Identifiers).

        .. deprecated:: v2.0.0
            Use the *from_ids* function of the EnEffCoConnection Class instead.

        :param code_list: List of EnEffCo identifiers to create nodes from.
        :param eneffco_url: URL to the EnEffCo system.
        :return: List of EnEffCo nodes.
        """
        nodes = []
        for code in code_list:
            nodes.append(cls(name=code, url=eneffco_url, protocol="eneffco", eneffco_code=code))
        return nodes


class NodeLocal(Node, protocol="local"):
    """Local Node (no specific protocol), useful for example to manually provide data to subscription handlers."""

    def __attrs_post_init__(self) -> None:
        """Ensure username and password are processed correctly."""
        super().__attrs_post_init__()

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> NodeLocal:
        """Create a local node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeLocal object.
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)
        try:
            return cls(name, url, "local", usr=usr, pwd=pwd, interval=interval)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}") from e


def _mb_endianness_converter(value: str) -> str:
    """Convert some values for mb_byteorder.

    :param value: Value to be converted to mb_byteorder
    :return: mb_byteorder corresponding to correct scheme.
    """
    value = _lower_str(value)
    if value in {"little", "littleendian"}:
        return "little"

    if value in {"big", "bigendian"}:
        return "big"

    return ""


class NodeModbus(Node, protocol="modbus"):
    """Node for the Modbus protocol."""

    #: Modbus Slave ID
    mb_slave: int | None = field(kw_only=True, default=32, converter=int)
    #: Modbus Register name. One of input, discrete_input, coils and holding. Note that only coils and
    #: holding can be written to.
    mb_register: str = field(
        kw_only=True, converter=_lower_str, validator=vld.in_(("input", "discrete_input", "coils", "holding"))
    )
    #: Modbus Channel (Address of the value)
    mb_channel: int = field(kw_only=True, converter=int)
    #: Length of the value in bits (default 32). This determines, how much data is read from the server. The
    #: value must be a multiple of 16.
    mb_bit_length: int = field(kw_only=True, default=32, converter=int, validator=vld.ge(1))

    #: Byteorder of values returned by modbus
    mb_byteorder: str = field(kw_only=True, converter=_mb_endianness_converter, validator=vld.in_(("little", "big")))
    #: Wordorder of values returned by modbus
    mb_wordorder: str = field(
        default="big", kw_only=True, converter=_mb_endianness_converter, validator=vld.in_(("little", "big"))
    )

    def __attrs_post_init__(self) -> None:
        """Add default port to the URL and convert mb_byteorder values."""
        super().__attrs_post_init__()

        # Set port to default 502 if it was not explicitly specified
        if not isinstance(self.url_parsed.port, int):
            url = self.url_parsed._replace(netloc=f"{self.url_parsed.hostname}:502")
            object.__setattr__(self, "url", url.geturl())
            object.__setattr__(self, "url_parsed", url)

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> Self:
        """Create a modbus node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeModbus object.
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)
        # Initialize node if protocol is 'modbus'
        try:
            mb_register = cls._try_dict_get_any(dikt, "mb_register", "modbusregistertype")
            mb_channel = cls._try_dict_get_any(dikt, "mb_channel", "modbuschannel")
            mb_byteorder = cls._try_dict_get_any(dikt, "mb_byteorder", "modbusbyteorder")
            mb_wordorder = dict_get_any(dikt, "mb_wordorder", "modbuswordorder", fail=False, default="big")
            mb_slave = dict_get_any(dikt, "mb_slave", "modbusslave", fail=False, default=32)
            mb_bit_length = dict_get_any(dikt, "mb_bit_length", "mb_bitlength", fail=False, default=32)
            dtype = dict_get_any(dikt, "dtype", "datentyp", fail=False)
        except KeyError as e:
            raise KeyError(
                f"The required parameter for the node configuration was not found (see log). The node {name} could "
                f"not load."
            ) from e
        try:
            return cls(
                name,
                url,
                "modbus",
                usr=usr,
                pwd=pwd,
                mb_register=mb_register,
                mb_slave=mb_slave,
                mb_channel=mb_channel,
                mb_bit_length=mb_bit_length,
                mb_byteorder=mb_byteorder,
                mb_wordorder=mb_wordorder,
                dtype=dtype,
                interval=interval,
            )
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e


class NodeOpcUa(Node, protocol="opcua"):
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
        object.__setattr__(self, "opc_name", self.opc_path_str.split(".")[-1])  # type: ignore

    @property
    @deprecated("This attribute will be removed in the future")
    def opc_path(self) -> list[NodeOpcUa]:
        split_path = (
            self.opc_path_str.rsplit(".", maxsplit=len(self.opc_path_str.split(".")) - 2)  # type: ignore
            if self.opc_path_str[0] == "."  # type: ignore
            else self.opc_path_str.split(".")  # type: ignore
        )

        path = []
        for k in range(len(split_path) - 1):
            path.append(
                NodeOpcUa(
                    split_path[k].strip(" ."),
                    self.url,
                    "opcua",
                    usr=self.usr,
                    pwd=self.pwd,
                    opc_id="ns={};s={}".format(self.opc_ns, ".".join(split_path[: k + 1])),
                )
            )
        return path

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> Self:
        """Create an opcua node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeOpcUa object.
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

    def evolve(self, **kwargs: Any) -> Node:
        """Returns a new node instance
        by copying the current node and changing only specified keyword arguments.

        This allows for seamless node instantiation with only a few changes.

        Adjusted attributes handling according to OpcUa node instantiation logic as in '__attrs_post_init__'.

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


class NodeEnEffCo(Node, protocol="eneffco"):
    """Node for the EnEffCo API."""

    #: EnEffCo datapoint code / ID.
    eneffco_code: str = field(kw_only=True, converter=str)

    def __attrs_post_init__(self) -> None:
        """Ensure username and password are processed correctly."""
        super().__attrs_post_init__()

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> Self:
        """Create a EnEffCo node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeEnEffCo object.
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


class NodeEntsoE(Node, protocol="entsoe"):
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

    `eta_connect.connectors.entso_e._ConnectionConfiguration._doc_types`

    .. list-table:: **Main bidding zone**
        :widths: 15 25
        :header-rows: 1

        * - Bidding Zone
          - Description
        * - DEU-LUX
          - Deutschland-Luxemburg

    The other possible bidding zones are listed in

    `eta_connect.connectors.entso_e._ConnectionConfiguration._bidding_zones`

    """

    #: REST endpoint.
    endpoint: str = field(kw_only=True, converter=str)
    #: Bidding zone.
    bidding_zone: str = field(kw_only=True, converter=str)

    def __attrs_post_init__(self) -> None:
        """Ensure username and password are processed correctly."""
        super().__attrs_post_init__()

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> NodeEntsoE:
        """Create an EntsoE node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeEntsoE object.
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


class NodeCumulocity(Node, protocol="cumulocity"):
    """Node for the Cumulocity API."""

    # parameters for reading/writing from/to cumulocity nodes
    device_id: str = field(kw_only=True, converter=str)
    measurement: str = field(kw_only=True, converter=str)
    fragment: str = field(kw_only=True, converter=str, default="")

    def __attrs_post_init__(self) -> None:
        """Ensure username and password are processed correctly."""
        super().__attrs_post_init__()

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> NodeCumulocity:
        """Create a Cumulocity node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeCumulocity object.
        """
        name, pwd, url, usr, interval = cls._read_dict_info(dikt)
        try:
            device_id = cls._try_dict_get_any(dikt, "id", "device_id")
        except KeyError as e:
            raise KeyError(
                f"The required parameter for the node configuration was not found (see log). The node {name} could "
                f"not load."
            ) from e
        try:
            measurement = cls._try_dict_get_any(dikt, "measurement", "Measurement")
        except KeyError as e:
            raise KeyError(
                f"The required parameter for the node configuration was not found (see log). The node {name} could "
                f"not load."
            ) from e

        try:
            fragment = cls._try_dict_get_any(dikt, "fragment", "Fragment")
        except KeyError:
            fragment = ""
        try:
            return cls(
                name,
                url,
                "cumulocity",
                usr=usr,
                pwd=pwd,
                device_id=device_id,
                measurement=measurement,
                fragment=fragment,
            )
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e


class NodeWetterdienst(Node):
    """
    Basic Node for the Wetterdienst API.
    This class is not meant to be used directly, but to be subclassed by
    NodeWetterdienstObservation and NodeWetterdienstPrediction.
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


class NodeWetterdienstObservation(NodeWetterdienst, protocol="wetterdienst_observation"):
    """
    Node for the Wetterdienst API to get weather observations.
    For more information see: https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/observation/
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
                params = DwdObservationParameter[resolution.name]  # type: ignore
                if self.parameter in [param.name for param in params if type(param) is not enum.EnumMeta]:
                    available_resolutions.append(resolution.name)  # type: ignore
            if len(available_resolutions) == 0:
                raise ValueError(f"Parameter {self.parameter} is not a valid observation parameter.")
            raise ValueError(
                f"Parameter {self.parameter} is not valid for the given resolution. "
                f"Valid resolutions for parameter {self.parameter} are: "
                f"{available_resolutions}"
            )

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> NodeWetterdienstObservation:
        """Create a WetterdienstObservation node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeWetterdienst object.
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


class NodeWetterdienstPrediction(NodeWetterdienst, protocol="wetterdienst_prediction"):
    """
    Node for the Wetterdienst API to get weather predictions.
    For more information see: https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/mosmix/
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
    def _from_dict(cls, dikt: dict[str, Any]) -> NodeWetterdienstPrediction:
        """Create a WetterdienstPrediction node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeWetterdienst object.
        """
        name, _, _, _, _ = cls._read_dict_info(dikt)
        params = cls._get_params(dikt)
        mosmix_type = dikt.get("mosmix_type")
        try:
            return cls(name, "", "wetterdienst_prediction", mosmix_type=mosmix_type, **params)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e


class EmonioConstants:
    """Dict constants for the Emonio API."""

    #: Mapping of parameters to addresses
    PARAMETER_MAP: Final[dict[int, list[str]]] = {
        0: ["VRMS", "V_RMS", "Voltage", "V", "Spannung"],
        2: ["IRMS", "I_RMS", "Current", "I", "Strom"],
        4: ["WATT", "Power", "W", "Leistung", "Wirkleistung"],
        6: ["VAR", "Reactive Power", "VAR", "Blindleistung"],
        8: ["VA", "Apparent Power", "VA", "Scheinleistung"],
        10: ["FREQ", "Frequency", "Hz", "Frequenz"],
        12: ["KWH", "Energy", "kWh", "Energie"],
        14: ["PF", "Power Factor", "PF", "Leistungsfaktor"],
        20: ["VRMS MIN", "VRMS_MIN", "Voltage Min", "V Min", "Spannung Min"],
        22: ["VRMS MAX", "VRMS_MAX", "Voltage Max", "V Max", "Spannung Max"],
        24: ["IRMS MIN", "IRMS_MIN", "Current Min", "I Min", "Strom Min"],
        26: ["IRMS MAX", "IRMS_MAX", "Current Max", "I Max", "Strom Max"],
        28: ["WATT MIN", "WATT_MIN", "Power Min", "W Min", "Leistung Min"],
        30: ["WATT MAX", "WATT_MAX", "Power Max", "W Max", "Leistung Max"],
        500: ["Temp", "degree", "Temperature", "°C", "Temperatur"],
        800: ["Impulse", "Impuls"],
    }
    #: Create dictionary with all upper cased parameters
    UPPER_CASED: Final[dict[int, list[str]]] = {
        adr: [par.upper() for par in par_list] for (adr, par_list) in PARAMETER_MAP.items()
    }
    #: Mapping of phases to address offsets
    PHASE_MAP: Final[dict[str, int]] = {
        "a": 0,
        "b": 100,
        "c": 200,
        "abc": 300,
    }


class NodeEmonio(Node, protocol="emonio"):
    """
    Node for the emonio. The parameter to read is specified by the name of the node.
    Available parameters are defined in the parameter_map class attribute.
    Additionally, the phase of the parameter can be specified, with 'a', 'b', 'c' or 'abc'.

    https://wiki.emonio.de/de/Emonio_P3
    """

    #: Modbus address of the parameter to read
    address: int = field(default=-1, kw_only=True, converter=int)
    #: Phase of the parameter (a, b, c). If not set, all phases are read
    phase: str = field(default="abc", kw_only=True, converter=_lower_str, validator=vld.in_(("a", "b", "c", "abc")))

    def __attrs_post_init__(self) -> None:
        """Ensure that all required parameters are present and valid."""
        super().__attrs_post_init__()

        if self.address == -1:
            address = self._translate_name()
            object.__setattr__(self, "address", address)
        assert self.address != -1

        _parameter = self.address % 100
        _phase = self.address // 100 * 100
        # Validate address
        if self.address in {500, 800}:
            pass
        elif _parameter not in EmonioConstants.PARAMETER_MAP or _phase not in EmonioConstants.PHASE_MAP.values():
            raise ValueError(f"Address {self.address} for node {self.name} is not valid.")
        elif _parameter >= 20 and _parameter <= 30 and _phase == 300:
            raise ValueError("Phase must be set for MIN/MAX values")

    def _translate_name(self) -> int:
        """Translate the name of the node to the correct parameter name.

        :return: Modbus address of the parameter.
        """
        parameter: int | None = None
        phase: int | None = None
        # Try to find matching parameter for the name
        for address in EmonioConstants.UPPER_CASED:
            # e.g. Server1.Voltage -> VOLTAGE
            parameter_str = self.name.split(".")[-1].upper()
            if parameter_str in EmonioConstants.UPPER_CASED[address]:
                parameter = address
                log.debug(f"Parameter {parameter_str} found at address {address}")
                break
        # If no parameter was found, raise an error
        if parameter is None:
            raise ValueError(f"Parameter for node {self.name} not found, name is not valid.")

        # Temperature and Impulse values do not have a phase
        if parameter in (500, 800):
            return parameter

        # Phase is set to 0, 100, 200 or 300. (300 is default)
        phase = EmonioConstants.PHASE_MAP[self.phase]

        # Return correct address (by adding the phase offset to the parameter)
        return parameter + phase

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> NodeEmonio:
        """Create an Emonio node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeEmonio object.
        """
        name, _, url, _, interval = cls._read_dict_info(dikt)

        phase = dikt.get("phase", "abc")
        phase = "abc" if pd.isna(phase) else phase

        address = dikt.get("address")
        address = -1 if pd.isna(address) else address
        try:
            return cls(name, url, "emonio", interval=interval, phase=phase, address=address)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e


# Forecast.Solar API Node
def _convert_list(_type: TypeAlias) -> Callable:
    """Convert an optional list of values to a single value or a list of values.

    :param _type: type to convert the values to.
    :return: converter function.
    """

    def converter(value: Any) -> _type | list[_type]:
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
    """Transform the fields of the ForecastSolar node class.

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


class NodeForecastSolar(Node, protocol="forecast_solar", attrs_args=attrs_args):
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
    :class:'eta_connect.connectors.forecast_solar.ForecastSolarConnection'.
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
            log.info("Passing 'url' to ForecastSolar node is not supported and will be ignored.")

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
        attr_names = NodeForecastSolar.__annotations__.keys()
        discard_keys = ["api_key", "_url_params", "_query_params"]
        attributes = {key: dikt.get(key) for key in attr_names if key not in discard_keys}
        # return only non-"nan" values
        return {key: value for key, value in attributes.items() if str(value) not in ["None", "nan"]}

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> NodeForecastSolar:
        """Create a Forecast Solar node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: NodeForecastSolar object.
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
