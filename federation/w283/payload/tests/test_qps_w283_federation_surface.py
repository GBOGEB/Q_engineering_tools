#!/usr/bin/env python3
import importlib.util, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/qps_w283_validate_federation_surface.py"
spec=importlib.util.spec_from_file_location("w283_validator",SCRIPT)
mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)

class W283Tests(unittest.TestCase):
    def test_candidate_passes(self):
        r=mod.validate()
        self.assertEqual(r["result"],"PASS_CANDIDATE_FUNCTION_BREADTH_ONLY")
        self.assertEqual(r["mapped_samples"],5)
        self.assertEqual(r["covered_functions"],4)
        self.assertEqual(r["governed_functions"],12)
        self.assertAlmostEqual(r["function_breadth"],1/3)
        self.assertIsNone(r["function_depth"])
        self.assertIsNone(r["global_fleet_penetration"])

    def test_duplicate_function_does_not_double_count(self):
        c=json.loads(mod.CROSS.read_text())
        mapped=[x["mapped_function"] for x in c["accepted_samples"]]
        self.assertEqual(mapped.count("MISSION_CONTROL_ORCHESTRATION"),2)
        self.assertEqual(len(set(mapped)),4)

    def test_depth_is_not_inferred_from_sample_depth(self):
        c=json.loads(mod.CROSS.read_text())
        self.assertEqual(c["measured_result"]["accepted_sample_mapping"]["value"],1.0)
        self.assertIsNone(c["measured_result"]["global_function_depth"])
        self.assertIsNone(c["measured_result"]["global_fleet_penetration"])
        self.assertIn("NO_BOUNDED_SAMPLE_DEPTH_EXTRAPOLATION",c["guards"])

    def test_bt_does_not_bridge_heterogeneous_component(self):
        b=json.loads(mod.BT.read_text())
        self.assertFalse(b["current_repair_component"]["finite_unregularized_mle"])
        self.assertTrue(b["separate_observed_component"]["finite_local_mle"])
        self.assertFalse(b["separate_observed_component"]["bridge_to_repair_component"])
        self.assertEqual(b["global_bt"],"WITHHELD_DISCONNECTED_HETEROGENEOUS_COMPARISON_GRAPH")

    def test_noncompensating_gates(self):
        ctl=json.loads(mod.CONTROL.read_text())
        self.assertIn("QPS_REPO_LOCAL_RUNNER_923",ctl["preserved_noncompensating"])
        self.assertIn("W275_R3_PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN",ctl["preserved_noncompensating"])
        self.assertFalse(ctl["authority_transfer"])
        self.assertEqual(sum(ctl["formal_credit_delta"].values()),0)

if __name__=="__main__":
    unittest.main()
