#!/usr/bin/env python3
"""Fail-closed validator for W285 federation function-depth measurement."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPTH = ROOT / "triage/w285/QPS_W285_FEDERATION_FUNCTION_DEPTH_v0.1.json"
TOPOLOGY = ROOT / "triage/w283/upstream/QPS_REPO_FUNCTION_TOPOLOGY_v1.yaml"
EXPECTED_TOPOLOGY_BLOB = "df0ee845697578cd644691b81eafb2465249d772"


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def extract_functions_and_current_use(text: str) -> tuple[set[str], dict[str, list[str]]]:
    functions: set[str] = set()
    current_use: dict[str, list[str]] = {}
    active_function: str | None = None
    in_current_use = False

    for raw in text.splitlines():
        if raw.startswith("  - repo:"):
            active_function = None
            in_current_use = False
            continue
        if raw.startswith("    function:"):
            active_function = raw.split(":", 1)[1].strip()
            if active_function != "NONE":
                functions.add(active_function)
                current_use.setdefault(active_function, [])
            in_current_use = False
            continue
        if raw == "    current_use:":
            in_current_use = active_function is not None
            continue
        if in_current_use and raw.startswith("      - "):
            current_use[active_function].append(raw[8:].strip())
            continue
        if in_current_use and raw.startswith("    ") and not raw.startswith("      "):
            in_current_use = False

    return functions, current_use


def validate() -> dict[str, object]:
    candidate = json.loads(DEPTH.read_text(encoding="utf-8"))
    topology_bytes = TOPOLOGY.read_bytes()
    observed_blob = git_blob_sha(topology_bytes)
    if observed_blob != EXPECTED_TOPOLOGY_BLOB:
        raise AssertionError(
            f"topology blob mismatch: {observed_blob} != {EXPECTED_TOPOLOGY_BLOB}"
        )

    functions, current_use = extract_functions_and_current_use(
        topology_bytes.decode("utf-8")
    )
    if len(functions) != 12:
        raise AssertionError(f"expected 12 authoritative functions, got {len(functions)}")

    covered = candidate["covered_functions"]
    covered_names = {entry["function"] for entry in covered}
    uncovered_names = set(candidate["uncovered_functions"])
    if covered_names | uncovered_names != functions:
        raise AssertionError("covered union uncovered does not equal authoritative function set")
    if covered_names & uncovered_names:
        raise AssertionError("covered and uncovered function sets overlap")

    accepted_samples = set(candidate["evidence_bindings"])
    per_function_depths: list[float] = []
    total_credited = 0
    total_atoms = 0
    seen_atom_ids: set[str] = set()

    for entry in covered:
        function = entry["function"]
        atoms = entry["atoms"]
        topology_atoms = current_use.get(function, [])
        candidate_atoms = [atom["text"] for atom in atoms]
        if candidate_atoms != topology_atoms:
            raise AssertionError(
                f"{function} current_use denominator differs from exact topology"
            )

        for atom in atoms:
            atom_id = atom["id"]
            if atom_id in seen_atom_ids:
                raise AssertionError(f"duplicate atom id: {atom_id}")
            seen_atom_ids.add(atom_id)
            if atom["credited"]:
                if not atom["evidence"]:
                    raise AssertionError(f"credited atom lacks evidence: {atom_id}")
                unknown = set(atom["evidence"]) - accepted_samples
                if unknown:
                    raise AssertionError(f"unknown evidence on {atom_id}: {sorted(unknown)}")
            elif atom["evidence"]:
                raise AssertionError(f"uncredited atom has evidence: {atom_id}")

        numerator = sum(1 for atom in atoms if atom["credited"])
        denominator = len(atoms)
        if numerator != entry["numerator"] or denominator != entry["denominator"]:
            raise AssertionError(f"{function} numerator/denominator mismatch")
        depth = numerator / denominator
        if not math.isclose(depth, entry["depth"], rel_tol=0.0, abs_tol=1e-12):
            raise AssertionError(f"{function} depth mismatch")
        per_function_depths.append(depth)
        total_credited += numerator
        total_atoms += denominator

    measured = candidate["measurement"]
    breadth = measured["breadth"]
    expected_breadth = len(covered_names) / len(functions)
    if breadth["numerator"] != 4 or breadth["denominator"] != 12:
        raise AssertionError("breadth numerator/denominator changed")
    if not math.isclose(breadth["value"], expected_breadth, abs_tol=1e-12):
        raise AssertionError("breadth value mismatch")

    pooled = measured["covered_atom_totals"]
    if pooled["credited"] != total_credited or pooled["denominator"] != total_atoms:
        raise AssertionError("pooled atom totals mismatch")
    if not math.isclose(pooled["pooled_ratio"], total_credited / total_atoms, abs_tol=1e-12):
        raise AssertionError("pooled atom ratio mismatch")

    function_depth = sum(per_function_depths) / len(per_function_depths)
    if measured["function_depth"]["aggregation"] != "UNWEIGHTED_MEAN_PER_COVERED_FUNCTION":
        raise AssertionError("unexpected function-depth aggregation")
    if not math.isclose(measured["function_depth"]["value"], function_depth, abs_tol=1e-12):
        raise AssertionError("function depth mismatch")

    pen = expected_breadth * function_depth
    if measured["global_fleet_penetration"]["formula"] != "B*D":
        raise AssertionError("penetration formula mismatch")
    if not math.isclose(measured["global_fleet_penetration"]["value"], pen, abs_tol=1e-12):
        raise AssertionError("global fleet penetration mismatch")

    if candidate["formal_credit_delta"] != {
        "engineering": 0,
        "compliance": 0,
        "negotiation": 0,
        "acceptance": 0,
        "release": 0,
    }:
        raise AssertionError("formal credit must remain zero")
    if candidate["authority_transfer"] is not False:
        raise AssertionError("authority transfer must remain false")

    return {
        "status": "PASS",
        "topology_blob": observed_blob,
        "authoritative_functions": len(functions),
        "covered_functions": len(covered_names),
        "credited_atoms": total_credited,
        "covered_atom_denominator": total_atoms,
        "function_depth": function_depth,
        "breadth": expected_breadth,
        "global_fleet_penetration": pen,
    }


def main() -> int:
    try:
        result = validate()
    except Exception as exc:  # fail closed for CI receipts
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
