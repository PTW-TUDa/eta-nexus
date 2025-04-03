from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

import pandas as pd
from attrs import (
    field,
    validators as vld,
)

from eta_connect.nodes.node import Node
from eta_connect.nodes.node_utils import _lower_str

if TYPE_CHECKING:
    from typing import Any, Final


log = getLogger(__name__)


class EmonioConstants:
    """Dict constants for the Emonio API."""

    #: Mapping of parameters to addresses
    PARAMETER_MAP: Final[dict[int, list[str]]] = {
        0: ["VRMS", "V_RMS", "Voltage", "V", "Spannung"],
        2: ["IRMS", "I_RMS", "Current", "I", "Strom"],
        4: ["WATT", "Power", "W", "Leistung", "Wirkleistung"],
        6: ["VAR", "Reactive Power", "VAR", "Blindleistung"],
        8: ["VA", "Apparent Power", "VA", "Scheinleistung"],
        10: ["FREQ", "Frequency", "Hz", "Frequenz"],
        12: ["KWH", "Energy", "kWh", "Energie"],
        14: ["PF", "Power Factor", "PF", "Leistungsfaktor"],
        20: ["VRMS MIN", "VRMS_MIN", "Voltage Min", "V Min", "Spannung Min"],
        22: ["VRMS MAX", "VRMS_MAX", "Voltage Max", "V Max", "Spannung Max"],
        24: ["IRMS MIN", "IRMS_MIN", "Current Min", "I Min", "Strom Min"],
        26: ["IRMS MAX", "IRMS_MAX", "Current Max", "I Max", "Strom Max"],
        28: ["WATT MIN", "WATT_MIN", "Power Min", "W Min", "Leistung Min"],
        30: ["WATT MAX", "WATT_MAX", "Power Max", "W Max", "Leistung Max"],
        500: ["Temp", "degree", "Temperature", "°C", "Temperatur"],
        800: ["Impulse", "Impuls"],
    }
    #: Create dictionary with all upper cased parameters
    UPPER_CASED: Final[dict[int, list[str]]] = {
        adr: [par.upper() for par in par_list] for (adr, par_list) in PARAMETER_MAP.items()
    }
    #: Mapping of phases to address offsets
    PHASE_MAP: Final[dict[str, int]] = {
        "a": 0,
        "b": 100,
        "c": 200,
        "abc": 300,
    }


class EmonioNode(Node, protocol="emonio"):
    """
    Node for the emonio. The parameter to read is specified by the name of the node.
    Available parameters are defined in the parameter_map class attribute.
    Additionally, the phase of the parameter can be specified, with 'a', 'b', 'c' or 'abc'.

    https://wiki.emonio.de/de/Emonio_P3
    """

    #: Modbus address of the parameter to read
    address: int = field(default=-1, kw_only=True, converter=int)
    #: Phase of the parameter (a, b, c). If not set, all phases are read
    phase: str = field(default="abc", kw_only=True, converter=_lower_str, validator=vld.in_(("a", "b", "c", "abc")))

    def __attrs_post_init__(self) -> None:
        """Ensure that all required parameters are present and valid."""
        super().__attrs_post_init__()

        if self.address == -1:
            address = self._translate_name()
            object.__setattr__(self, "address", address)
        assert self.address != -1

        _parameter = self.address % 100
        _phase = self.address // 100 * 100
        # Validate address
        if self.address in {500, 800}:
            pass
        elif _parameter not in EmonioConstants.PARAMETER_MAP or _phase not in EmonioConstants.PHASE_MAP.values():
            raise ValueError(f"Address {self.address} for node {self.name} is not valid.")
        elif _parameter >= 20 and _parameter <= 30 and _phase == 300:
            raise ValueError("Phase must be set for MIN/MAX values")

    def _translate_name(self) -> int:
        """Translate the name of the node to the correct parameter name.

        :return: Modbus address of the parameter.
        """
        parameter: int | None = None
        phase: int | None = None
        # Try to find matching parameter for the name
        for address in EmonioConstants.UPPER_CASED:
            # e.g. Server1.Voltage -> VOLTAGE
            parameter_str = self.name.split(".")[-1].upper()
            if parameter_str in EmonioConstants.UPPER_CASED[address]:
                parameter = address
                log.debug(f"Parameter {parameter_str} found at address {address}")
                break
        # If no parameter was found, raise an error
        if parameter is None:
            raise ValueError(f"Parameter for node {self.name} not found, name is not valid.")

        # Temperature and Impulse values do not have a phase
        if parameter in (500, 800):
            return parameter

        # Phase is set to 0, 100, 200 or 300. (300 is default)
        phase = EmonioConstants.PHASE_MAP[self.phase]

        # Return correct address (by adding the phase offset to the parameter)
        return parameter + phase

    @classmethod
    def _from_dict(cls, dikt: dict[str, Any]) -> EmonioNode:
        """Create an Emonio node from a dictionary of node information.

        :param dikt: dictionary with node information.
        :return: EmonioNode object.
        """
        name, _, url, _, interval = cls._read_dict_info(dikt)

        phase = dikt.get("phase", "abc")
        phase = "abc" if pd.isna(phase) else phase

        address = dikt.get("address")
        address = -1 if pd.isna(address) else address
        try:
            return cls(name, url, "emonio", interval=interval, phase=phase, address=address)
        except (TypeError, AttributeError) as e:
            raise TypeError(f"Could not convert all types for node {name}.") from e
