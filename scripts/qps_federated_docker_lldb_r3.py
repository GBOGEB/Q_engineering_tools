#!/usr/bin/env python3
"""W2F-R5: preserve the single-client LLDB proof while bounding startup races.

R4 repaired the LLDB option/command argv pairs and proved the source-local
`observed = 42` value. The remaining Historian finding is narrower: Docker can
report the container running before lldb-server has reached its listen call.
A single immediate `gdb-remote` can therefore fail with an explicit connection
refusal even though the endpoint becomes ready moments later.

R5 never opens a raw TCP health connection. It retries the complete LLDB client
transaction only when the previous LLDB process explicitly reports
"connection refused", i.e. before a debugger session was established. Any other
failure remains first-red and is returned without retry.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import qps_federated_docker_lldb_r2 as r2

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "qps_debug"
RECEIPT = OUT / "qps_federated_docker_lldb_receipt.json"

_original_run = r2._original_run
_RETRY_DELAYS_S = (0.5, 1.0, 2.0)


def _explicit_connection_refused(result: dict) -> bool:
    combined = (
        f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
    ).lower()
    return result.get("returncode") != 0 and "connection refused" in combined


def run_with_value_observation(args: list[str], timeout: int = 300) -> dict:
    patched = list(args)
    is_lldb = (
        bool(patched)
        and patched[0].endswith("lldb")
        and "thread step-over" in patched
    )
    if is_lldb:
        try:
            bt_index = patched.index("thread backtrace")
        except ValueError:
            bt_index = len(patched)

        # LLDB batch commands are encoded as complete `-o`, `<command>` pairs.
        # Insert before the existing backtrace pair, never between its two argv
        # elements. This preserves the R4 repair exactly.
        insert_at = bt_index
        if bt_index > 0 and patched[bt_index - 1] == "-o":
            insert_at = bt_index - 1
        patched[insert_at:insert_at] = [
            "-o",
            "thread step-over",
            "-o",
            "frame variable observed",
        ]

    attempts = 1
    delays_used: list[float] = []
    result = _original_run(patched, timeout)

    if is_lldb:
        for delay_s in _RETRY_DELAYS_S:
            if not _explicit_connection_refused(result):
                break
            delays_used.append(delay_s)
            time.sleep(delay_s)
            attempts += 1
            result = _original_run(patched, timeout)

        result["readiness_retry"] = {
            "policy": "EXPLICIT_CONNECTION_REFUSED_ONLY",
            "attempts": attempts,
            "max_attempts": 1 + len(_RETRY_DELAYS_S),
            "retry_delays_s": delays_used,
            "raw_socket_probe_used": False,
            "single_client_rule_preserved": True,
            "final_connection_refused": _explicit_connection_refused(result),
        }

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
    retry = (payload.get("debug") or {}).get("readiness_retry")
    payload["readiness_control"] = retry or {
        "policy": "EXPLICIT_CONNECTION_REFUSED_ONLY",
        "attempts": 0,
        "max_attempts": 1 + len(_RETRY_DELAYS_S),
        "retry_delays_s": [],
        "raw_socket_probe_used": False,
        "single_client_rule_preserved": True,
        "final_connection_refused": None,
    }
    payload["readiness_control"]["historian_issue"] = (
        "GBOGEB/Q_engineering_tools#83"
    )
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
