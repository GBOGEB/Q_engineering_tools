import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.qplant_hepak_mip_burndown import evaluate, validate_sline_recovery_receipt


class HepakMIPBurndownTests(unittest.TestCase):
    def _receipts(self, root: Path) -> Path:
        receipts = root / "receipts"
        receipts.mkdir()
        return receipts

    def test_empty_repo_is_zero_of_five_and_bt0_first(self):
        with tempfile.TemporaryDirectory() as td:
            r = evaluate(Path(td))
            self.assertEqual(r["physical_conversion"]["converted"], 0)
            self.assertEqual(r["physical_conversion"]["total"], 5)
            self.assertEqual(r["next_blocker"], "BT0_HEPAK")
            self.assertEqual(r["formal_engineering_delta"], 0)

    def test_non_hepak_manifest_does_not_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = self._receipts(root)
            csvp = receipts / "he_reference_hepak_lowT_grid.csv"
            csvp.write_text("x\n1\n", encoding="utf-8")
            (receipts / "he_reference_hepak_lowT_grid.csv.manifest.json").write_text(
                json.dumps(
                    {
                        "provider": "CoolProp",
                        "csv_sha256": "bad",
                        "status": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            r = evaluate(root)
            self.assertFalse(r["blockers"]["BT0_HEPAK"]["converted"])

    def test_self_consistent_garbage_cannot_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = self._receipts(root)
            csvp = receipts / "he_reference_hepak_lowT_grid.csv"
            csvp.write_text("not,a,hepak,receipt\n1,2,3,4\n", encoding="utf-8")
            digest = hashlib.sha256(csvp.read_bytes()).hexdigest()
            manifest = {
                "schema": "qps-hepak-lowt-grid-receipt/v1",
                "provider": "HEPAK",
                "provider_version": "fake",
                "status": "PASS",
                "unit_set": 1,
                "pressure_basis": "ABSOLUTE_PA",
                "execution_utc": "2026-09-22T00:00:00Z",
                "solve_policy": "H_FIRST_S_SECOND_TP_SOURCE_BOUND_DENSITY_LAST",
                "source_workbook_sha256": "a" * 64,
                "csv_sha256": digest,
                "row_count": 1,
                "state_ids": ["A_CONTRACT"],
            }
            (receipts / "he_reference_hepak_lowT_grid.csv.manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            r = evaluate(root)
            self.assertFalse(r["blockers"]["BT0_HEPAK"]["converted"])

    def test_bt1_rejects_presence_only_null_geometry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = self._receipts(root)
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(
                    {
                        "source_locator": None,
                        "revision": None,
                        "segments": [],
                    }
                ),
                encoding="utf-8",
            )
            r = evaluate(root)
            self.assertFalse(r["blockers"]["BT1_LINEB_GEOMETRY"]["converted"])

    def test_bt2_rejects_blank_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = self._receipts(root)
            path = receipts / "lineb_qcell_bflow_current.csv"
            fields = [
                "qcell_id",
                "installed_or_future",
                "longitudinal_position",
                "mode",
                "configuration",
                "B_flow_g_s",
                "source_locator",
                "authority_class",
                "cumulative_segment_flow_g_s",
                "mass_balance_residual",
            ]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({field: "" for field in fields})
            r = evaluate(root)
            self.assertFalse(r["blockers"]["BT2_BFLOW"]["converted"])

    def test_bt2_rejects_undersized_mode_configuration_populations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = self._receipts(root)
            path = receipts / "lineb_qcell_bflow_current.csv"
            fields = [
                "qcell_id",
                "installed_or_future",
                "longitudinal_position",
                "mode",
                "configuration",
                "B_flow_g_s",
                "source_locator",
                "authority_class",
                "cumulative_segment_flow_g_s",
                "mass_balance_residual",
            ]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for mode in ("2K_OP", "2K_SB"):
                    for configuration in ("config24", "config30"):
                        writer.writerow(
                            {
                                "qcell_id": "QCELL-01",
                                "installed_or_future": "installed",
                                "longitudinal_position": "1",
                                "mode": mode,
                                "configuration": configuration,
                                "B_flow_g_s": "1.0",
                                "source_locator": "offer:lineb",
                                "authority_class": "CURRENT_SELECTED",
                                "cumulative_segment_flow_g_s": "1.0",
                                "mass_balance_residual": "0.0",
                            }
                        )
            r = evaluate(root)
            self.assertFalse(r["blockers"]["BT2_BFLOW"]["converted"])
            self.assertIn("population", r["blockers"]["BT2_BFLOW"]["reason"])

    def test_bt3_rejects_non_hepak_provider_even_with_numeric_row(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = self._receipts(root)
            path = receipts / "lineb_spatial_thermal_field_current.csv"
            fields = [
                "segment_id",
                "heat_leak_W_m_or_discrete_W",
                "inlet_T_K",
                "inlet_h_J_kg",
                "outlet_T_K",
                "outlet_h_J_kg",
                "phase",
                "rho_kg_m3",
                "mu_Pa_s",
                "provider",
                "provider_version",
                "HEPAK_anchor_or_validation_identity",
                "source_locator",
            ]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "segment_id": "S1",
                        "heat_leak_W_m_or_discrete_W": "1",
                        "inlet_T_K": "3.6",
                        "inlet_h_J_kg": "10",
                        "outlet_T_K": "3.7",
                        "outlet_h_J_kg": "11",
                        "phase": "gas",
                        "rho_kg_m3": "1",
                        "mu_Pa_s": "0.000001",
                        "provider": "CoolProp",
                        "provider_version": "test",
                        "HEPAK_anchor_or_validation_identity": "none",
                        "source_locator": "test",
                    }
                )
            r = evaluate(root)
            self.assertFalse(r["blockers"]["BT3_THERMAL_FIELD"]["converted"])

    def test_bt4_rejects_presence_only_empty_values(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = self._receipts(root)
            path = receipts / "sline_applicant_recovery_current.json"
            path.write_text(
                json.dumps(
                    {
                        "applicants": [],
                        "pressure_hierarchy_bara": {},
                        "psv": {},
                        "source_locators": [],
                    }
                ),
                encoding="utf-8",
            )
            r = evaluate(root)
            self.assertFalse(r["blockers"]["BT4_SLINE_RECOVERY"]["converted"])

    def test_bt4_accepts_substantive_structured_receipt_without_hardcoded_thresholds(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "receipt.json"
            path.write_text(
                json.dumps(
                    {
                        "applicants": ["Applicant-A"],
                        "pressure_hierarchy_bara": {"fill_close": 1.5, "psv": 1.7},
                        "psv": {"setpoint_bara": 1.7, "basis": "selected design"},
                        "source_locators": ["offer:recovery:revA"],
                    }
                ),
                encoding="utf-8",
            )
            ok, reason = validate_sline_recovery_receipt(path)
            self.assertTrue(ok, reason)

    def test_placeholder_geometry_json_does_not_convert_bt1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(
                    {
                        "source_locator": None,
                        "revision": None,
                        "segments": None,
                    }
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT1_LINEB_GEOMETRY"]["converted"])

    def test_substantive_geometry_json_converts_bt1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(
                    {
                        "source_locator": "P&ID-LB-001 rev C",
                        "revision": "C",
                        "segments": [
                            {
                                "segment_id": "LB-001",
                                "inner_diameter_mm": 150.0,
                                "length_m": 12.5,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertTrue(result["blockers"]["BT1_LINEB_GEOMETRY"]["converted"])

    def test_blank_bflow_row_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_qcell_bflow_current.csv").write_text(
                "qcell_id,mode,configuration,B_flow_g_s,source_locator\n,,,,\n",
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT2_BFLOW"]["converted"])

    def test_legacy_only_bflow_population_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "qcell_id",
                        "mode",
                        "configuration",
                        "B_flow_g_s",
                        "source_locator",
                    ],
                )
                writer.writeheader()
                for index in range(1, 25):
                    writer.writerow(
                        {
                            "qcell_id": f"QC{index:02d}",
                            "mode": "2K_OP",
                            "configuration": "CONFIG24",
                            "B_flow_g_s": "1.8",
                            "source_locator": "FLOW-MATRIX-REV-A",
                        }
                    )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT2_BFLOW"]["converted"])

    def test_complete_bflow_population_converts_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "qcell_id",
                        "mode",
                        "configuration",
                        "B_flow_g_s",
                        "source_locator",
                    ],
                )
                writer.writeheader()
                for mode in ("2K_OP", "2K_SB"):
                    for configuration, count in (("CONFIG24", 24), ("CONFIG30", 30)):
                        for index in range(1, count + 1):
                            writer.writerow(
                                {
                                    "qcell_id": f"QC{index:02d}",
                                    "mode": mode,
                                    "configuration": configuration,
                                    "B_flow_g_s": "1.8",
                                    "source_locator": "FLOW-MATRIX-REV-A",
                                }
                            )
            result = evaluate(root)
            self.assertTrue(result["blockers"]["BT2_BFLOW"]["converted"])

    def test_non_hepak_thermal_row_does_not_convert_bt3(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_spatial_thermal_field_current.csv").write_text(
                (
                    "segment_id,inlet_T_K,outlet_T_K,provider,source_locator\n"
                    "LB-1,3.6,3.7,CoolProp,THERMAL-REV-A\n"
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT3_THERMAL_FIELD"]["converted"])

    def test_hepak_thermal_row_converts_bt3(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_spatial_thermal_field_current.csv").write_text(
                (
                    "segment_id,inlet_T_K,outlet_T_K,provider,source_locator\n"
                    "LB-1,3.6,3.7,HEPAK,THERMAL-REV-A\n"
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertTrue(result["blockers"]["BT3_THERMAL_FIELD"]["converted"])

    def test_placeholder_sline_json_does_not_convert_bt4(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "sline_applicant_recovery_current.json").write_text(
                json.dumps(
                    {
                        "applicants": [],
                        "pressure_hierarchy_bara": {},
                        "psv": {},
                        "source_locators": [],
                    }
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT4_SLINE_RECOVERY"]["converted"])

    def test_source_bound_sline_json_converts_bt4(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "sline_applicant_recovery_current.json").write_text(
                json.dumps(
                    {
                        "applicants": [
                            {
                                "name": "ALAT",
                                "storage_m3": 555,
                            }
                        ],
                        "pressure_hierarchy_bara": {
                            "minimum": 1.05,
                            "nominal": 1.10,
                            "maximum_current_protected_interface": 1.30,
                        },
                        "psv": {
                            "tag": "PSV-QPS-001",
                            "set_pressure_bara": 1.70,
                            "reseat_pressure_bara": 1.55,
                        },
                        "source_locators": [
                            "RTM-242/243",
                            "P&ID-PSV-QPS-001",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertTrue(result["blockers"]["BT4_SLINE_RECOVERY"]["converted"])


if __name__ == "__main__":
    unittest.main()
