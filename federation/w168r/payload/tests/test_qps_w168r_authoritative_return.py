import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "qps_w168r_validate_authoritative_return.py"
RETURN = ROOT / "triage" / "w168" / "QPS_W168_FEDERATION_EXPANSION_RUNTIME_CONTROL_v0.1.json"
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


class TestW168RAuthoritativeReturn(unittest.TestCase):
    def test_canonical_return_passes(self):
        run = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, check=True, capture_output=True, text=True)
        receipt = json.loads(run.stdout)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["PEN"], 1.0)
        self.assertEqual(receipt["specialists_control_eligible"], 6)
        self.assertEqual(receipt["specialists_control_promoted"], 0)

    def test_sample2_breadth_depth_penetration_close(self):
        ret = load(RETURN)
        self.assertEqual(ret["measurement_final"]["breadth"]["value"], 1.0)
        self.assertEqual(ret["measurement_final"]["depth"]["value"], 1.0)
        self.assertEqual(ret["measurement_final"]["penetration"], 1.0)

    def test_native_gate_remains_non_compensating(self):
        ret = load(RETURN)
        native = ret["mission_control_source"]["native_runtime"]
        self.assertEqual(native["runner_id"], 0)
        self.assertEqual(native["recorded_steps"], 0)
        self.assertIn("QPS_REPO_LOCAL_RUNNER_923", ret["preserved_non_compensating_gates"])

    def test_six_specialists_are_eligible_but_not_auto_promoted(self):
        ret = load(RETURN)
        self.assertEqual(set(ret["specialist_repeat"]["roles"]), SPECIALISTS)
        self.assertTrue(ret["specialist_repeat"]["CONTROL_eligibility"])
        self.assertEqual(ret["specialist_repeat"]["CONTROL_state"], "ELIGIBLE_NOT_AUTOMATICALLY_PROMOTED")

    def test_registry_reconciles_all_six_specialists(self):
        registry = load(REGISTRY)
        members = {row["CREW_ID"]: row for row in registry["members"]}
        for crew_id in SPECIALISTS:
            self.assertTrue(members[crew_id]["CONTROL_eligibility"])
            self.assertEqual(members[crew_id]["maturity"], "MEASURED_DISTINCT_REPEAT_ACCEPTED")

    def test_two_samples_do_not_become_global_denominator(self):
        ret = load(RETURN)
        sampling = ret["fleet_sampling"]
        self.assertEqual(sampling["accepted_bounded_samples"], 2)
        self.assertIsNone(sampling["global_fleet_denominator"])
        self.assertIsNone(sampling["global_fleet_penetration"])

    def test_pca_and_bt_remain_withheld(self):
        matrix = load(MATRIX)
        self.assertEqual(matrix["analytics_gate"]["accepted_row_count"], 2)
        self.assertEqual(matrix["analytics_gate"]["pca_state"], "WITHHELD_N_LT_3")
        self.assertEqual(matrix["analytics_gate"]["bt_state"], "WITHHELD_NO_OBSERVED_PAIRWISE_OUTCOME_EVIDENCE")

    def test_authority_does_not_transfer(self):
        ret = load(RETURN)
        self.assertTrue(ret["ambassador"]["round_trip_complete"])
        self.assertFalse(ret["ambassador"]["authority_transfer"])


if __name__ == "__main__":
    unittest.main()
