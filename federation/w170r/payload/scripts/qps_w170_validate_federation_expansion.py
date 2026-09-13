#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/QPS_W170_FEDERATION_SAMPLE3_CURRENT_v1.json"
MATRIX = ROOT / "triage/w170/QPS_W170_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"
PAIRWISE = ROOT / "triage/w170/QPS_W170_PAIRWISE_DISPOSITION_LEDGER_v0.1.json"
RUNTIME = ROOT / "triage/w170/QPS_W170_FEDERATION_EXPANSION_RUNTIME_CONTROL_v0.1.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(cond, msg):
    if not cond:
        raise SystemExit(f"W170R REJECT: {msg}")


def main():
    c, m, p, r = map(load, (CONTROL, MATRIX, PAIRWISE, RUNTIME))
    require(c["wave"] == "W170R", "current control is not authoritative-return state")
    require(c["namespace"]["w169"].startswith("OCCUPIED_"), "W169 collision guard missing")
    require(c["surface"]["source_repo"] == "GBOGEB/CODEX", "source repo mismatch")
    require(c["source_package"]["merge"] == "21374d6b8bfb6ff68ba5a50a9d4391d79556a64d", "source merge mismatch")
    require(c["native_missioncontrol_runtime"]["recorded_steps"] == 0, "native preexecution evidence changed")
    require(c["native_missioncontrol_runtime"]["compensated"] is False, "native gate compensated")
    for vector in (c["federated_exact_proof"]["pr_head"], c["federated_exact_proof"]["postmerge"]):
        require(vector["runner_id"] > 0 and vector["result"] == "PASS", "federated proof missing")
    require(c["measurement"]["breadth"]["value"] == 1.0, "B not complete")
    require(c["measurement"]["depth"]["value"] == 1.0, "D not complete")
    require(c["measurement"]["penetration"] == 1.0, "PEN not complete")
    require(c["global_denominators"]["fleet"] is None, "global denominator fabricated")
    require(all(v == 0 for v in c["formal_credit_delta"].values()), "formal credit changed")

    require(len(m["rows"]) == 3, "matrix row count mismatch")
    require(sum(row["accepted_sample"] for row in m["rows"]) == 3, "accepted sample count mismatch")
    sample3 = next(row for row in m["rows"] if row["sample_id"] == "FED-SAMPLE-003-CODEX-M05")
    require(sample3["depth_ratio"] == 1.0 and sample3["penetration"] == 1.0 and sample3["accepted_sample"] == 1, "sample3 not accepted")
    require(m["analytics_gate"]["pca_state"] == "MEASURED_SMALL_N_ACCEPTED", "PCA not admitted")
    require(m["analytics_gate"]["accepted_row_count"] == 3, "PCA accepted n mismatch")
    require(m["fleet_sampling_guard"]["global_fleet_denominator"] is None, "matrix global denominator fabricated")

    require(len(p["outcomes"]) == 3 and all(x["observed"] for x in p["outcomes"]), "pairwise evidence incomplete")
    require(p["bt_gate"]["connected_comparison_graph"] is False, "BT graph incorrectly connected")
    require(p["bt_gate"]["fit_state"].startswith("WITHHELD_"), "BT admitted prematurely")

    require(r["acceptance"]["accepted_sample"] is True, "runtime control not accepted")
    require(r["pca"]["state"] == "MEASURED_SMALL_N_ACCEPTED", "runtime PCA state mismatch")
    require(r["bt"]["state"].startswith("CAPTURE_ACTIVE_FIT_WITHHELD_"), "runtime BT gate weakened")
    print("W170R PASS: Sample #3 accepted B=D=PEN=1; measured small-n PCA n=3; BT capture active, fit withheld")


if __name__ == "__main__":
    main()
