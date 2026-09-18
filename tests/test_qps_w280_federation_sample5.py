#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/qps_w280_validate_federation_sample5.py"
spec = importlib.util.spec_from_file_location("w280_validator", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class W280FederationSample5Tests(unittest.TestCase):
    def test_candidate_control_passes(self):
        receipt = mod.validate()
        self.assertEqual(receipt["result"], "PASS_CANDIDATE_CONTROL_ONLY")
        self.assertFalse(receipt["sample5_accepted"])
        self.assertEqual(receipt["accepted_reference_samples"], 4)

    def test_bt_is_not_promoted_to_finite_fit(self):
        bt = json.loads(mod.BT.read_text(encoding="utf-8"))
        self.assertFalse(bt["topology"]["directed_strongly_connected"])
        self.assertEqual(
            bt["federation_interpretation"],
            "WITHHELD_NO_FINITE_UNREGULARIZED_MLE",
        )

    def test_global_denominator_remains_unfrozen(self):
        census = json.loads(mod.CENSUS.read_text(encoding="utf-8"))
        control = json.loads(mod.CONTROL.read_text(encoding="utf-8"))
        self.assertEqual(census["accessible_repository_universe_total"], 83)
        self.assertIsNone(control["fleet_census"]["governed_surface_denominator"])
        self.assertIsNone(control["fleet_census"]["global_fleet_penetration"])

    def test_w80_cannot_seed_pairwise_events(self):
        bt = json.loads(mod.BT.read_text(encoding="utf-8"))
        self.assertEqual(bt["abacus_w80_guard"]["pairwise_events"], 0)
        self.assertFalse(bt["abacus_w80_guard"]["permitted_as_bt_evidence"])


if __name__ == "__main__":
    unittest.main()
