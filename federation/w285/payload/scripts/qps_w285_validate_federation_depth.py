#!/usr/bin/env python3
"""Validate W285 federation function-depth against exact W283 authority bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PAYLOAD = Path(__file__).resolve().parents[1]
DEPTH = PAYLOAD / "upstream/QPS_ROUTING_FUNCTION_SUBSURFACE_DEPTH_v1.json"
TOPOLOGY = REPO_ROOT / "federation/w283r/payload/triage/w283/upstream/QPS_REPO_FUNCTION_TOPOLOGY_v1.yaml"
CROSSWALK = REPO_ROOT / "federation/w283r/payload/triage/w283/QPS_W283_FEDERATION_SAMPLE_ROUTING_CROSSWALK_v0.1.json"

EXPECTED_DEPTH_BLOB = "2bf94393a7516b7f45a1a8a5e4408cfae6bd7659"
EXPECTED_TOPOLOGY_BLOB = "df0ee845697578cd644691b81eafb2465249d772"
EXPECTED_CROSSWALK_BLOB = "cb3133ec98adb2cdf096376fe5b00ccc606172d1"


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def topology_current_use(text: str) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    current_function: str | None = None
    in_current_use = False
    for raw in text.splitlines():
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        if stripped.startswith("function:"):
            value = stripped.split(":", 1)[1].strip()
            current_function = None if value == "NONE" else value
            if current_function:
                out.setdefault(current_function, {"current_use": []})
            in_current_use = False
            continue
        if current_function and indent == 4 and stripped.startswith("current_use:"):
            if stripped == "current_use: []":
                out[current_function]["current_use"] = []
                in_current_use = False
            else:
                in_current_use = True
            continue
        if in_current_use:
            if indent >= 6 and stripped.startswith("- "):
                out[current_function]["current_use"].append(stripped[2:].strip())
                continue
            if stripped and indent <= 4:
                in_current_use = False
    return out


def validate() -> dict:
    depth = load_json(DEPTH)
    cross = load_json(CROSSWALK)

    assert git_blob_sha(DEPTH) == EXPECTED_DEPTH_BLOB
    assert git_blob_sha(TOPOLOGY) == EXPECTED_TOPOLOGY_BLOB
    assert git_blob_sha(CROSSWALK) == EXPECTED_CROSSWALK_BLOB

    assert depth["schema"] == "qps-triage-ultra/routing-function-subsurface-depth/1.0"
    assert depth["wave"] == "W285"
    assert depth["effective_on"] == "MERGE_TO_PIPELINE_AUTOMATION_HUB_MASTER"
    assert depth["authority_transfer"] is False
    assert depth["formal_credit_delta"] == 0

    topo = topology_current_use(TOPOLOGY.read_text(encoding="utf-8"))
    function_rows = {row["function"]: row for row in depth["functions"]}
    assert len(topo) == 12
    assert set(function_rows) == set(topo)

    all_positive_atoms = 0
    for function, info in topo.items():
        source_items = info["current_use"]
        positive = [x for x in source_items if not x.lower().startswith("no current ")]
        negative = [x for x in source_items if x.lower().startswith("no current ")]
        row = function_rows[function]
        atom_source = [x["source_text"] for x in row["subsurfaces"]]
        atom_ids = [x["atom_id"] for x in row["subsurfaces"]]
        assert atom_source == positive
        assert len(atom_ids) == len(set(atom_ids))
        assert all("::" not in atom_id for atom_id in atom_ids)
        if negative:
            assert row.get("excluded_current_use") == negative
        else:
            assert not row.get("excluded_current_use")
        all_positive_atoms += len(positive)

    assert all_positive_atoms == 29

    accepted = {x["sample_id"]: x for x in cross["accepted_samples"]}
    mappings = depth["sample_to_subsurface"]
    assert len(accepted) == 5
    assert len(mappings) == 5
    assert len({x["sample_id"] for x in mappings}) == 5

    observed_atoms: set[str] = set()
    covered_functions: set[str] = set()
    for mapping in mappings:
        sample = accepted[mapping["sample_id"]]
        assert mapping["function"] == sample["mapped_function"]
        row = function_rows[mapping["function"]]
        valid_atoms = {x["atom_id"] for x in row["subsurfaces"]}
        assert mapping["atom_id"] in valid_atoms
        assert mapping["classification"] == "DERIVED_ROUTING_MEASUREMENT"
        observed_atoms.add(f'{mapping["function"]}::{mapping["atom_id"]}')
        covered_functions.add(mapping["function"])

    cross_covered = set(cross["measured_result"]["unique_functions_covered"])
    assert covered_functions == cross_covered
    assert len(covered_functions) == 4
    assert len(observed_atoms) == 5

    covered_denominator = sum(len(function_rows[f]["subsurfaces"]) for f in covered_functions)
    assert covered_denominator == 16

    m = depth["measurement"]
    assert m["all_functions_current_use_atoms"]["numerator"] == 29
    assert m["all_functions_current_use_atoms"]["denominator"] == 29
    assert m["breadth"]["numerator"] == 4
    assert m["breadth"]["denominator"] == 12
    assert abs(m["breadth"]["value"] - (4/12)) < 1e-12
    d = m["depth_conditioned_on_breadth"]
    assert d["method"] == "MACRO_AVERAGE_PER_FUNCTION"
    assert d["breadth_covered_functions"] == 4
    expected_macro = ((2/5) + (1/4) + (1/4) + (1/3)) / 4
    assert abs(d["value"] - expected_macro) < 1e-12
    micro = m["depth_micro_diagnostic"]
    assert micro["method"] == "ATOM_WEIGHTED_DIAGNOSTIC_NOT_USED_IN_PEN"
    assert micro["numerator_unique_covered_atoms"] == 5
    assert micro["denominator_atoms_in_breadth_covered_functions"] == 16
    assert abs(micro["value"] - (5/16)) < 1e-12
    assert abs(m["global_fleet_penetration"]["value"] - ((4/12)*expected_macro)) < 1e-12

    return {
        "schema": "qps-w285-federation-depth-validation/v1",
        "wave": "W285",
        "result": "PASS_EXACT_DEPTH_DENOMINATOR_AND_MEASUREMENT",
        "depth_blob": EXPECTED_DEPTH_BLOB,
        "topology_blob": EXPECTED_TOPOLOGY_BLOB,
        "crosswalk_blob": EXPECTED_CROSSWALK_BLOB,
        "functions": 12,
        "all_current_use_atoms": 29,
        "breadth": 4/12,
        "depth_micro_numerator": 5,
        "depth_micro_denominator": 16,
        "function_depth": ((2/5) + (1/4) + (1/4) + (1/3)) / 4,
        "global_fleet_penetration": (4/12)*(((2/5) + (1/4) + (1/4) + (1/3)) / 4),
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out")
    a = p.parse_args()
    result = validate()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if a.out:
        Path(a.out).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
