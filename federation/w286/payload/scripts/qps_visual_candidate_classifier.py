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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _nonnegative_int(value: object, name: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{name} must be an integer")
    require(value >= 0, f"{name} must be >= 0")
    return value


def validate_common(data: dict) -> None:
    require(data.get("schema") == "qps-w286-visual-candidate-classification-input/1.0", "unexpected schema")
    require(data.get("sample_only") is True, "sample_only must remain true")
    require(data.get("authority_transfer") is False, "authority_transfer must remain false")
    require(data.get("formal_credit_delta") == 0, "formal_credit_delta must remain zero")
    require(data.get("golden_replaced") is False, "golden_replaced must remain false")
    require(data.get("candidate_promoted") is False, "candidate_promoted must remain false")

    for key in ("golden_render_sha256", "candidate_render_sha256"):
        value = data.get(key)
        require(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"invalid {key}")

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
    _nonnegative_int(declared.get("changed_property_count"), "declared_visual_change.changed_property_count")

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

    # Hard defects always dominate uncertainty.
    if semantic > 0 or text > 0 or geometry > 0 or out_of_bounds > 0 or bounds == "FAIL":
        return "REGRESSION"

    golden_hash = data["golden_render_sha256"]
    candidate_hash = data["candidate_render_sha256"]
    render_changed = data["render_changed"]
    declared = data["declared_visual_change"]
    complete = data["evidence_complete"]

    hash_changed = golden_hash != candidate_hash

    # Incomplete or internally inconsistent evidence is never auto-accepted.
    if not complete or bounds == "UNKNOWN" or hash_changed != render_changed:
        return "REVIEW_REQUIRED"

    # Exact replay of the frozen golden.
    if not render_changed:
        if declared["present"] or declared["changed_property_count"] != 0:
            return "REVIEW_REQUIRED"
        return "PASS"

    # Changed pixels with no declared source-bound visual intent require review.
    if not declared["present"] or declared["changed_property_count"] == 0:
        return "REVIEW_REQUIRED"

    # Render changed, declaration exists, semantic/geometry/bounds remained clean.
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
