from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

BLOCKERS = {
    "BT0_HEPAK": {
        "files": [
            "receipts/he_reference_hepak_lowT_grid.csv",
            "receipts/he_reference_hepak_lowT_grid.csv.manifest.json",
        ],
        "required": "licensed HEPAK CSV + manifest",
    },
    "BT1_LINEB_GEOMETRY": {
        "files": ["receipts/lineb_selected_geometry_current.json"],
        "required": "current selected Line-B geometry",
    },
    "BT2_BFLOW": {
        "files": ["receipts/lineb_qcell_bflow_current.csv"],
        "required": "per-QCELL B-flow population",
    },
    "BT3_THERMAL_FIELD": {
        "files": ["receipts/lineb_spatial_thermal_field_current.csv"],
        "required": "source-bound Line-B thermal/property field",
    },
    "BT4_SLINE_RECOVERY": {
        "files": ["receipts/sline_applicant_recovery_current.json"],
        "required": "applicant-specific S-line recovery + PSV receipt",
    },
}

REQUIRED_HEPAK_STATES = {
    "A_CONTRACT": (4.5, 300000.0),
    "A_LKT_SELECTED": (4.4, 300000.0),
    "B_OWNER_EXACT_GATE": (3.6, 2200.0),
    "B_CONTRACT_LKT": (3.8, 2600.0),
    "B_LOCAL_2K_26MBAR": (2.0, 2600.0),
    "B_LOCAL_2K_31MBAR": (2.0, 3100.0),
    "LAMBDA_NEAR": (2.1768, 2600.0),
    "NORMAL_BOILING_VALIDATION": (4.222, 101325.0),
}

HEPAK_NUMERIC_FIELDS = {
    "enthalpy_J_kg",
    "entropy_J_kgK",
    "density_kg_m3",
    "cp_J_kgK",
    "cv_J_kgK",
    "viscosity_Pa_s",
    "thermal_conductivity_W_mK",
}

