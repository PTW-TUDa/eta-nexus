from __future__ import annotations

import datetime
from collections.abc import Sequence
from os import PathLike
from typing import Literal, SupportsFloat, TypeVar

import numpy as np
from cryptography.hazmat.primitives.asymmetric import (
    dh,
    dsa,
    ec,
    ed448,
    ed25519,
    rsa,
    x448,
    x25519,
)

from eta_nexus.nodes.node import Node

try:
    # For Python 3.11+
    from typing import Self  # type: ignore[attr-defined]
except ImportError:
    # For Python < 3.11, Self is not available, so we import it from typing_extensions
    from typing_extensions import Self

__all__ = [
    "FillMethod",
    "N",
    "N_contra",
    "Nodes",
    "Number",
    "Path",
    "Primitive",
    "PrivateKey",
    "Self",
    "TimeStep",
]


# Other custom types:
Path = str | PathLike
Number = float | int | np.floating | np.signedinteger | np.unsignedinteger
TimeStep = int | float | datetime.timedelta
# str, bool, bytes explicitly defined for clarity, despite being implicitly included in SupportsFloat
Primitive = SupportsFloat | str | bool | bytes

FillMethod = Literal["ffill", "bfill", "interpolate", "asfreq"]

PrivateKey = (
    dh.DHPrivateKey
    | ed25519.Ed25519PrivateKey
    | ed448.Ed448PrivateKey
    | rsa.RSAPrivateKey
    | dsa.DSAPrivateKey
    | ec.EllipticCurvePrivateKey
    | x25519.X25519PrivateKey
    | x448.X448PrivateKey
)


"Generic Template for Nodes, N has to be a subclass of Node"
N = TypeVar("N", bound=Node)

"Contravariancy allows N to be a supertype of Node. This is necessary for mypy in some cases."
N_contra = TypeVar("N_contra", bound=Node, contravariant=True)

Nodes = Sequence[N] | set[N]
