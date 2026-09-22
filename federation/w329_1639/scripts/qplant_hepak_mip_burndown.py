from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
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


BT0_TRUST_ANCHOR_PATH = Path("controls/W326_HEPAK_SOURCE_TRUST_ANCHOR_v0.1.json")
BT0_OWNER_SHA_ENV = "QPS_HEPAK_OWNER_SOURCE_SHA256"
BT0_OWNER_WORKBOOK_ENV = "QPS_HEPAK_OWNER_SOURCE_WORKBOOK"
_PROVENANCE_FORBIDDEN_TOKEN_RE = re.compile(
    r"(?:^|[^a-z0-9])(?:fixture|synthetic|placeholder|test)(?:$|[^a-z0-9])"
)


def _validate_bt0_trust_anchor(
    root: Path,
    *,
    source_workbook: str,
    source_sha256: str,
) -> tuple[bool, str]:
    anchor_path = root / BT0_TRUST_ANCHOR_PATH
    if not anchor_path.exists():
        return False, "trusted HEPAK source anchor missing"
    try:
        anchor = _json(anchor_path)
    except Exception as exc:
        return False, f"invalid trusted HEPAK source anchor: {exc}"
    if not isinstance(anchor, dict):
        return False, "trusted HEPAK source anchor must be an object"
    if anchor.get("schema") != "qps-hepak-source-trust-anchor/v1":
        return False, "unexpected trusted HEPAK source anchor schema"
    if anchor.get("status") != "ACTIVE_TRUST_ANCHOR":
        return False, "trusted HEPAK source anchor is not active"
    if anchor.get("authority") != "OWNER_SOURCE_ATTESTATION":
        return False, "trusted HEPAK source anchor authority is not owner attestation"

    owner_sha = os.environ.get(BT0_OWNER_SHA_ENV, "").strip().lower()
    owner_workbook = os.environ.get(BT0_OWNER_WORKBOOK_ENV, "").strip()
    if not _SHA256_RE.fullmatch(owner_sha):
        return False, "owner-controlled HEPAK SHA256 attestation missing/invalid"
    if not owner_workbook:
        return False, "owner-controlled HEPAK workbook identity missing"

    anchor_workbook = anchor.get("source_workbook")
    anchor_sha = anchor.get("source_workbook_sha256")
    source_reference = anchor.get("source_reference")
    if not isinstance(anchor_workbook, str) or not anchor_workbook.strip():
        return False, "trusted HEPAK anchor source_workbook missing"
    if not isinstance(anchor_sha, str) or not _SHA256_RE.fullmatch(anchor_sha.lower()):
        return False, "trusted HEPAK anchor source_workbook_sha256 missing/invalid"
    if not isinstance(source_reference, dict):
        return False, "trusted HEPAK anchor source_reference missing"
    if not isinstance(source_reference.get("kind"), str) or not source_reference["kind"].strip():
        return False, "trusted HEPAK anchor source_reference.kind missing"
    if not isinstance(source_reference.get("id"), str) or not source_reference["id"].strip():
        return False, "trusted HEPAK anchor source_reference.id missing"

    if anchor_workbook.strip() != source_workbook:
        return False, "trusted HEPAK anchor workbook identity mismatch"
    if anchor_sha.lower() != source_sha256:
        return False, "trusted HEPAK anchor workbook SHA256 mismatch"
    if owner_workbook != source_workbook or owner_workbook != anchor_workbook.strip():
        return False, "owner-controlled HEPAK workbook attestation mismatch"
    if owner_sha != source_sha256 or owner_sha != anchor_sha.lower():
        return False, "owner-controlled HEPAK SHA256 attestation mismatch"

    source_file = anchor.get("source_file")
    if source_file is not None:
        if not isinstance(source_file, str) or not source_file.strip():
            return False, "trusted HEPAK anchor source_file must be a non-empty relative path"
        relative_source = Path(source_file)
        if relative_source.is_absolute():
            return False, "trusted HEPAK anchor source_file must be relative"
        root_resolved = root.resolve()
        candidate = (root / relative_source).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            return False, "trusted HEPAK anchor source_file escapes governed root"
        if not candidate.exists():
            return False, "trusted HEPAK anchor source_file is unavailable"
        if sha256(candidate) != source_sha256:
            return False, "trusted HEPAK source_file SHA256 mismatch"

    return True, "trusted HEPAK source anchor matched"


