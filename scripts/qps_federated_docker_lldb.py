#!/usr/bin/env python3
"""Execute the exact QPS Docker/lldb-server primitive on a federated Linux runner."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runtime/debug/qps_federated_docker_manifest.json"
OUT = ROOT / "artifacts/qps_debug"
DOCKERFILE = ROOT / "triage/runtime_health/docker/Dockerfile.debug"


def run(args: list[str], timeout: int = 300) -> dict:
    try:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": args,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-20000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": args,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "timed out",
        }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_port(port: int, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.25)
    return False


def assigned_port(docker: str, container_id: str) -> int | None:
    result = run([docker, "port", container_id, "4711/tcp"], 30)
    if result["returncode"] != 0:
        return None
    for line in result["stdout"].splitlines():
        endpoint = line.strip()
        if endpoint.startswith("127.0.0.1:"):
            try:
                return int(endpoint.rsplit(":", 1)[1])
            except ValueError:
                return None
    return None


def write_receipt(payload: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    payload["receipt_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    path = OUT / "qps_federated_docker_lldb_receipt.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    file_checks = {}
    files_ok = True
    for rel, expected in manifest["files"].items():
        path = ROOT / rel
        observed = sha256(path)
        match = observed == expected["sha256"]
        file_checks[rel] = {
            "expected_sha256": expected["sha256"],
            "observed_sha256": observed,
            "git_blob_sha": expected["git_blob_sha"],
            "match": match,
        }
        files_ok = files_ok and match

    docker = shutil.which("docker")
    lldb = shutil.which("lldb")
    base = {
        "schema": "qps.federated_docker_lldb_receipt.v1",
        "receipt_id": "QPS-FEDERATED-DOCKER-LLDB-W2F-001",
        "created_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "classification": "MAINTENANCE_RUNTIME_ONLY",
        "source": {
            "repository": manifest["source_repository"],
            "exact_sha": manifest["source_exact_sha"],
            "file_checks": file_checks,
            "exact_payload_match": files_ok,
        },
        "executor": {
            "repository": os.getenv(
                "GITHUB_REPOSITORY",
                "GBOGEB/Q_engineering_tools",
            ),
            "exact_sha": os.getenv("GITHUB_SHA", "UNKNOWN"),
            "runner_name": os.getenv("RUNNER_NAME"),
            "runner_os": os.getenv("RUNNER_OS"),
            "runner_arch": os.getenv("RUNNER_ARCH"),
            "docker": docker,
            "lldb": lldb,
        },
        "authority_guards": {
            "qps_permanent_self_hosted_docker_gate": "WITHHELD_CAPACITY",
            "federated_primitive_pass_does_not_claim_permanent_pool_ready": True,
            "formal_engineering_credit_delta": 0,
            "negotiation_credit_delta": 0,
        },
    }

    if not files_ok:
        base.update(
            {
                "probe_status": "REJECT",
                "dov_status": "WITHHELD",
                "reason": "QPS_DOCKER_PAYLOAD_HASH_MISMATCH",
            }
        )
        write_receipt(base)
        return 2
    if not docker or not lldb:
        base.update(
            {
                "probe_status": "DEFER",
                "dov_status": "WITHHELD",
                "reason": "DOCKER_OR_HOST_LLDB_MISSING",
            }
        )
        write_receipt(base)
        return 3

    tag = f"qps-federated-debug:{manifest['source_exact_sha'][:12]}"
    build = run(
        [docker, "build", "-f", str(DOCKERFILE), "-t", tag, "."],
        900,
    )
    if build["returncode"] != 0:
        base.update(
            {
                "probe_status": "REJECT",
                "dov_status": "WITHHELD",
                "reason": "DOCKER_BUILD_FAILED",
                "build": build,
            }
        )
        write_receipt(base)
        return 2

    image_id = run(
        [docker, "image", "inspect", "--format", "{{.Id}}", tag],
        30,
    )["stdout"].strip()
    launch = run(
        [docker, "run", "-d", "--rm", "-p", "127.0.0.1::4711", tag],
        60,
    )
    container_id = launch["stdout"].strip()
    if launch["returncode"] != 0 or not container_id:
        base.update(
            {
                "probe_status": "REJECT",
                "dov_status": "WITHHELD",
                "reason": "CONTAINER_LAUNCH_FAILED",
                "build": build,
                "launch": launch,
            }
        )
        write_receipt(base)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    local_binary = OUT / "qps_docker_probe"
    host_port = None
    try:
        host_port = assigned_port(docker, container_id)
        ready = bool(host_port and wait_port(host_port))
        copy = run(
            [docker, "cp", f"{container_id}:/opt/qps-debug/probe", str(local_binary)],
            60,
        )
        if not host_port or not ready or copy["returncode"] != 0:
            base.update(
                {
                    "probe_status": "REJECT",
                    "dov_status": "WITHHELD",
                    "reason": "REMOTE_STUB_OR_SYMBOL_COPY_FAILED",
                    "container": {
                        "id": container_id,
                        "image": tag,
                        "image_id": image_id,
                    },
                    "port": {
                        "host": "127.0.0.1",
                        "host_port": host_port,
                        "container_port": 4711,
                        "scope": "loopback",
                    },
                    "port_ready": ready,
                    "copy": copy,
                }
            )
            write_receipt(base)
            return 2

        debug = run(
            [
                lldb,
                "--batch",
                "-o",
                f"target create {local_binary}",
                "-o",
                f"gdb-remote 127.0.0.1:{host_port}",
                "-o",
                "breakpoint set --name main",
                "-o",
                "continue",
                "-o",
                "thread step-over",
                "-o",
                "thread backtrace",
            ],
            180,
        )
        combined = f"{debug.get('stdout', '')}\n{debug.get('stderr', '')}"
        steps = (
            combined.count("stop reason")
            + combined.count("frame #")
            + combined.count("thread step-over")
        )
        observed_42 = "observed=42" in combined
        status = (
            "ACCEPT"
            if debug["returncode"] == 0 and steps > 0 and observed_42
            else "REJECT"
        )
        base.update(
            {
                "probe_status": status,
                "dov_status": "PASS" if status == "ACCEPT" else "WITHHELD",
                "reason": (
                    "EXACT_QPS_DOCKER_REMOTE_LLDB_ACCEPT"
                    if status == "ACCEPT"
                    else "REMOTE_LLDB_PROOF_FAILED"
                ),
                "build": {
                    "returncode": build["returncode"],
                    "image": tag,
                    "image_id": image_id,
                },
                "container": {"id": container_id},
                "port": {
                    "host": "127.0.0.1",
                    "host_port": host_port,
                    "container_port": 4711,
                    "scope": "loopback",
                    "allocation": "docker_dynamic_host_port",
                },
                "real_probe_steps": steps,
                "observed_value_42": observed_42,
                "debug": debug,
                "minimum_victory_condition": {
                    "exact_qps_payload_match": files_ok,
                    "docker_build_returncode_zero": build["returncode"] == 0,
                    "dynamic_loopback_port_observed": bool(host_port),
                    "remote_stub_reachable": ready,
                    "lldb_returncode_zero": debug["returncode"] == 0,
                    "real_probe_steps_gt_zero": steps > 0,
                    "observed_value_42": observed_42,
                },
            }
        )
        write_receipt(base)
        print(json.dumps(base, indent=2, sort_keys=True))
        return 0 if status == "ACCEPT" else 2
    finally:
        run([docker, "rm", "-f", container_id], 60)


if __name__ == "__main__":
    raise SystemExit(main())
