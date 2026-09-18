import copy, importlib.util, tempfile, unittest
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("w282",ROOT/"scripts/qps_w282_validate_visual_lineage.py")
w282=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(w282)

class W282VisualLineageTests(unittest.TestCase):
    def test_current_lineage_passes(self):
        r=w282.validate(ROOT)
        self.assertEqual(r["status"],"PASS_VISUAL_LINEAGE_RESTART_CONTROL")
        self.assertEqual(r["validated_lineage"],["W162","W188","W231"])

    def test_stale_w162_restart_guard_exists(self):
        c=yaml.safe_load((ROOT/"controls/QPS_VISUAL_LINEAGE_CURRENT_v0.1.yaml").read_text())
        self.assertIn("REOPEN_N200_COLLECTION_FROM_W162",c["current_visual_predicate"]["prohibited_stale_restart"])
        self.assertEqual(c["current_visual_predicate"]["state"],"STOP_FROZEN_WAIT_GOVERNED_TRIGGER")

    def test_n300_control_is_not_promoted(self):
        w=yaml.safe_load((ROOT/"triage/w231/QPS_W231_N300_ATOMIC_SWAP_UNIQUE_STATS_v0.1.yaml").read_text())
        self.assertEqual(w["control_disposition"]["N300_CONTROL"],"WITHHELD_MSA_FIRST_RED")

    def test_qtg_requires_governed_trigger(self):
        q=yaml.safe_load((ROOT/"handover/qps_recursive/QTG_CURRENT.yaml").read_text())
        self.assertIn("NO_FURTHER_N300_MSA_ITERATION_WITHOUT_GOVERNED_TRIGGER",q["stop_rules"])

if __name__=="__main__": unittest.main()
