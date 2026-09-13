import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "w162", ROOT / "scripts" / "qps_w162_validate_visual_convergence.py"
)
w162 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(w162)


class VisualConvergenceTests(unittest.TestCase):
    def test_current_w162_binding_passes(self):
        result = w162.validate(
            ROOT,
            "triage/w162/QPS_W162_VISUAL_N200_CENSUS_v0.2.yaml",
            "ocd-adr/40_implementation/QPS_VISUAL_PCA_N100_GENERATION_RECEIPT.json",
            "ocd-adr/40_implementation/QPS_VISUAL_PCA_BALANCED_SAMPLE_CONVERGENCE.csv",
            "ocd-adr/40_implementation/QPS_VISUAL_N400_EXPANSION_PLAN_v0.1.yaml",
        )
        self.assertEqual(result["status"], "PASS_W162_VISUAL_CONVERGENCE")
        self.assertEqual(result["N200_independent_new_artifacts"], 0)
        self.assertEqual(result["N200_remaining_deficit_total"], 100)

    def test_subsampling_cannot_earn_n200_credit(self):
        source = yaml.safe_load(
            (ROOT / "triage/w162/QPS_W162_VISUAL_N200_CENSUS_v0.2.yaml").read_text(encoding="utf-8")
        )
        source["N200_gate"]["progress_credit_from_N60_N80_subsampling"] = 20
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "triage/w162").mkdir(parents=True)
            (tmp_root / "ocd-adr/40_implementation").mkdir(parents=True)
            (tmp_root / "triage/w162/QPS_W162_VISUAL_N200_CENSUS_v0.2.yaml").write_text(
                yaml.safe_dump(source, sort_keys=False), encoding="utf-8"
            )
            for name in [
                "QPS_VISUAL_PCA_N100_GENERATION_RECEIPT.json",
                "QPS_VISUAL_PCA_BALANCED_SAMPLE_CONVERGENCE.csv",
                "QPS_VISUAL_N400_EXPANSION_PLAN_v0.1.yaml",
            ]:
                src = ROOT / "ocd-adr/40_implementation" / name
                dst = tmp_root / "ocd-adr/40_implementation" / name
                dst.write_bytes(src.read_bytes())
            result = w162.validate(
                tmp_root,
                "triage/w162/QPS_W162_VISUAL_N200_CENSUS_v0.2.yaml",
                "ocd-adr/40_implementation/QPS_VISUAL_PCA_N100_GENERATION_RECEIPT.json",
                "ocd-adr/40_implementation/QPS_VISUAL_PCA_BALANCED_SAMPLE_CONVERGENCE.csv",
                "ocd-adr/40_implementation/QPS_VISUAL_N400_EXPANSION_PLAN_v0.1.yaml",
            )
        self.assertEqual(result["status"], "FAIL_W162_VISUAL_CONVERGENCE")
        self.assertTrue(any("subsampling must earn zero N200 credit" in e for e in result["errors"]))

    def test_n200_claim_fails_without_new_independent_artifacts(self):
        source = yaml.safe_load(
            (ROOT / "triage/w162/QPS_W162_VISUAL_N200_CENSUS_v0.2.yaml").read_text(encoding="utf-8")
        )
        source["analysis_disposition"]["N200"] = "ACHIEVED"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "triage/w162").mkdir(parents=True)
            (tmp_root / "ocd-adr/40_implementation").mkdir(parents=True)
            (tmp_root / "triage/w162/QPS_W162_VISUAL_N200_CENSUS_v0.2.yaml").write_text(
                yaml.safe_dump(source, sort_keys=False), encoding="utf-8"
            )
            for name in [
                "QPS_VISUAL_PCA_N100_GENERATION_RECEIPT.json",
                "QPS_VISUAL_PCA_BALANCED_SAMPLE_CONVERGENCE.csv",
                "QPS_VISUAL_N400_EXPANSION_PLAN_v0.1.yaml",
            ]:
                src = ROOT / "ocd-adr/40_implementation" / name
                dst = tmp_root / "ocd-adr/40_implementation" / name
                dst.write_bytes(src.read_bytes())
            result = w162.validate(
                tmp_root,
                "triage/w162/QPS_W162_VISUAL_N200_CENSUS_v0.2.yaml",
                "ocd-adr/40_implementation/QPS_VISUAL_PCA_N100_GENERATION_RECEIPT.json",
                "ocd-adr/40_implementation/QPS_VISUAL_PCA_BALANCED_SAMPLE_CONVERGENCE.csv",
                "ocd-adr/40_implementation/QPS_VISUAL_N400_EXPANSION_PLAN_v0.1.yaml",
            )
        self.assertEqual(result["status"], "FAIL_W162_VISUAL_CONVERGENCE")
        self.assertTrue(any("N200 must remain NOT_ACHIEVED" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