def validate_bt0(root: Path) -> tuple[bool, str]:
    csvp = root / BLOCKERS["BT0_HEPAK"]["files"][0]
    manp = root / BLOCKERS["BT0_HEPAK"]["files"][1]
    if not csvp.exists() or not manp.exists():
        return False, "missing CSV and/or manifest"

    try:
        manifest = _json(manp)
    except Exception as exc:
        return False, f"invalid manifest: {exc}"
    if not isinstance(manifest, dict):
        return False, "HEPAK manifest must be an object"

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
    execution_utc = manifest.get("execution_utc")
    if not isinstance(execution_utc, str) or not execution_utc.strip():
        return False, "missing execution timestamp"
    if manifest.get("solve_policy") != "H_FIRST_S_SECOND_TP_SOURCE_BOUND_DENSITY_LAST":
        return False, "unexpected solve policy"

    source_sha_raw = manifest.get("source_workbook_sha256")
    source_workbook_raw = manifest.get("source_workbook")
    runtime_host_raw = manifest.get("runtime_host")
    if not isinstance(source_sha_raw, str) or not _SHA256_RE.fullmatch(source_sha_raw.lower()):
        return False, "missing/invalid source workbook SHA256"
    if not isinstance(source_workbook_raw, str) or not source_workbook_raw.strip():
        return False, "missing source workbook identity"
    if not isinstance(runtime_host_raw, str) or not runtime_host_raw.strip():
        return False, "missing runtime host identity"
    source_sha = source_sha_raw.lower()
    source_workbook = source_workbook_raw.strip()
    runtime_host = runtime_host_raw.strip()

    if _has_forbidden_provenance_token(source_workbook):
        return False, "test/synthetic source workbook is not production evidence"
    if _has_forbidden_provenance_token(runtime_host) or runtime_host.upper().startswith("TEST"):
        return False, "test/synthetic runtime host is not production evidence"

    trusted, reason = _validate_bt0_trust_anchor(
        root,
        source_workbook=source_workbook,
        source_sha256=source_sha,
    )
    if not trusted:
        return False, reason

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

    expected_state_ids = list(REQUIRED_HEPAK_STATES)
    if len(rows) != len(expected_state_ids):
        return False, "HEPAK CSV must contain exactly the governed eight states"
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
    if csv_state_ids != expected_state_ids:
        return False, "HEPAK CSV must contain exactly the governed eight states in canonical order"

    provider_version = str(manifest["provider_version"])
    for row, (state_id, (expected_t, expected_p)) in zip(
        rows,
        REQUIRED_HEPAK_STATES.items(),
        strict=True,
    ):
        if row.get("state_id") != state_id:
            return False, f"unexpected state order at {state_id}"
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
        if row.get("solve_pair_used") != "T+P_SOURCE_BOUND":
            return False, f"{state_id}: unexpected solve_pair_used"
        if row.get("execution_utc") != execution_utc:
            return False, f"{state_id}: execution timestamp mismatch"
        if row.get("source_workbook_sha256", "").lower() != source_sha:
            return False, f"{state_id}: source workbook SHA mismatch"
        if row.get("source_workbook", "").strip() != source_workbook:
            return False, f"{state_id}: source workbook identity mismatch"
        if row.get("runtime_host", "").strip() != runtime_host:
            return False, f"{state_id}: runtime host identity mismatch"
        for provenance_field in ("reason", "source_workbook", "runtime_host"):
            if _has_forbidden_provenance_token(row.get(provenance_field)):
                return False, (
                    f"{state_id}: synthetic/test {provenance_field} provenance "
                    "is not admissible"
                )
        if str(row.get("runtime_host", "")).upper().startswith("TEST"):
            return False, f"{state_id}: test runtime host is not admissible"

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

    return True, f"validated trusted HEPAK receipt with {len(rows)} governed rows"

