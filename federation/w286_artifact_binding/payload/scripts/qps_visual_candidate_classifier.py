#!/usr/bin/env python3
"""Fail-closed W286 four-way classifier.

Accepting states (PASS / INTENTIONAL_VISUAL_CHANGE) are available only for
repository-controlled contract fixtures whose actual candidate bytes are read,
hashed, and compared by this program. External/unbound evidence can only remain
REVIEW_REQUIRED or fail more closed to REGRESSION.
"""
from __future__ import annotations

import argparse
import hashlib
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
RUNTIME_GOLD_923_STATE = "INDEPENDENT_NON_COMPENSATING"
N300_STATE = "UNCHANGED"
PROJECT_GLOBAL_PCA_STATE = "WITHHELD"

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_EVIDENCE_PATH = (
    ROOT / "triage" / "w286" / "QPS_W286_VISUAL_CLASSIFIER_CONTRACT_EVIDENCE_v0.1.json"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _nonnegative_int(value: object, name: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{name} must be an integer")
    require(value >= 0, f"{name} must be >= 0")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_path(relative: object) -> Path:
    require(isinstance(relative, str) and relative, "artifact path must be a nonblank string")
    candidate = (ROOT / relative).resolve()
    root = ROOT.resolve()
    require(candidate.is_relative_to(root), "artifact path escapes repository root")
    require(candidate.is_file(), f"artifact file missing: {relative}")
    return candidate


def _load_contract_evidence() -> dict:
    data = json.loads(CONTRACT_EVIDENCE_PATH.read_text(encoding="utf-8"))
    require(
        data.get("schema") == "qps-w286-classifier-contract-evidence/1.0",
        "unexpected contract evidence schema",
    )
    require(data.get("sample_only") is True, "contract evidence must remain sample_only")
    require(data.get("authority_transfer") is False, "contract evidence authority_transfer must remain false")
    require(data.get("formal_credit_delta") == 0, "contract evidence formal_credit_delta must remain zero")
    require(
        data.get("purpose")
        == "classifier contract fixture only; not visual, engineering, acceptance, or release evidence",
        "contract evidence purpose drift",
    )
    entries = data.get("entries")
    require(isinstance(entries, dict) and entries, "contract evidence entries missing")
    return data


def _load_fixture(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(
        set(data) == {"fixture_id", "schema", "shape", "surface"},
        "fixture top-level fields outside closed-world contract",
    )
    require(
        data.get("schema") == "qps-w286-classifier-contract-fixture/1.0",
        "unexpected contract fixture schema",
    )
    require(
        data.get("surface") == "contract_fixture_not_visual_authority",
        "fixture attempted visual-authority promotion",
    )
    shape = data.get("shape")
    require(isinstance(shape, dict), "fixture shape missing")
    require(
        set(shape) == {"index", "fill_rgb", "geometry", "text"},
        "fixture shape fields outside closed-world contract",
    )
    require(isinstance(shape.get("index"), int), "fixture shape.index invalid")
    require(isinstance(shape.get("fill_rgb"), str) and shape["fill_rgb"], "fixture fill_rgb invalid")
    require(
        isinstance(shape.get("geometry"), list)
        and len(shape["geometry"]) == 4
        and all(isinstance(v, int) for v in shape["geometry"]),
        "fixture geometry invalid",
    )
    require(isinstance(shape.get("text"), str), "fixture text invalid")
    return data


def _fixture_property_changes(baseline: dict, candidate: dict) -> list[str]:
    """Derive observed changes from artifact content, never from caller/catalog claims."""
    require(
        baseline.get("schema") == candidate.get("schema") == "qps-w286-classifier-contract-fixture/1.0",
        "fixture schema drift",
    )
    require(
        baseline.get("fixture_id") == candidate.get("fixture_id") == "CONTRACT_SURFACE_01",
        "fixture identity drift",
    )
    require(
        baseline.get("surface") == candidate.get("surface") == "contract_fixture_not_visual_authority",
        "fixture attempted visual-authority promotion",
    )

    changes: list[str] = []

    before = baseline["shape"]
    after = candidate["shape"]

    if before["index"] != after["index"]:
        changes.append(f"shape.index:{before['index']}->{after['index']}")
    if before["fill_rgb"] != after["fill_rgb"]:
        changes.append(f"shape.fill_rgb:{before['fill_rgb']}->{after['fill_rgb']}")
    if before["geometry"] != after["geometry"]:
        changes.append(
            "shape.geometry:"
            + json.dumps(before["geometry"], separators=(",", ":"))
            + "->"
            + json.dumps(after["geometry"], separators=(",", ":"))
        )
    if before["text"] != after["text"]:
        changes.append(f"shape.text:{before['text']!r}->{after['text']!r}")

    return changes


def _validate_global_guards(data: dict) -> None:
    require(
        data.get("schema") == "qps-w286-visual-candidate-classification-input/3.0",
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
    require(
        data.get("evidence_mode") in {"CONTRACT_REPLAY", "EXTERNAL_UNBOUND"},
        "invalid evidence_mode",
    )


def _classify_contract_replay(data: dict) -> str:
    evidence_id = data.get("evidence_id")
    require(isinstance(evidence_id, str) and evidence_id, "contract replay requires evidence_id")

    contract = _load_contract_evidence()
    entry = contract["entries"].get(evidence_id)
    require(isinstance(entry, dict), "unknown contract evidence_id")

    expected = entry.get("classification")
    require(expected in {"PASS", "INTENTIONAL_VISUAL_CHANGE"}, "contract entry cannot grant this classification")

    baseline_path = _repo_path(entry.get("baseline_artifact_path"))
    candidate_path = _repo_path(entry.get("candidate_artifact_path"))

    baseline_expected_hash = entry.get("baseline_artifact_sha256")
    candidate_expected_hash = entry.get("candidate_artifact_sha256")
    require(
        isinstance(baseline_expected_hash, str) and HEX64.fullmatch(baseline_expected_hash) is not None,
        "invalid baseline artifact sha256",
    )
    require(
        isinstance(candidate_expected_hash, str) and HEX64.fullmatch(candidate_expected_hash) is not None,
        "invalid candidate artifact sha256",
    )

    baseline_actual_hash = _sha256(baseline_path)
    candidate_actual_hash = _sha256(candidate_path)
    require(baseline_actual_hash == baseline_expected_hash, "baseline artifact bytes do not match contract")
    require(candidate_actual_hash == candidate_expected_hash, "candidate artifact bytes do not match contract")

    # Optional caller echo is validation-only; it cannot substitute for hashing actual bytes.
    if "candidate_artifact_sha256" in data:
        require(
            data["candidate_artifact_sha256"] == candidate_actual_hash,
            "submitted candidate hash does not match classified artifact bytes",
        )

    baseline = _load_fixture(baseline_path)
    candidate = _load_fixture(candidate_path)
    observed = _fixture_property_changes(baseline, candidate)

    declared = entry.get("declared_property_changes")
    require(isinstance(declared, list), "declared property changes missing")
    require(all(isinstance(item, str) and item for item in declared), "declared property changes invalid")

    if expected == "PASS":
        require(baseline_actual_hash == candidate_actual_hash, "PASS requires byte-identical contract replay")
        require(not declared, "PASS contract cannot declare property changes")
        require(not observed, "PASS contract observed unexpected property changes")
        return "PASS"

    # INTENTIONAL is proven only by the program's independent artifact diff.
    require(baseline_actual_hash != candidate_actual_hash, "INTENTIONAL requires different candidate bytes")
    require(observed == declared, "observed artifact diff does not match declared intentional change")
    require(
        len(observed) == 1 and observed[0].startswith("shape.fill_rgb:"),
        "INTENTIONAL contract permits exactly one independently observed fill change",
    )
    return "INTENTIONAL_VISUAL_CHANGE"


def _classify_external_unbound(data: dict) -> str:
    """Unbound external evidence is never an accepting state."""
    candidate_hash = data.get("candidate_artifact_sha256")
    require(
        isinstance(candidate_hash, str) and HEX64.fullmatch(candidate_hash) is not None,
        "invalid candidate_artifact_sha256",
    )

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


def classify_candidate(data: dict) -> str:
    _validate_global_guards(data)
    if data["evidence_mode"] == "CONTRACT_REPLAY":
        result = _classify_contract_replay(data)
    else:
        result = _classify_external_unbound(data)
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
