from pathlib import Path
import importlib.util
import copy

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qps_m08_validate_native_excel_owner_reentry.py"

spec = importlib.util.spec_from_file_location("owner_validate", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


def good_receipt():
    return {
        "schema": mod.EXPECTED_SCHEMA,
        "status": mod.EXPECTED_STATUS,
        "source_repo": "GBOGEB/cryoplant-project",
        "source_commit": mod.EXPECTED_SOURCE_COMMIT,
        "payload_git_blobs": dict(mod.EXPECTED_BLOBS),
        "payload_blob_verification": "PASS_EXACT",
        "equation_version": mod.EXPECTED_EQUATION,
        "input_raw_sha256": mod.EXPECTED_RAW_SHA,
        "input_normalized_release_sha256": mod.EXPECTED_NORMALIZED_SHA,
        "native_receipt_sha256": "1" * 64,
        "native_status": "PASS_NATIVE_EXCEL_TECHNICAL_ROUNDTRIP_OPERATOR_DIALOG_CONFIRMATION_REQUIRED",
        "native_output_sha256": "2" * 64,
        "excel_version": "16.0",
        "excel_build": "12345",
        "host": "OWNERHOST",
        "user": "operator",
        "operator_confirmed_no_repair_dialog": True,
        "finalized_utc": "2026-09-18T16:45:00Z",
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def test_accepts_exact_owner_pass():
    out = mod.validate(good_receipt())
    assert out["status"] == "PASS_VALIDATED_OWNER_NATIVE_EXCEL_CLEAN_ROUNDTRIP"
    assert out["mip3_3p3_admission"] == "ADMITTED_BY_M08_NATIVE_EXCEL_GATE_SUBJECT_TO_QPS_CHILD_REENTRY"
    assert out["authority_transfer"] is False
    assert out["formal_credit_delta"] == 0


def test_rejects_stale_normalized_input():
    data = good_receipt()
    data["input_normalized_release_sha256"] = "3" * 64
    try:
        mod.validate(data)
    except AssertionError as exc:
        assert "normalized release SHA" in str(exc)
    else:
        raise AssertionError("stale normalized input must be rejected")


def test_rejects_source_blob_drift():
    data = good_receipt()
    data["payload_git_blobs"] = copy.deepcopy(data["payload_git_blobs"])
    data["payload_git_blobs"]["scripts/qps_w183_generate_offer_eval_workbook.py"] = "4" * 40
    try:
        mod.validate(data)
    except AssertionError as exc:
        assert "payload Git blob set drift" in str(exc)
    else:
        raise AssertionError("source blob drift must be rejected")


def test_rejects_missing_operator_confirmation():
    data = good_receipt()
    data["operator_confirmed_no_repair_dialog"] = False
    try:
        mod.validate(data)
    except AssertionError as exc:
        assert "operator no-repair confirmation" in str(exc)
    else:
        raise AssertionError("operator confirmation must be required")
