#!/usr/bin/env python3
"""G4: execute native-QPLANT versus beam-impact separation without imputation.

Authoritative engineering rows come only from the governed G2 state ledger. Unknowns
remain null. Non-engineering test vectors verify the algebra and null propagation but
are explicitly excluded from engineering outputs and credit.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ocd-adr/40_implementation/QPS_RELIABILITY_SHARED_STATE_LEDGER_G2_v0.1.json"
OUT = ROOT / "artifacts/qps_reliability_g4"


def digest(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def project(lambda_native_per_h: Any, exposure_h: Any, p_prop: Any) -> dict:
    native_ready = is_number(lambda_native_per_h) and is_number(exposure_h)
    mu_native = float(lambda_native_per_h) * float(exposure_h) if native_ready else None

    beam_ready = native_ready and is_number(p_prop)
    lambda_beam = float(lambda_native_per_h) * float(p_prop) if beam_ready else None
    mu_beam = mu_native * float(p_prop) if beam_ready else None

    return {
        "lambda_native_per_h": lambda_native_per_h if is_number(lambda_native_per_h) else None,
        "exposure_h": exposure_h if is_number(exposure_h) else None,
        "p_propagate_to_beam": p_prop if is_number(p_prop) else None,
        "mu_native": mu_native,
        "lambda_beam_impact_per_h": lambda_beam,
        "mu_beam_impact": mu_beam,
        "native_ready": native_ready,
        "beam_ready": beam_ready,
        "native_null_reason": None if native_ready else "LAMBDA_NATIVE_OR_EXPOSURE_UNKNOWN",
        "beam_null_reason": None if beam_ready else "NATIVE_EXPECTATION_OR_PROPAGATION_UNKNOWN"
    }


def assert_close(name: str, observed: float, expected: float) -> None:
    if not math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{name}: {observed!r} != {expected!r}")


def run_non_engineering_test_vectors() -> dict:
    # These values are mathematical test vectors only. They are not QPLANT engineering data.
    full = project(0.001, 100.0, 0.2)
    assert_close("test.mu_native", full["mu_native"], 0.1)
    assert_close("test.lambda_beam", full["lambda_beam_impact_per_h"], 0.0002)
    assert_close("test.mu_beam", full["mu_beam_impact"], 0.02)

    native_only = project(0.001, 100.0, None)
    assert_close("test.native_only_mu", native_only["mu_native"], 0.1)
    if native_only["mu_beam_impact"] is not None:
        raise ValueError("unknown p_prop was incorrectly coerced into beam expectation")

    no_native = project(None, 100.0, 0.2)
    if no_native["mu_native"] is not None or no_native["mu_beam_impact"] is not None:
        raise ValueError("unknown native rate was incorrectly coerced to zero")

    return {
        "classification": "NON_ENGINEERING_TEST_VECTOR_ONLY",
        "excluded_from_engineering_outputs": True,
        "full_numeric_vector": full,
        "unknown_propagation_vector": native_only,
        "unknown_native_vector": no_native,
        "tests": "PASS"
    }


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if ledger.get("unknown_policy", {}).get("rule") != "UNKNOWN_OR_DEFER_NE_ZERO":
        raise ValueError("ledger unknown policy drifted")

    rows = []
    for state in ledger["states"]:
        out = project(
            state.get("lambda_native_per_h"),
            state.get("exposure_h"),
            state.get("p_propagate_to_beam"),
        )
        out.update({
            "state_id": state["state_id"],
            "programme_fraction": state.get("programme_fraction"),
            "evidence_class": state["evidence_class"],
            "source_reference": state["source_reference"],
            "authority": "GOVERNED_LEDGER_ROW"
        })
        rows.append(out)

    # Current governed state rows intentionally contain unresolved numerical evidence.
    # Prove that none of those nulls were silently zero-filled.
    for row in rows:
        source = next(s for s in ledger["states"] if s["state_id"] == row["state_id"])
        if source.get("lambda_native_per_h") is None and row["lambda_native_per_h"] is not None:
            raise ValueError(f"{row['state_id']}: lambda native imputation detected")
        if source.get("exposure_h") is None and row["exposure_h"] is not None:
            raise ValueError(f"{row['state_id']}: exposure imputation detected")
        if source.get("p_propagate_to_beam") is None and row["p_propagate_to_beam"] is not None:
            raise ValueError(f"{row['state_id']}: propagation imputation detected")

    test_vectors = run_non_engineering_test_vectors()
    ledger_sha = digest(ledger)
    projection = {
        "schema": "qps.reliability.g4.native_beam_projection.v0.1",
        "ledger_sha256": ledger_sha,
        "authority": {
            "engineering_rows": "GOVERNED_G2_LEDGER_ONLY",
            "test_vectors": "NON_ENGINEERING_EXCLUDED",
            "unknown_or_DEFER_NE_zero": True,
            "beam_clock_NE_native_clock": True,
            "table10_compliance_NE_poisson_overlay": True
        },
        "equations": {
            "mu_native": "lambda_native_per_h * exposure_h",
            "lambda_beam_impact_per_h": "lambda_native_per_h * p_propagate_to_beam",
            "mu_beam_impact": "mu_native * p_propagate_to_beam"
        },
        "rows": rows,
        "non_engineering_test_vectors": test_vectors
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "native_beam_projection.json").write_text(
        json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    receipt = {
        "schema": "qps.reliability.g4.execution_receipt.v0.1",
        "ledger_sha256": ledger_sha,
        "projection_sha256": digest(projection),
        "state_ids": [r["state_id"] for r in rows],
        "governed_rows_zero_imputation_detected": False,
        "governed_rows_unknowns_preserved_as_null": True,
        "native_and_beam_fields_distinct": True,
        "beam_requires_explicit_p_prop": True,
        "non_engineering_test_vectors": "PASS_EXCLUDED_FROM_ENGINEERING",
        "G4_candidate": "PASS_EXECUTABLE_NATIVE_BEAM_SEPARATION",
        "G4_formal_control": "WITHHELD_UNTIL_CHILD_BINDS_EXECUTED_RECEIPT",
        "next_first_red": "G5_COST_RCM_SPARES_HOOKS_CONSUMED",
        "credit_delta": {"engineering": 0, "compliance": 0, "negotiation": 0, "release": 0}
    }
    (OUT / "g4_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
