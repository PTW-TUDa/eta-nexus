from __future__ import annotations

import datetime
from collections.abc import Sequence
from os import PathLike
from typing import Literal, TypeVar, Union

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

from eta_connect.nodes.node import Node

# Other custom types:
Path = Union[str, PathLike]
Number = Union[float, int, np.floating, np.signedinteger, np.unsignedinteger]
TimeStep = Union[int, float, datetime.timedelta]

FillMethod = Literal["ffill", "fillna", "bfill", "interpolate", "asfreq"]

PrivateKey = Union[
    dh.DHPrivateKey,
    ed25519.Ed25519PrivateKey,
    ed448.Ed448PrivateKey,
    rsa.RSAPrivateKey,
    dsa.DSAPrivateKey,
    ec.EllipticCurvePrivateKey,
    x25519.X25519PrivateKey,
    x448.X448PrivateKey,
]


# Generic Template for Nodes, N has to be a subclass of Node
N = TypeVar("N", bound=Node)

Nodes = Union[Sequence[N], set[N]]