def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_forbidden_provenance_token(value: Any) -> bool:
    return isinstance(value, str) and bool(
        _PROVENANCE_FORBIDDEN_TOKEN_RE.search(value.strip().lower())
    )


def _substantive_source_locator(value: Any) -> bool:
    if not _nonempty_text(value):
        return False
    normalized = value.strip().lower()
    forbidden = {
        "placeholder", "tbd", "todo", "unknown", "none", "null",
        "n/a", "na", "pending", "deferred",
    }
    return normalized not in forbidden and not _has_forbidden_provenance_token(value)


def _source_authority_valid(value: Any) -> bool:
    if not _nonempty_text(value):
        return False
    normalized = re.sub(r"[^A-Z0-9]+", "_", value.strip().upper()).strip("_")
    forbidden = {
        "PLACEHOLDER", "TBD", "TODO", "UNKNOWN", "NONE", "NULL",
        "NA", "N_A", "PENDING", "DEFERRED", "INFERRED", "DERIVED",
        "POSTULATED", "PLANNING",
    }
    if normalized in forbidden:
        return False
    return any(
        token in normalized
        for token in ("SOURCE", "SSOT", "CONTROLLED", "CONTRACT", "ATTESTATION")
    )


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def _finite_positive(value: Any) -> bool:
    return _finite_number(value) and float(value) > 0


def _finite_nonnegative(value: Any) -> bool:
    return _finite_number(value) and float(value) >= 0


