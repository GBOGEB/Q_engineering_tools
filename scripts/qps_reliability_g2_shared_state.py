#!/usr/bin/env python3
"""Generate COST and reliability projections from one governed G2 state ledger.

This is an integration proof, not a source-data imputation engine. Unknown numeric
fields stay null. The two projections must carry the same exact ledger digest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ocd-adr/40_implementation/QPS_RELIABILITY_SHARED_STATE_LEDGER_G2_v0.1.json"
OUT = ROOT / "artifacts/qps_reliability_g2"

STATE_IDS = ["OP", "COLD_SB", "RUNDOWN"]
REQUIRED = [
    "state_id", "exposure_h", "power_kW", "energy_kWh", "starts",
    "load_fraction", "pressure_ratio", "degraded_state_hours",
    "redundancy_utilisation", "lambda_native_per_h", "p_propagate_to_beam",
    "event_class_NONE_A_B_C", "MTTR_h", "MDT_h", "spare_id", "spare_cost",
    "spare_lead_time_h", "labour_cost", "recovery_energy_cost",
    "helium_or_consumables_cost", "downtime_cost_rate", "evidence_class",
    "source_reference",
]


def canonical_bytes(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(obj: object) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(ledger: dict) -> list[dict]:
    if ledger.get("schema") != "qps.reliability.shared_state_ledger.g2.v0.1":
        raise ValueError("unexpected ledger schema")
    states = ledger.get("states")
    if not isinstance(states, list) or [row.get("state_id") for row in states] != STATE_IDS:
        raise ValueError("state order/identity must be OP, COLD_SB, RUNDOWN")
    for row in states:
        missing = [field for field in REQUIRED if field not in row]
        if missing:
            raise ValueError(f"{row.get('state_id')}: missing fields {missing}")
    if ledger["unknown_policy"].get("prohibit_zero_fill") is not True:
        raise ValueError("zero-imputation guard is not enabled")
    if ledger["unknown_policy"].get("rule") != "UNKNOWN_OR_DEFER_NE_ZERO":
        raise ValueError("unknown-state semantics drifted")
    active = states[0].get("programme_fraction")
    standby = states[1].get("programme_fraction")
    if round(float(active) + float(standby), 9) != 1.0:
        raise ValueError("OP + COLD_SB programme fractions must equal one")
    if states[2].get("programme_fraction") is not None:
        raise ValueError("RUNDOWN is event-driven and must not consume 9/14 programme fraction")
    return states


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    states = validate(ledger)
    ledger_sha = digest(ledger)
    OUT.mkdir(parents=True, exist_ok=True)

    cost_rows = []
    reliability_rows = []
    for row in states:
        cost_rows.append({
            "state_id": row["state_id"],
            "programme_fraction": row.get("programme_fraction"),
            "exposure_h": row["exposure_h"],
            "power_kW": row["power_kW"],
            "energy_kWh": row["energy_kWh"],
            "spare_cost": row["spare_cost"],
            "labour_cost": row["labour_cost"],
            "recovery_energy_cost": row["recovery_energy_cost"],
            "helium_or_consumables_cost": row["helium_or_consumables_cost"],
            "downtime_cost_rate": row["downtime_cost_rate"],
            "energy_expression": "power_kW * exposure_h",
            "corrective_cost_expression": ledger["derived_expressions"]["expected_corrective_cost"],
            "evidence_class": row["evidence_class"],
            "source_reference": row["source_reference"],
        })
        reliability_rows.append({
            "state_id": row["state_id"],
            "programme_fraction": row.get("programme_fraction"),
            "exposure_h": row["exposure_h"],
            "lambda_native_per_h": row["lambda_native_per_h"],
            "p_propagate_to_beam": row["p_propagate_to_beam"],
            "event_class_NONE_A_B_C": row["event_class_NONE_A_B_C"],
            "MTTR_h": row["MTTR_h"],
            "MDT_h": row["MDT_h"],
            "mu_native_expression": ledger["derived_expressions"]["mu_native_state"],
            "lambda_beam_impact_expression": ledger["derived_expressions"]["lambda_beam_impact_per_h"],
            "mu_beam_expression": ledger["derived_expressions"]["mu_beam_state"],
            "evidence_class": row["evidence_class"],
            "source_reference": row["source_reference"],
        })

    cost = {
        "schema": "qps.reliability.g2.cost_projection.v0.1",
        "ledger_sha256": ledger_sha,
        "unknowns_preserved_as_null": True,
        "rows": cost_rows,
    }
    reliability = {
        "schema": "qps.reliability.g2.reliability_projection.v0.1",
        "ledger_sha256": ledger_sha,
        "native_vs_beam_impact_kept_separate": True,
        "rows": reliability_rows,
    }
    write_json(OUT / "cost_projection.json", cost)
    write_json(OUT / "reliability_projection.json", reliability)

    receipt = {
        "schema": "qps.reliability.g2.shared_consumption_receipt.v0.1",
        "ledger_sha256": ledger_sha,
        "cost_projection_sha256": digest(cost),
        "reliability_projection_sha256": digest(reliability),
        "state_ids": STATE_IDS,
        "same_ledger_consumed_by_both_domains": cost["ledger_sha256"] == reliability["ledger_sha256"],
        "unknowns_preserved_as_null": True,
        "programme_fraction_sum": round(
            float(states[0]["programme_fraction"]) + float(states[1]["programme_fraction"]), 9
        ),
        "rundown_event_driven": states[2]["programme_fraction"] is None,
        "G2_candidate": "PASS_EXECUTABLE_SHARED_LEDGER_CONSUMPTION",
        "G2_formal_control": "WITHHELD_UNTIL_CHILD_BINDS_EXECUTED_RECEIPT_AND_DOWNSTREAM_MASTER_CONSUMPTION",
        "G3_G7": "UNCHANGED_OPEN",
        "credit_delta": {
            "engineering": 0,
            "compliance": 0,
            "negotiation": 0,
            "release": 0
        }
    }
    if not receipt["same_ledger_consumed_by_both_domains"]:
        raise ValueError("COST and reliability projections do not share ledger digest")
    if receipt["programme_fraction_sum"] != 1.0:
        raise ValueError("programme fraction sum drift")
    write_json(OUT / "g2_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
