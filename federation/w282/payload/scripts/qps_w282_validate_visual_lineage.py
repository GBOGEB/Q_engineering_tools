#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: mapping required")
    return data


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate(root: Path) -> dict:
    errors: list[str] = []

    current = load_yaml(root / "controls/QPS_VISUAL_LINEAGE_CURRENT_v0.1.yaml")
    w162 = load_yaml(root / "triage/w162/QPS_W162_VISUAL_CONVERGENCE_RUNTIME_CONTROL_v0.1.yaml")
    w188 = load_yaml(root / "triage/w188/QPS_W188_N200_TABLE_READABILITY_DIAGNOSIS_v0.1.yaml")
    w231 = load_yaml(root / "triage/w231/QPS_W231_N300_ATOMIC_SWAP_UNIQUE_STATS_v0.1.yaml")
    qtg = load_yaml(root / "handover/qps_recursive/QTG_CURRENT.yaml")

    # Historical W231 diagnostic is intentionally preserved byte-for-byte even though
    # its sequence/mapping indentation is not accepted by PyYAML. W282 validates only
    # the exact governance markers it consumes instead of rewriting historical evidence.
    d231_path = root / "triage/w231/QPS_W231_TABLE_READABILITY_MSA_DIAGNOSTIC_v0.1.yaml"
    d231_text = d231_path.read_text(encoding="utf-8")

    require(
        current.get("status") == "FROZEN_N300_DIAGNOSTIC_WAIT_GOVERNED_TRIGGER",
        "visual current status drift",
        errors,
    )
    require(
        w162.get("measured_convergence_control", {}).get("validated_N") == [60, 80, 100],
        "W162 convergence lineage missing",
        errors,
    )
    require(
        w188.get("source_checkpoint", {}).get("population", {}).get("N") == 200,
        "W188 N200 checkpoint missing",
        errors,
    )
    require(
        w188.get("child_disposition", {}).get("N200_measurement") == "ACCEPT_MEASURED_CHECKPOINT_EVIDENCE",
        "W188 N200 measurement not accepted",
        errors,
    )
    require(
        w188.get("child_disposition", {}).get("N200_CONTROL_promotion") == "WITHHELD",
        "W188 N200 CONTROL unexpectedly promoted",
        errors,
    )
    require(w231.get("unique_matrix", {}).get("rows") == 300, "W231 N300 matrix missing", errors)
    require(
        w231.get("unique_matrix", {}).get("per_format")
        == {"HTML": 75, "PDF": 75, "PPTX": 75, "XLSX": 75},
        "W231 N300 balance drift",
        errors,
    )
    require(
        w231.get("control_disposition", {}).get("N300_CONTROL") == "WITHHELD_MSA_FIRST_RED",
        "W231 N300 CONTROL unexpectedly promoted",
        errors,
    )
    require(
        abs(float(w231.get("adequacy", {}).get("minimum_MSA", {}).get("value", 0.0)) - 0.4466305167113992)
        < 1e-12,
        "W231 minimum MSA drift",
        errors,
    )

    require(
        "governed_gate_redefinition: NOT_AUTHORIZED_BY_THIS_DIAGNOSTIC" in d231_text,
        "W231 diagnostic governance boundary marker missing",
        errors,
    )
    require(
        "all_format_strata_above_0_50: true" in d231_text,
        "W231 per-format MSA diagnostic marker missing",
        errors,
    )
    require(
        "table_readability_MSA: 0.4466305167113997" in d231_text,
        "W231 pooled diagnostic MSA marker missing",
        errors,
    )
    require(
        "heterogeneous-format pooling / suppression structure" in d231_text,
        "W231 heterogeneous-format diagnostic interpretation missing",
        errors,
    )

    stop_rules = set(qtg.get("stop_rules") or [])
    require(
        "NO_FURTHER_N300_MSA_ITERATION_WITHOUT_GOVERNED_TRIGGER" in stop_rules,
        "QTG N300 stop rule missing",
        errors,
    )
    current_bd = qtg.get("current_bd") or []
    require(
        any(
            row.get("item") == "N300_method_or_population_change"
            and row.get("state") == "STOP_UNTIL_GOVERNED_TRIGGER"
            for row in current_bd
        ),
        "QTG visual BD stop missing",
        errors,
    )

    predicate = current.get("current_visual_predicate", {})
    require(
        predicate.get("state") == "STOP_FROZEN_WAIT_GOVERNED_TRIGGER",
        "current predicate not frozen",
        errors,
    )
    require(
        "REOPEN_N200_COLLECTION_FROM_W162" in (predicate.get("prohibited_stale_restart") or []),
        "stale W162 restart guard missing",
        errors,
    )
    require(
        current.get("non_compensation", {}).get("issue_923") == "RED_OWNER_ACTION",
        "923 guard changed",
        errors,
    )
    require(
        current.get("non_compensation", {}).get("Bradley_Terry")
        == "WITHHELD_NO_OBSERVED_PAIRWISE_OUTCOMES",
        "BT guard changed",
        errors,
    )

    return {
        "schema": "qps.w282.visual_lineage_validation.v1",
        "status": "PASS_VISUAL_LINEAGE_RESTART_CONTROL" if not errors else "FAIL_VISUAL_LINEAGE_RESTART_CONTROL",
        "validated_lineage": ["W162", "W188", "W231"],
        "historical_w231_diagnostic_parse_mode": "IMMUTABLE_TEXT_MARKERS",
        "current_visual_predicate": predicate.get("state"),
        "errors": errors,
        "formal_credit_delta": {
            "engineering": 0,
            "compliance": 0,
            "negotiation": 0,
            "acceptance": 0,
            "release": 0,
        },
        "authority_transfer": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = validate(Path(args.root).resolve())
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
