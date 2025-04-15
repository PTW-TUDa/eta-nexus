from __future__ import annotations

import datetime
from collections.abc import Sequence
from os import PathLike
from typing import Literal, TypeVar

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

# Other custom types:
Path = str | PathLike
Number = float | int | np.floating | np.signedinteger | np.unsignedinteger
TimeStep = int | float | datetime.timedelta

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


# Generic Template for Nodes, N has to be a subclass of Node
N = TypeVar("N", bound=Node)

Nodes = Sequence[N] | set[N]
