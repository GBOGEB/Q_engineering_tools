#!/usr/bin/env python3
"""Fail-closed validator for W280 Federation Sample #5 candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/QPS_W280_FEDERATION_SAMPLE5_CURRENT_v0.1.json"
MATRIX = ROOT / "triage/w280/QPS_W280_SAMPLE5_FEATURE_MATRIX_CANDIDATE_v0.1.json"
BT = ROOT / "triage/w280/QPS_W280_BT_BRIDGE_LEDGER_v0.1.json"
CENSUS = ROOT / "triage/w280/QPS_W280_FLEET_CENSUS_FRAME_v0.1.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> dict:
    control = load(CONTROL)
    matrix = load(MATRIX)
    bt = load(BT)
    census = load(CENSUS)

    assert control["wave"] == "W280"
    assert control["state"] == "CANDIDATE_NOT_ACCEPTED"
    assert control["source_surface"]["pr"] == 31
    assert control["source_surface"]["merge"] == "7cc101f41a60bce2a858d38d63930612598b6655"
    assert control["source_surface"]["exact_source_blobs"] == {
        "workflow": "be182c723b1bc8a23ec0fe6ccda1743162d9a961",
        "gate": "ad578c9c6e5ac116acbee81a26583312fcd95de9",
        "observations": "fe7cae19965ac123434ba294472ccbb5482cdaba",
    }

    row = matrix["candidate_row"]
    assert row["accepted_sample"] == 0
    assert row["repositories_observed"] == 1
    assert row["artifact_units"] == 3
    assert row["runtime_vectors"] == 6
    assert row["lineage_nodes"] == 8
    assert row["lineage_edges"] == 7
    assert row["runtime_first_red_present"] == 1
    assert len(matrix["accepted_reference_rows"]) == 4
    assert all(r["accepted_sample"] == 1 for r in matrix["accepted_reference_rows"])

    n5 = control["candidate_n5_pca"]
    assert n5["status"] == "SENSITIVITY_ONLY_NOT_ACCEPTED"
    assert abs(n5["explained_variance_ratio"][0] - 0.618903181) < 1e-9
    assert abs(n5["explained_variance_ratio"][1] - 0.307076472) < 1e-9
    assert n5["pc1_loading_congruence_abs_n4_to_n5"] > 0.95
    assert n5["pc2_loading_congruence_abs_n4_to_n5"] < 0.50

    assert len(bt["comparisons"]) == 2
    assert bt["topology"]["node_count"] == 3
    assert bt["topology"]["edge_count"] == 2
    assert bt["topology"]["undirected_components"] == 1
    assert bt["topology"]["directed_strongly_connected"] is False
    assert bt["federation_interpretation"] == "WITHHELD_NO_FINITE_UNREGULARIZED_MLE"
    assert bt["abacus_w80_guard"]["pairwise_events"] == 0
    assert bt["abacus_w80_guard"]["permitted_as_bt_evidence"] is False

    repos = census["repositories"]
    assert census["accessible_repository_universe_total"] == 83
    assert len(repos) == 83
    assert len(set(repos)) == 83
    assert census["denominator_policy"]["global_fleet_penetration"] is None
    assert control["fleet_census"]["governed_surface_denominator"] is None
    assert control["fleet_census"]["global_fleet_penetration"] is None

    assert control["bounded_measurement_candidate"]["depth"]["value"] == 0.875
    assert control["bounded_measurement_candidate"]["penetration_candidate"] == 0.875
    assert "FORMAL_CREDIT_DELTA_ZERO" in control["guards"]

    return {
        "schema": "qps-w280-federation-sample5-validation-receipt/v0.1",
        "wave": "W280",
        "result": "PASS_CANDIDATE_CONTROL_ONLY",
        "sample5_accepted": False,
        "candidate_penetration": 0.875,
        "accepted_reference_samples": 4,
        "candidate_n5_pc1_evr": n5["explained_variance_ratio"][0],
        "candidate_n5_pc2_evr": n5["explained_variance_ratio"][1],
        "candidate_pc1_congruence": n5["pc1_loading_congruence_abs_n4_to_n5"],
        "candidate_pc2_congruence": n5["pc2_loading_congruence_abs_n4_to_n5"],
        "bt_fit": bt["federation_interpretation"],
        "accessible_repository_context_denominator": 83,
        "governed_surface_denominator": None,
        "formal_credit_delta": 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    receipt = validate()
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
