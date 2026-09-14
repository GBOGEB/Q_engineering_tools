#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

EXPECTED_SCHEMA = "qtools-w184-exact-payload-mirror/0.1.0"
EXPECTED_SOURCE_REPOSITORY = "GBOGEB/cryoplant-project"
EXPECTED_SOURCE_SHA = "8fe56e088514660babdd0002055ef99dec939eb6"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.reader(handle)) - 1


def fail(message: str) -> None:
    raise SystemExit(f"W184_MIRROR_FAIL: {message}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    root = args.mirror_root.resolve()
    manifest_path = root / "MANIFEST.json"
    if not manifest_path.is_file():
        fail(f"missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != EXPECTED_SCHEMA:
        fail(f"manifest schema mismatch: {manifest.get('schema_version')}")
    if manifest.get("source_repository") != EXPECTED_SOURCE_REPOSITORY:
        fail(f"source repository mismatch: {manifest.get('source_repository')}")
    if manifest.get("source_commit_sha") != EXPECTED_SOURCE_SHA:
        fail(f"source SHA mismatch: {manifest.get('source_commit_sha')}")
    if manifest.get("payload_mode") != "GOVERNED_SELF_CONTAINED_EXACT_HASH_MIRROR":
        fail("payload_mode is not governed exact-hash mirror")
    if manifest.get("private_runtime_credential_required") is not False:
        fail("mirror unexpectedly requires a private runtime credential")
    if manifest.get("repo_local_runner_923_compensated") is not False:
        fail("mirror must not claim compensation of cryoplant #923")
    if manifest.get("authority_transfer") is not False or manifest.get("formal_credit_delta") != 0:
        fail("mirror authority boundary was widened")

    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != 18:
        fail(f"expected exactly 18 governed source files, found {len(entries) if isinstance(entries, list) else 'invalid'}")

    expected_rel = []
    verified = []
    post_rows = 0
    for entry in entries:
        rel = entry.get("path")
        expected_blob = entry.get("source_git_blob_sha1")
        if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in Path(rel).parts:
            fail(f"unsafe manifest path: {rel!r}")
        if not isinstance(expected_blob, str) or len(expected_blob) != 40:
            fail(f"invalid source blob for {rel}: {expected_blob!r}")
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            fail(f"path escapes mirror root: {rel}")
        if not path.is_file():
            fail(f"missing governed file: {rel}")
        actual_blob = git_blob(path)
        if actual_blob != expected_blob:
            fail(f"source blob mismatch for {rel}: {actual_blob} != {expected_blob}")
        rows = None
        if "expected_rows" in entry:
            rows = csv_rows(path)
            if rows != int(entry["expected_rows"]):
                fail(f"row count mismatch for {rel}: {rows} != {entry['expected_rows']}")
            if entry.get("role") == "POST_N100_ACCEPTED_COHORT":
                post_rows += rows
        expected_rel.append(rel)
        verified.append({
            "path": rel,
            "role": entry.get("role"),
            "source_git_blob_sha1": expected_blob,
            "sha256": sha256(path),
            "rows": rows,
        })

    contract = manifest.get("post_n100_contract", {})
    expected_post_rows = int(contract.get("expected_total_rows", -1))
    if post_rows != expected_post_rows:
        fail(f"post-N100 total row mismatch: {post_rows} != {expected_post_rows}")

    actual_rel = sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file() and path.name != "MANIFEST.json"
    )
    if actual_rel != sorted(expected_rel):
        missing = sorted(set(expected_rel) - set(actual_rel))
        extra = sorted(set(actual_rel) - set(expected_rel))
        fail(f"payload closure mismatch missing={missing} extra={extra}")

    aggregate_material = "\n".join(
        f"{item['path']}|{item['source_git_blob_sha1']}|{item['sha256']}"
        for item in sorted(verified, key=lambda item: item["path"])
    ).encode("utf-8")
    aggregate_sha256 = hashlib.sha256(aggregate_material).hexdigest()

    receipt = {
        "schema_version": "qtools-w184-exact-payload-mirror-verification/0.1.0",
        "status": "PASS_EXACT_HASH_BOUND_SELF_CONTAINED_W184_PAYLOAD",
        "source_repository": EXPECTED_SOURCE_REPOSITORY,
        "source_commit_sha": EXPECTED_SOURCE_SHA,
        "payload_mode": manifest["payload_mode"],
        "manifest_git_blob_sha1": git_blob(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "verified_file_count": len(verified),
        "post_n100_verified_rows": post_rows,
        "aggregate_payload_sha256": aggregate_sha256,
        "files": verified,
        "private_runtime_credential_required": False,
        "repo_local_runner_923_compensated": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()

    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": receipt["status"],
        "source_commit_sha": receipt["source_commit_sha"],
        "verified_file_count": receipt["verified_file_count"],
        "post_n100_verified_rows": receipt["post_n100_verified_rows"],
        "aggregate_payload_sha256": receipt["aggregate_payload_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
