#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
BLOCKED = ("WITHHELD", "TBD", "UNKNOWN", "NOT_BOUND", "PLACEHOLDER")


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def nonplaceholder(value: Any, field: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{field} missing")
    text = value.strip()
    upper = text.upper()
    require(not any(token in upper for token in BLOCKED), f"{field} placeholder rejected")
    return text


def version_tuple(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)*)", value)
    require(match is not None, "release_config_version malformed")
    return tuple(int(part) for part in match.group(1).split("."))


def validate(data: dict[str, Any], *, allow_test_vector: bool = False) -> dict[str, Any]:
    require(data.get("schema") == "qps.g6.release_identity_return.v1", "schema mismatch")
    if not allow_test_vector:
        require(data.get("authority") == "GOVERNED_RELEASE_RETURN", "authority mismatch")
        require(data.get("test_vector") is not True, "test vector cannot earn identity credit")

    release_id = nonplaceholder(data.get("release_id"), "release_id")
    config_version = nonplaceholder(data.get("release_config_version"), "release_config_version")
    require(version_tuple(config_version) >= (4, 2), "release config must be v4.2 or later")

    source_commit = nonplaceholder(data.get("source_commit_sha"), "source_commit_sha")
    manifest_sha = nonplaceholder(data.get("source_manifest_sha256"), "source_manifest_sha256")
    require(HEX40.fullmatch(source_commit) is not None, "source_commit_sha must be 40 lowercase hex")
    require(HEX64.fullmatch(manifest_sha) is not None, "source_manifest_sha256 must be 64 lowercase hex")

    artifacts = data.get("artifacts")
    require(isinstance(artifacts, dict), "artifacts mapping missing")
    require(set(artifacts) == {"Excel", "HTML", "PDF"}, "artifacts must be exactly Excel/HTML/PDF")

    expected = {
        "Excel": ("QPS_COST_Master.xlsx", "NUMERICAL_COST_SSOT_PROJECTION"),
        "HTML": ("QPS_COST_Master_HTML_CURRENT.html", "READ_ONLY_REVIEW_PROJECTION"),
        "PDF": (None, "CONTROLLED_FIXED_NARRATIVE"),
    }
    seen_paths: set[str] = set()
    for kind, (canonical_name, expected_role) in expected.items():
        item = artifacts[kind]
        require(isinstance(item, dict), f"{kind} artifact malformed")
        path = nonplaceholder(item.get("path"), f"{kind}.path")
        sha = nonplaceholder(item.get("sha256"), f"{kind}.sha256")
        role = nonplaceholder(item.get("role"), f"{kind}.role")
        require(HEX64.fullmatch(sha) is not None, f"{kind}.sha256 must be 64 lowercase hex")
        require(role == expected_role, f"{kind}.role mismatch")
        if canonical_name is not None:
            require(Path(path).name == canonical_name, f"{kind} canonical filename mismatch")
        else:
            require(Path(path).suffix.lower() == ".pdf", "PDF path must select one manifest-bound PDF")
        require(path not in seen_paths, "artifact paths must be distinct")
        seen_paths.add(path)

    guards = data.get("authority_guards")
    require(isinstance(guards, dict), "authority_guards missing")
    require(guards.get("actual_numeric_cost_release") == "WITHHELD_SOURCE_VALUES", "numeric release guard drift")
    require(guards.get("source_gates_for_actual_spares_values") == [974, 981], "source gate drift")
    require(guards.get("unknown_numeric_semantics") == "NULL_NOT_ZERO", "null semantics drift")
    require(guards.get("topology_execution_status") == "PASS_EXECUTED_EXACT_PAYLOAD", "topology status drift")
    require(guards.get("horizontal_promotion_status") == "PASS_GOVERNED", "G5 promotion status drift")

    return {
        "schema": "qps.g6.release_identity_validation.v1",
        "release_id": release_id,
        "release_config_version": config_version,
        "source_commit_sha": source_commit,
        "source_manifest_sha256": manifest_sha,
        "artifact_sha256": {key: artifacts[key]["sha256"] for key in ("Excel", "HTML", "PDF")},
        "artifact_identity_gate": "PASS",
        "parity_execution": "NOT_EARNED_BY_IDENTITY_VALIDATION",
        "numeric_cost_release": "WITHHELD_SOURCE_VALUES",
        "source_gates": [974, 981],
        "status": "PASS_IDENTITY_CONTRACT_ONLY",
    }


def self_test() -> int:
    h40 = "1" * 40
    h64 = "2" * 64
    vector = {
        "schema": "qps.g6.release_identity_return.v1",
        "authority": "NON_ENGINEERING_TEST_VECTOR",
        "test_vector": True,
        "release_id": "TEST-v4.2",
        "release_config_version": "v4.2",
        "source_commit_sha": h40,
        "source_manifest_sha256": h64,
        "artifacts": {
            "Excel": {"path": "dist/QPS_COST_Master.xlsx", "sha256": "3" * 64, "role": "NUMERICAL_COST_SSOT_PROJECTION"},
            "HTML": {"path": "dist/QPS_COST_Master_HTML_CURRENT.html", "sha256": "4" * 64, "role": "READ_ONLY_REVIEW_PROJECTION"},
            "PDF": {"path": "dist/manifest_selected.pdf", "sha256": "5" * 64, "role": "CONTROLLED_FIXED_NARRATIVE"},
        },
        "authority_guards": {
            "actual_numeric_cost_release": "WITHHELD_SOURCE_VALUES",
            "source_gates_for_actual_spares_values": [974, 981],
            "unknown_numeric_semantics": "NULL_NOT_ZERO",
            "topology_execution_status": "PASS_EXECUTED_EXACT_PAYLOAD",
            "horizontal_promotion_status": "PASS_GOVERNED",
        },
    }
    validate(vector, allow_test_vector=True)
    broken = json.loads(json.dumps(vector))
    broken["artifacts"]["Excel"]["sha256"] = "WITHHELD"
    try:
        validate(broken, allow_test_vector=True)
    except SystemExit:
        pass
    else:
        fail("negative placeholder test did not fail closed")
    print(json.dumps({
        "schema": "qps.g6.release_identity_validator_selftest.v1",
        "positive_vector": "PASS",
        "placeholder_rejection": "PASS",
        "engineering_credit": 0,
        "release_credit": 0,
        "status": "PASS_CONTRACT_SELF_TEST_NON_ENGINEERING",
    }, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("identity", nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    require(args.identity is not None, "identity JSON path required")
    data = json.loads(Path(args.identity).read_text(encoding="utf-8"))
    print(json.dumps(validate(data), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
