import pytest

from eta_nexus.connections.connection_utils import RetryWaiter
from eta_nexus.nodes.modbus_node import ModbusNode, bitarray_to_registers

modbus_values = (
    (5, "big", 8, bytes([0x05])),
    (1001, "big", 32, bytes([0x00, 0x00, 0x03, 0xE9])),
    (1001, "little", 32, bytes([0xE9, 0x03, 0x00, 0x00])),
    (129387, "big", 32, bytes([0x00, 0x01, 0xF9, 0x6B])),
    (129387, "little", 32, bytes([0x6B, 0xF9, 0x01, 0x00])),
    (2.3782, "big", 32, bytes([0x40, 0x18, 0x34, 0x6E])),
    (2.3782, "little", 32, bytes([0x6E, 0x34, 0x18, 0x40])),
    ("string", "big", 48, b"string"),
    ("string", "little", 48, b"string"),
    (b"string", "little", 64, b"string\x00\x00"),
)


@pytest.fixture(scope="module")
def node() -> ModbusNode:
    return ModbusNode(
        name="foo",
        url="bar",
        protocol="modbus",
        mb_register="holding",
        mb_channel=0,
        mb_bit_length=32,
        mb_byteorder="little",
        dtype="int",
    )


@pytest.mark.parametrize(("value", "byteorder", "bitlength", "expected"), modbus_values)
def test_encode_modbus_value(value, node: ModbusNode, byteorder, bitlength, expected):
    _node = node.evolve(mb_byteorder=byteorder, mb_bit_length=bitlength, dtype=type(value).__name__)

    result = _node.encode_bits(value)
    assert int("".join(str(v) for v in result), 2).to_bytes(bitlength // 8, "big") == expected


@pytest.mark.parametrize(("value", "byteorder", "bitlength", "expected"), modbus_values)
def test_encode_decode(node: ModbusNode, value, byteorder, bitlength, expected):
    node = node.evolve(mb_byteorder=byteorder, mb_bit_length=bitlength, dtype=type(value).__name__)

    encoded_value = node.encode_bits(value)
    decoded_value = node.decode_modbus_value(bitarray_to_registers(encoded_value))

    # Allow 0.1% deviation for floats
    if isinstance(value, float):
        assert abs(decoded_value - value) < 1e-4 * value
    # Decoded bytes may be filled with zero bytes
    elif isinstance(value, bytes):
        assert decoded_value.startswith(value)
    else:
        assert decoded_value == value


def test_retry_waiter():
    """Test using Retry Waiter"""

    i = 0
    retry_waiter = RetryWaiter()

    while i <= 2:
        retry_waiter.wait()
        retry_waiter.tried()
        i += 1

    assert retry_waiter.counter == 3
