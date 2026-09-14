#!/usr/bin/env python3
"""Fail-closed validator for the QRT-D artifact readiness control.

This validates control semantics only. It does not validate a current COST release,
perform Excel/HTML/PDF parity, or create engineering/release credit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VECTOR = ROOT / "controls" / "QPS_QRT_D_READINESS_VECTOR_v1.yaml"
DEFAULT_PROFILE = ROOT / "controls" / "QPS_QRT_D_CANONICAL_PACK_PROFILE_v1.yaml"

ALLOWED_STATES = {
    "PASS_CONTROLLED",
    "PASS_READINESS_ONLY",
    "HOLD_EXTERNAL_RETURN",
    "HOLD_LOCAL_ACCEPTANCE",
    "BLOCKED_UPSTREAM",
    "NOT_APPLICABLE",
}
AXES = [
    "A1_SOURCE_IDENTITY",
    "A2_AUTHORITY_BOUNDARY",
    "A3_LINEAGE_HASH",
    "A4_SEMANTIC_PARITY",
    "A5_RENDER_ACCEPTANCE",
    "A6_PUBLICATION_RECEIPT",
]
EXPECTED_PRODUCTS = {
    "COST_XLSX": ("QPS_COST", "QPS_COST_Master.xlsx", "NUMERICAL_SSOT"),
    "COST_HTML": ("QPS_COST", "QPS_COST_Master_HTML_CURRENT.html", "READ_ONLY_REVIEW_PROJECTION"),
    "COST_PDF": ("QPS_COST", "MANIFEST_SELECTED_NO_FILENAME_GUESSING", "CONTROLLED_FIXED_REVIEW_PROJECTION"),
    "OCD_ADR_DOCX": ("OCD_ADR_OUTWARD", "QPS_OCD_ADR_review_pack.docx", "REVIEW_PROJECTION"),
    "OCD_ADR_PDF": ("OCD_ADR_OUTWARD", "QPS_OCD_ADR_review_pack.pdf", "FIXED_REVIEW_PROJECTION"),
    "OCD_ADR_XLSX": ("OCD_ADR_OUTWARD", "QPS_OCD_ADR_trace_evidence_review.xlsx", "TRACE_EVIDENCE_NAVIGATION_PROJECTION_NOT_COST_SSOT"),
    "OCD_ADR_PPTX": ("OCD_ADR_OUTWARD", "QPS_OCD_ADR_review_brief.pptx", "DECISION_BRIEF_PROJECTION"),
    "OCD_ADR_HTML": ("OCD_ADR_OUTWARD", "index.html", "STATIC_NAVIGATOR_PROJECTION"),
}


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a mapping")
    return value


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate(vector: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    require(vector.get("schema") == "qps-qrt-d-readiness-vector/v1", "wrong readiness-vector schema", failures)
    require(vector.get("authority") == "CONTROL_DIAGNOSTIC_ONLY", "readiness vector must remain diagnostic only", failures)

    method = vector.get("method", {})
    require(method.get("mip_stage") == "INNOVATE", "MIP stage must be INNOVATE", failures)
    require(method.get("acceptance_authority") is False, "readiness vector must not have acceptance authority", failures)
    require(method.get("pca_eligible") is False, "QRT-D readiness vector must not claim PCA eligibility", failures)
    require(method.get("bt_eligible") is False, "QRT-D readiness vector must not claim BT eligibility", failures)

    guards = vector.get("shared_guards", {})
    require(guards.get("current_first_red") == "G6_ARTIFACT_IDENTITY_01", "current first-red must remain G6_ARTIFACT_IDENTITY_01", failures)
    require(guards.get("G5_topology_execution") == "PASS_EXECUTED_EXACT_PAYLOAD", "G5 topology guard drift", failures)
    require(guards.get("G5_horizontal_promotion") == "PASS_GOVERNED", "G5 horizontal guard drift", failures)
    require(guards.get("actual_numeric_cost_rows_ready") == "0_of_3", "numeric-cost row readiness must remain 0_of_3", failures)
    require(guards.get("actual_numeric_cost_release") == "WITHHELD_SOURCE_VALUES", "numeric COST release must remain source-withheld", failures)
    require(guards.get("source_value_gates") == [974, 981], "source-value gates must remain [974, 981]", failures)
    require(guards.get("unknown_numeric_semantics") == "NULL_NOT_ZERO", "unknown numeric semantics must remain NULL_NOT_ZERO", failures)
    credits = guards.get("formal_credit_delta", {})
    require(all(credits.get(k) == 0 for k in ("engineering", "compliance", "negotiation", "acceptance", "release", "grand_mission")), "formal credit delta must remain zero", failures)

    rows = vector.get("product_rows")
    require(isinstance(rows, list), "product_rows must be a list", failures)
    if not isinstance(rows, list):
        return failures

    row_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            failures.append("every product row must be a mapping")
            continue
        product_id = row.get("product_id")
        if not isinstance(product_id, str):
            failures.append("product row missing product_id")
            continue
        if product_id in row_map:
            failures.append(f"duplicate product_id: {product_id}")
        row_map[product_id] = row
        for axis in AXES:
            require(row.get(axis) in ALLOWED_STATES, f"{product_id}: invalid {axis} state {row.get(axis)!r}", failures)

    require(set(row_map) == set(EXPECTED_PRODUCTS), f"product set mismatch: {sorted(row_map)}", failures)

    for product_id, (family, basename, role) in EXPECTED_PRODUCTS.items():
        row = row_map.get(product_id)
        if not row:
            continue
        require(row.get("family") == family, f"{product_id}: family mismatch", failures)
        require(row.get("basename") == basename, f"{product_id}: basename mismatch", failures)
        require(row.get("role") == role, f"{product_id}: role mismatch", failures)
        require(row.get("A2_AUTHORITY_BOUNDARY") == "PASS_CONTROLLED", f"{product_id}: authority boundary must be controlled", failures)

    cost_rows = [row_map.get(pid) for pid in ("COST_XLSX", "COST_HTML", "COST_PDF")]
    for row in [r for r in cost_rows if r]:
        pid = row["product_id"]
        require(row.get("A1_SOURCE_IDENTITY") == "HOLD_EXTERNAL_RETURN", f"{pid}: identity must remain held before governed v4.2+ return", failures)
        require(row.get("A3_LINEAGE_HASH") == "HOLD_EXTERNAL_RETURN", f"{pid}: lineage hash must remain held before governed return", failures)
        for axis in ("A4_SEMANTIC_PARITY", "A5_RENDER_ACCEPTANCE", "A6_PUBLICATION_RECEIPT"):
            require(row.get(axis) == "BLOCKED_UPSTREAM", f"{pid}: {axis} must remain blocked upstream", failures)
        require(row.get("first_red") == "G6_ARTIFACT_IDENTITY_01", f"{pid}: wrong first-red", failures)

    outward_ids = ("OCD_ADR_DOCX", "OCD_ADR_PDF", "OCD_ADR_XLSX", "OCD_ADR_PPTX", "OCD_ADR_HTML")
    for pid in outward_ids:
        row = row_map.get(pid)
        if not row:
            continue
        require(row.get("A1_SOURCE_IDENTITY") == "PASS_CONTROLLED", f"{pid}: source identity control should be PASS_CONTROLLED", failures)
        require(row.get("A3_LINEAGE_HASH") == "PASS_READINESS_ONLY", f"{pid}: lineage status must be readiness-only", failures)
        require(row.get("A4_SEMANTIC_PARITY") == "PASS_READINESS_ONLY", f"{pid}: semantic QA must remain readiness-only", failures)
        require(row.get("A5_RENDER_ACCEPTANCE") == "HOLD_LOCAL_ACCEPTANCE", f"{pid}: render acceptance must remain local hold", failures)
        require(row.get("A6_PUBLICATION_RECEIPT") == "HOLD_LOCAL_ACCEPTANCE", f"{pid}: publication receipt must remain local hold", failures)

    summary = vector.get("measured_summary", {})
    require(summary.get("total_product_rows") == 8, "summary total_product_rows must be 8", failures)
    require(summary.get("qps_cost_rows") == 3, "summary qps_cost_rows must be 3", failures)
    require(summary.get("ocd_adr_outward_rows") == 5, "summary ocd_adr_outward_rows must be 5", failures)
    require(summary.get("qps_cost_rows_with_current_identity") == 0, "current COST identity count must remain zero", failures)
    require(summary.get("qps_cost_rows_with_semantic_parity_pass") == 0, "current COST parity PASS count must remain zero", failures)
    require(summary.get("ocd_adr_rows_with_repo_side_readiness") == 5, "repo-side outward readiness count must be five", failures)
    require(summary.get("ocd_adr_rows_with_local_visual_acceptance") == 0, "local visual acceptance count must remain zero", failures)
    require(summary.get("dominant_blocker") == "G6_ARTIFACT_IDENTITY_01", "dominant blocker drift", failures)
    require(summary.get("formal_credit_delta") == 0, "summary formal credit delta must remain zero", failures)

    profile_ssot = profile.get("canonical_authority", {}).get("numerical_ssot", {})
    require(profile_ssot.get("artifact") == "QPS_COST_Master.xlsx", "source profile numerical SSOT drift", failures)
    require(profile_ssot.get("authority") == "NUMERICAL_SSOT", "source profile authority drift", failures)
    require(profile_ssot.get("current_identity") == "WITHHELD_GOVERNED_V4_2_RETURN", "source profile current identity must remain withheld", failures)
    profile_source = profile.get("source_state_preserved", {})
    require(profile_source.get("actual_numeric_cost_release") == "WITHHELD_SOURCE_VALUES", "source profile numeric release guard drift", failures)
    require(profile_source.get("source_value_gates") == [974, 981], "source profile source gates drift", failures)
    require(profile_source.get("unknown_numeric_semantics") == "NULL_NOT_ZERO", "source profile null semantics drift", failures)

    next_transition = vector.get("next_transition", {})
    require(next_transition.get("method") == "3PC-QRT-D-02", "next method must be 3PC-QRT-D-02", failures)
    require(next_transition.get("state") == "PREPARED_NOT_ADMITTED", "3PC must remain prepared-not-admitted before current identity", failures)

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vector", type=Path, default=DEFAULT_VECTOR)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    args = parser.parse_args()

    vector = load_yaml(args.vector)
    profile = load_yaml(args.profile)
    failures = validate(vector, profile)
    result = {
        "schema": "qps-qrt-d-readiness-validation/v1",
        "status": "PASS" if not failures else "FAIL",
        "method": "MIP_INNOVATE",
        "next_method": "3PC_QRT_D_02_PREPARED_NOT_ADMITTED",
        "current_first_red": "G6_ARTIFACT_IDENTITY_01",
        "formal_credit_delta": 0,
        "failure_count": len(failures),
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