def _contains_numeric(
    value: Any,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_numeric(item, positive=positive, nonnegative=nonnegative)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(
            _contains_numeric(item, positive=positive, nonnegative=nonnegative)
            for item in value
        )
    if positive:
        return _finite_positive(value)
    if nonnegative:
        return _finite_nonnegative(value)
    return _finite_number(value)


_ENGINEERING_VALUE_KEYS = {
    "value",
    "numeric_value",
    "magnitude",
    "nominal",
    "nominal_value",
    "design_value",
    "guaranteed_value",
    "measured_value",
}


def _bounded_numeric(
    value: Any,
    *,
    nonnegative: bool = False,
    positive: bool = False,
) -> bool:
    if isinstance(value, bool):
        return False
    if positive:
        return _finite_positive(value)
    if nonnegative:
        return _finite_nonnegative(value)
    return _finite_number(value)


def _semantic_payload_numeric(
    value: Any,
    *,
    nonnegative: bool = False,
    positive: bool = False,
) -> bool:
    """Accept a semantic payload numeric without inheriting unrelated metadata."""
    if isinstance(value, bool):
        return False
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")
            if normalized not in _ENGINEERING_VALUE_KEYS:
                continue
            if _semantic_payload_numeric(
                item,
                nonnegative=nonnegative,
                positive=positive,
            ):
                return True
        return False
    if isinstance(value, list):
        return any(
            _semantic_payload_numeric(
                item,
                nonnegative=nonnegative,
                positive=positive,
            )
            for item in value
        )
    return _bounded_numeric(
        value,
        nonnegative=nonnegative,
        positive=positive,
    )


def _engineering_numeric(
    value: Any,
    *,
    semantic_keys: set[str],
    nonnegative: bool = False,
    positive: bool = False,
    _direct: bool = True,
) -> bool:
    """Find engineering numerics without allowing metadata to satisfy the predicate."""
    if isinstance(value, bool):
        return False
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")
            if normalized in semantic_keys and _semantic_payload_numeric(
                item,
                nonnegative=nonnegative,
                positive=positive,
            ):
                return True
            if isinstance(item, (dict, list)) and _engineering_numeric(
                item,
                semantic_keys=semantic_keys,
                nonnegative=nonnegative,
                positive=positive,
                _direct=False,
            ):
                return True
        return False
    if isinstance(value, list):
        return any(
            _engineering_numeric(
                item,
                semantic_keys=semantic_keys,
                nonnegative=nonnegative,
                positive=positive,
                _direct=_direct,
            )
            for item in value
        )
    if not _direct:
        return False
    return _bounded_numeric(
        value,
        nonnegative=nonnegative,
        positive=positive,
    )


def _contains_positive_numeric(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_positive_numeric(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_positive_numeric(item) for item in value)
    if isinstance(value, bool):
        return False
    return _finite_positive(value)


def _source_locators_valid(value: Any) -> bool:
    if isinstance(value, str):
        return _nonempty_text(value)
    if isinstance(value, list):
        return bool(value) and all(_source_locators_valid(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(_source_locators_valid(item) for item in value.values())
    return False


def validate_bt1(path: Path) -> tuple[bool, str]:
    """Validate the full W57 selected-current Line-B geometry contract."""
    if not path.exists():
        return False, "missing receipt"
    try:
        data = _json(path)
    except Exception as exc:
        return False, f"invalid JSON: {exc}"

    if not isinstance(data, dict):
        return False, "geometry receipt must be an object"

    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        return False, "segments must be a non-empty list"

    required_text = {
        "segment_id",
        "drawing_or_offer_locator",
        "revision",
        "material",
        "roughness_basis",
    }
    required_numeric = {
        "ID_mm",
        "segment_length_m",
    }
    required_structured = {
        "DN_or_OD",
        "wall_or_schedule",
        "fittings_and_branch_local_losses",
        "valve_K_or_Cv",
        "QCELL_branch_position",
    }

    segment_ids: set[str] = set()
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict) or not segment:
            return False, f"segment #{index} must be a non-empty object"

        missing = (
            required_text
            | required_numeric
            | required_structured
            | {"elevation_delta_m"}
        ) - set(segment)
        if missing:
            return False, f"segment #{index} missing geometry fields: {sorted(missing)}"

        for field in required_text:
            if not _nonempty_text(segment.get(field)):
                return False, f"segment #{index} has empty {field}"

        for field in required_numeric:
            if not _finite_positive(segment.get(field)):
                return False, f"segment #{index} {field} must be finite and > 0"

        if not _finite_number(segment.get("elevation_delta_m")):
            return False, f"segment #{index} elevation_delta_m must be finite"

        for field in ("DN_or_OD", "wall_or_schedule"):
            value = segment.get(field)
            if isinstance(value, str):
                valid = _nonempty_text(value)
            else:
                valid = _finite_positive(value)
            if not valid:
                return False, f"segment #{index} has empty or invalid {field}"

        if not _engineering_numeric(
            segment.get("fittings_and_branch_local_losses"),
            semantic_keys={
                "k",
                "k_total",
                "equivalent_k",
                "loss",
                "loss_coefficient",
                "local_loss",
                "local_loss_coefficient",
                "minor_loss",
                "minor_loss_coefficient",
                "coefficient",
            },
            nonnegative=True,
        ):
            return False, (
                f"segment #{index} fittings_and_branch_local_losses "
                "must contain a finite nonnegative engineering value"
            )
        if not _engineering_numeric(
            segment.get("valve_K_or_Cv"),
            semantic_keys={
                "k",
                "kv",
                "cv",
                "valve_k",
                "valve_kv",
                "valve_cv",
                "k_value",
                "kv_value",
                "cv_value",
                "coefficient",
            },
            nonnegative=True,
        ):
            return False, (
                f"segment #{index} valve_K_or_Cv must contain a finite nonnegative value"
            )
        if not _engineering_numeric(
            segment.get("QCELL_branch_position"),
            semantic_keys={
                "position",
                "position_m",
                "chainage",
                "chainage_m",
                "station",
                "station_m",
                "longitudinal_position",
                "longitudinal_position_m",
            },
            nonnegative=True,
        ):
            return False, (
                f"segment #{index} QCELL_branch_position "
                "must contain a finite nonnegative position"
            )

        segment_id = segment["segment_id"].strip()
        if segment_id in segment_ids:
            return False, f"duplicate segment_id: {segment_id}"
        segment_ids.add(segment_id)

    return True, f"validated {len(segments)} complete W57 geometry segments"


def validate_bt2(path: Path) -> tuple[bool, str]:
    """Validate the complete W57 P09 per-QCELL B-flow contract."""
    required = {
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
    if not path.exists():
        return False, "missing receipt"
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            rows = list(reader)
    except Exception as exc:
        return False, f"invalid CSV: {exc}"

    missing = required - fields
    if missing:
        return False, f"missing W57 P09 columns: {sorted(missing)}"
    if not rows:
        return False, "no data rows"

    required_cohorts = {
        ("2K_OP", "config24"): 24,
        ("2K_SB", "config24"): 24,
        ("2K_OP", "config30"): 30,
        ("2K_SB", "config30"): 30,
    }
    cohorts: dict[tuple[str, str], list[dict[str, str]]] = {}

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
            if not _nonempty_text(row.get(field)):
                return False, f"row {index}: empty {field}"

        installed_state = row["installed_or_future"].strip().lower()
        if installed_state not in {"installed", "future"}:
            return False, f"row {index}: installed_or_future must be installed or future"
        if not _substantive_source_locator(row.get("source_locator")):
            return False, f"row {index}: source_locator is not substantive source evidence"
        if not _source_authority_valid(row.get("authority_class")):
            return False, f"row {index}: authority_class is not source/controlled authority"

        mode = row["mode"].strip()
        configuration = row["configuration"].strip()
        cohort = (mode, configuration)
        if cohort not in required_cohorts:
            return False, f"row {index}: unsupported governed cohort {cohort}"

        if not _finite_number(row.get("longitudinal_position")):
            return False, f"row {index}: longitudinal_position must be finite"
        if not _finite_nonnegative(row.get("B_flow_g_s")):
            return False, f"row {index}: B_flow_g_s must be finite and >= 0"
        if not _finite_nonnegative(row.get("cumulative_segment_flow_g_s")):
            return False, f"row {index}: cumulative_segment_flow_g_s must be finite and >= 0"
        if not _finite_number(row.get("mass_balance_residual")):
            return False, f"row {index}: mass_balance_residual must be finite"
        if "tolerance" in fields and str(row.get("tolerance", "")).strip():
            if not _finite_nonnegative(row.get("tolerance")):
                return False, f"row {index}: tolerance must be finite and >= 0"

        cohort_rows = cohorts.setdefault(cohort, [])
        qcell_id = row["qcell_id"].strip()
        if any(existing["qcell_id"].strip() == qcell_id for existing in cohort_rows):
            return False, f"row {index}: duplicate qcell_id {qcell_id} in {mode}/{configuration}"
        cohort_rows.append(row)

    missing_cohorts = sorted(set(required_cohorts) - set(cohorts))
    if missing_cohorts:
        return False, f"missing governed mode/configuration populations: {missing_cohorts}"

    # W57 defines accumulation from the farthest user back toward QRB/QDB.
    # This is an algebraic integrity check, not an engineering acceptance tolerance.
    abs_tol = 1e-9
    for cohort, expected_minimum in required_cohorts.items():
        cohort_rows = cohorts[cohort]
        if len(cohort_rows) < expected_minimum:
            return False, (
                f"{cohort[0]}/{cohort[1]} population {len(cohort_rows)} below "
                f"governed configuration minimum {expected_minimum}"
            )

        ordered = sorted(
            cohort_rows,
            key=lambda row: float(row["longitudinal_position"]),
            reverse=True,
        )
        positions = [float(row["longitudinal_position"]) for row in ordered]
        if len(positions) != len(set(positions)):
            return False, f"{cohort[0]}/{cohort[1]} has duplicate longitudinal positions"

        cumulative = 0.0
        for row in ordered:
            cumulative += float(row["B_flow_g_s"])
            supplied_cumulative = float(row["cumulative_segment_flow_g_s"])
            residual = float(row["mass_balance_residual"])
            if not math.isclose(
                supplied_cumulative,
                cumulative,
                rel_tol=0.0,
                abs_tol=abs_tol,
            ):
                return False, (
                    f"{cohort[0]}/{cohort[1]} {row['qcell_id']}: "
                    "cumulative_segment_flow_g_s is inconsistent with reverse-order "
                    "per-QCELL accumulation"
                )
            residual_abs = abs(residual)
            if residual == 0.0:
                continue
            tolerance_raw = row.get("tolerance", "")
            if not str(tolerance_raw).strip():
                return False, (
                    f"{cohort[0]}/{cohort[1]} {row['qcell_id']}: nonzero "
                    "mass_balance_residual requires source-defined tolerance"
                )
            tolerance = float(tolerance_raw)
            if residual_abs > tolerance:
                return False, (
                    f"{cohort[0]}/{cohort[1]} {row['qcell_id']}: "
                    "mass_balance_residual exceeds source-defined tolerance"
                )

    return True, f"validated {len(rows)} complete W57 P09 per-QCELL B-flow rows"


def validate_bt3(path: Path) -> tuple[bool, str]:
    """Validate the full W57 source-bound spatial thermal/property field."""
    required = {
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
    if not path.exists():
        return False, "missing receipt"
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            rows = list(reader)
    except Exception as exc:
        return False, f"invalid CSV: {exc}"

    missing = required - fields
    if missing:
        return False, f"missing thermal/property columns: {sorted(missing)}"
    if not rows:
        return False, "no data rows"

    segment_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        for field in (
            "segment_id",
            "phase",
            "provider_version",
            "HEPAK_anchor_or_validation_identity",
            "source_locator",
        ):
            if not _nonempty_text(row.get(field)):
                return False, f"row #{index} has empty {field}"

        if str(row.get("provider", "")).strip().upper() != "HEPAK":
            return False, f"row #{index} provider must be HEPAK"

        if not _finite_nonnegative(row.get("heat_leak_W_m_or_discrete_W")):
            return False, (
                f"row #{index} heat_leak_W_m_or_discrete_W must be finite and >= 0"
            )
        for field in ("inlet_T_K", "outlet_T_K", "rho_kg_m3", "mu_Pa_s"):
            if not _finite_positive(row.get(field)):
                return False, f"row #{index} {field} must be finite and > 0"
        for field in ("inlet_h_J_kg", "outlet_h_J_kg"):
            if not _finite_number(row.get(field)):
                return False, f"row #{index} {field} must be finite"

        segment_id = row["segment_id"].strip()
        if segment_id in segment_ids:
            return False, f"duplicate segment_id: {segment_id}"
        segment_ids.add(segment_id)

    return True, f"validated {len(rows)} complete W57 HEPAK thermal/property rows"


def _routing_sequence_valid(value: Any) -> bool:
    if isinstance(value, str):
        return _nonempty_text(value)
    if isinstance(value, list):
        return bool(value) and all(_nonempty_text(item) for item in value)
    return False


def validate_bt4(path: Path) -> tuple[bool, str]:
    """Validate W58 applicant-specific recovery initial state and protection."""
    if not path.exists():
        return False, "missing receipt"
    try:
        data = _json(path)
    except Exception as exc:
        return False, f"invalid JSON: {exc}"

    if not isinstance(data, dict):
        return False, "S-line receipt must be an object"

    applicants = data.get("applicants")
    if isinstance(applicants, list):
        applicant_rows = applicants
    elif isinstance(applicants, dict):
        applicant_rows = [
            dict(value, name=key) if isinstance(value, dict) and "name" not in value else value
            for key, value in applicants.items()
        ]
    else:
        return False, "applicants must be a non-empty list or object"

    if not applicant_rows:
        return False, "applicants must not be empty"

    by_name: dict[str, dict[str, Any]] = {}
    for index, applicant in enumerate(applicant_rows, start=1):
        if not isinstance(applicant, dict) or not applicant:
            return False, f"applicant #{index} must be a non-empty object"
        name = str(applicant.get("name", "")).strip().upper()
        if name not in {"ALAT", "LKT"}:
            return False, f"applicant #{index} name must be ALAT or LKT"
        if name in by_name:
            return False, f"duplicate applicant recovery object: {name}"
        by_name[name] = applicant

    missing_applicants = {"ALAT", "LKT"} - set(by_name)
    if missing_applicants:
        return False, f"missing applicant recovery evidence: {sorted(missing_applicants)}"

    numeric_positive = {
        "active_recovery_capacity_g_s",
        "initial_inventory_kg",
        "initial_temperature_K",
    }
    for name, applicant in by_name.items():
        for field in numeric_positive:
            if not _finite_positive(applicant.get(field)):
                return False, f"{name}: {field} must be finite and > 0"
        if not _finite_nonnegative(applicant.get("start_delay_s")):
            return False, f"{name}: start_delay_s must be finite and >= 0"
        if not _routing_sequence_valid(applicant.get("routing_sequence")):
            return False, f"{name}: routing_sequence must be non-empty"
        if not _nonempty_text(applicant.get("source_locator")):
            return False, f"{name}: source_locator must be non-empty"

    pressure = data.get("pressure_hierarchy_bara")
    if not isinstance(pressure, dict):
        return False, "pressure_hierarchy_bara must be an object"
    for key in ("minimum", "nominal", "maximum_current_protected_interface"):
        if not _finite_positive(pressure.get(key)):
            return False, f"pressure_hierarchy_bara.{key} must be finite and > 0"
    minimum = float(pressure["minimum"])
    nominal = float(pressure["nominal"])
    maximum = float(pressure["maximum_current_protected_interface"])
    if not minimum <= nominal <= maximum:
        return False, "pressure hierarchy must satisfy minimum <= nominal <= maximum"

    psv = data.get("psv")
    if not isinstance(psv, dict) or not psv:
        return False, "psv must be a non-empty object"
    for field in ("tag", "discharge_destination"):
        if not _nonempty_text(psv.get(field)):
            return False, f"psv.{field} must be source-bound and non-empty"
    if not _finite_positive(psv.get("set_pressure_bara")):
        return False, "psv.set_pressure_bara must be finite and > 0"
    if not _finite_positive(psv.get("reseat_pressure_bara")):
        return False, "psv.reseat_pressure_bara must be finite and > 0"
    if float(psv["reseat_pressure_bara"]) > float(psv["set_pressure_bara"]):
        return False, "psv reseat pressure cannot exceed set pressure"
    if float(psv["set_pressure_bara"]) <= maximum:
        return False, "psv set pressure must exceed the protected operating maximum"

    if not _source_locators_valid(data.get("source_locators")):
        return False, "source_locators must contain non-empty source locators"

    return True, "validated ALAT and LKT recovery initial state plus PSV protection"


def evaluate(root: Path) -> dict[str, Any]:
    status: dict[str, dict[str, Any]] = {}
    ok, reason = validate_bt0(root)
    status["BT0_HEPAK"] = {"converted": ok, "reason": reason}

    ok, reason = validate_bt1(
        root / "receipts/lineb_selected_geometry_current.json"
    )
    status["BT1_LINEB_GEOMETRY"] = {"converted": ok, "reason": reason}

    ok, reason = validate_bt2(root / "receipts/lineb_qcell_bflow_current.csv")
    status["BT2_BFLOW"] = {"converted": ok, "reason": reason}

    ok, reason = validate_bt3(
        root / "receipts/lineb_spatial_thermal_field_current.csv"
    )
    status["BT3_THERMAL_FIELD"] = {"converted": ok, "reason": reason}

    ok, reason = validate_bt4(
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
