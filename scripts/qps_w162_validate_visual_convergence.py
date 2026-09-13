#!/usr/bin/env python3
"""Validate the W162 visual N60/N80/N100 convergence binding.

This validator proves that the W162 control receipt is a lossless projection of the
frozen N100 generation evidence and that no resampling result is miscredited toward
N200. It creates visual-QA measurement evidence only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import yaml

EXPECTED_NS = (60, 80, 100)
FORMATS = ("HTML", "PDF", "PPTX", "XLSX")


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping")
    return data


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected object")
    return data


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def close(a, b, tol=1e-12) -> bool:
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def read_csv_rows(path: Path) -> dict[int, dict[str, str]]:
    rows = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows[int(row["N"])] = row
    return rows


def validate(root: Path, receipt_path: str, generation_path: str, csv_path: str, plan_path: str) -> dict:
    errors: list[str] = []
    receipt = load_yaml(root / receipt_path)
    generation = load_json(root / generation_path)
    plan = load_yaml(root / plan_path)
    csv_rows = read_csv_rows(root / csv_path)

    require(receipt.get("schema") == "qps-w162-visual-n200-census/0.2", "wrong receipt schema", errors)
    require(receipt.get("authority") == "VISUAL_QA_MEASUREMENT_ONLY", "wrong authority", errors)
    require(receipt.get("wave") == "W162", "wrong wave", errors)

    gen_conv = {int(row["N"]): row for row in generation.get("convergence", [])}
    require(tuple(sorted(gen_conv)) == EXPECTED_NS, f"generation convergence Ns != {EXPECTED_NS}", errors)
    require(tuple(sorted(csv_rows)) == EXPECTED_NS, f"CSV convergence Ns != {EXPECTED_NS}", errors)

    expected_csv_sha = generation.get("outputs_sha256", {}).get("QPS_VISUAL_PCA_BALANCED_SAMPLE_CONVERGENCE.csv")
    actual_csv_sha = sha256(root / csv_path)
    require(actual_csv_sha == expected_csv_sha, "convergence CSV sha256 differs from frozen generation receipt", errors)

    bound = receipt.get("incremental_N_convergence", {})
    key_map = {
        "KMO_median": ("KMO", "median"),
        "KMO_p05": ("KMO", "p05"),
        "KMO_p95": ("KMO", "p95"),
        "PC1_pct_median": ("PC1_explained_pct", "median"),
        "PC1_pct_p05": ("PC1_explained_pct", "p05"),
        "PC1_pct_p95": ("PC1_explained_pct", "p95"),
        "PC1_congruence_to_N100_median": ("PC1_loading_congruence_to_N100", "median"),
        "PC1_congruence_p05": ("PC1_loading_congruence_to_N100", "p05"),
        "PC2_eigen_median": ("PC2_eigen_median", None),
        "PA95_PC2_threshold": ("PA95_PC2_threshold", None),
        "PC2_retention_fraction": ("PC2_retention_fraction", None),
        "BT_spearman_to_N100_median": ("visual_reverse_pressure_spearman_to_N100", "median"),
        "BT_spearman_p05": ("visual_reverse_pressure_spearman_to_N100", "p05"),
    }

    for n in EXPECTED_NS:
        label = f"N{n}"
        b = bound.get(label, {})
        g = gen_conv[n]
        c = csv_rows[n]
        require(int(b.get("artifact_N", -1)) == n, f"{label}: artifact_N mismatch", errors)
        require(int(b.get("per_format", -1)) == int(g["per_format"]), f"{label}: per_format mismatch", errors)
        require(int(b.get("repetitions", -1)) == int(g["reps"]), f"{label}: repetitions mismatch", errors)
        for source_key, (receipt_key, child_key) in key_map.items():
            target = b.get(receipt_key)
            if child_key is not None:
                target = (target or {}).get(child_key)
            require(target is not None, f"{label}: missing {receipt_key}/{child_key}", errors)
            if target is not None:
                require(close(target, g[source_key]), f"{label}: receipt {source_key} differs from generation", errors)
                require(close(target, c[source_key]), f"{label}: receipt {source_key} differs from convergence CSV", errors)

    note = str(bound.get("canonical_metric_note", ""))
    require("VISUAL_REVERSE_PRESSURE" in note, "legacy BT field semantic repair is not bound", errors)
    require("Bradley-Terry" in note, "Bradley-Terry non-fit guard missing", errors)

    n200 = receipt.get("N200_gate", {})
    require(int(n200.get("target_artifact_N", -1)) == 200, "N200 target must be 200", errors)
    require(int(n200.get("current_governed_artifact_N", -1)) == 100, "current governed N must remain 100", errors)
    require(int(n200.get("independently_new_eligible_artifacts_bound_after_N100", -1)) == 0, "new N200 artifacts must remain 0", errors)
    require(int(n200.get("remaining_deficit_total", -1)) == 100, "N200 deficit total must remain 100", errors)
    require(int(n200.get("progress_credit_from_N60_N80_subsampling", -1)) == 0, "subsampling must earn zero N200 credit", errors)
    require(n200.get("state") == "OPEN_UNEARNED_COLLECTION_GATE", "N200 state must remain open/unearned", errors)
    for fmt in FORMATS:
        require(int((n200.get("remaining_deficit_per_format") or {}).get(fmt, -1)) == 25, f"{fmt}: N200 deficit must be 25", errors)

    checkpoint = (plan.get("checkpoints") or {}).get("N200", {})
    require(int(checkpoint.get("per_format", -1)) == 50, "expansion plan N200 per-format target changed", errors)
    require(int(checkpoint.get("added_from_N100_per_format", -1)) == 25, "expansion plan N200 increment changed", errors)

    disposition = receipt.get("analysis_disposition", {})
    require(disposition.get("N60_N80_N100_convergence") == "PASS_MEASURED_WITHIN_N100", "within-N100 convergence disposition missing", errors)
    require(disposition.get("N200") == "NOT_ACHIEVED", "N200 must remain NOT_ACHIEVED", errors)
    require(disposition.get("PCA_recompute") == "NOT_AUTHORIZED_UNTIL_BALANCED_N200_IS_BOUND", "PCA recompute guard missing", errors)
    require(disposition.get("project_global_PCA") == "WITHHELD", "project-global PCA must remain WITHHELD", errors)
    require(disposition.get("Bradley_Terry_fit") == "NOT_PERFORMED", "Bradley-Terry non-fit guard missing", errors)

    formal = disposition.get("formal_credit_delta", {})
    for key in ("engineering", "compliance", "negotiation", "release"):
        require(int(formal.get(key, -1)) == 0, f"formal credit {key} must remain zero", errors)

    return {
        "schema": "qps.w162.visual_convergence_validation_receipt.v1",
        "status": "PASS_W162_VISUAL_CONVERGENCE" if not errors else "FAIL_W162_VISUAL_CONVERGENCE",
        "authority": "VISUAL_QA_MEASUREMENT_ONLY",
        "validated_N": list(EXPECTED_NS),
        "convergence_csv_sha256": actual_csv_sha,
        "N200_independent_new_artifacts": n200.get("independently_new_eligible_artifacts_bound_after_N100"),
        "N200_remaining_deficit_total": n200.get("remaining_deficit_total"),
        "N200_remaining_deficit_per_format": n200.get("remaining_deficit_per_format"),
        "errors": errors,
        "formal_credit_delta": {"engineering": 0, "compliance": 0, "negotiation": 0, "release": 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--receipt", default="triage/w162/QPS_W162_VISUAL_N200_CENSUS_v0.2.yaml")
    parser.add_argument("--generation", default="ocd-adr/40_implementation/QPS_VISUAL_PCA_N100_GENERATION_RECEIPT.json")
    parser.add_argument("--convergence-csv", default="ocd-adr/40_implementation/QPS_VISUAL_PCA_BALANCED_SAMPLE_CONVERGENCE.csv")
    parser.add_argument("--plan", default="ocd-adr/40_implementation/QPS_VISUAL_N400_EXPANSION_PLAN_v0.1.yaml")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = validate(Path(args.root).resolve(), args.receipt, args.generation, args.convergence_csv, args.plan)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
