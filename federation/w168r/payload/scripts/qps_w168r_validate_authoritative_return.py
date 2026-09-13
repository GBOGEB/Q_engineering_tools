#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETURN = ROOT / "triage" / "w168" / "QPS_W168_FEDERATION_EXPANSION_RUNTIME_CONTROL_v0.1.json"
DELTA = ROOT / "triage" / "w168" / "QPS_W168_SPECIALIST_CONTROL_ELIGIBILITY_DELTA_v0.1.json"
MATRIX = ROOT / "triage" / "w168" / "QPS_W168_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"
REGISTRY = ROOT / "controls" / "QPS_CREW_REGISTRY_CURRENT_v1.json"

SPECIALISTS = {
    "CREW-FED-AMBASSADOR",
    "CREW-FED-GEOGRAPHER",
    "CREW-FED-GEOLOGIST",
    "CREW-FED-CALLIGRAPHER",
    "CREW-FED-NEURON",
    "CREW-H2-HISTORIAN",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def validate():
    ret = load(RETURN)
    delta = load(DELTA)
    matrix = load(MATRIX)
    registry = load(REGISTRY)

    require(ret["wave"] == "W168R", "return wave drift")
    require(ret["parent_wave"] == "W168", "parent wave drift")
    require(ret["sample_id"] == "FED-SAMPLE-002-ABACUS-W74", "sample drift")
    require(ret["source_authority_repair"]["result"] == "PASS", "source repair must pass")
    require(ret["source_authority_repair"]["merge_sha"] == "e53a92490a9ae8b5b67cb75eb7f522f84ccb0188", "source repair merge drift")
    require(ret["mission_control_source"]["native_runtime"]["runner_id"] == 0, "native gate must remain zero-runner")
    require(ret["mission_control_source"]["native_runtime"]["recorded_steps"] == 0, "native gate must remain zero-step")

    fed = ret["federated_exact_executor"]
    require(fed["pr_head_execution"]["result"] == "PASS", "federated PR-head execution not PASS")
    require(fed["postmerge_repeat"]["result"] == "PASS", "federated postmerge repeat not PASS")
    require(fed["pr_head_execution"]["runner_id"] != 0, "PR-head runner missing")
    require(fed["postmerge_repeat"]["runner_id"] != 0, "postmerge runner missing")
    require(len(fed["payload_blobs"]) == 5, "exact payload must bind five blobs")

    m = ret["measurement_final"]
    require(m["breadth"] == {"numerator": 17, "denominator": 17, "value": 1.0}, "breadth drift")
    require(m["depth"]["numerator"] == 8 and m["depth"]["denominator"] == 8 and m["depth"]["value"] == 1.0, "depth drift")
    require(m["penetration"] == m["breadth"]["value"] * m["depth"]["value"] == 1.0, "PEN drift")
    require(m["scope"] == "BOUNDED_W74_W168_SURFACE_ONLY", "scope widened")

    sampling = ret["fleet_sampling"]
    require(sampling["accepted_bounded_samples"] == 2, "sample count drift")
    require(sampling["global_fleet_denominator"] is None, "global fleet denominator must remain null")
    require(sampling["global_fleet_penetration"] is None, "global fleet penetration must remain null")
    require(sampling["grand_mission_penetration"] is None, "grand mission penetration must remain null")

    repeat = ret["specialist_repeat"]
    require(set(repeat["roles"]) == SPECIALISTS, "return specialist set drift")
    require(repeat["CONTROL_eligibility"] is True, "specialist eligibility not activated")
    require(repeat["CONTROL_state"] == "ELIGIBLE_NOT_AUTOMATICALLY_PROMOTED", "eligibility must not imply CONTROL")

    require(len(delta["updates"]) == 6, "eligibility delta must contain six specialists")
    require({row["CREW_ID"] for row in delta["updates"]} == SPECIALISTS, "delta specialist set drift")
    require(all(row["CONTROL_eligibility"] is True for row in delta["updates"]), "delta eligibility incomplete")
    require(all(row["control_state"] == "ELIGIBLE_NOT_AUTOMATICALLY_PROMOTED" for row in delta["updates"]), "delta auto-promoted CONTROL")

    members = {row["CREW_ID"]: row for row in registry["members"]}
    require(SPECIALISTS <= set(members), "specialists missing from canonical registry")
    for crew_id in SPECIALISTS:
        row = members[crew_id]
        require(row["CONTROL_eligibility"] is True, f"{crew_id} registry eligibility false")
        require(row["maturity"] == "MEASURED_DISTINCT_REPEAT_ACCEPTED", f"{crew_id} maturity drift")
        require("W166F_EXACT_REPEAT" in row["runtime_receipts"], f"{crew_id} missing W166 repeat")
        require("W168F_EXACT_REPEAT" in row["runtime_receipts"], f"{crew_id} missing W168 repeat")

    require(len(matrix["rows"]) == 2, "matrix row count drift")
    require(matrix["analytics_gate"]["accepted_row_count"] == 2, "both samples must be accepted")
    require(all(row["accepted_sample"] == 1 for row in matrix["rows"]), "unaccepted row remains")
    require(matrix["rows"][1]["depth_ratio"] == 1.0 and matrix["rows"][1]["penetration"] == 1.0, "sample 2 closure not reflected")
    require(matrix["analytics_gate"]["pca_state"] == "WITHHELD_N_LT_3", "PCA must remain withheld at n=2")
    require(matrix["analytics_gate"]["bt_state"] == "WITHHELD_NO_OBSERVED_PAIRWISE_OUTCOME_EVIDENCE", "BT must remain withheld")

    require(ret["ambassador"]["round_trip_complete"] is True, "Ambassador round trip incomplete")
    require(ret["ambassador"]["authority_transfer"] is False, "authority transfer forbidden")
    require(all(value == 0 for value in ret["formal_credit_delta"].values()), "formal credit must remain zero")
    require("QPS_REPO_LOCAL_RUNNER_923" in ret["preserved_non_compensating_gates"], "#923 gate lost")
    require("W165_EDGE_K8S_MEASUREMENT_GATE" in ret["preserved_non_compensating_gates"], "W165 gate lost")
    require("W167_VISUAL_N200_RENDER_IDENTITY_HUNT" in ret["preserved_non_compensating_gates"], "W167 owner lost")

    return {
        "schema": "qps-w168r-authoritative-return-validation/v1",
        "status": "PASS",
        "sample_id": ret["sample_id"],
        "B": 1.0,
        "D": 1.0,
        "PEN": 1.0,
        "accepted_samples": 2,
        "specialists_control_eligible": 6,
        "specialists_control_promoted": 0,
        "pca": matrix["analytics_gate"]["pca_state"],
        "bt": matrix["analytics_gate"]["bt_state"],
        "native_gate_923_preserved": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
