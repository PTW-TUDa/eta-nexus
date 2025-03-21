from __future__ import annotations

import struct
from asyncio import sleep as async_sleep
from datetime import datetime
from itertools import groupby
from time import sleep
from typing import TYPE_CHECKING

import pandas as pd

from eta_connect.connectors.node import Node
from eta_connect.util import ensure_timezone

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from typing import Any, Final

    from eta_connect.type_hints import TimeStep


class RetryWaiter:
    """Helper class which keeps track of waiting time before retrying a connection."""

    VALUES: Final[list[int]] = [0, 1, 3, 5, 5, 10, 20, 30, 40, 60]

    def __init__(self) -> None:
        self.counter = 0

    def tried(self) -> None:
        """Register a retry with the RetryWaiter."""
        self.counter += 1

    def success(self) -> None:
        """Register a successful connection with the RetryWaiter."""
        self.counter = 0

    @property
    def wait_time(self) -> int:
        """Return the time to wait for."""
        if self.counter >= len(self.VALUES) - 1:
            return self.VALUES[-1]
        return self.VALUES[self.counter]

    def wait(self) -> None:
        """Wait/sleep synchronously."""
        sleep(self.wait_time)

    async def wait_async(self) -> None:
        """Wait/sleep asynchronously - must be awaited."""
        await async_sleep(self.wait_time)


def decode_modbus_value(
    value: Sequence[int], byteorder: str, type_: Callable | None = None, wordorder: str = "big"
) -> Any:
    r"""Method to decode incoming modbus values. Strings are always decoded as utf-8 values. If you do not
    want this behaviour specify 'bytes' as the data type.

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
    for i in range(0, b_size):
        start = i * 16
        register_list[i] = int("".join([str(v) for v in _bits[start : start + 16]]), 2)

    return register_list


def all_equal(iterable: Iterable[Any]) -> bool:
    """Check if all values inside iterable are equal

    :param iterable: python iterable
    :return: True if all values are equal False elsewhere
    """

    g = groupby(iterable)
    return bool(next(g, True)) and not bool(next(g, False))


class IntervalChecker:
    """Class for the subscription interval checking."""

    def __init__(self) -> None:
        #: Dictionary that stores the value and the time for checking changes and the time interval
        self.node_latest_values: dict[Node, list] = {}

        #: :py:func:`eta_connect.util.ensure_timezone`
        self._assert_tz_awareness = ensure_timezone

    def push(
        self,
        node: Node,
        value: Any | pd.Series | Sequence[Any],
        timestamp: datetime | pd.DatetimeIndex | TimeStep | None = None,
    ) -> None:
        """Push value and time in dictionary for a node. If the value doesn't change compared to the previous
        timestamp, the push is skipped.

        :param node: Node to check.
        :param value: Value from the subscription.
        :param timestamp: Time of the incoming value of the node.
        """

        if node in self.node_latest_values:
            if value != self.node_latest_values[node][0]:
                self.node_latest_values[node] = [value, timestamp]
        elif node.interval is not None:
            self.node_latest_values[node] = [value, timestamp]

    def check_interval_connection(self) -> bool | None:
        """Check the interval between old and new value. If no interval has been defined, the check interval is skipped.

        :return: Boolean for the interval check.
        """

        # Get the current time to compare the interval
        time = self._assert_tz_awareness(datetime.now())

        if len(self.node_latest_values) > 0:
            for node in self.node_latest_values:
                _time_since_last_check = (
                    (time - self.node_latest_values[node][1]).total_seconds()
                    if node in self.node_latest_values
                    else None
                )
                if node in self.node_latest_values and _time_since_last_check is not None:
                    if _time_since_last_check <= float(node.interval):  # type: ignore
                        _changed_within_interval = True
                    else:
                        _changed_within_interval = False
                        break
                else:
                    _changed_within_interval = True
        else:
            _changed_within_interval = True

        return _changed_within_interval
