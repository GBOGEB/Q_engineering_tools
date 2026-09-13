import copy
import json
import tempfile
import unittest
from pathlib import Path
import importlib.util

SCRIPT = Path("scripts/qps_w164_validate_mission_federation.py")
spec = importlib.util.spec_from_file_location("w164_validator", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

CONTROL = Path("controls/QPS_MISSION_FEDERATION_CURRENT_v1.json")
CREW = Path("controls/QPS_CREW_REGISTRY_CURRENT_v1.json")


class W164MissionFederationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.control = json.loads(CONTROL.read_text(encoding="utf-8"))
        cls.crew = json.loads(CREW.read_text(encoding="utf-8"))

    def test_canonical_payload_passes(self):
        mod.validate_control(copy.deepcopy(self.control))
        mod.validate_crew(copy.deepcopy(self.crew))
        mod.validate_cross_binding(copy.deepcopy(self.control), copy.deepcopy(self.crew))

    def test_early_learning_cannot_claim_runtime_receipt(self):
        bad = copy.deepcopy(self.control)
        bad["early_learning_state_machine"]["forbidden_prelaunch_claims"] = ["CANONICAL_CHILD", "ACCEPTANCE", "MISSION_COMPLETE"]
        with self.assertRaises(AssertionError):
            mod.validate_control(bad)

    def test_federation_cannot_become_grand_mission_vi(self):
        bad = copy.deepcopy(self.control)
        bad["federation_mission"]["class"] = "GM-VI"
        with self.assertRaises(AssertionError):
            mod.validate_control(bad)

    def test_penetration_formula_is_fail_closed(self):
        bad = copy.deepcopy(self.control)
        bad["penetration_model"]["formula"] = "PEN=B+D"
        with self.assertRaises(AssertionError):
            mod.validate_control(bad)

    def test_seeded_crew_cannot_be_control_eligible_without_evidence(self):
        bad = copy.deepcopy(self.crew)
        member = next(m for m in bad["members"] if m["maturity"] == "SEEDED")
        member["CONTROL_eligibility"] = True
        with self.assertRaises(AssertionError):
            mod.validate_crew(bad)

    def test_zero_credit_guard_is_fail_closed(self):
        bad = copy.deepcopy(self.control)
        bad["formal_credit_delta"]["engineering"] = 1
        with self.assertRaises(AssertionError):
            mod.validate_control(bad)

    def test_all_ten_points_required(self):
        bad = copy.deepcopy(self.control)
        bad["ten_point_control"].pop()
        with self.assertRaises(AssertionError):
            mod.validate_control(bad)


if __name__ == "__main__":
    unittest.main()
