#!/usr/bin/env python3
"""Reproduce governed G3 reliability analytical landmarks from canonical inputs.

Poisson outputs are engineering overlays only. Contractual Table-10 compliance remains
count/exposure based and is not converted into a contractual MTBF requirement.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "ocd-adr/20_canonical/analysis/QPLANT_Reliability_Cost_Model_v2.json"
OUT = ROOT / "artifacts/qps_reliability_g3"
TOL = 1e-12


def canonical_sha(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def poisson_cdf(k_max: int, mu: float) -> float:
    return sum(math.exp(-mu) * (mu**k) / math.factorial(k) for k in range(k_max + 1))


def assert_close(name: str, observed: float, expected: float, tol: float = TOL) -> None:
    if not math.isclose(observed, expected, rel_tol=tol, abs_tol=tol):
        raise ValueError(f"{name}: observed={observed!r} expected={expected!r}")


def main() -> int:
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    mission = model["mission"]
    linac = model["linac"]
    cc = model["cc_provisional"]
    table10 = model["qps_table10"]

    if mission["campaigns"] != 3 or mission["days_each"] != 90:
        raise ValueError("G3 requires the governed 3 x 90-day mission basis")
    if table10["B"] != {"cap": 5, "years": 5}:
        raise ValueError("Table-10 class-B five-year count envelope drifted")

    t90_h = mission["days_each"] * 24.0
    mu_t90 = t90_h / float(linac["reference_mtbf_h"])
    p_le10_t90 = poisson_cdf(int(linac["cap_per_T90"]), mu_t90)

    mu_3t90 = float(mission["campaigns"]) * mu_t90
    cap_3t90 = int(linac["cap_three_T90"])
    p_le30_3t90 = poisson_cdf(cap_3t90, mu_3t90)
    p_all_three_le10 = p_le10_t90 ** int(mission["campaigns"])

    cc_lambda_y = float(cc["lambda_y"])
    b_years = float(table10["B"]["years"])
    b_cap = int(table10["B"]["cap"])
    cc_mu5 = cc_lambda_y * b_years
    cc_p_le5 = poisson_cdf(b_cap, cc_mu5)

    # Reproduce the pre-existing canonical analytical overlay exactly. These
    # comparisons prevent narrative numbers from drifting away from executable math.
    assert_close("linac.mu_T90", mu_t90, float(linac["mu_T90"]))
    assert_close("linac.P_le10_T90", p_le10_t90, float(linac["P_le10_T90"]))
    assert_close("linac.P_le30_3T90", p_le30_3t90, float(linac["P_le30_3T90"]))
    assert_close("linac.P_all_three_le10", p_all_three_le10, float(linac["P_all_three_le10"]))
    assert_close("cc.mu5", cc_mu5, float(cc["mu5"]))
    assert_close("cc.P_le5", cc_p_le5, float(cc["P_le5"]))

    OUT.mkdir(parents=True, exist_ok=True)
    generated = {
        "schema": "qps.reliability.g3.generated_math.v0.1",
        "authority": {
            "table10_contract_semantics": "COUNT_AND_CUMULATIVE_EXPOSURE",
            "poisson_role": "ENGINEERING_OVERLAY_ONLY",
            "poisson_NE_contractual_MTBF": True,
            "provisional_CC_NE_verified_budget_consumption": True
        },
        "mission": {
            "campaigns": int(mission["campaigns"]),
            "days_each": int(mission["days_each"]),
            "T90_hours": t90_h
        },
        "linac_reference_overlay": {
            "reference_mtbf_h": float(linac["reference_mtbf_h"]),
            "mu_T90": mu_t90,
            "P_N_le_10_T90": p_le10_t90,
            "mu_3T90": mu_3t90,
            "P_N_le_30_3T90": p_le30_3t90,
            "P_all_three_campaigns_each_N_le_10": p_all_three_le10
        },
        "qps_five_year_provisional_CC_overlay": {
            "failure_class": "B_PROVISIONAL_NOT_VERIFIED",
            "lambda_y": cc_lambda_y,
            "years": b_years,
            "cap": b_cap,
            "mu_5y": cc_mu5,
            "P_N_le_5_5y": cc_p_le5
        },
        "source_model_sha256": canonical_sha(model)
    }
    generated_path = OUT / "generated_math.json"
    generated_path.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    receipt = {
        "schema": "qps.reliability.g3.execution_receipt.v0.1",
        "source_model_sha256": generated["source_model_sha256"],
        "generated_math_sha256": canonical_sha(generated),
        "canonical_overlay_comparisons": "PASS_6_OF_6",
        "T90_reproduced": True,
        "three_T90_reproduced": True,
        "five_year_reproduced": True,
        "table10_authority_preserved": True,
        "poisson_role": "ENGINEERING_OVERLAY_ONLY",
        "G3_candidate": "PASS_EXECUTABLE_MATH_REPRODUCTION",
        "G3_formal_control": "WITHHELD_UNTIL_CHILD_BINDS_EXECUTED_RECEIPT",
        "next_first_red": "G4_NATIVE_VS_BEAM_IMPACT_SEPARATION_IN_GENERATOR",
        "credit_delta": {"engineering": 0, "compliance": 0, "negotiation": 0, "release": 0}
    }
    (OUT / "g3_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
