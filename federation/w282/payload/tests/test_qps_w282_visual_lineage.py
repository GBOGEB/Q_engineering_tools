import importlib.util
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "w282", ROOT / "scripts" / "qps_w282_validate_visual_lineage.py"
)
w282 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(w282)


class W282VisualLineageTests(unittest.TestCase):
    def test_current_lineage_passes(self):
        result = w282.validate(ROOT)
        self.assertEqual(result["status"], "PASS_VISUAL_LINEAGE_RESTART_CONTROL")
        self.assertEqual(result["validated_lineage"], ["W162", "W188", "W231"])
        self.assertEqual(
            result["historical_w231_diagnostic_parse_mode"], "IMMUTABLE_TEXT_MARKERS"
        )

    def test_stale_w162_restart_guard_exists(self):
        current = yaml.safe_load(
            (ROOT / "controls/QPS_VISUAL_LINEAGE_CURRENT_v0.1.yaml").read_text(encoding="utf-8")
        )
        self.assertIn(
            "REOPEN_N200_COLLECTION_FROM_W162",
            current["current_visual_predicate"]["prohibited_stale_restart"],
        )
        self.assertEqual(
            current["current_visual_predicate"]["state"],
            "STOP_FROZEN_WAIT_GOVERNED_TRIGGER",
        )

    def test_n300_control_is_not_promoted(self):
        w231 = yaml.safe_load(
            (
                ROOT
                / "triage/w231/QPS_W231_N300_ATOMIC_SWAP_UNIQUE_STATS_v0.1.yaml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            w231["control_disposition"]["N300_CONTROL"], "WITHHELD_MSA_FIRST_RED"
        )

    def test_qtg_requires_governed_trigger(self):
        qtg = yaml.safe_load(
            (ROOT / "handover/qps_recursive/QTG_CURRENT.yaml").read_text(encoding="utf-8")
        )
        self.assertIn(
            "NO_FURTHER_N300_MSA_ITERATION_WITHOUT_GOVERNED_TRIGGER",
            qtg["stop_rules"],
        )

    def test_historical_w231_diagnostic_is_not_reparsed_or_rewritten(self):
        text = (
            ROOT
            / "triage/w231/QPS_W231_TABLE_READABILITY_MSA_DIAGNOSTIC_v0.1.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "governed_gate_redefinition: NOT_AUTHORIZED_BY_THIS_DIAGNOSTIC", text
        )
        self.assertIn("all_format_strata_above_0_50: true", text)
        self.assertIn("heterogeneous-format pooling / suppression structure", text)


if __name__ == "__main__":
    unittest.main()
