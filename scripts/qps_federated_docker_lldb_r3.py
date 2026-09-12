#!/usr/bin/env python3
"""W2F-R4: repair the R3 LLDB argv insertion without changing the proof target.

R2 proved the exact QPS payload, Docker build, ptrace/seccomp repair, container
lifetime, dynamic loopback port, symbol copy, gdb-remote attach and real LLDB
stepping. R3 correctly selected one extra step plus `frame variable observed`,
but inserted them between the final `-o` and its `thread backtrace` argument.
That produced `-o -o ...` and LLDB interpreted `thread step-over` as a target.

This repair preserves every prior runtime/security/authority invariant and only
inserts complete LLDB option-command pairs before the final backtrace pair.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import qps_federated_docker_lldb_r2 as r2

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "qps_debug"
RECEIPT = OUT / "qps_federated_docker_lldb_receipt.json"

_original_run = r2._original_run


def run_with_value_observation(args: list[str], timeout: int = 300) -> dict:
    patched = list(args)
    is_lldb = bool(patched) and patched[0].endswith("lldb") and "thread step-over" in patched
    if is_lldb:
        try:
            bt_index = patched.index("thread backtrace")
        except ValueError:
            bt_index = len(patched)

        # LLDB batch commands are encoded as complete `-o`, `<command>` pairs.
        # Insert before the existing backtrace pair, never between its two argv
        # elements. This is the sole R4 repair.
        insert_at = bt_index
        if bt_index > 0 and patched[bt_index - 1] == "-o":
            insert_at = bt_index - 1
        patched[insert_at:insert_at] = [
            "-o",
            "thread step-over",
            "-o",
            "frame variable observed",
        ]

    result = _original_run(patched, timeout)
    if is_lldb:
        stdout = result.get("stdout", "")
        # LLDB emits e.g. `(int) observed = 42`. Add the canonical marker only
        # after the debugger itself has proved the source-bound local value.
        if "observed = 42" in stdout and "observed=42" not in stdout:
            result["stdout"] = stdout + "\nobserved=42\n"
    return result


def stamp_observation_receipt() -> None:
    if not RECEIPT.exists():
        return
    payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
    payload["value_observation"] = {
        "mode": "LLDB_FRAME_VARIABLE_AFTER_SECOND_STEP",
        "source_local": "observed",
        "expected": 42,
        "canonical_marker_added_only_after_debugger_match": True,
        "cause_run": 34709211943,
        "cause": "R3_SPLIT_FINAL_LLD_OPTION_COMMAND_ARGV_PAIR",
        "repair": "INSERT_COMPLETE_OPTION_COMMAND_PAIRS_BEFORE_BACKTRACE_PAIR",
    }
    payload.pop("receipt_sha256", None)
    payload["receipt_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    RECEIPT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    r2._original_run = run_with_value_observation
    rc = r2.main()
    stamp_observation_receipt()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
