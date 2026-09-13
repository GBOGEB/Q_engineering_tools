#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls" / "QPS_FEDERATION_EXPANSION_SAMPLE2_CURRENT_v1.json"
CENSUS = ROOT / "triage" / "w168" / "QPS_W168_FEDERATION_SAMPLE2_CENSUS_v0.1.json"
MATRIX = ROOT / "triage" / "w168" / "QPS_W168_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def validate():
    control = load(CONTROL)
    census = load(CENSUS)
    matrix = load(MATRIX)

    require(control["wave"] == "W168", "wave must be W168")
    require(control["namespace_resolution"]["collision"] is True, "W167 collision must be preserved")
    require(control["namespace_resolution"]["resolved_namespace"] == "W168", "namespace resolution drift")
    require(control["sample_surface"]["source_repository"] == "GBOGEB/ABACUS", "source repository drift")
    require(control["sample_surface"]["source_pr"] == 1178, "source PR drift")
    require(control["sample_surface"]["source_head_sha"] == "0af0c834a9fdb6677fb62454096f9cf439b872ab", "source head drift")
    require(control["sample_surface"]["crossfeed_pr"] == 1183, "crossfeed PR drift")

    runtime = control["observed_runtime"]
    require(runtime["runner_id"] != 0, "sample 2 requires an assigned runner")
    require(runtime["steps_gt_zero"] is True, "sample 2 requires >0 steps")
    require(runtime["validator_status"] == "PASS", "validator PASS must be preserved")
    require(runtime["regression_status"] == "FAIL_COLLECTION", "harness collection failure must be preserved")
    require("numpy" in runtime["first_red"].lower(), "first-red dependency evidence missing")

    breadth = control["measurement"]["breadth"]
    require(breadth["repositories"] == {"numerator": 2, "denominator": 2}, "repository breadth drift")
    require(breadth["source_changed_files"] == {"numerator": 8, "denominator": 8}, "file breadth drift")
    require(breadth["observed_runtime_vectors"] == {"numerator": 1, "denominator": 1}, "runtime breadth drift")
    require(breadth["specialist_outputs"] == {"numerator": 6, "denominator": 6}, "specialist breadth drift")
    require(breadth["total"]["numerator"] == 17 and breadth["total"]["denominator"] == 17, "breadth denominator drift")
    b = breadth["total"]["ratio"]

    depth = control["measurement"]["depth"]
    passed = [row for row in depth["layers"] if row["state"] == "PASS"]
    pending = [row for row in depth["layers"] if row["state"] == "PENDING"]
    require(len(passed) == 6 and len(pending) == 2, "depth state count drift")
    require(depth["numerator"] == 6 and depth["denominator"] == 8, "depth denominator drift")
    d = depth["ratio"]
    require(abs(control["measurement"]["pen"] - b * d) < 1e-12, "PEN must equal B*D")
    require(control["measurement"]["pen"] == 0.75, "bounded sample penetration drift")

    require(control["scope_guard"]["global_fleet_denominator"] is None, "global denominator must remain null")
    require(control["scope_guard"]["global_fleet_penetration"] is None, "global penetration must remain null")
    require(control["scope_guard"]["grand_mission_penetration"] is None, "grand mission penetration must remain null")
    require(all(value == 0 for value in control["scope_guard"]["formal_credit_delta"].values()), "formal credit must remain zero")
    require("W165_EDGE_K8S_MEASUREMENT_GATE" in control["preserved_non_compensating_gates"], "W165 gate lost")
    require("W167_VISUAL_N200_RENDER_IDENTITY_HUNT" in control["preserved_non_compensating_gates"], "existing W167 owner lost")

    require(len(census["source"]["changed_files"]) == 8, "census must bind all eight W74 changed files")
    require(census["neuron"]["observed_node_count"] == len(census["historian"]["observed_nodes"]), "node count mismatch")
    require(census["neuron"]["observed_edge_count"] == len(census["historian"]["observed_edges"]), "edge count mismatch")
    require(census["ambassador"]["authority_transfer"] is False, "Ambassador may not transfer authority")
    require(census["ambassador"]["round_trip_complete"] is False, "round trip cannot complete before return")
    require(census["promotion_guard"]["control_eligibility"] is False, "specialist CONTROL promotion is premature")
    require("flowchart" in census["calligrapher"]["mermaid"], "Mermaid rendering missing")
    require("->" in census["calligrapher"]["ascii"], "ASCII rendering missing")

    rows = matrix["rows"]
    require(len(rows) == 2, "cross-surface matrix must start with exactly two observed rows")
    require(rows[0]["accepted_sample"] == 1, "sample 1 acceptance drift")
    require(rows[1]["accepted_sample"] == 0, "sample 2 must remain unaccepted")
    require(matrix["analytics_gate"]["pca_state"] == "WITHHELD_N_LT_3", "PCA must be withheld at n=2")
    require(matrix["analytics_gate"]["bt_state"] == "WITHHELD_NO_OBSERVED_PAIRWISE_OUTCOME_EVIDENCE", "BT must be withheld without outcomes")

    return {
        "schema": "qps-w168-validation-receipt/v1",
        "status": "PASS",
        "wave": "W168",
        "sample_id": census["sample_id"],
        "breadth": b,
        "depth": d,
        "penetration": control["measurement"]["pen"],
        "matrix_rows": len(rows),
        "specialist_control_eligibility": False,
        "next_depth_gates": ["REPAIRED_SOURCE_RUNTIME", "AUTHORITATIVE_RETURN"],
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
