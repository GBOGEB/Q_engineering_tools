import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/QPS_W170_FEDERATION_SAMPLE3_CURRENT_v1.json"
MATRIX = ROOT / "triage/w170/QPS_W170_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"
PAIRWISE = ROOT / "triage/w170/QPS_W170_PAIRWISE_DISPOSITION_LEDGER_v0.1.json"
RUNTIME = ROOT / "triage/w170/QPS_W170_FEDERATION_EXPANSION_RUNTIME_CONTROL_v0.1.json"


class TestW170FederationExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control = json.loads(CONTROL.read_text())
        cls.matrix = json.loads(MATRIX.read_text())
        cls.pairwise = json.loads(PAIRWISE.read_text())
        cls.runtime = json.loads(RUNTIME.read_text())

    def test_namespace_and_surface(self):
        self.assertTrue(self.control["namespace"]["w169"].startswith("OCCUPIED_"))
        self.assertEqual(self.control["surface"]["source_repo"], "GBOGEB/CODEX")

    def test_breadth_depth_penetration_accepted(self):
        m = self.control["measurement"]
        self.assertEqual(m["breadth"]["value"], 1.0)
        self.assertEqual(m["depth"]["value"], 1.0)
        self.assertEqual(m["penetration"], 1.0)

    def test_exact_federated_repeat(self):
        for key in ("pr_head", "postmerge"):
            self.assertGreater(self.control["federated_exact_proof"][key]["runner_id"], 0)
            self.assertEqual(self.control["federated_exact_proof"][key]["result"], "PASS")

    def test_native_gate_noncompensating(self):
        self.assertEqual(self.control["native_missioncontrol_runtime"]["recorded_steps"], 0)
        self.assertFalse(self.control["native_missioncontrol_runtime"]["compensated"])

    def test_matrix_three_accepted_rows(self):
        self.assertEqual(len(self.matrix["rows"]), 3)
        self.assertEqual(sum(x["accepted_sample"] for x in self.matrix["rows"]), 3)
        self.assertEqual(self.matrix["analytics_gate"]["pca_state"], "MEASURED_SMALL_N_ACCEPTED")

    def test_bt_capture_not_fit(self):
        self.assertEqual(len(self.pairwise["outcomes"]), 3)
        self.assertFalse(self.pairwise["bt_gate"]["connected_comparison_graph"])
        self.assertTrue(self.pairwise["bt_gate"]["fit_state"].startswith("WITHHELD_"))

    def test_global_denominators_null(self):
        self.assertIsNone(self.control["global_denominators"]["fleet"])
        self.assertIsNone(self.matrix["fleet_sampling_guard"]["global_fleet_denominator"])

    def test_runtime_control(self):
        self.assertTrue(self.runtime["acceptance"]["accepted_sample"])
        self.assertEqual(self.runtime["pca"]["state"], "MEASURED_SMALL_N_ACCEPTED")

    def test_validator(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/qps_w170_validate_federation_expansion.py")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
