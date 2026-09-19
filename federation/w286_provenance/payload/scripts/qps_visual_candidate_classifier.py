#!/usr/bin/env python3
"""Fail-closed four-way classifier for W286 sample-only visual candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
ALLOWED = {
    "PASS",
    "INTENTIONAL_VISUAL_CHANGE",
    "REGRESSION",
    "REVIEW_REQUIRED",
}
RUNTIME_GOLD_923_STATE = "INDEPENDENT_NON_COMPENSATING"
N300_STATE = "UNCHANGED"
PROJECT_GLOBAL_PCA_STATE = "WITHHELD"

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "triage" / "w286" / "QPS_W286_VISUAL_CLASSIFIER_EVIDENCE_CATALOG_v0.1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _nonnegative_int(value: object, name: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{name} must be an integer")
    require(value >= 0, f"{name} must be >= 0")
    return value


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _load_catalog() -> dict:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    require(data.get("schema") == "qps-w286-visual-classifier-evidence-catalog/1.0", "unexpected evidence catalog schema")
    require(data.get("sample_only") is True, "catalog sample_only must remain true")
    require(data.get("authority_transfer") is False, "catalog authority_transfer must remain false")
    require(data.get("formal_credit_delta") == 0, "catalog formal_credit_delta must remain zero")
    entries = data.get("entries")
    require(isinstance(entries, dict) and entries, "catalog entries missing")
    return data


def _validate_global_guards(data: dict) -> None:
    require(data.get("schema") == "qps-w286-visual-candidate-classification-input/2.0", "unexpected schema")
    require(data.get("sample_only") is True, "sample_only must remain true")
    require(data.get("authority_transfer") is False, "authority_transfer must remain false")
    require(data.get("formal_credit_delta") == 0, "formal_credit_delta must remain zero")
    require(data.get("golden_replaced") is False, "golden_replaced must remain false")
    require(data.get("candidate_promoted") is False, "candidate_promoted must remain false")
    require(data.get("runtime_gold_923") == RUNTIME_GOLD_923_STATE, "runtime_gold_923 must remain independent/non-compensating")
    require(data.get("N300_method_population") == N300_STATE, "N300 method/population mutation is prohibited")
    require(data.get("project_global_PCA") == PROJECT_GLOBAL_PCA_STATE, "project/global PCA must remain withheld")
    require(data.get("evidence_mode") in {"GOVERNED_REPLAY", "EXTERNAL_UNBOUND"}, "invalid evidence_mode")


def _validate_unbound(data: dict) -> str:
    """External/unregistered evidence may never auto-PASS or auto-INTENTIONAL."""
    candidate_hash = data.get("candidate_render_sha256")
    require(isinstance(candidate_hash, str) and HEX64.fullmatch(candidate_hash) is not None, "invalid candidate_render_sha256")
    semantic = _nonnegative_int(data.get("semantic_mismatch_count"), "semantic_mismatch_count")
    text = _nonnegative_int(data.get("text_mismatch_count"), "text_mismatch_count")
    geometry = _nonnegative_int(data.get("geometry_mismatch_count"), "geometry_mismatch_count")
    out_of_bounds = _nonnegative_int(data.get("out_of_bounds_shape_count"), "out_of_bounds_shape_count")
    bounds = data.get("bounds_status")
    require(bounds in {"PASS", "FAIL", "UNKNOWN"}, "invalid bounds_status")
    require(isinstance(data.get("evidence_complete"), bool), "evidence_complete must be boolean")

    if semantic > 0 or text > 0 or geometry > 0 or out_of_bounds > 0 or bounds == "FAIL":
        return "REGRESSION"
    return "REVIEW_REQUIRED"


def _yaml_scalars(text: str, key: str) -> list[str]:
    matches = re.findall(rf"^\\s*{re.escape(key)}:\\s*['\"]?([^'\"\\n#]+?)['\"]?\\s*$", text, re.MULTILINE)
    require(matches, f"bound diff receipt missing {key}")
    return [value.strip() for value in matches]


def _yaml_scalar(text: str, key: str) -> str:
    values = _yaml_scalars(text, key)
    require(len(values) == 1, f"bound diff receipt has ambiguous {key}")
    return values[0]


def _verify_entry_against_bound_source(evidence_id: str, entry: dict, source: Path) -> None:
    """Re-derive trusted evidence facts from the exact bound source receipt."""
    if evidence_id == "GOLDEN_REPLAY_A_DARK_EXEC":
        src = json.loads(source.read_text(encoding="utf-8"))
        trusted = src["variants"]["A_dark_exec"]["golden_renders"]["pptx_slide_1"]
        require(entry["candidate_render_sha256"] == trusted, "catalog golden render does not match bound registry")
        require(entry["classification"] == "PASS", "golden registry entry must classify PASS")
        return

    if evidence_id == "INTENTIONAL_DIFF_01":
        text = source.read_text(encoding="utf-8")
        render_hashes = _yaml_scalars(text, "slide_1_render_sha256")
        require(len(render_hashes) == 2, "bound diff receipt must contain baseline and candidate render hashes")
        trusted_hash = render_hashes[1]
        slide = _yaml_scalar(text, "slide")
        shape = _yaml_scalar(text, "shape_index")
        prop = _yaml_scalar(text, "property")
        before = _yaml_scalar(text, "before")
        after = _yaml_scalar(text, "after")
        trusted_change = f"pptx:slide={slide}:shape={shape}:{prop}:{before}->{after}"
        require(entry["candidate_render_sha256"] == trusted_hash, "catalog candidate render does not match bound diff receipt")
        require(entry.get("declared_property_changes") == [trusted_change], "catalog declared change does not match bound diff receipt")
        require(entry.get("observed_property_changes") == [trusted_change], "catalog observed change does not match bound diff receipt")
        require(_yaml_scalar(text, "semantic_geometry_mismatch_count") == "0", "bound diff receipt semantic mismatch is not zero")
        require(_yaml_scalar(text, "fill_diff_count") == "1", "bound diff receipt fill diff count is not one")
        require(_yaml_scalar(text, "pptx_overflow_bounds") == "PASS", "bound diff receipt bounds are not PASS")
        return

    if evidence_id == "REGRESSION_01":
        src = json.loads(source.read_text(encoding="utf-8"))
        require(entry["candidate_render_sha256"] == src["hashes"]["candidate_slide_1_render_sha256"], "catalog regression render does not match bound receipt")
        require(entry.get("geometry_mismatch_count") == src["semantic_geometry"]["geometry_mismatch_count"], "catalog regression geometry count drift")
        require(entry.get("out_of_bounds_shape_count") == src["semantic_geometry"]["out_of_bounds_shape_count"], "catalog regression out-of-bounds count drift")
        require(src.get("pptx_bounds_overflow") == "FAIL_EXPECTED_FOR_REGRESSION", "bound regression receipt no longer proves bounds failure")
        return

    raise ValueError("unsupported governed evidence_id")


def _validate_governed_replay(data: dict) -> str:
    """Classify only from repository-bound evidence; caller cannot supply observed provenance."""
    evidence_id = data.get("evidence_id")
    require(isinstance(evidence_id, str) and evidence_id, "governed replay requires evidence_id")
    catalog = _load_catalog()
    entry = catalog["entries"].get(evidence_id)
    require(isinstance(entry, dict), "unknown governed evidence_id")

    classification = entry.get("classification")
    require(classification in {"PASS", "INTENTIONAL_VISUAL_CHANGE", "REGRESSION"}, "invalid governed classification")

    source_path = entry.get("source_path")
    source_blob = entry.get("source_git_blob_sha1")
    require(isinstance(source_path, str) and source_path, "catalog source_path missing")
    require(isinstance(source_blob, str) and HEX40.fullmatch(source_blob) is not None, "invalid source_git_blob_sha1")
    source = ROOT / source_path
    require(source.is_file(), "catalog source file missing")
    require(_git_blob_sha1(source) == source_blob, "catalog source Git blob mismatch")
    _verify_entry_against_bound_source(evidence_id, entry, source)

    candidate_hash = entry.get("candidate_render_sha256")
    require(isinstance(candidate_hash, str) and HEX64.fullmatch(candidate_hash) is not None, "invalid governed candidate hash")

    if classification == "PASS":
        require(evidence_id == "GOLDEN_REPLAY_A_DARK_EXEC", "PASS is restricted to the registered golden replay")
        require(entry.get("bounds_status") == "PASS", "golden replay bounds must PASS")
        require(entry.get("semantic_mismatch_count") == 0, "golden replay semantic mismatch")
        require(entry.get("text_mismatch_count") == 0, "golden replay text mismatch")
        require(entry.get("geometry_mismatch_count") == 0, "golden replay geometry mismatch")
        require(entry.get("out_of_bounds_shape_count") == 0, "golden replay out-of-bounds mismatch")
        return "PASS"

    if classification == "INTENTIONAL_VISUAL_CHANGE":
        declared = entry.get("declared_property_changes")
        observed = entry.get("observed_property_changes")
        require(isinstance(declared, list) and declared, "intentional replay declared changes missing")
        require(isinstance(observed, list) and observed, "intentional replay observed changes missing")
        require(declared == observed, "governed declared/observed property changes diverge")
        require(entry.get("bounds_status") == "PASS", "intentional replay bounds must PASS")
        require(entry.get("semantic_mismatch_count") == 0, "intentional replay semantic mismatch")
        require(entry.get("text_mismatch_count") == 0, "intentional replay text mismatch")
        require(entry.get("geometry_mismatch_count") == 0, "intentional replay geometry mismatch")
        require(entry.get("out_of_bounds_shape_count") == 0, "intentional replay out-of-bounds mismatch")
        return "INTENTIONAL_VISUAL_CHANGE"

    # A governed hard-defect receipt remains a regression.
    require(
        entry.get("bounds_status") == "FAIL"
        or entry.get("semantic_mismatch_count", 0) > 0
        or entry.get("text_mismatch_count", 0) > 0
        or entry.get("geometry_mismatch_count", 0) > 0
        or entry.get("out_of_bounds_shape_count", 0) > 0,
        "governed regression entry has no hard defect",
    )
    return "REGRESSION"


def classify_candidate(data: dict) -> str:
    _validate_global_guards(data)
    if data["evidence_mode"] == "GOVERNED_REPLAY":
        result = _validate_governed_replay(data)
    else:
        result = _validate_unbound(data)
    require(result in ALLOWED, "classifier emitted invalid state")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    print(classify_candidate(data))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)
