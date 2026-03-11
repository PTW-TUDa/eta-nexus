"""Utilities for type checking and validation across different connection types."""

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncua import ua

if TYPE_CHECKING:
    from collections.abc import Callable
    from logging import Logger
    from typing import Any

# Mapping from Python types to compatible OPC UA VariantTypes
DTYPE_TO_VARIANT_TYPE: dict[type, tuple[ua.VariantType, ...]] = {
    int: (
        ua.VariantType.Int16,
        ua.VariantType.Int32,
        ua.VariantType.Int64,
        ua.VariantType.UInt16,
        ua.VariantType.UInt32,
        ua.VariantType.UInt64,
        ua.VariantType.Byte,
        ua.VariantType.SByte,
    ),
    float: (ua.VariantType.Float, ua.VariantType.Double),
    str: (ua.VariantType.String,),
    bool: (ua.VariantType.Boolean,),
    bytes: (ua.VariantType.ByteString,),
}


def check_type_mismatch(
    node_dtype: type | Callable[..., Any] | None,
    opcua_variant_type: ua.VariantType,
    node_name: str,
    logger: Logger,
) -> None:
    """Check if the configured dtype matches the OPC UA server's data type and log a warning if not.

    :param node_dtype: The configured dtype of the node.
    :param opcua_variant_type: The actual OPC UA VariantType from the server.
    :param node_name: The name of the node (for logging).
    :param logger: Logger instance to use.
    """
    if node_dtype is None:
        return

    # node_dtype may be a Callable (e.g., int, str) which is also a type
    # We cast to type for the dictionary lookup since the keys are Python types
    expected_variant_types = DTYPE_TO_VARIANT_TYPE.get(node_dtype)  # type: ignore[call-overload]
    if expected_variant_types is None:
        return  # Unknown dtype, skip check

    if opcua_variant_type not in expected_variant_types:
        dtype_name = getattr(node_dtype, "__name__", str(node_dtype))
        logger.warning(
            f"Type mismatch for node '{node_name}': configured dtype is '{dtype_name}', "
            f"but OPC UA server data type is '{opcua_variant_type.name}'. "
            f"The value will be converted, but this may indicate a configuration error."
        )
