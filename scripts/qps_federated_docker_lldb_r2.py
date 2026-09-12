#!/usr/bin/env python3
"""W2F-R2: recurse only the first real Docker/LLDB red.

Run 34707611364 proved the exact QPS image builds, but lldb-server exits before
attach with `personality set failed: Operation not permitted`. Docker's default
seccomp profile blocks the personality/ptrace operations needed by a debugger.
This wrapper changes only the ephemeral debug-container launch: grant SYS_PTRACE
and use an unconfined seccomp profile. All payload hashes, debugger sequence,
acceptance checks, authority guards, and cleanup remain in the canonical W2F
executor.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import qps_federated_docker_lldb as base

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "qps_debug"
RECEIPT = OUT / "qps_federated_docker_lldb_receipt.json"

_original_run = base.run


def run_with_debug_security(args: list[str], timeout: int = 300) -> dict:
    patched = list(args)
    # Patch only the long-lived debug target launch. Diagnostic one-shot
    # `docker run --rm ...` calls remain unchanged.
    if (
        len(patched) >= 3
        and patched[1:3] == ["run", "-d"]
        and patched[0].endswith("docker")
    ):
        patched = [
            patched[0],
            "run",
            "--cap-add=SYS_PTRACE",
            "--security-opt",
            "seccomp=unconfined",
            *patched[2:],
        ]
    return _original_run(patched, timeout)


def stamp_security_receipt() -> None:
    if not RECEIPT.exists():
        return
    payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
    payload["container_security"] = {
        "cap_add": ["SYS_PTRACE"],
        "seccomp": "unconfined",
        "scope": "EPHEMERAL_FEDERATED_DEBUG_CONTAINER_ONLY",
        "cause_receipt_run": 34707611364,
        "cause": "LLDB_SERVER_PERSONALITY_OPERATION_NOT_PERMITTED",
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
    base.run = run_with_debug_security
    rc = base.main()
    stamp_security_receipt()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
