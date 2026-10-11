#!/usr/bin/env python3
"""Delete stale branches only when the deletion is provably lossless.

Each line of the list file is ``<branch>\\t<expected head SHA>\\t<mode>``, where
mode is ``delete`` (default when omitted) or ``archive``. A branch is removed
only when every guard holds at execution time:

* its live head SHA still equals the SHA recorded at triage (nothing new pushed);
* it is not the default branch and not protected;
* no open pull request uses it as head;
* ``delete``: every commit is already on the default branch (``ahead_by == 0``),
  or a merged pull request has exactly this head SHA (the commits stay
  reachable through ``refs/pull/<n>/head``);
* ``archive``: the head is first preserved as tag ``archive/<branch>`` and the
  tag is read back at the same SHA, so unmerged work stays one
  ``git push`` away from being a branch again.

Anything else is skipped with a reason, never deleted. The receipt lists the
restore command for every deleted branch. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

Api = Callable[..., Any]


def rate_limit_wait(exc: urllib.error.HTTPError, now: float) -> float | None:
    """Seconds to wait before retrying a rate-limited request, or None if not rate limited."""
    if exc.code not in (403, 429):
        return None
    retry_after = exc.headers.get("retry-after")
    if retry_after:
        return float(retry_after)
    if exc.headers.get("x-ratelimit-remaining") == "0":
        return max(float(exc.headers.get("x-ratelimit-reset", now)) - now, 0) + 5
    return None


def make_api(repo: str, token: str, max_waits: int = 8) -> Api:
    def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        for _ in range(max_waits):
            try:
                return request(method, path, body)
            except urllib.error.HTTPError as exc:
                wait = rate_limit_wait(exc, time.time())
                if wait is None:
                    raise
                print(f"rate limited; waiting {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
        return request(method, path, body)

    def request(method: str, path: str, body: dict[str, Any] | None) -> Any:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "branch-hygiene",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        if method != "GET":
            time.sleep(1)  # GitHub asks for >=1s between mutating requests
        return json.loads(payload) if payload else {}

    return call


MODES = {"delete", "archive"}
ARCHIVE_PREFIX = "archive/"


def parse_list(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 2:
            parts.append("delete")
        if len(parts) != 3 or len(parts[1]) != 40 or parts[2] not in MODES:
            raise SystemExit(
                f"malformed list line (want branch<TAB>40-char sha[<TAB>delete|archive]): {raw!r}"
            )
        rows.append((parts[0], parts[1], parts[2]))
    return rows


def assess(
    api: Api,
    branch: str,
    expected_sha: str,
    default_branch: str,
    mode: str = "delete",
    owner: str | None = None,
) -> dict[str, Any]:
    quoted = urllib.parse.quote(branch, safe="")
    row: dict[str, Any] = {"branch": branch, "expected_sha": expected_sha, "mode": mode}
    if branch == default_branch:
        return {**row, "action": "skip", "reason": "default_branch"}
    info = api("GET", f"/branches/{quoted}")
    if info is None:
        return {**row, "action": "skip", "reason": "already_absent"}
    live_sha = info["commit"]["sha"]
    row["live_sha"] = live_sha
    if info.get("protected"):
        return {**row, "action": "skip", "reason": "protected"}
    if live_sha != expected_sha:
        return {**row, "action": "skip", "reason": "head_moved_since_triage"}

    owner = owner or api("GET", "")["owner"]["login"]
    head = urllib.parse.quote(f"{owner}:{branch}", safe="")
    pulls = api("GET", f"/pulls?state=all&head={head}&per_page=100") or []
    if any(p["state"] == "open" for p in pulls):
        return {**row, "action": "skip", "reason": "open_pull_request"}

    if mode == "archive":
        tag = ARCHIVE_PREFIX + branch
        existing = api("GET", f"/git/ref/tags/{urllib.parse.quote(tag, safe='/')}")
        if existing and existing["object"]["sha"] != live_sha:
            return {
                **row,
                "action": "skip",
                "reason": "archive_tag_exists_at_other_sha",
            }
        return {
            **row,
            "action": "delete",
            "proof": "archived_as_tag",
            "archive_tag": tag,
        }

    compare = api(
        "GET", f"/compare/{urllib.parse.quote(default_branch, safe='')}...{quoted}"
    )
    ahead = compare.get("ahead_by") if compare else None
    if ahead == 0:
        return {**row, "action": "delete", "proof": "fully_merged_into_default"}
    merged = [
        p["number"]
        for p in pulls
        if p.get("merged_at") and p["head"]["sha"] == live_sha
    ]
    if merged:
        return {
            **row,
            "action": "delete",
            "proof": "merged_pull_request_head",
            "pull_request": merged[0],
            "retained_ref": f"refs/pull/{merged[0]}/head",
        }
    return {**row, "action": "skip", "reason": f"unmerged_commits_ahead_{ahead}"}


def archive(api: Api, tag: str, sha: str) -> None:
    ref = urllib.parse.quote(tag, safe="/")
    if not api("GET", f"/git/ref/tags/{ref}"):
        api("POST", "/git/refs", {"ref": f"refs/tags/{tag}", "sha": sha})
    readback = api("GET", f"/git/ref/tags/{ref}")
    if not readback or readback["object"]["sha"] != sha:
        raise SystemExit(f"archive tag {tag} did not read back at {sha}; branch kept")


def run(
    api: Api, repo: str, rows: list[tuple[str, str, str]], execute: bool
) -> dict[str, Any]:
    info = api("GET", "")
    default_branch, owner = info["default_branch"], info["owner"]["login"]
    results = []
    for branch, sha, mode in rows:
        try:
            result = assess(api, branch, sha, default_branch, mode, owner)
            if result["action"] == "delete":
                result["deleted"] = False
                if execute:
                    if result.get("archive_tag"):
                        archive(api, result["archive_tag"], result["live_sha"])
                    api(
                        "DELETE",
                        f"/git/refs/heads/{urllib.parse.quote(branch, safe='/')}",
                    )
                    result["deleted"] = True
                result["restore"] = (
                    f"git push origin {result['live_sha']}:refs/heads/{branch}"
                )
        except (SystemExit, urllib.error.URLError, KeyError, TypeError) as exc:
            # One bad branch must not abort the run; it is kept and reported.
            result = {
                "branch": branch,
                "expected_sha": sha,
                "mode": mode,
                "action": "error",
                "reason": str(exc)[:200],
                "deleted": False,
            }
        results.append(result)
    deleted = [r for r in results if r.get("deleted")]
    return {
        "schema": "branch-hygiene-receipt/v1",
        "repository": repo,
        "default_branch": default_branch,
        "mode": "execute" if execute else "dry_run",
        "listed": len(rows),
        "eligible": sum(r["action"] == "delete" for r in results),
        "deleted": len(deleted),
        "skipped": sum(r["action"] == "skip" for r in results),
        "errors": sum(r["action"] == "error" for r in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("list_file", type=Path)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument(
        "--execute", action="store_true", help="delete; default is dry run"
    )
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not args.repo or not token:
        raise SystemExit("need --repo (or GITHUB_REPOSITORY) and GITHUB_TOKEN")

    rows = parse_list(args.list_file.read_text(encoding="utf-8"))
    receipt = run(make_api(args.repo, token), args.repo, rows, args.execute)
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(payload, encoding="utf-8")
    print(payload, end="")
    print(
        f"{receipt['mode']}: {receipt['eligible']}/{receipt['listed']} lossless, "
        f"{receipt['deleted']} deleted, {receipt['skipped']} skipped, "
        f"{receipt['errors']} errors",
        file=sys.stderr,
    )
    return 1 if receipt["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
