import copy
import json
import unittest
from pathlib import Path
import importlib.util

SCRIPT = Path("scripts/qps_w166_validate_federation_measurement.py")
spec = importlib.util.spec_from_file_location("w166_validator", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

CONTROL = Path("controls/QPS_FEDERATION_MEASUREMENT_CURRENT_v1.json")
CENSUS = Path("triage/w166/QPS_W166_FEDERATION_PILOT_CENSUS_v0.1.json")


class W166FederationMeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control = json.loads(CONTROL.read_text(encoding="utf-8"))
        cls.census = json.loads(CENSUS.read_text(encoding="utf-8"))

    def test_canonical_payload_passes(self):
        mod.validate_control(copy.deepcopy(self.control))
        mod.validate_census(copy.deepcopy(self.census))

    def test_penetration_math_fails_closed(self):
        bad = copy.deepcopy(self.census)
        bad["penetration"]["PEN"] = 0.5
        with self.assertRaises(AssertionError):
            mod.validate_census(bad)

    def test_unknown_global_denominator_cannot_be_zero_imputed(self):
        bad = copy.deepcopy(self.census)
        bad["unknowns"]["global_repo_denominator"] = 0
        with self.assertRaises(AssertionError):
            mod.validate_census(bad)

    def test_static_specialist_output_cannot_promote_crew(self):
        bad = copy.deepcopy(self.census)
        bad["crew_candidate_receipts"][0]["state"] = "MEASURED"
        with self.assertRaises(AssertionError):
            mod.validate_census(bad)

    def test_authority_transfer_forbidden(self):
        bad = copy.deepcopy(self.census)
        bad["ambassador_round_trip"]["authority_transfer"] = True
        with self.assertRaises(AssertionError):
            mod.validate_census(bad)

    def test_breadth_requires_explicit_denominator(self):
        bad = copy.deepcopy(self.census)
        bad["breadth"]["repositories"]["denominator"] = 3
        with self.assertRaises(AssertionError):
            mod.validate_census(bad)

    def test_depth_layer_loss_fails_closed(self):
        bad = copy.deepcopy(self.census)
        bad["depth"]["layers"][6]["observed"] = False
        with self.assertRaises(AssertionError):
            mod.validate_census(bad)

    def test_w165_gate_must_remain_non_compensating(self):
        bad = copy.deepcopy(self.control)
        bad["preserved_non_compensating_gates"].remove("W165_EDGE_K8S_MEASUREMENT_GATE")
        with self.assertRaises(AssertionError):
            mod.validate_control(bad)


if __name__ == "__main__":
    unittest.main()
