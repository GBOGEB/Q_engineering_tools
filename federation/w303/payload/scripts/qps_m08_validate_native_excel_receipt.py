#!/usr/bin/env python3
"""Validate a returned M08 native Microsoft Excel roundtrip receipt.

This validator is fail-closed. It accepts only a full PASS receipt from a real
Microsoft Excel runtime with explicit operator confirmation that no repair
dialog was observed. It does not create engineering, compliance, acceptance,
release, negotiation, or award credit.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require_sha(name: str, value: object) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise AssertionError(f"{name} must be lowercase SHA-256")
    return value


def validate(data: dict) -> dict:
    if data.get("schema") != "qps.m08.native_excel_roundtrip.v1":
        raise AssertionError("unexpected schema")
    if data.get("status") != "PASS_NATIVE_EXCEL_CLEAN_ROUNDTRIP":
        raise AssertionError(f"receipt status is not PASS: {data.get('status')!r}")
    if not data.get("excel_version"):
        raise AssertionError("excel_version missing")
    if data.get("open_save_close_reopen") is not True:
        raise AssertionError("open_save_close_reopen must be true")
    if data.get("repair_mode_observed") is not False:
        raise AssertionError("repair_mode_observed must be false")
    if data.get("table1_recovery_log_observed") is not False:
        raise AssertionError("table1_recovery_log_observed must be false")
    if data.get("operator_confirmed_no_repair_dialog") is not True:
        raise AssertionError("operator confirmation is required")
    if not data.get("host") or not data.get("user") or not data.get("timestamp_utc"):
        raise AssertionError("host/user/timestamp identity incomplete")
    input_sha = require_sha("governed_input_sha256", data.get("governed_input_sha256"))
    output_sha = require_sha("output_sha256", data.get("output_sha256"))
    if data.get("authority_transfer") is not False:
        raise AssertionError("authority_transfer must remain false")
    if data.get("formal_credit_delta") != 0:
        raise AssertionError("formal_credit_delta must remain 0")

    return {
        "status": "PASS_VALIDATED_NATIVE_EXCEL_CLEAN_ROUNDTRIP_RECEIPT",
        "governed_input_sha256": input_sha,
        "output_sha256": output_sha,
        "excel_version": data["excel_version"],
        "host": data["host"],
        "user": data["user"],
        "timestamp_utc": data["timestamp_utc"],
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "mip3_3p3_admission": "ADMITTED_BY_NATIVE_EXCEL_GATE_ONLY",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt", type=Path)
    args = ap.parse_args()
    data = json.loads(args.receipt.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise AssertionError("receipt root must be an object")
    print(json.dumps(validate(data), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