HEPAK_CSV_FIELDS = (
    "state_id",
    "reason",
    "temperature_K",
    "pressure_Pa_abs",
    "enthalpy_J_kg",
    "entropy_J_kgK",
    "density_kg_m3",
    "cp_J_kgK",
    "cv_J_kgK",
    "viscosity_Pa_s",
    "thermal_conductivity_W_mK",
    "quality",
    "gibbs_J_kg",
    "dT_lambda_isochoric_K",
    "dT_lambda_isobaric_K",
    "superfluid_density_fraction",
    "lambda_temperature_K",
    "phase_status",
    "solve_pair_used",
    "provider",
    "provider_version",
    "unit_set",
    "pressure_basis",
    "source_workbook",
    "source_workbook_sha256",
    "execution_utc",
    "runtime_host",
    "receipt_status",
    "row_sha256",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _row_digest(row: dict[str, str]) -> str:
    payload = "|".join(
        f"{key}={row.get(key, '')}" for key in HEPAK_CSV_FIELDS if key != "row_sha256"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finite(row: dict[str, str], field: str) -> tuple[bool, str]:
    try:
        value = float(row.get(field, ""))
    except (TypeError, ValueError):
        return False, f"{row.get('state_id', '?')}: non-numeric {field}"
    if not math.isfinite(value):
        return False, f"{row.get('state_id', '?')}: non-finite {field}"
    return True, ""


def validate_bt0(root: Path) -> tuple[bool, str]:
    csvp = root / BLOCKERS["BT0_HEPAK"]["files"][0]
    manp = root / BLOCKERS["BT0_HEPAK"]["files"][1]
    if not csvp.exists() or not manp.exists():
        return False, "missing CSV and/or manifest"

    try:
        manifest = _json(manp)
    except Exception as exc:
        return False, f"invalid manifest: {exc}"

    if manifest.get("schema") != "qps-hepak-lowt-grid-receipt/v1":
        return False, "unexpected manifest schema"
    if str(manifest.get("provider", "")).upper() != "HEPAK":
        return False, "manifest provider is not HEPAK"
    if not str(manifest.get("provider_version", "")).strip():
        return False, "missing HEPAK provider_version"
    if str(manifest.get("status", "")).upper() != "PASS":
        return False, "manifest status is not PASS"
    if manifest.get("unit_set") != 1:
        return False, "manifest unit_set is not SI set 1"
    if manifest.get("pressure_basis") != "ABSOLUTE_PA":
        return False, "manifest pressure basis is not ABSOLUTE_PA"
    if not str(manifest.get("execution_utc", "")).strip():
        return False, "missing execution timestamp"
    if manifest.get("solve_policy") != "H_FIRST_S_SECOND_TP_SOURCE_BOUND_DENSITY_LAST":
        return False, "unexpected solve policy"
    source_sha = str(manifest.get("source_workbook_sha256", "")).lower()
    if not _SHA256_RE.fullmatch(source_sha):
        return False, "missing/invalid source workbook SHA256"
    if manifest.get("csv_sha256") != sha256(csvp):
        return False, "CSV SHA mismatch"

    try:
        with csvp.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            rows = list(reader)
    except Exception as exc:
        return False, f"invalid CSV: {exc}"

    missing_fields = sorted(set(HEPAK_CSV_FIELDS) - set(fields))
    if missing_fields:
        return False, f"missing HEPAK columns: {missing_fields}"
    if not rows:
        return False, "HEPAK CSV has no rows"
    if manifest.get("row_count") != len(rows):
        return False, "manifest row_count does not match CSV"

    manifest_state_ids = manifest.get("state_ids")
    if not isinstance(manifest_state_ids, list):
        return False, "manifest state_ids missing"
    csv_state_ids = [row.get("state_id", "") for row in rows]
    if len(csv_state_ids) != len(set(csv_state_ids)):
        return False, "duplicate state_id rows"
    if manifest_state_ids != csv_state_ids:
        return False, "manifest state_ids do not match CSV row order"

    by_state = {row["state_id"]: row for row in rows}
    missing_states = sorted(set(REQUIRED_HEPAK_STATES) - set(by_state))
    if missing_states:
        return False, f"missing required HEPAK states: {missing_states}"

    provider_version = str(manifest["provider_version"])
    for state_id, (expected_t, expected_p) in REQUIRED_HEPAK_STATES.items():
        row = by_state[state_id]
        if str(row.get("provider", "")).upper() != "HEPAK":
            return False, f"{state_id}: row provider is not HEPAK"
        if row.get("provider_version") != provider_version:
            return False, f"{state_id}: provider_version mismatch"
        if row.get("unit_set") != "1":
            return False, f"{state_id}: unit_set mismatch"
        if row.get("pressure_basis") != "ABSOLUTE_PA":
            return False, f"{state_id}: pressure basis mismatch"
        if row.get("receipt_status") != "PASS":
            return False, f"{state_id}: receipt_status is not PASS"
        if not row.get("solve_pair_used"):
            return False, f"{state_id}: missing solve_pair_used"
        if not row.get("execution_utc"):
            return False, f"{state_id}: missing execution_utc"
        if row.get("source_workbook_sha256", "").lower() != source_sha:
            return False, f"{state_id}: source workbook SHA mismatch"

        try:
            t_k = float(row["temperature_K"])
            p_pa = float(row["pressure_Pa_abs"])
        except (KeyError, TypeError, ValueError):
            return False, f"{state_id}: invalid state coordinates"
        if not math.isclose(t_k, expected_t, rel_tol=0.0, abs_tol=1e-9):
            return False, f"{state_id}: temperature mismatch"
        if not math.isclose(p_pa, expected_p, rel_tol=0.0, abs_tol=1e-6):
            return False, f"{state_id}: pressure mismatch"

        for field in HEPAK_NUMERIC_FIELDS:
            ok, reason = _finite(row, field)
            if not ok:
                return False, reason

        row_sha = row.get("row_sha256", "").lower()
        if not _SHA256_RE.fullmatch(row_sha):
            return False, f"{state_id}: invalid row SHA256"
        if row_sha != _row_digest(row):
            return False, f"{state_id}: row SHA mismatch"

    return True, f"validated HEPAK receipt with {len(rows)} rows"


def _substantive(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return bool(value) and all(_substantive(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(
            _substantive(key) and _substantive(item) for key, item in value.items()
        )
    return True


def _number(value: Any, *, positive: bool = False, nonnegative: bool = False) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(number):
        return False
    if positive and number <= 0:
        return False
    if nonnegative and number < 0:
        return False
    return True


def _numeric_leaves(value: Any) -> list[float]:
    leaves: list[float] = []
    if isinstance(value, dict):
        for child in value.values():
            leaves.extend(_numeric_leaves(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            leaves.extend(_numeric_leaves(child))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(float(value)):
            leaves.append(float(value))
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            pass
        else:
            if math.isfinite(number):
                leaves.append(number)
    return leaves


def validate_lineb_geometry_receipt(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing receipt"
    try:
        data = _json(path)
    except Exception as exc:
        return False, f"invalid JSON: {exc}"
    for field in ("source_locator", "revision"):
        if not _substantive(data.get(field)):
            return False, f"missing/substantive {field}"
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        return False, "segments must be a non-empty list"

    required = {
        "segment_id",
        "material",
        "DN_or_OD",
        "wall_or_schedule",
        "ID_mm",
        "segment_length_m",
        "elevation_delta_m",
        "roughness_basis",
        "fittings_and_branch_local_losses",
        "valve_K_or_Cv",
        "QCELL_branch_position",
    }
    seen: set[str] = set()
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            return False, f"segment {index}: not an object"
        missing = required - set(segment)
        if missing:
            return False, f"segment {index}: missing fields {sorted(missing)}"
        for field in required - {"elevation_delta_m"}:
            if not _substantive(segment.get(field)):
                return False, f"segment {index}: empty {field}"
        if not _number(segment.get("ID_mm"), positive=True):
            return False, f"segment {index}: invalid ID_mm"
        if not _number(segment.get("segment_length_m"), positive=True):
            return False, f"segment {index}: invalid segment_length_m"
        if not _number(segment.get("elevation_delta_m")):
            return False, f"segment {index}: invalid elevation_delta_m"
        segment_id = str(segment["segment_id"]).strip()
        if segment_id in seen:
            return False, f"duplicate segment_id: {segment_id}"
        seen.add(segment_id)
    return True, f"validated {len(segments)} source-bound Line-B segments"


BFLOW_FIELDS = {
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
}
BFLOW_MODES = {"2K_OP", "2K_SB"}
BFLOW_CONFIGURATIONS = {"config24", "config30"}


def validate_bflow_receipt(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing receipt"
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            rows = list(reader)
    except Exception as exc:
        return False, f"invalid CSV: {exc}"
    missing = BFLOW_FIELDS - fields
    if missing:
        return False, f"missing columns: {sorted(missing)}"
    if not rows:
        return False, "no data rows"

    populations: dict[tuple[str, str], set[str]] = {}
    positive_flow: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        for field in (
            "qcell_id",
            "installed_or_future",
            "longitudinal_position",
            "mode",
            "configuration",
            "source_locator",
            "authority_class",
        ):
            if not _substantive(row.get(field)):
                return False, f"row {index}: empty {field}"
        mode = row["mode"].strip()
        configuration = row["configuration"].strip()
        if mode not in BFLOW_MODES:
            return False, f"row {index}: unsupported mode {mode}"
        if configuration not in BFLOW_CONFIGURATIONS:
            return False, f"row {index}: unsupported configuration {configuration}"
        if not _number(row.get("B_flow_g_s"), nonnegative=True):
            return False, f"row {index}: invalid B_flow_g_s"
        if not _number(row.get("cumulative_segment_flow_g_s"), nonnegative=True):
            return False, f"row {index}: invalid cumulative_segment_flow_g_s"
        if not _number(row.get("mass_balance_residual")):
            return False, f"row {index}: invalid mass_balance_residual"

        key = (mode, configuration)
        qcell_id = row["qcell_id"].strip()
        population = populations.setdefault(key, set())
        if qcell_id in population:
            return False, f"row {index}: duplicate qcell_id {qcell_id} in {mode}/{configuration}"
        population.add(qcell_id)
        if float(row["B_flow_g_s"]) > 0:
            positive_flow.add(key)

    required_pairs = {
        (mode, configuration)
        for mode in BFLOW_MODES
        for configuration in BFLOW_CONFIGURATIONS
    }
    missing_pairs = sorted(required_pairs - set(populations))
    if missing_pairs:
        return False, f"missing mode/configuration populations: {missing_pairs}"
    for mode, configuration in sorted(required_pairs):
        minimum = int(configuration.removeprefix("config"))
        count = len(populations[(mode, configuration)])
        if count < minimum:
            return False, (
                f"{mode}/{configuration}: population {count} is below configuration count {minimum}"
            )
        if (mode, configuration) not in positive_flow:
            return False, f"{mode}/{configuration}: no positive B-flow row"
    return True, f"validated {len(rows)} source-bound per-QCELL B-flow rows"


THERMAL_FIELDS = {
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
}


def validate_thermal_field_receipt(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing receipt"
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            rows = list(reader)
    except Exception as exc:
        return False, f"invalid CSV: {exc}"
    missing = THERMAL_FIELDS - fields
    if missing:
        return False, f"missing columns: {sorted(missing)}"
    if not rows:
        return False, "no data rows"

    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        for field in (
            "segment_id",
            "phase",
            "provider",
            "provider_version",
            "HEPAK_anchor_or_validation_identity",
            "source_locator",
        ):
            if not _substantive(row.get(field)):
                return False, f"row {index}: empty {field}"
        if row["provider"].strip().upper() != "HEPAK":
            return False, f"row {index}: provider is not HEPAK"
        checks = {
            "heat_leak_W_m_or_discrete_W": {"nonnegative": True},
            "inlet_T_K": {"positive": True},
            "inlet_h_J_kg": {},
            "outlet_T_K": {"positive": True},
            "outlet_h_J_kg": {},
            "rho_kg_m3": {"positive": True},
            "mu_Pa_s": {"positive": True},
        }
        for field, options in checks.items():
            if not _number(row.get(field), **options):
                return False, f"row {index}: invalid {field}"
        segment_id = row["segment_id"].strip()
        if segment_id in seen:
            return False, f"duplicate segment_id: {segment_id}"
        seen.add(segment_id)
    return True, f"validated {len(rows)} source-bound HEPAK thermal-field rows"


def validate_sline_recovery_receipt(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing receipt"
    try:
        data = _json(path)
    except Exception as exc:
        return False, f"invalid JSON: {exc}"
    required = {"applicants", "pressure_hierarchy_bara", "psv", "source_locators"}
    missing = required - set(data)
    if missing:
        return False, f"missing keys: {sorted(missing)}"
    for field in required:
        if not _substantive(data.get(field)):
            return False, f"empty {field}"

    pressures = _numeric_leaves(data["pressure_hierarchy_bara"])
    if not pressures or any(value <= 0 for value in pressures):
        return False, "pressure_hierarchy_bara must contain positive numeric values"
    if not isinstance(data["psv"], dict):
        return False, "psv must be a structured object"
    psv_numbers = _numeric_leaves(data["psv"])
    if not psv_numbers or not any(value > 0 for value in psv_numbers):
        return False, "psv must contain a positive numeric design/set-point value"
    if isinstance(data["source_locators"], list) and not all(
        isinstance(item, str) and item.strip() for item in data["source_locators"]
    ):
        return False, "source_locators contains empty/non-text entries"
    return True, "validated applicant-specific S-line recovery/PSV receipt"


def evaluate(root: Path) -> dict[str, Any]:
    status: dict[str, dict[str, Any]] = {}
    ok, reason = validate_bt0(root)
    status["BT0_HEPAK"] = {"converted": ok, "reason": reason}

    ok, reason = validate_lineb_geometry_receipt(
        root / "receipts/lineb_selected_geometry_current.json"
    )
    status["BT1_LINEB_GEOMETRY"] = {"converted": ok, "reason": reason}

    ok, reason = validate_bflow_receipt(
        root / "receipts/lineb_qcell_bflow_current.csv"
    )
    status["BT2_BFLOW"] = {"converted": ok, "reason": reason}

    ok, reason = validate_thermal_field_receipt(
        root / "receipts/lineb_spatial_thermal_field_current.csv"
    )
    status["BT3_THERMAL_FIELD"] = {"converted": ok, "reason": reason}

    ok, reason = validate_sline_recovery_receipt(
        root / "receipts/sline_applicant_recovery_current.json"
    )
    status["BT4_SLINE_RECOVERY"] = {"converted": ok, "reason": reason}

    n = sum(1 for value in status.values() if value["converted"])
    total = len(status)
    return {
        "schema": "qps-hepak-mip-burndown/v1",
        "authority": "CONTROL_DIAGNOSTIC_ONLY",
        "formal_engineering_delta": 0,
        "strict_numerical_delta": 0,
        "blockers": status,
        "physical_conversion": {"converted": n, "total": total, "fraction": n / total},
        "bt0_priority_preserved": not status["BT0_HEPAK"]["converted"],
        "next_blocker": next(
            (key for key, value in status.items() if not value["converted"]),
            None,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("artifacts/hepak_mip_burndown.json"),
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=Path("artifacts/hepak_mip_burndown.md"),
    )
    args = parser.parse_args()
    result = evaluate(args.root)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# HEPAK MIP blocker burndown",
        "",
        (
            "Physical conversion: "
            f"**{result['physical_conversion']['converted']}/"
            f"{result['physical_conversion']['total']}**"
        ),
        f"Next blocker: **{result['next_blocker']}**",
        "",
    ]
    for key, value in result["blockers"].items():
        lines.append(
            f"- {key}: {'PASS' if value['converted'] else 'BLOCKED'} — {value['reason']}"
        )
    lines += [
        "",
        "Formal engineering delta: **0**",
        "Strict numerical delta: **0**",
    ]
    args.md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
