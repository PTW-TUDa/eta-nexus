"""This module implements the node class, which is used to parametrize connections"""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from attrs import (
    field,
    validators as vld,
)

from eta_nexus import dict_get_any
from eta_nexus.nodes.node import Node
from eta_nexus.nodes.node_utils import _lower_str

if TYPE_CHECKING:
    from typing import Any

    from typing_extensions import Self


log = getLogger(__name__)


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


class ModbusNode(Node, protocol="modbus"):
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
        :return: ModbusNode object.
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
