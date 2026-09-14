from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qps_validate_qrt_d_readiness.py"
VECTOR = ROOT / "controls" / "QPS_QRT_D_READINESS_VECTOR_v1.yaml"
PROFILE = ROOT / "controls" / "QPS_QRT_D_CANONICAL_PACK_PROFILE_v1.yaml"

spec = importlib.util.spec_from_file_location("qrt_d_validator", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestQrtDReadiness(unittest.TestCase):
    def setUp(self):
        self.vector = load(VECTOR)
        self.profile = load(PROFILE)

    def test_current_vector_passes(self):
        self.assertEqual([], module.validate(self.vector, self.profile))

    def test_fake_cost_identity_promotion_fails_closed(self):
        mutated = copy.deepcopy(self.vector)
        row = next(r for r in mutated["product_rows"] if r["product_id"] == "COST_XLSX")
        row["A1_SOURCE_IDENTITY"] = "PASS_CONTROLLED"
        failures = module.validate(mutated, self.profile)
        self.assertTrue(any("identity must remain held" in item for item in failures))

    def test_html_cannot_become_numerical_ssot(self):
        mutated = copy.deepcopy(self.vector)
        row = next(r for r in mutated["product_rows"] if r["product_id"] == "COST_HTML")
        row["role"] = "NUMERICAL_SSOT"
        failures = module.validate(mutated, self.profile)
        self.assertTrue(any("role mismatch" in item for item in failures))

    def test_numeric_release_cannot_escape_source_hold(self):
        mutated = copy.deepcopy(self.vector)
        mutated["shared_guards"]["actual_numeric_cost_release"] = "RELEASED"
        failures = module.validate(mutated, self.profile)
        self.assertTrue(any("numeric COST release must remain source-withheld" in item for item in failures))

    def test_outward_smoke_cannot_self_promote_local_acceptance(self):
        mutated = copy.deepcopy(self.vector)
        row = next(r for r in mutated["product_rows"] if r["product_id"] == "OCD_ADR_PPTX")
        row["A5_RENDER_ACCEPTANCE"] = "PASS_CONTROLLED"
        failures = module.validate(mutated, self.profile)
        self.assertTrue(any("render acceptance must remain local hold" in item for item in failures))

    def test_3pc_stays_prepared_not_admitted(self):
        mutated = copy.deepcopy(self.vector)
        mutated["next_transition"]["state"] = "ADMITTED"
        failures = module.validate(mutated, self.profile)
        self.assertTrue(any("3PC must remain prepared-not-admitted" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
