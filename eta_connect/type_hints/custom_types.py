from __future__ import annotations

import datetime
from os import PathLike
from typing import Literal, Union

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
