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
CROSSWALK = ROOT / "triage/w283/QPS_W283_FEDERATION_SAMPLE_ROUTING_CROSSWALK_v0.1.json"
EXPECTED_TOPOLOGY_BLOB = "df0ee845697578cd644691b81eafb2465249d772"
EXPECTED_CROSSWALK_BLOB = "cb3133ec98adb2cdf096376fe5b00ccc606172d1"


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


def validate(candidate_override: dict[str, object] | None = None) -> dict[str, object]:
    candidate = candidate_override if candidate_override is not None else json.loads(DEPTH.read_text(encoding="utf-8"))
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

    crosswalk_bytes = CROSSWALK.read_bytes()
    observed_crosswalk_blob = git_blob_sha(crosswalk_bytes)
    if observed_crosswalk_blob != EXPECTED_CROSSWALK_BLOB:
        raise AssertionError(
            f"crosswalk blob mismatch: {observed_crosswalk_blob} != {EXPECTED_CROSSWALK_BLOB}"
        )
    crosswalk = json.loads(crosswalk_bytes.decode("utf-8"))
    accepted_by_id = {row["sample_id"]: row for row in crosswalk["accepted_samples"]}
    bindings = candidate["evidence_bindings"]
    if set(bindings) != set(accepted_by_id):
        raise AssertionError("evidence binding keys differ from exact accepted crosswalk")

    for sample_id, accepted in accepted_by_id.items():
        binding = bindings[sample_id]
        expected = accepted["evidence"]
        if binding["path"] != expected["path"] or binding["blob"] != expected["blob"]:
            raise AssertionError(f"{sample_id} binding differs from exact crosswalk")
        evidence_path = ROOT / binding["path"]
        if not evidence_path.is_file():
            raise AssertionError(f"{sample_id} evidence path missing: {binding['path']}")
        observed = git_blob_sha(evidence_path.read_bytes())
        if observed != binding["blob"]:
            raise AssertionError(
                f"{sample_id} evidence blob mismatch: {observed} != {binding['blob']}"
            )

    covered = candidate["covered_functions"]
    if len(covered) != 4:
        raise AssertionError(f"expected exactly four covered-function entries, got {len(covered)}")
    covered_name_list = [entry["function"] for entry in covered]
    if len(set(covered_name_list)) != len(covered_name_list):
        raise AssertionError("duplicate covered-function entries are prohibited")
    covered_names = set(covered_name_list)
    uncovered_names = set(candidate["uncovered_functions"])
    if covered_names | uncovered_names != functions:
        raise AssertionError("covered union uncovered does not equal authoritative function set")
    if covered_names & uncovered_names:
        raise AssertionError("covered and uncovered function sets overlap")

    accepted_samples = set(accepted_by_id)
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
                wrong_function = [
                    sample_id
                    for sample_id in atom["evidence"]
                    if accepted_by_id[sample_id]["mapped_function"] != function
                ]
                if wrong_function:
                    raise AssertionError(
                        f"evidence mapped to wrong function on {atom_id}: {sorted(wrong_function)}"
                    )
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
        "crosswalk_blob": observed_crosswalk_blob,
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
