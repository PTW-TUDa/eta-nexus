"""This module implements the node class, which is used to parametrize connections."""

from __future__ import annotations

import pathlib
from collections.abc import Mapping
from logging import getLogger
from typing import TYPE_CHECKING

import attrs
import pandas as pd
from attrs import (
    converters,
    define,
    field,
)

from eta_nexus import dict_get_any, url_parse
from eta_nexus.nodes.node_utils import _dtype_converter, _strip_str

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any, ClassVar
    from urllib.parse import ParseResult

    from typing_extensions import Self

    from eta_nexus.util.type_annotations import Path

default_schemes = {
    "modbus": "modbus.tcp",
    "emonio": "modbus.tcp",
    "opcua": "opc.tcp",
    "eneffco": "https",
    "local": "https",
    "entsoe": "https",
    "wetterdienst_observation": "https",
    "wetterdienst_prediction": "https",
    "forecast_solar": "https",
}

log = getLogger(__name__)


class MetaNode(type):
    """Metaclass to define all Node classes as frozen attr dataclasses."""

    def __new__(cls, name: str, bases: tuple, namespace: dict[str, Any], **kwargs: Any) -> MetaNode:
        attrs_args = kwargs.pop("attrs_args", {})
        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)
        return define(frozen=True, slots=False, **attrs_args)(new_cls)


class Node(metaclass=MetaNode):
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
        return attrs.evolve(self, **kwargs)  # type: ignore[misc]

    def as_dict(self, *, filter_none: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Return the attrs attribute values of node instance as a dict.

        :param filter_none: Filter none values, defaults to False
        :return: dict of attribute values
        """
        filter_func = self.__class__._filter_none(self) if filter_none else None
        return attrs.asdict(self, filter=filter_func, **kwargs)  # type: ignore[arg-type]

    def as_tuple(self, *, filter_none: bool = False, **kwargs: Any) -> tuple[Any, ...]:
        """Return the attrs attribute values of inst as a tuple.

        :param filter_none: Filter none values, defaults to False
        :return: tuple of attribute values
        """
        filter_func = self.__class__._filter_none(self) if filter_none else None
        return attrs.astuple(self, filter=filter_func, **kwargs)  # type: ignore[arg-type]

    @staticmethod
    def _filter_none(node: Node) -> Callable[[attrs.Attribute[Any], Any], bool]:
        """Return callable to filter none values, to be passed to attrs.asdict or attrs.astuple."""
        attributes = attrs.asdict(node)  # type: ignore[arg-type]
        non_values = {key: value for key, value in attributes.items() if value is None}
        return attrs.filters.exclude(*non_values.keys())

    @classmethod
    def from_dict(cls, dikt: Sequence[Mapping] | Mapping[str, Any], *, fail: bool = True) -> list[Self]:
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

        For Eneffco nodes the code field must be present.

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
                protocol = str(dict_get_any(node, "protocol"))
            except KeyError as e:
                text = f"Error reading node protocol in row {idx + 1}: {e}."
                if fail:
                    raise KeyError(text) from e
                log.exception(text)
                continue

            try:
                node_class = cls._registry[protocol.strip().lower()]
            except KeyError as e:
                text = f"Specified an unsupported protocol in row {idx + 1}: {protocol}."
                if fail:
                    raise ValueError(text) from e
                log.exception(text)
                continue

            try:
                nodes.append(node_class._from_dict(node))
            except (TypeError, KeyError) as e:
                text = f"Error while reading the configuration data for node in row {idx + 1}: {e}."
                if fail:
                    raise TypeError(text) from e
                log.exception(text)
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
        except KeyError as e:
            raise KeyError("Name or Code must be specified for all nodes in the dictionary.") from e
        if name in ("None", "nan", ""):
            raise ValueError("Names for Nodes can't be None.")
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
        except KeyError:
            log.exception(f"Could not get values {names} for node.")
            raise

        return value

    @classmethod
    def from_excel(cls, path: Path, sheet_name: str, *, fail: bool = True) -> list[Self]:
        """Method to read out nodes from an Excel document. The document must specify the following fields:

            * Code, IP, Port, Protocol (modbus or opcua or eneffco).

        For Modbus nodes the following additional fields are required:

            * ModbusRegisterType, ModbusByte, ModbusChannel.

        For OPC UA nodes the following additional fields are required:

            * Identifier.

        For Eneffco nodes the Code field must be present.

        The IP-Address should always be given without scheme (https://).

        :param path: Path to Excel document.
        :param sheet_name: name of Excel sheet, which will be read out.
        :param fail: Set this to false, if you would like to log errors instead of raising them.
        :return: List of Node objects.
        """
        file = path if isinstance(path, pathlib.Path) else pathlib.Path(path)
        input_ = pd.read_excel(file, sheet_name=sheet_name, dtype=str)
        return cls.from_dict(list(input_.to_dict("index").values()), fail=fail)
