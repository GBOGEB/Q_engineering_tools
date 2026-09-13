#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/QPS_W170_FEDERATION_SAMPLE3_CURRENT_v1.json"
MATRIX = ROOT / "triage/w170/QPS_W170_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"
PAIRWISE = ROOT / "triage/w170/QPS_W170_PAIRWISE_DISPOSITION_LEDGER_v0.1.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(cond, msg):
    if not cond:
        raise SystemExit(f"W170 REJECT: {msg}")


def main():
    c = load(CONTROL)
    m = load(MATRIX)
    p = load(PAIRWISE)

    require(c["wave"] == "W170", "wave mismatch")
    require(c["namespace"]["w169"].startswith("OCCUPIED_"), "W169 collision guard missing")
    require(c["namespace"]["w170"] == "FEDERATION_EXPANSION_SAMPLE_3", "W170 namespace mismatch")
    require(c["surface"]["type"] == "SUPPLY_CHAIN_PROVENANCE_ATTESTATION", "surface not distinct")
    require(c["surface"]["source_repo"] == "GBOGEB/CODEX", "source repo mismatch")
    require(c["surface"]["source_control_pr"] == 648 and c["surface"]["source_return_pr"] == 649, "source PR lineage mismatch")

    blobs = c["exact_source_blobs"]
    require(blobs == {
        "workflow": "1ee9b60dad1016731dd3b2c40b7f618b3648f93c",
        "delegate_retain": "b49ecd5ddc9d53f20ac2eed06df5cc28ba9ce955",
        "runtime_control": "6412e44d3edc169afc33cfd4d58f2dab8e0dcb4a",
        "source_owner_return": "9c4dcfbd37117a226cd30185f93984b06042261e",
    }, "source blob identity mismatch")

    for key in ("exact_pinned_pr", "automatic_main_repeat"):
        v = c["observed_runtime"][key]
        require(v["runner_id"] > 0 and v["result"] == "PASS", f"runtime vector {key} not observed PASS")
        require(v["artifact_digest"].startswith("sha256:"), f"runtime vector {key} missing artifact digest")

    b = c["measurement"]["breadth"]
    require((b["numerator"], b["denominator"], b["value"]) == (23, 23, 1.0), "breadth mismatch")
    require(sum(x["numerator"] for x in b["components"].values()) == 23, "breadth component sum mismatch")
    require(sum(x["denominator"] for x in b["components"].values()) == 23, "breadth denominator sum mismatch")
    require(c["measurement"]["depth_candidate"]["numerator"] == 7, "candidate depth numerator mismatch")
    require(c["measurement"]["depth_candidate"]["denominator"] == 8, "candidate depth denominator mismatch")
    require(c["measurement"]["depth_on_activation"]["value"] == 1.0, "activation depth mismatch")
    require(abs(c["measurement"]["penetration_candidate"] - 0.875) < 1e-12, "candidate PEN mismatch")
    require(c["global_denominators"]["fleet"] is None and c["global_denominators"]["grand_mission"] is None, "global denominator fabricated")
    require(all(v == 0 for v in c["formal_credit_delta"].values()), "formal credit changed")

    rows = m["rows"]
    require(len(rows) == 3, "matrix must contain three candidate rows")
    require(sum(r["accepted_sample"] for r in rows) == 2, "pre-return accepted row count must remain 2")
    s3 = next(r for r in rows if r["sample_id"] == "FED-SAMPLE-003-CODEX-M05")
    require(s3["accepted_sample"] == 0 and s3["candidate_on_exact_federated_repeat"] is True, "sample 3 must remain candidate")
    require(m["analytics_gate"]["pca_state"] == "CANDIDATE_COMPUTABLE_WITHHELD_PENDING_SAMPLE3_ACCEPTANCE", "PCA gate weakened")
    require(m["fleet_sampling_guard"]["global_fleet_denominator"] is None, "matrix global denominator fabricated")

    require(len(p["outcomes"]) == 3 and all(x["observed"] for x in p["outcomes"]), "pairwise capture incomplete")
    require(p["bt_gate"]["connected_comparison_graph"] is False, "BT graph incorrectly connected")
    require(p["bt_gate"]["fit_state"].startswith("WITHHELD_"), "BT fit admitted prematurely")

    print("W170 PASS: sample3 candidate bound; B=23/23; D=7/8 candidate; PCA candidate only; BT capture 3 outcomes fit withheld")


if __name__ == "__main__":
    main()
