import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "qps_w168_validate_federation_expansion.py"
CONTROL = ROOT / "controls" / "QPS_FEDERATION_EXPANSION_SAMPLE2_CURRENT_v1.json"
CENSUS = ROOT / "triage" / "w168" / "QPS_W168_FEDERATION_SAMPLE2_CENSUS_v0.1.json"
MATRIX = ROOT / "triage" / "w168" / "QPS_W168_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_payload_passes():
    run = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, check=True, capture_output=True, text=True)
    receipt = json.loads(run.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["penetration"] == 0.75
    assert receipt["matrix_rows"] == 2


def test_penetration_is_breadth_times_depth():
    control = load(CONTROL)
    b = control["measurement"]["breadth"]["total"]["ratio"]
    d = control["measurement"]["depth"]["ratio"]
    assert control["measurement"]["pen"] == b * d == 0.75


def test_w167_namespace_is_preserved_not_reused():
    control = load(CONTROL)
    ns = control["namespace_resolution"]
    assert ns["collision"] is True
    assert ns["resolved_namespace"] == "W168"
    assert "W167_VISUAL_N200_RENDER_IDENTITY_HUNT" in control["preserved_non_compensating_gates"]


def test_validator_pass_and_harness_fail_are_distinct():
    control = load(CONTROL)
    runtime = control["observed_runtime"]
    assert runtime["validator_status"] == "PASS"
    assert runtime["regression_status"] == "FAIL_COLLECTION"
    census = load(CENSUS)
    nodes = census["historian"]["observed_nodes"]
    assert "W74_VALIDATOR_PASS" in nodes
    assert "W74_PYTEST_COLLECTION_FAIL" in nodes


def test_second_sample_does_not_promote_specialists_early():
    control = load(CONTROL)
    census = load(CENSUS)
    assert control["crew_promotion"]["sample_count"] == 2
    assert control["crew_promotion"]["second_sample_accepted"] is False
    assert census["promotion_guard"]["control_eligibility"] is False


def test_global_unknowns_remain_null():
    control = load(CONTROL)
    guard = control["scope_guard"]
    assert guard["global_fleet_denominator"] is None
    assert guard["global_fleet_penetration"] is None
    assert guard["grand_mission_penetration"] is None


def test_pca_and_bt_are_withheld_at_two_rows():
    matrix = load(MATRIX)
    gate = matrix["analytics_gate"]
    assert len(matrix["rows"]) == 2
    assert gate["pca_state"] == "WITHHELD_N_LT_3"
    assert gate["bt_state"] == "WITHHELD_NO_OBSERVED_PAIRWISE_OUTCOME_EVIDENCE"


def test_ambassador_cannot_transfer_authority():
    census = load(CENSUS)
    assert census["ambassador"]["authority_transfer"] is False
    assert census["ambassador"]["round_trip_complete"] is False
