#!/usr/bin/env python3
"""Validate the source-bound M08 owner/native-Excel re-entry receipt.

This is stricter than the historical generic W291 native-Excel receipt validator.
It accepts only the exact current W302 owner-input release identity and a clean
visible Microsoft Excel roundtrip with explicit operator no-repair confirmation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "qps.m08.native_excel_owner_reentry.v1"
EXPECTED_STATUS = "PASS_OWNER_NATIVE_EXCEL_CLEAN_ROUNDTRIP"
EXPECTED_SOURCE_COMMIT = "d2e495fca88752ed5efff82bd2466432ce5a8e35"
EXPECTED_RAW_SHA = "a01b53014681f8c154c349b273c9db9686abe6f7d00b0e03d9b10f6f685f226a"
EXPECTED_NORMALIZED_SHA = "de54d5ccf3da1afcf8d517d7c22244765073798e0572ee1beef14cd0d8b9b18e"
EXPECTED_EQUATION = "OFFER_EVAL_EQ_v1"
EXPECTED_BLOBS = {
    "controls/QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml": "52592fee795bd19d151f0b7612642d28f5a6a88d",
    "controls/QPS_OFFER_EVAL_EQUATION_CURRENT_v1.yaml": "2bda13cc9a5353986ebe6f9d3adc7a45e3a611c3",
    "controls/QPS_OFFER_EVAL_WORKBOOK_DELTA_2026-09-14_v1.yaml": "2eed4189bef5361bdf25ef79c2e7d1f32a18590e",
    "scripts/qps_w183_generate_offer_eval_workbook.py": "77b69c721d84434ac5c81269df757d95c512637a",
    "scripts/qps_ooxml_normalized_release_identity.py": "ad9c549a2b205d94dad80d33cd279487f321ac71",
    "scripts/qps_m08_native_excel_roundtrip.ps1": "0323123732a3b5897881f5c41654bf74fc15069f",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_sha(name: str, value: Any) -> str:
    require(isinstance(value, str) and SHA256_RE.fullmatch(value) is not None, f"{name} must be lowercase SHA-256")
    return value


def validate(data: dict[str, Any]) -> dict[str, Any]:
    require(data.get("schema") == EXPECTED_SCHEMA, "unexpected schema")
    require(data.get("status") == EXPECTED_STATUS, f"owner re-entry is not PASS: {data.get('status')!r}")
    require(data.get("source_repo") == "GBOGEB/cryoplant-project", "source repo drift")
    require(data.get("source_commit") == EXPECTED_SOURCE_COMMIT, "source commit drift")
    require(data.get("equation_version") == EXPECTED_EQUATION, "equation version drift")
    require(data.get("payload_blob_verification") == "PASS_EXACT", "payload blob verification not PASS")
    require(data.get("payload_git_blobs") == EXPECTED_BLOBS, "payload Git blob set drift")

    require_sha("input_raw_sha256", data.get("input_raw_sha256"))
    require_sha("input_normalized_release_sha256", data.get("input_normalized_release_sha256"))
    require(data["input_raw_sha256"] == EXPECTED_RAW_SHA, "owner input raw SHA does not match W302 release")
    require(data["input_normalized_release_sha256"] == EXPECTED_NORMALIZED_SHA, "owner input normalized release SHA does not match W302 release")

    require(data.get("native_status") == "PASS_NATIVE_EXCEL_TECHNICAL_ROUNDTRIP_OPERATOR_DIALOG_CONFIRMATION_REQUIRED", "native technical roundtrip state drift")
    require_sha("native_receipt_sha256", data.get("native_receipt_sha256"))
    require_sha("native_output_sha256", data.get("native_output_sha256"))
    require(bool(data.get("excel_version")), "excel_version missing")
    require(bool(data.get("host")), "host missing")
    require(bool(data.get("user")), "user missing")
    require(bool(data.get("finalized_utc")), "finalized_utc missing")
    require(data.get("operator_confirmed_no_repair_dialog") is True, "operator no-repair confirmation required")

    require(data.get("authority_transfer") is False, "authority_transfer must remain false")
    require(data.get("formal_credit_delta") == 0, "formal_credit_delta must remain zero")

    return {
        "schema": "qps.m08.native_excel_owner_reentry_validation.v1",
        "status": "PASS_VALIDATED_OWNER_NATIVE_EXCEL_CLEAN_ROUNDTRIP",
        "source_commit": EXPECTED_SOURCE_COMMIT,
        "input_raw_sha256": EXPECTED_RAW_SHA,
        "input_normalized_release_sha256": EXPECTED_NORMALIZED_SHA,
        "native_output_sha256": data["native_output_sha256"],
        "excel_version": data["excel_version"],
        "excel_build": data.get("excel_build"),
        "host": data["host"],
        "user": data["user"],
        "finalized_utc": data["finalized_utc"],
        "mip3_3p3_admission": "ADMITTED_BY_M08_NATIVE_EXCEL_GATE_SUBJECT_TO_QPS_CHILD_REENTRY",
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt", type=Path)
    ap.add_argument("--receipt-out", type=Path)
    args = ap.parse_args()

    data = json.loads(args.receipt.read_text(encoding="utf-8-sig"))
    require(isinstance(data, dict), "receipt root must be object")
    result = validate(data)
    if args.receipt_out:
        args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
