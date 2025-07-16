"""This module implements the node class, which is used to parametrize connections."""

from __future__ import annotations

import struct
from logging import getLogger
from typing import TYPE_CHECKING

from attrs import (
    field,
    validators as vld,
)

from eta_nexus.nodes.node import Node
from eta_nexus.nodes.node_utils import _lower_str
from eta_nexus.util import dict_get_any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from eta_nexus.util.type_annotations import Self


log = getLogger(__name__)

_FLOAT_TYPES = {2: "e", 4: "f", 8: "d"}
_INT_TYPES = {1: "b", 2: "h", 4: "i", 8: "q"}


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


def bitarray_to_registers(bits: list[int | bool]) -> list[int]:
    """Convert a list of bits into a list of 16 bit 'bytes'."""
    # Make sure that _bits is a list of integers, not bools.
    _bits = [int(x) for x in bits] if isinstance(bits[0], bool) else bits

    b_size = (len(_bits) + 15) // 16
    register_list = [0] * b_size
    for i in range(b_size):
        start = i * 16
        register_list[i] = int("".join([str(v) for v in _bits[start : start + 16]]), 2)

    return register_list


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

        # Set default type of float
        if self.dtype is None:
            object.__setattr__(self, "dtype", float)

        if self.dtype not in (int, float, str, bytes, bool):
            raise ValueError(
                f"The given modbus data type was not recognized: {self.dtype}. Please use int, float, str, bytes, bool."
            )

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

    def decode_modbus_value(self, value: Sequence[int]) -> Any:
        """Decode incoming modbus values.

        Strings are always decoded as utf-8 values.
        If you do not want this behaviour, specify 'bytes' as the data type for the Node.

        :param value: Current value to be decoded
        :return: Decoded value as the Node's data type.
        """
        # Boolean values don't need decoding
        if self.dtype is bool:
            if len(value) > 1:
                raise ValueError(f"Length of boolean values mustn't exceed one, got {len(value)}")
            return bool(value[0])

        bo = "<" if self.mb_byteorder == "little" else ">"

        # Swap words if word order is little endian
        if self.dtype in (int, float) and self.mb_wordorder == "little":
            value = value[::-1]

        dtype, _len = self._get_decode_params(value)

        # Determine the format strings for packing and unpacking the received byte sequences. These format strings
        # depend on the endianness (determined by bo), the length of the value in bytes and the data type.
        pack = f">{len(value):1d}H"
        unpack = f"{bo}{_len}{dtype}"

        # Convert the value into the appropriate format
        val: Any = struct.unpack(unpack, struct.pack(pack, *value))[0]
        if self.dtype is str:
            try:
                val = str(val, encoding="utf-8")
            except UnicodeDecodeError:
                log.exception(f"Could not convert value {val} to string")
                val = ""
        elif self.dtype is not None:
            val = self.dtype(val)
        else:
            val = float(val)

        return val

    def encode_bits(self, value: str | float | bytes) -> list[int]:
        """Encode python data type to modbus value.
        This means an array of bytes to send to a modbus server.

        :param value: Current value to be decoded into float.
        :return: Decoded value as a python type.
        """
        # Make sure that value is of the type specified by the node.
        if self.dtype is not None:
            value = self.dtype(value)

        if self.dtype is str:
            value = bytes(str(value), encoding="utf-8")

        _type, _len = self._get_encode_params(value)

        bo = "<" if self.mb_byteorder == "little" else ">"

        try:
            byte = struct.pack(f"{bo}{_len}{_type}", value)
        except struct.error as e:
            raise ValueError(f"Could not convert value {value!r} to bits.") from e

        bitstrings = [f"{bin(x)[2:]:0>8}" for x in byte]
        return [int(z) for z in "".join(bitstrings)]

    def _get_encode_params(self, value: str | float | bytes) -> tuple[str, int]:
        byte_length: int = self.mb_bit_length // 8

        try:
            if isinstance(value, int):
                type_format = _INT_TYPES[byte_length]
                if value >= 0:
                    type_format = type_format.upper()  # Use unsigned integer
                return type_format, 1
            if isinstance(value, float):
                return _FLOAT_TYPES[byte_length], 1
            if isinstance(value, (str, bytes)):
                return "s", byte_length
        except KeyError as e:
            raise ValueError(
                f"The length of the value ({byte_length}) does not match the data type: {type(value)}"
            ) from e

    def _get_decode_params(self, value: Sequence[int]) -> tuple[str, int]:
        """Provide parameters for decoding incoming modbus values

        :param value: Incoming data
        :return: Struct format and length
        """
        byte_length = len(value) * 2  # Conversion from 16 to 8 Bit length (Register to Byte)
        try:
            if self.dtype is int:
                return _INT_TYPES[byte_length], 1
            if self.dtype is float:
                return _FLOAT_TYPES[byte_length], 1
        except KeyError:
            raise ValueError(
                f"The length of the received value ({len(value)}) does not match the data type: {self.dtype}"
            ) from None
        else:  # str and bytes
            return "s", byte_length
