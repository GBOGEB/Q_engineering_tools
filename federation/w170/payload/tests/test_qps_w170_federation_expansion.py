import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/QPS_W170_FEDERATION_SAMPLE3_CURRENT_v1.json"
MATRIX = ROOT / "triage/w170/QPS_W170_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"
PAIRWISE = ROOT / "triage/w170/QPS_W170_PAIRWISE_DISPOSITION_LEDGER_v0.1.json"


class TestW170FederationExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control = json.loads(CONTROL.read_text())
        cls.matrix = json.loads(MATRIX.read_text())
        cls.pairwise = json.loads(PAIRWISE.read_text())

    def test_namespace_guard(self):
        self.assertTrue(self.control["namespace"]["w169"].startswith("OCCUPIED_"))
        self.assertEqual(self.control["wave"], "W170")

    def test_distinct_surface(self):
        self.assertEqual(self.control["surface"]["type"], "SUPPLY_CHAIN_PROVENANCE_ATTESTATION")
        self.assertEqual(self.control["surface"]["source_repo"], "GBOGEB/CODEX")

    def test_breadth_depth_penetration_candidate(self):
        m = self.control["measurement"]
        self.assertEqual((m["breadth"]["numerator"], m["breadth"]["denominator"]), (23, 23))
        self.assertEqual((m["depth_candidate"]["numerator"], m["depth_candidate"]["denominator"]), (7, 8))
        self.assertAlmostEqual(m["penetration_candidate"], 0.875)

    def test_runtime_vectors_are_real(self):
        for key in ("exact_pinned_pr", "automatic_main_repeat"):
            self.assertGreater(self.control["observed_runtime"][key]["runner_id"], 0)
            self.assertEqual(self.control["observed_runtime"][key]["result"], "PASS")

    def test_matrix_admission_withheld(self):
        self.assertEqual(len(self.matrix["rows"]), 3)
        self.assertEqual(sum(x["accepted_sample"] for x in self.matrix["rows"]), 2)
        self.assertEqual(self.matrix["analytics_gate"]["pca_state"], "CANDIDATE_COMPUTABLE_WITHHELD_PENDING_SAMPLE3_ACCEPTANCE")

    def test_bt_independent_and_withheld(self):
        self.assertEqual(len(self.pairwise["outcomes"]), 3)
        self.assertFalse(self.pairwise["bt_gate"]["connected_comparison_graph"])
        self.assertTrue(self.pairwise["bt_gate"]["fit_state"].startswith("WITHHELD_"))

    def test_global_denominators_null(self):
        self.assertIsNone(self.control["global_denominators"]["fleet"])
        self.assertIsNone(self.matrix["fleet_sampling_guard"]["global_fleet_denominator"])

    def test_validator(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/qps_w170_validate_federation_expansion.py")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
