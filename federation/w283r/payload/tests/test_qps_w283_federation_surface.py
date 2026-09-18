#!/usr/bin/env python3
import importlib.util, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/qps_w283_validate_federation_surface.py"
spec=importlib.util.spec_from_file_location("w283r_validator",SCRIPT)
mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)

class W283RTests(unittest.TestCase):
    def test_repaired_candidate_passes(self):
        r=mod.validate()
        self.assertEqual(r["result"],"PASS_REPAIRED_CANDIDATE_EXTERNAL_FUNCTION_SET_BOUND")
        self.assertEqual(r["authoritative_functions"],12)
        self.assertEqual(r["covered_functions"],4)
        self.assertAlmostEqual(r["function_breadth"],1/3)
        self.assertIsNone(r["function_depth"])
        self.assertIsNone(r["global_fleet_penetration"])

    def test_authoritative_topology_and_census_are_exact(self):
        self.assertEqual(mod.git_blob_sha(mod.TOPOLOGY),mod.EXPECTED_TOPOLOGY_BLOB)
        self.assertEqual(mod.git_blob_sha(mod.CENSUS),mod.EXPECTED_CENSUS_BLOB)
        topo=mod.topology_functions(mod.TOPOLOGY.read_text())
        census=set(json.loads(mod.CENSUS.read_text())["denominator"]["unique_functions"])
        self.assertEqual(topo,census)
        self.assertEqual(len(topo),12)

    def test_covered_uncovered_partition_authority_set(self):
        c=json.loads(mod.CROSS.read_text())
        topo=mod.topology_functions(mod.TOPOLOGY.read_text())
        mapped={x["mapped_function"] for x in c["accepted_samples"]}
        uncovered=set(c["measured_result"]["uncovered_functions"])
        self.assertEqual(mapped|uncovered,topo)
        self.assertTrue(mapped.isdisjoint(uncovered))
        self.assertEqual(len(mapped),4)
        self.assertEqual(len(uncovered),8)

    def test_duplicate_mission_control_sample_does_not_double_count(self):
        c=json.loads(mod.CROSS.read_text())
        mapped=[x["mapped_function"] for x in c["accepted_samples"]]
        self.assertEqual(mapped.count("MISSION_CONTROL_ORCHESTRATION"),2)
        self.assertEqual(len(set(mapped)),4)

    def test_prior_green_is_explicitly_insufficient(self):
        ctl=json.loads(mod.CONTROL.read_text())
        self.assertEqual(ctl["rex"]["prior_green_proof_disposition"],"INSUFFICIENT_FOR_CONTROL_AFTER_P1")
        self.assertEqual(ctl["three_pc"]["prove"],"WAIT_REPAIRED_EXACT_EXTERNAL_PR_HEAD_AND_DISTINCT_REPEAT")

    def test_bt_and_923_remain_noncompensating(self):
        b=json.loads(mod.BT.read_text()); ctl=json.loads(mod.CONTROL.read_text())
        self.assertFalse(b["current_repair_component"]["finite_unregularized_mle"])
        self.assertFalse(b["separate_observed_component"]["bridge_to_repair_component"])
        self.assertIn("QPS_REPO_LOCAL_RUNNER_923",ctl["preserved_noncompensating"])
        self.assertEqual(sum(ctl["formal_credit_delta"].values()),0)

if __name__=="__main__":
    unittest.main()
