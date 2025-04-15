from __future__ import annotations

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any


def decode_modbus_value(
    value: Sequence[int], byteorder: str, type_: Callable | None = None, wordorder: str = "big"
) -> Any:
    r"""Method to decode incoming modbus values. Strings are always decoded as utf-8 values.

    If you do not want this behaviour specify 'bytes' as the data type.

    :param value: Current value to be decoded into float.
    :param byteorder: Byteorder for decoding i.e. 'little' or 'big' endian.
    :param type\_: Type of the output value. See `Python struct format character documentation
                  <https://docs.python.org/3/library/struct.html#format-characters>` for all possible
                  format strings (default: f).
    :return: Decoded value as a python type.
    """
    if byteorder not in ("little", "big"):
        raise ValueError(f"Specified an invalid byteorder: '{byteorder}'")
    if wordorder not in ("little", "big"):
        raise ValueError(f"Specified an invalid wordorder: '{wordorder}'")

    bo = "<" if byteorder == "little" else ">"

    # Swap words if word order is little endian
    if type_ in (int, float) and wordorder == "little":
        value = value[::-1]

    dtype, _len = _get_decode_params(value, type_)

    # Boolean values don't need decoding
    if type_ is bool:
        return bool(value[0])

    # Determine the format strings for packing and unpacking the received byte sequences. These format strings
    # depend on the endianness (determined by bo), the length of the value in bytes and the data type.
    pack = f">{len(value):1d}H"
    unpack = f"{bo}{_len}{dtype}"

    # Convert the value into the appropriate format
    val = struct.unpack(unpack, struct.pack(pack, *value))[0]
    if type_ is str:
        try:
            val = type_(val, "utf-8")
        except UnicodeDecodeError:
            val = ""
    elif type_ is not None:
        val = type_(val)
    else:
        val = float(val)

    return val


def _get_decode_params(value: Sequence[int], type_: Callable | None = None) -> tuple[str, int]:
    if type_ is str or type_ is bytes:
        dtype = "s"
        _len = len(value) * 2
    elif type_ is bool:
        dtype = "?"
        _len = 1
        if _len != len(value):
            raise ValueError(f"The length of the received value ({len(value)})does not match the data type {type_}")
    elif type_ is int:
        _int_types = {1: "b", 2: "h", 4: "i", 8: "q"}
        _len = 1
        try:
            dtype = _int_types[len(value) * 2]
        except KeyError:
            raise ValueError(
                f"The length of the received value ({len(value)})does not match the data type {type_}"
            ) from None
    elif type_ is float or type_ is None:
        _float_types = {2: "e", 4: "f", 8: "d"}
        _len = 1
        try:
            dtype = _float_types[len(value) * 2]
        except KeyError:
            raise ValueError(
                f"The length of the received value ({len(value)}) does not match the data type: {type_}"
            ) from None
    else:
        raise ValueError(f"The given modbus data type was not recognized: {type_}")

    return dtype, _len


def encode_bits(
    value: str | float | bytes, byteorder: str, bit_length: int, type_: Callable | None = None
) -> list[int]:
    r"""Method to encode python data type to modbus value. This means an array of bytes to send to a
    modbus server.

    :param value: Current value to be decoded into float.
    :param byteorder: Byteorder for decoding i.e. 'little' or 'big' endian.
    :param bit_length: Length of the value in bits.
    :param type\_: Type of the output value. See `Python struct format character documentation
                  <https://docs.python.org/3/library/struct.html#format-characters>` for all possible
                  format strings (default: f).
    :return: Decoded value as a python type.
    """
    byte_length = bit_length // 8
    # Make sure that value is of the type specified by the node.
    if type_ is not None:
        value = type_(value)

    if isinstance(value, int):
        _types = {1: "b", 2: "h", 4: "i", 8: "q"} if value < 0 else {1: "B", 2: "H", 4: "I", 8: "Q"}
        try:
            _type = _types[byte_length]
        except KeyError as e:
            raise ValueError(f"Byte length for integers must be either 1, 2, 4 or 8. Got {byte_length}.") from e
        _len: str | int = ""

    elif isinstance(value, float):
        _types = {2: "e", 4: "f", 8: "d"}
        try:
            _type = _types[byte_length]
        except KeyError as e:
            raise ValueError(f"Byte length for floats must be either 4 or 8. Got {byte_length}.") from e
        _len = ""

    else:
        _type = "s"
        _len = byte_length
        if not isinstance(value, bytes):
            value = bytes(value, "utf-8")

    _order = {"big": ">", "little": "<"}
    try:
        bo = _order[byteorder]
    except KeyError:
        raise ValueError(f"Unknown byte order specified: {byteorder}") from None

    try:
        byte = struct.pack(f"{bo}{_len}{_type}", value)
    except struct.error as e:
        raise ValueError(f"Could not convert value {value!r} to bits.") from e

    bitstrings = [f"{bin(x)[2:]:0>8}" for x in byte]
    return [int(z) for z in "".join(bitstrings)]


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
