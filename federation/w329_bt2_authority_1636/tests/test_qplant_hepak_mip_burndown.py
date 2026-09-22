import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.qplant_hepak_mip_burndown import (
    HEPAK_CSV_FIELDS,
    REQUIRED_HEPAK_STATES,
    _row_digest,
    evaluate,
)


class HepakMIPBurndownTests(unittest.TestCase):
    def test_empty_repo_is_zero_of_five_and_bt0_first(self):
        with tempfile.TemporaryDirectory() as td:
            result = evaluate(Path(td))
            self.assertEqual(result["physical_conversion"]["converted"], 0)
            self.assertEqual(result["physical_conversion"]["total"], 5)
            self.assertEqual(result["next_blocker"], "BT0_HEPAK")
            self.assertEqual(result["formal_engineering_delta"], 0)

    def test_non_hepak_manifest_does_not_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "receipts").mkdir()
            csvp = root / "receipts/he_reference_hepak_lowT_grid.csv"
            csvp.write_text("x\n1\n", encoding="utf-8")
            manifest = {
                "schema": "qps-hepak-lowt-grid-receipt/v1",
                "provider": "CoolProp",
                "csv_sha256": "bad",
                "status": "PASS",
            }
            (root / "receipts/he_reference_hepak_lowT_grid.csv.manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT0_HEPAK"]["converted"])

    def test_trivial_hepak_label_cannot_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "receipts").mkdir()
            csvp = root / "receipts/he_reference_hepak_lowT_grid.csv"
            csvp.write_text("x\n1\n", encoding="utf-8")
            manifest = {
                "schema": "qps-hepak-lowt-grid-receipt/v1",
                "provider": "HEPAK",
                "provider_version": "3.4",
                "status": "PASS",
                "unit_set": 1,
                "pressure_basis": "ABSOLUTE_PA",
                "execution_utc": "2026-09-22T12:00:00+00:00",
                "solve_policy": "H_FIRST_S_SECOND_TP_SOURCE_BOUND_DENSITY_LAST",
                "source_workbook_sha256": "a" * 64,
                "csv_sha256": hashlib.sha256(csvp.read_bytes()).hexdigest(),
                "row_count": 1,
                "state_ids": ["FAKE"],
            }
            (root / "receipts/he_reference_hepak_lowT_grid.csv.manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT0_HEPAK"]["converted"])

    def _write_trust_anchor(
        self,
        root: Path,
        workbook_sha: str,
        *,
        status: str = "ACTIVE_TRUST_ANCHOR",
        authority: str = "OWNER_SOURCE_ATTESTATION",
    ) -> Path:
        controls = root / "controls"
        controls.mkdir(exist_ok=True)
        anchor = {
            "schema": "qps-hepak-source-trust-anchor/v1",
            "status": status,
            "authority": authority,
            "source_workbook": "CH15_HEPAK_QPLANT_Runtime_v0_1.xlsx",
            "source_workbook_sha256": workbook_sha if status == "ACTIVE_TRUST_ANCHOR" else None,
            "source_reference": {
                "kind": "owner_attested_source",
                "id": "UNIT-BOUNDARY",
            },
        }
        path = controls / "W326_HEPAK_SOURCE_TRUST_ANCHOR_v0.1.json"
        path.write_text(json.dumps(anchor), encoding="utf-8")
        return path

    def _write_valid_hepak_receipt(
        self,
        root: Path,
        *,
        with_active_anchor: bool = False,
    ) -> tuple[Path, Path]:
        receipts = root / "receipts"
        receipts.mkdir()
        csvp = receipts / "he_reference_hepak_lowT_grid.csv"
        workbook_sha = "b" * 64
        execution_utc = "2026-09-22T12:00:00+00:00"
        source_workbook = "CH15_HEPAK_QPLANT_Runtime_v0_1.xlsx"
        runtime_host = "QPS-HEPAK-WIN01"
        rows = []
        for state_id, (temperature_k, pressure_pa) in REQUIRED_HEPAK_STATES.items():
            row = {field: "" for field in HEPAK_CSV_FIELDS}
            row.update(
                {
                    "state_id": state_id,
                    "reason": "governed_lowT_grid_state",
                    "temperature_K": str(temperature_k),
                    "pressure_Pa_abs": str(pressure_pa),
                    "enthalpy_J_kg": "1000.0",
                    "entropy_J_kgK": "100.0",
                    "density_kg_m3": "10.0",
                    "cp_J_kgK": "5000.0",
                    "cv_J_kgK": "3000.0",
                    "viscosity_Pa_s": "1e-6",
                    "thermal_conductivity_W_mK": "0.02",
                    "quality": "",
                    "gibbs_J_kg": "",
                    "dT_lambda_isochoric_K": "",
                    "dT_lambda_isobaric_K": "",
                    "superfluid_density_fraction": "",
                    "lambda_temperature_K": "",
                    "phase_status": "SINGLE_PHASE_OR_QUALITY_UNDEFINED",
                    "solve_pair_used": "T+P_SOURCE_BOUND",
                    "provider": "HEPAK",
                    "provider_version": "3.4",
                    "unit_set": "1",
                    "pressure_basis": "ABSOLUTE_PA",
                    "source_workbook": source_workbook,
                    "source_workbook_sha256": workbook_sha,
                    "execution_utc": execution_utc,
                    "runtime_host": runtime_host,
                    "receipt_status": "PASS",
                }
            )
            row["row_sha256"] = _row_digest(row)
            rows.append(row)

        with csvp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEPAK_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        manifest = {
            "schema": "qps-hepak-lowt-grid-receipt/v1",
            "status": "PASS",
            "csv_path": csvp.name,
            "csv_sha256": hashlib.sha256(csvp.read_bytes()).hexdigest(),
            "source_workbook": source_workbook,
            "source_workbook_sha256": workbook_sha,
            "provider": "HEPAK",
            "provider_version": "3.4",
            "unit_set": 1,
            "pressure_basis": "ABSOLUTE_PA",
            "execution_utc": execution_utc,
            "runtime_host": runtime_host,
            "row_count": len(rows),
            "state_ids": [row["state_id"] for row in rows],
            "solve_policy": "H_FIRST_S_SECOND_TP_SOURCE_BOUND_DENSITY_LAST",
        }
        manp = receipts / "he_reference_hepak_lowT_grid.csv.manifest.json"
        manp.write_text(json.dumps(manifest), encoding="utf-8")
        if with_active_anchor:
            self._write_trust_anchor(root, workbook_sha)
        return csvp, manp

    def test_self_consistent_receipt_without_trust_anchor_does_not_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_valid_hepak_receipt(root)
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT0_HEPAK"]["converted"])
            self.assertIn("trust anchor", result["blockers"]["BT0_HEPAK"]["reason"])

    def test_pending_trust_anchor_does_not_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_valid_hepak_receipt(root)
            self._write_trust_anchor(
                root,
                "b" * 64,
                status="PENDING_TRUSTED_DIGEST",
                authority="OWNER_SOURCE_ATTESTATION_PENDING",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT0_HEPAK"]["converted"])
            self.assertIn("not active", result["blockers"]["BT0_HEPAK"]["reason"])

    def test_mismatched_trust_anchor_digest_does_not_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_valid_hepak_receipt(root)
            self._write_trust_anchor(root, "c" * 64)
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT0_HEPAK"]["converted"])
            self.assertIn("SHA256 mismatch", result["blockers"]["BT0_HEPAK"]["reason"])

    def test_active_trust_anchor_allows_contract_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_valid_hepak_receipt(root, with_active_anchor=True)
            result = evaluate(root)
            self.assertTrue(result["blockers"]["BT0_HEPAK"]["converted"])
            self.assertEqual(result["physical_conversion"]["converted"], 1)

    def test_ninth_extra_hepak_state_does_not_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csvp, manp = self._write_valid_hepak_receipt(root, with_active_anchor=True)
            rows = list(csv.DictReader(csvp.open(newline="", encoding="utf-8")))
            extra = dict(rows[-1])
            extra["state_id"] = "EXTRA_UNGOVERNED_STATE"
            extra["reason"] = "ungoverned_extra_state"
            extra["row_sha256"] = _row_digest(extra)
            rows.append(extra)
            with csvp.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEPAK_CSV_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            manifest = json.loads(manp.read_text(encoding="utf-8"))
            manifest["row_count"] = len(rows)
            manifest["state_ids"] = [row["state_id"] for row in rows]
            manifest["csv_sha256"] = hashlib.sha256(csvp.read_bytes()).hexdigest()
            manp.write_text(json.dumps(manifest), encoding="utf-8")
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT0_HEPAK"]["converted"])
            self.assertIn(
                "exactly the governed eight states",
                result["blockers"]["BT0_HEPAK"]["reason"],
            )

    def test_null_manifest_source_identity_does_not_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _csvp, manp = self._write_valid_hepak_receipt(root, with_active_anchor=True)
            manifest = json.loads(manp.read_text(encoding="utf-8"))
            manifest["source_workbook"] = None
            manp.write_text(json.dumps(manifest), encoding="utf-8")
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT0_HEPAK"]["converted"])

    def test_corrupt_row_hash_does_not_convert_bt0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            csvp, manp = self._write_valid_hepak_receipt(root, with_active_anchor=True)
            rows = list(csv.DictReader(csvp.open(newline="", encoding="utf-8")))
            rows[0]["row_sha256"] = "0" * 64
            with csvp.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEPAK_CSV_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            manifest = json.loads(manp.read_text(encoding="utf-8"))
            manifest["csv_sha256"] = hashlib.sha256(csvp.read_bytes()).hexdigest()
            manp.write_text(json.dumps(manifest), encoding="utf-8")
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT0_HEPAK"]["converted"])

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

    def test_unrelated_numeric_geometry_does_not_convert_bt1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "segment_id": "LB-001",
                                "unrelated": 1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT1_LINEB_GEOMETRY"]["converted"])

    def test_empty_structured_geometry_values_do_not_convert_bt1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "segment_id": "LB-001",
                                "drawing_or_offer_locator": "P&ID-LB-001",
                                "revision": "C",
                                "material": "316L",
                                "DN_or_OD": "DN150",
                                "wall_or_schedule": "2.77 mm",
                                "ID_mm": 162.76,
                                "segment_length_m": 12.5,
                                "elevation_delta_m": 0.0,
                                "roughness_basis": "source-bound 316L",
                                "fittings_and_branch_local_losses": {"K_total": None},
                                "valve_K_or_Cv": {"Cv": None},
                                "QCELL_branch_position": {"chainage_m": None},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT1_LINEB_GEOMETRY"]["converted"])

    def test_boolean_structured_geometry_value_does_not_convert_bt1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            payload = {
                "segments": [{
                    "segment_id": "LB-001",
                    "drawing_or_offer_locator": "P&ID-LB-001",
                    "revision": "C",
                    "material": "316L",
                    "DN_or_OD": "DN150",
                    "wall_or_schedule": "2.77 mm",
                    "ID_mm": 162.76,
                    "segment_length_m": 12.5,
                    "elevation_delta_m": 0.0,
                    "roughness_basis": "source-bound 316L",
                    "fittings_and_branch_local_losses": {"K_total": 2.1},
                    "valve_K_or_Cv": {"Cv": True},
                    "QCELL_branch_position": {"chainage_m": 12.5},
                }]
            }
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            self.assertFalse(evaluate(root)["blockers"]["BT1_LINEB_GEOMETRY"]["converted"])

    def test_metadata_numeric_cannot_mask_invalid_bt1_engineering_value(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            payload = {
                "segments": [{
                    "segment_id": "LB-001",
                    "drawing_or_offer_locator": "P&ID-LB-001",
                    "revision": "C",
                    "material": "316L",
                    "DN_or_OD": "DN150",
                    "wall_or_schedule": "2.77 mm",
                    "ID_mm": 162.76,
                    "segment_length_m": 12.5,
                    "elevation_delta_m": 0.0,
                    "roughness_basis": "source-bound 316L",
                    "fittings_and_branch_local_losses": {
                        "K_total": None,
                        "source_page": 3,
                    },
                    "valve_K_or_Cv": {
                        "Cv": True,
                        "source_page": 3,
                    },
                    "QCELL_branch_position": {
                        "chainage_m": None,
                        "source_page": 3,
                    },
                }]
            }
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            self.assertFalse(
                evaluate(root)["blockers"]["BT1_LINEB_GEOMETRY"]["converted"]
            )

    def test_metadata_inside_semantic_container_cannot_mask_missing_value(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            payload = {
                "segments": [{
                    "segment_id": "LB-001",
                    "drawing_or_offer_locator": "P&ID-LB-001",
                    "revision": "C",
                    "material": "316L",
                    "DN_or_OD": "DN150",
                    "wall_or_schedule": "2.77 mm",
                    "ID_mm": 162.76,
                    "segment_length_m": 12.5,
                    "elevation_delta_m": 0.0,
                    "roughness_basis": "source-bound 316L",
                    "fittings_and_branch_local_losses": {
                        "K_total": {"value": None, "source_page": 3},
                    },
                    "valve_K_or_Cv": {
                        "Cv": {"value": None, "source_page": 3},
                    },
                    "QCELL_branch_position": {
                        "chainage_m": {"value": None, "source_page": 3},
                    },
                }]
            }
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            self.assertFalse(
                evaluate(root)["blockers"]["BT1_LINEB_GEOMETRY"]["converted"]
            )

    def test_nested_engineering_value_under_semantic_key_converts_bt1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            payload = {
                "segments": [{
                    "segment_id": "LB-001",
                    "drawing_or_offer_locator": "P&ID-LB-001",
                    "revision": "C",
                    "material": "316L",
                    "DN_or_OD": "DN150",
                    "wall_or_schedule": "2.77 mm",
                    "ID_mm": 162.76,
                    "segment_length_m": 12.5,
                    "elevation_delta_m": 0.0,
                    "roughness_basis": "source-bound 316L",
                    "fittings_and_branch_local_losses": {
                        "K_total": {"value": 2.1, "source_page": 3},
                    },
                    "valve_K_or_Cv": {
                        "Cv": {"value": 50.0, "source_page": 3},
                    },
                    "QCELL_branch_position": {
                        "chainage_m": {"value": 12.5, "source_page": 3},
                    },
                }]
            }
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            self.assertTrue(
                evaluate(root)["blockers"]["BT1_LINEB_GEOMETRY"]["converted"]
            )

    def test_zero_source_bound_valve_loss_remains_valid_bt1_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            payload = {
                "segments": [{
                    "segment_id": "LB-001",
                    "drawing_or_offer_locator": "P&ID-LB-001",
                    "revision": "C",
                    "material": "316L",
                    "DN_or_OD": "DN150",
                    "wall_or_schedule": "2.77 mm",
                    "ID_mm": 162.76,
                    "segment_length_m": 12.5,
                    "elevation_delta_m": 0.0,
                    "roughness_basis": "source-bound 316L",
                    "fittings_and_branch_local_losses": {"K_total": 0.0},
                    "valve_K_or_Cv": {"K": 0.0},
                    "QCELL_branch_position": {"chainage_m": 0.0},
                }]
            }
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            self.assertTrue(evaluate(root)["blockers"]["BT1_LINEB_GEOMETRY"]["converted"])

    def test_substantive_geometry_json_converts_bt1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_selected_geometry_current.json").write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "segment_id": "LB-001",
                                "drawing_or_offer_locator": "P&ID-LB-001",
                                "revision": "C",
                                "material": "316L",
                                "DN_or_OD": "DN150",
                                "wall_or_schedule": "2.77 mm",
                                "ID_mm": 162.76,
                                "segment_length_m": 12.5,
                                "elevation_delta_m": 0.0,
                                "roughness_basis": "source-bound 316L",
                                "fittings_and_branch_local_losses": {"K_total": 2.1},
                                "valve_K_or_Cv": {"Cv": 50.0},
                                "QCELL_branch_position": {"chainage_m": 12.5},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = evaluate(root)
            self.assertTrue(result["blockers"]["BT1_LINEB_GEOMETRY"]["converted"])

    def _write_w57_bflow(
        self,
        path: Path,
        complete: bool,
        *,
        flow_value: float = 1.0,
        extra_config24_future: bool = False,
        tolerance: float | None = None,
        authority_class: str = "SOURCE_SUPPORTED",
    ) -> None:
        fieldnames = [
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
        if tolerance is not None:
            fieldnames.append("tolerance")

        cohorts = [("2K_OP", "config24", 24)]
        if complete:
            cohorts = [
                ("2K_OP", "config24", 24),
                ("2K_SB", "config24", 24),
                ("2K_OP", "config30", 30),
                ("2K_SB", "config30", 30),
            ]

        rows = []
        for mode, configuration, count in cohorts:
            cohort_rows = []
            for index in range(1, count + 1):
                cohort_rows.append(
                    {
                        "qcell_id": f"QC{index:02d}",
                        "installed_or_future": (
                            "installed" if index <= 24 else "future"
                        ),
                        "longitudinal_position": str(index * 3.0),
                        "mode": mode,
                        "configuration": configuration,
                        "B_flow_g_s": str(flow_value),
                        "source_locator": "FLOW-MATRIX-REV-A",
                        "authority_class": authority_class,
                        "mass_balance_residual": "0.0",
                    }
                )
            if extra_config24_future and configuration == "config24":
                cohort_rows.append(
                    {
                        "qcell_id": "QC25",
                        "installed_or_future": "future",
                        "longitudinal_position": "75.0",
                        "mode": mode,
                        "configuration": configuration,
                        "B_flow_g_s": str(flow_value),
                        "source_locator": "FLOW-MATRIX-REV-A",
                        "authority_class": authority_class,
                        "mass_balance_residual": "0.0",
                    }
                )

            cumulative = 0.0
            for row in sorted(
                cohort_rows,
                key=lambda item: float(item["longitudinal_position"]),
                reverse=True,
            ):
                cumulative += float(row["B_flow_g_s"])
                row["cumulative_segment_flow_g_s"] = str(cumulative)
                if tolerance is not None:
                    row["tolerance"] = str(tolerance)
            rows.extend(cohort_rows)

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_blank_bflow_row_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_qcell_bflow_current.csv").write_text(
                "qcell_id,installed_or_future,longitudinal_position,mode,configuration,"
                "B_flow_g_s,source_locator,authority_class,cumulative_segment_flow_g_s,"
                "mass_balance_residual\n"
                ",,,,,,,,,\n",
                encoding="utf-8",
            )
            self.assertFalse(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_uppercase_or_partial_bflow_population_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(path, complete=False)
            text = path.read_text(encoding="utf-8").replace("config24", "CONFIG24")
            path.write_text(text, encoding="utf-8")
            self.assertFalse(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_single_lowercase_cohort_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(path, complete=False)
            self.assertFalse(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_complete_w57_p09_bflow_population_converts_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(path, complete=True)
            self.assertTrue(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_open_source_required_authority_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(
                path,
                complete=True,
                authority_class="OPEN_SOURCE_REQUIRED",
            )
            result = evaluate(root)
            self.assertFalse(result["blockers"]["BT2_BFLOW"]["converted"])
            self.assertIn(
                "not an admitted source-bearing class",
                result["blockers"]["BT2_BFLOW"]["reason"],
            )

    def test_current_offer_source_bound_authority_converts_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(
                path,
                complete=True,
                authority_class="CURRENT_OFFER_SOURCE_BOUND",
            )
            self.assertTrue(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_explicit_future_rows_beyond_config24_minimum_remain_valid_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(
                path,
                complete=True,
                extra_config24_future=True,
            )
            self.assertTrue(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_inconsistent_reverse_cumulative_flow_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(path, complete=True)
            rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
            rows[0]["cumulative_segment_flow_g_s"] = "999.0"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            self.assertFalse(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_nonzero_residual_without_source_tolerance_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(path, complete=True)
            rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
            rows[0]["mass_balance_residual"] = "0.01"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            self.assertFalse(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_residual_inside_source_defined_tolerance_converts_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(path, complete=True, tolerance=0.02)
            rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
            rows[0]["mass_balance_residual"] = "0.01"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            self.assertTrue(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_residual_above_source_defined_tolerance_does_not_convert_bt2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            path = receipts / "lineb_qcell_bflow_current.csv"
            self._write_w57_bflow(path, complete=True, tolerance=0.005)
            rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
            rows[0]["mass_balance_residual"] = "0.01"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            self.assertFalse(evaluate(root)["blockers"]["BT2_BFLOW"]["converted"])

    def test_temperature_only_hepak_row_does_not_convert_bt3(self):
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
            self.assertFalse(result["blockers"]["BT3_THERMAL_FIELD"]["converted"])

    def test_non_hepak_thermal_row_does_not_convert_bt3(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "lineb_spatial_thermal_field_current.csv").write_text(
                (
                    "segment_id,heat_leak_W_m_or_discrete_W,inlet_T_K,inlet_h_J_kg,"
                    "outlet_T_K,outlet_h_J_kg,phase,rho_kg_m3,mu_Pa_s,provider,"
                    "provider_version,HEPAK_anchor_or_validation_identity,source_locator\n"
                    "LB-1,1.0,3.6,1000,3.7,1010,VAPOR,1.2,1e-6,CoolProp,6.8,"
                    "B_OWNER_EXACT_GATE,THERMAL-REV-A\n"
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
                    "segment_id,heat_leak_W_m_or_discrete_W,inlet_T_K,inlet_h_J_kg,"
                    "outlet_T_K,outlet_h_J_kg,phase,rho_kg_m3,mu_Pa_s,provider,"
                    "provider_version,HEPAK_anchor_or_validation_identity,source_locator\n"
                    "LB-1,1.0,3.6,1000,3.7,1010,VAPOR,1.2,1e-6,HEPAK,3.4,"
                    "B_OWNER_EXACT_GATE,THERMAL-REV-A\n"
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

    def test_storage_only_applicant_does_not_convert_bt4(self):
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
                            },
                            {
                                "name": "LKT",
                                "storage_m3": 600,
                            },
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
                            "discharge_destination": "RECOVERY_HEADER",
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
                                "active_recovery_capacity_g_s": 100.0,
                                "start_delay_s": 3.0,
                                "initial_inventory_kg": 500.0,
                                "initial_temperature_K": 300.0,
                                "routing_sequence": ["LINE_S", "RECOVERY", "WSH"],
                                "source_locator": "ALAT-RECOVERY-REV-A",
                            },
                            {
                                "name": "LKT",
                                "active_recovery_capacity_g_s": 100.0,
                                "start_delay_s": 3.0,
                                "initial_inventory_kg": 500.0,
                                "initial_temperature_K": 300.0,
                                "routing_sequence": ["LINE_S", "RECOVERY", "WSH"],
                                "source_locator": "LKT-RECOVERY-REV-A",
                            },
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
                            "discharge_destination": "RECOVERY_HEADER",
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
