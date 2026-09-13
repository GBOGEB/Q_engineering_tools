#!/usr/bin/env python3
"""G5: execute COST / RCM / spares hook consumption from the governed state ledger.

This proves integration topology only. Missing spare, cost, MDT, lead-time or rate evidence
remains null. No energy, reliability, duty or test-vector quantity may be used as a proxy for
missing engineering or commercial source data.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ocd-adr/40_implementation/QPS_RELIABILITY_SHARED_STATE_LEDGER_G2_v0.1.json"
BRIDGE = ROOT / "ocd-adr/40_implementation/QPS_COST_RELIABILITY_BRIDGE_v0.2.yaml"
OUT = ROOT / "artifacts/qps_reliability_g5"

HOOK_FIELDS = [
    "MTTR_h",
    "MDT_h",
    "spare_id",
    "spare_cost",
    "spare_lead_time_h",
    "labour_cost",
    "recovery_energy_cost",
    "helium_or_consumables_cost",
    "downtime_cost_rate",
]
COST_NUMERIC_FIELDS = [
    "spare_cost",
    "labour_cost",
    "recovery_energy_cost",
    "helium_or_consumables_cost",
    "MDT_h",
    "downtime_cost_rate",
]


def digest(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def mu_native(row: dict) -> float | None:
    lam = row.get("lambda_native_per_h")
    exposure = row.get("exposure_h")
    if is_number(lam) and is_number(exposure):
        return float(lam) * float(exposure)
    return None


def corrective_cost(row: dict) -> float | None:
    mu = mu_native(row)
    if mu is None or not all(is_number(row.get(field)) for field in COST_NUMERIC_FIELDS):
        return None
    event_cost = (
        float(row["spare_cost"])
        + float(row["labour_cost"])
        + float(row["recovery_energy_cost"])
        + float(row["helium_or_consumables_cost"])
        + float(row["MDT_h"]) * float(row["downtime_cost_rate"])
    )
    return mu * event_cost


def project_row(row: dict) -> dict:
    missing_hook_fields = [field for field in HOOK_FIELDS if row.get(field) is None]
    result = {
        "state_id": row["state_id"],
        "evidence_class": row["evidence_class"],
        "source_reference": row["source_reference"],
        "lambda_native_per_h": row.get("lambda_native_per_h"),
        "exposure_h": row.get("exposure_h"),
        "mu_native": mu_native(row),
        "MTTR_h": row.get("MTTR_h"),
        "MDT_h": row.get("MDT_h"),
        "spare_id": row.get("spare_id"),
        "spare_cost": row.get("spare_cost"),
        "spare_lead_time_h": row.get("spare_lead_time_h"),
        "labour_cost": row.get("labour_cost"),
        "recovery_energy_cost": row.get("recovery_energy_cost"),
        "helium_or_consumables_cost": row.get("helium_or_consumables_cost"),
        "downtime_cost_rate": row.get("downtime_cost_rate"),
        "expected_corrective_cost": corrective_cost(row),
        "hook_fields_present_in_schema": all(field in row for field in HOOK_FIELDS),
        "missing_source_values": missing_hook_fields,
        "actual_numeric_cost_ready": not missing_hook_fields
        and mu_native(row) is not None
        and all(is_number(row.get(field)) for field in COST_NUMERIC_FIELDS),
        "actual_rcm_spares_release": "WITHHELD_SOURCE_VALUES" if missing_hook_fields else "CANDIDATE_SOURCE_COMPLETE",
        "external_source_gates": [974, 981],
    }
    return result


def assert_close(name: str, observed: float, expected: float) -> None:
    if not math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{name}: {observed!r} != {expected!r}")


def run_non_engineering_test_vectors() -> dict:
    numeric = {
        "state_id": "TEST",
        "lambda_native_per_h": 0.001,
        "exposure_h": 100.0,
        "MTTR_h": 2.0,
        "MDT_h": 4.0,
        "spare_id": "TEST-SPARE",
        "spare_cost": 1000.0,
        "spare_lead_time_h": 48.0,
        "labour_cost": 200.0,
        "recovery_energy_cost": 50.0,
        "helium_or_consumables_cost": 25.0,
        "downtime_cost_rate": 100.0,
        "evidence_class": "NON_ENGINEERING_TEST_VECTOR_ONLY",
        "source_reference": "NONE_TEST_ONLY",
    }
    expected = 0.1 * (1000.0 + 200.0 + 50.0 + 25.0 + 4.0 * 100.0)
    observed = corrective_cost(numeric)
    assert_close("test.expected_corrective_cost", observed, expected)

    no_spare_cost = dict(numeric)
    no_spare_cost["spare_cost"] = None
    if corrective_cost(no_spare_cost) is not None:
        raise ValueError("missing spare cost was inferred instead of preserved as null")

    no_mdt = dict(numeric)
    no_mdt["MDT_h"] = None
    if corrective_cost(no_mdt) is not None:
        raise ValueError("missing MDT was inferred instead of preserved as null")

    no_lambda = dict(numeric)
    no_lambda["lambda_native_per_h"] = None
    if corrective_cost(no_lambda) is not None:
        raise ValueError("missing native rate was inferred instead of preserved as null")

    return {
        "classification": "NON_ENGINEERING_TEST_VECTOR_ONLY",
        "excluded_from_engineering_outputs": True,
        "numeric_formula_expected": expected,
        "numeric_formula_observed": observed,
        "null_spare_cost": "PASS",
        "null_MDT": "PASS",
        "null_native_rate": "PASS",
    }


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if ledger.get("unknown_policy", {}).get("rule") != "UNKNOWN_OR_DEFER_NE_ZERO":
        raise ValueError("unknown policy drifted")
    if ledger.get("unknown_policy", {}).get("prohibit_energy_to_spares_inference") is not True:
        raise ValueError("energy-to-spares inference guard is not enabled")

    rows = [project_row(row) for row in ledger["states"]]
    for source, projected in zip(ledger["states"], rows, strict=True):
        if not projected["hook_fields_present_in_schema"]:
            raise ValueError(f"{projected['state_id']}: G5 hook field missing from governed schema")
        for field in HOOK_FIELDS:
            if source.get(field) is None and projected.get(field) is not None:
                raise ValueError(f"{projected['state_id']}: {field} imputation detected")
        if projected["expected_corrective_cost"] is not None and projected["actual_numeric_cost_ready"] is False:
            raise ValueError(f"{projected['state_id']}: cost emitted without complete source values")

    tests = run_non_engineering_test_vectors()
    ledger_sha = digest(ledger)
    projection = {
        "schema": "qps.reliability.g5.cost_rcm_spares_projection.v0.1",
        "ledger_sha256": ledger_sha,
        "bridge_sha256": file_sha256(BRIDGE),
        "authority": {
            "engineering_rows": "GOVERNED_G2_LEDGER_ONLY",
            "unknown_or_DEFER_NE_zero": True,
            "energy_to_spares_inference": "PROHIBITED",
            "reliability_to_spare_cost_inference": "PROHIBITED",
            "missing_MDT_or_lead_time_imputation": "PROHIBITED",
            "external_spares_source_gates": [974, 981],
            "test_vectors": "NON_ENGINEERING_EXCLUDED",
        },
        "expected_corrective_cost_expression": (
            "mu_native * (spare_cost + labour_cost + recovery_energy_cost + "
            "helium_or_consumables_cost + MDT_h * downtime_cost_rate)"
        ),
        "rows": rows,
        "non_engineering_test_vectors": tests,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cost_rcm_spares_projection.json").write_text(
        json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    receipt = {
        "schema": "qps.reliability.g5.execution_receipt.v0.1",
        "ledger_sha256": ledger_sha,
        "bridge_sha256": projection["bridge_sha256"],
        "projection_sha256": digest(projection),
        "state_ids": [row["state_id"] for row in rows],
        "hook_fields_present_all_states": all(row["hook_fields_present_in_schema"] for row in rows),
        "governed_unknowns_preserved_as_null": True,
        "governed_numeric_cost_rows_ready": sum(1 for row in rows if row["actual_numeric_cost_ready"]),
        "governed_numeric_cost_rows_total": len(rows),
        "source_gates_for_actual_spares_values": [974, 981],
        "no_energy_to_spares_inference": True,
        "no_reliability_to_spare_cost_inference": True,
        "non_engineering_test_vectors": "PASS_EXCLUDED_FROM_ENGINEERING",
        "G5_candidate": "PASS_EXECUTABLE_COST_RCM_SPARES_HOOK_TOPOLOGY",
        "G5_actual_numeric_cost_release": "WITHHELD_SOURCE_VALUES",
        "G5_formal_control": "WITHHELD_UNTIL_CHILD_BINDS_EXECUTED_RECEIPT",
        "next_first_red": "G6_EXCEL_HTML_PDF_PARITY_QA",
        "credit_delta": {"engineering": 0, "compliance": 0, "negotiation": 0, "release": 0},
    }
    (OUT / "g5_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
