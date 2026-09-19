#!/usr/bin/env python3
"""Fail-closed four-way classifier for W286 sample-only visual candidates."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED = {
    "PASS",
    "INTENTIONAL_VISUAL_CHANGE",
    "REGRESSION",
    "REVIEW_REQUIRED",
}
GOVERNED_GOLDEN_RENDER_SHA256 = (
    "efc646210debc1bf11e3027255c389b92e2de13883223ab6ff2f518a852b83c7"
)
RUNTIME_GOLD_923_STATE = "INDEPENDENT_NON_COMPENSATING"
N300_STATE = "UNCHANGED"
PROJECT_GLOBAL_PCA_STATE = "WITHHELD"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _nonnegative_int(value: object, name: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{name} must be an integer")
    require(value >= 0, f"{name} must be >= 0")
    return value


def _change_list(value: object, name: str) -> list[str]:
    require(isinstance(value, list), f"{name} must be a list")
    require(all(isinstance(item, str) and item.strip() for item in value), f"{name} items must be nonblank strings")
    require(len(set(value)) == len(value), f"{name} contains duplicate entries")
    return list(value)


def validate_common(data: dict) -> None:
    require(
        data.get("schema") == "qps-w286-visual-candidate-classification-input/1.1",
        "unexpected schema",
    )
    require(data.get("sample_only") is True, "sample_only must remain true")
    require(data.get("authority_transfer") is False, "authority_transfer must remain false")
    require(data.get("formal_credit_delta") == 0, "formal_credit_delta must remain zero")
    require(data.get("golden_replaced") is False, "golden_replaced must remain false")
    require(data.get("candidate_promoted") is False, "candidate_promoted must remain false")

    require(
        data.get("runtime_gold_923") == RUNTIME_GOLD_923_STATE,
        "runtime_gold_923 must remain independent/non-compensating",
    )
    require(
        data.get("N300_method_population") == N300_STATE,
        "N300 method/population mutation is prohibited",
    )
    require(
        data.get("project_global_PCA") == PROJECT_GLOBAL_PCA_STATE,
        "project/global PCA must remain withheld",
    )

    for key in ("golden_render_sha256", "candidate_render_sha256"):
        value = data.get(key)
        require(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"invalid {key}")

    require(
        data["golden_render_sha256"] == GOVERNED_GOLDEN_RENDER_SHA256,
        "golden_render_sha256 does not match governed A_dark_exec baseline",
    )

    for key in (
        "semantic_mismatch_count",
        "text_mismatch_count",
        "geometry_mismatch_count",
        "out_of_bounds_shape_count",
    ):
        _nonnegative_int(data.get(key), key)

    declared = data.get("declared_visual_change")
    require(isinstance(declared, dict), "declared_visual_change must be an object")
    require(isinstance(declared.get("present"), bool), "declared_visual_change.present must be boolean")
    declared_changes = _change_list(
        declared.get("declared_property_changes"),
        "declared_visual_change.declared_property_changes",
    )
    observed_changes = _change_list(
        declared.get("observed_property_changes"),
        "declared_visual_change.observed_property_changes",
    )
    if declared["present"]:
        require(declared_changes, "declared visual change must name at least one property change")
    else:
        require(not declared_changes, "undeclared visual change cannot contain declared property changes")

    require(data.get("bounds_status") in {"PASS", "FAIL", "UNKNOWN"}, "invalid bounds_status")
    require(isinstance(data.get("render_changed"), bool), "render_changed must be boolean")
    require(isinstance(data.get("evidence_complete"), bool), "evidence_complete must be boolean")


def classify_candidate(data: dict) -> str:
    """Return PASS / INTENTIONAL_VISUAL_CHANGE / REGRESSION / REVIEW_REQUIRED."""
    validate_common(data)

    semantic = data["semantic_mismatch_count"]
    text = data["text_mismatch_count"]
    geometry = data["geometry_mismatch_count"]
    out_of_bounds = data["out_of_bounds_shape_count"]
    bounds = data["bounds_status"]

    # Hard defects always dominate uncertainty or claimed intent.
    if semantic > 0 or text > 0 or geometry > 0 or out_of_bounds > 0 or bounds == "FAIL":
        return "REGRESSION"

    golden_hash = data["golden_render_sha256"]
    candidate_hash = data["candidate_render_sha256"]
    render_changed = data["render_changed"]
    declared = data["declared_visual_change"]
    declared_changes = declared["declared_property_changes"]
    observed_changes = declared["observed_property_changes"]
    complete = data["evidence_complete"]

    hash_changed = golden_hash != candidate_hash

    # Incomplete or internally inconsistent evidence is never auto-accepted.
    if not complete or bounds == "UNKNOWN" or hash_changed != render_changed:
        return "REVIEW_REQUIRED"

    # Exact replay of the governed frozen golden.
    if not render_changed:
        if declared["present"] or declared_changes or observed_changes:
            return "REVIEW_REQUIRED"
        return "PASS"

    # Any changed render without a complete source-bound declaration requires human review.
    if not declared["present"]:
        return "REVIEW_REQUIRED"

    # The classifier compares declared source changes with independently observed property changes.
    # A mismatch is ambiguous and cannot be labelled intentional.
    if declared_changes != observed_changes:
        return "REVIEW_REQUIRED"

    return "INTENTIONAL_VISUAL_CHANGE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = classify_candidate(data)
    require(result in ALLOWED, "classifier emitted invalid state")
    print(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)
