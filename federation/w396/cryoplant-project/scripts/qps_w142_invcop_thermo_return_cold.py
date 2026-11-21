#!/usr/bin/env python3
"""W142 executable thermodynamic/invCOP control atoms.

Stdlib-only. The module provides deterministic calculations and fail-closed guards.
It does not promote bidder/source values or SAT acceptance by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Iterable, Optional

R_HE_J_KG_K = 2077.1
DEFAULT_GAMMA = 1.66


@dataclass(frozen=True)
class CompressionPoint:
    mass_flow_kg_s: float
    p1_bar_a: float
    p2_bar_a: float
    t1_K: float
    measured_package_kW: Optional[float] = None

    def validate(self) -> None:
        if self.mass_flow_kg_s <= 0:
            raise ValueError("mass_flow_kg_s must be > 0")
        if self.p1_bar_a <= 0 or self.p2_bar_a <= 0:
            raise ValueError("pressures must be absolute and > 0")
        if self.p2_bar_a <= self.p1_bar_a:
            raise ValueError("compression requires p2 > p1")
        if self.t1_K <= 0:
            raise ValueError("t1_K must be > 0")
        if self.measured_package_kW is not None and self.measured_package_kW <= 0:
            raise ValueError("measured_package_kW must be > 0 when supplied")


def ideal_isothermal_kW(point: CompressionPoint, gas_R: float = R_HE_J_KG_K) -> float:
    point.validate()
    return point.mass_flow_kg_s * gas_R * point.t1_K * log(point.p2_bar_a / point.p1_bar_a) / 1000.0


def ideal_isentropic_kW(
    point: CompressionPoint,
    gamma: float = DEFAULT_GAMMA,
    gas_R: float = R_HE_J_KG_K,
) -> float:
    point.validate()
    if gamma <= 1.0:
        raise ValueError("gamma must be > 1")
    cp = gamma * gas_R / (gamma - 1.0)
    pressure_ratio = point.p2_bar_a / point.p1_bar_a
    return (
        point.mass_flow_kg_s
        * cp
        * point.t1_K
        * (pressure_ratio ** ((gamma - 1.0) / gamma) - 1.0)
        / 1000.0
    )


def package_efficiency(ideal_kW: float, package_kW: float) -> float:
    if ideal_kW < 0 or package_kW <= 0:
        raise ValueError("invalid power values")
    return ideal_kW / package_kW


def electrical_residual_kW(package_kW: float, modeled_compression_kW: float) -> float:
    if package_kW < 0 or modeled_compression_kW < 0:
        raise ValueError("power values must be >= 0")
    return package_kW - modeled_compression_kW


def invcop(numerator_kW: float, q_4p5K_eq_kW: float) -> float:
    if numerator_kW < 0:
        raise ValueError("numerator must be >= 0")
    if q_4p5K_eq_kW <= 0:
        raise ValueError("q_4p5K_eq_kW must be > 0")
    return numerator_kW / q_4p5K_eq_kW


def user_heat_kW(mass_flow_kg_s: float, h_supply_kJ_kg: float, h_return_kJ_kg: float) -> float:
    if mass_flow_kg_s < 0:
        raise ValueError("mass flow must be >= 0")
    return mass_flow_kg_s * (h_return_kJ_kg - h_supply_kJ_kg)


def duplicate_credit_check(physical_effect_keys: Iterable[str]) -> bool:
    keys = [k.strip() for k in physical_effect_keys]
    if any(not k for k in keys):
        raise ValueError("credit keys must be non-empty")
    return len(keys) == len(set(keys))


def reconcile_total(known_terms_kW: Iterable[float], total_kW: Optional[float]) -> dict:
    known = list(known_terms_kW)
    if any(v < 0 for v in known):
        raise ValueError("known terms must be >= 0")
    subtotal = sum(known)
    if total_kW is None:
        return {"known_subtotal_kW": subtotal, "residual_kW": None, "state": "DEFER_TOTAL_UNBOUND"}
    if total_kW < subtotal:
        return {
            "known_subtotal_kW": subtotal,
            "residual_kW": total_kW - subtotal,
            "state": "RED_TOTAL_BELOW_KNOWN_SUBTOTAL",
        }
    return {
        "known_subtotal_kW": subtotal,
        "residual_kW": total_kW - subtotal,
        "state": "BOUNDED_RESIDUAL_NOT_BASELOAD_UNLESS_CLASSIFIED",
    }


def self_check() -> None:
    # Current W135/W136 LKT source-corrected direct refrigerator subtotal.
    direct = reconcile_total([814.0, 83.0, 5.0, 3.0, 3.0, 0.0], None)
    assert abs(direct["known_subtotal_kW"] - 908.0) < 1e-12

    # Reproduce current bidder boundary arithmetic without turning it into owner E3.
    cws_kW = 0.10 * (733.0 + 75.0)
    pre_u = 908.0 + cws_kW
    with_u = pre_u * 1.05
    assert abs(cws_kW - 80.8) < 1e-12
    assert abs(pre_u - 988.8) < 1e-12
    assert abs(with_u - 1038.24) < 1e-12
    assert abs(invcop(1038.0, 3.35) - 309.8507462686567) < 1e-9

    # Compression diagnostics must be positive and isentropic > isothermal for this ideal-gas comparison.
    hp = CompressionPoint(0.326, 1.05, 14.0, 300.0, measured_package_kW=814.0)
    w_iso = ideal_isothermal_kW(hp)
    w_is = ideal_isentropic_kW(hp)
    assert w_iso > 0.0
    assert w_is > w_iso
    assert 0.0 < package_efficiency(w_iso, hp.measured_package_kW) < 1.0

    # Return-cold rule: the same physical exported load cannot appear twice.
    assert duplicate_credit_check(["QCELL_NET_A_TO_B_REFRIGERATION"])
    assert not duplicate_credit_check([
        "QCELL_NET_A_TO_B_REFRIGERATION",
        "QCELL_NET_A_TO_B_REFRIGERATION",
    ])


if __name__ == "__main__":
    self_check()
    print("W142 INVCOP THERMO/RETURN-COLD CONTROL: PASS")
    print("LKT direct refrigerator subtotal reproduced: 908.0 kW")
    print("LKT modeled CWS term reproduced: 80.8 kW")
    print("LKT pre-uncertainty bidder invCOP power reproduced: 988.8 kW")
    print("LKT +5% bidder power uncertainty reproduced: 1038.24 kW")
    print("Owner E3 remains a separate meter-bound acceptance question")
    print("Baseload inference remains DEFER until same-boundary multistate or direct auxiliary evidence exists")
    print("Returned cold may reduce internal work but must not be credited again as a second exported refrigeration load")
