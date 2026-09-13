#!/usr/bin/env python3
"""W163 MissionControl namespace collision validator.

Governance only: validate the canonical namespace contract, grandfathered aliases,
repository file identifiers and a bounded recent-PR census. No engineering authority.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

TEXT_SUFFIXES = {".html", ".htm", ".js", ".ts", ".md", ".yaml", ".yml", ".json", ".py"}
WAVE_RE = re.compile(r"\bW(\d{1,4})\b", re.IGNORECASE)
NAV_G_RE = re.compile(
    r"\bG(\d+)\s+(Board|Contract|Engineering|Evidence|Governance|Handover)\b",
    re.IGNORECASE,
)
NAV_ID_RE = re.compile(r"\bid\s*[:=]\s*['\"]G\d+['\"]", re.IGNORECASE)
NAV_GROUP_RE = re.compile(
    r"\bG[0-5]_(?:BOARD|CONTRACT_NEGOTIATION|ENGINEERING_ACCEPTANCE|"
    r"EVIDENCE_DELIVERY|GOVERNANCE_LINEAGE|HANDOVER)\b"
)
MISSION_ROMAN_RE = re.compile(r"\bMission\s+([IVXLCDM]+)\b", re.IGNORECASE)
DESCRIPTOR_PATHS = {
    "controls/QPS_MISSION_CONTROL_NAMESPACE_TAXONOMY_v1.yaml",
    "controls/QPS_MISSION_CONTROL_LEGACY_ALIAS_REGISTRY_v1.yaml",
}


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping")
    return data


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def validate_taxonomy(taxonomy: dict, errors: list[str]) -> None:
    namespaces = taxonomy.get("namespaces") or {}
    required = {"GM", "M", "H", "G", "W", "CH", "N", "REX"}
    missing = sorted(required - set(namespaces))
    if missing:
        fail(errors, f"taxonomy missing namespaces: {missing}")
    if (namespaces.get("G") or {}).get("reserved_exclusively_for") != "GOVERNED_GATES":
        fail(errors, "G must be reserved exclusively for governed gates")
    if (namespaces.get("CH") or {}).get("replaces_legacy_navigation_prefix") != "G":
        fail(errors, "CH must explicitly replace legacy navigation G")
    if (namespaces.get("REX") or {}).get("expansion") != "WITHHELD_NO_CANONICAL_EXPANSION_FOUND":
        fail(errors, "REX expansion must remain withheld until a canonical source defines it")
    rules = "\n".join(taxonomy.get("global_rules") or [])
    for fragment in ("historical collisions", "UI or navigation", "new bare W"):
        if fragment.lower() not in rules.lower():
            fail(errors, f"taxonomy global rules missing guard fragment: {fragment}")


def alias_index(aliases: dict, errors: list[str]):
    rows = aliases.get("legacy_aliases") or []
    ids: set[str] = set()
    pr_index: dict[tuple[str, int], list[dict]] = defaultdict(list)
    wave_index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    nav_paths: set[str] = set()
    for row in rows:
        alias_id = row.get("alias_id")
        if not alias_id or alias_id in ids:
            fail(errors, f"duplicate or missing alias_id: {alias_id!r}")
        ids.add(alias_id)
        repo = row.get("repo")
        if not repo:
            fail(errors, f"{alias_id}: repo missing")
            continue
        for pr in row.get("prs") or []:
            pr_index[(repo, int(pr))].append(row)
        token = str(row.get("historical_token") or "")
        if re.fullmatch(r"W\d+", token, re.IGNORECASE):
            wave_index[(repo, token.upper())].append(row)
        if row.get("collision_class") == "GOVERNED_GATE_PREFIX_USED_FOR_NAVIGATION":
            nav_paths.update(str(p) for p in (row.get("paths") or []))
    return rows, pr_index, wave_index, nav_paths


def validate_aliases(aliases: dict, errors: list[str]) -> tuple:
    rows, pr_index, wave_index, nav_paths = alias_index(aliases, errors)
    required_aliases = {
        "LEGACY-W153-COST",
        "LEGACY-W153-G5",
        "LEGACY-W152-REL",
        "LEGACY-W152-RTM",
        "LEGACY-NAV-G0-G5",
        "LEGACY-MISSION-I-COOLPROP",
        "LEGACY-GMI-W4-COOLPROP",
    }
    present = {row.get("alias_id") for row in rows}
    missing = sorted(required_aliases - present)
    if missing:
        fail(errors, f"legacy registry missing observed collision aliases: {missing}")

    w153 = wave_index.get(("GBOGEB/cryoplant-project", "W153"), [])
    identities = {row.get("canonical_qualified_identity") for row in w153}
    if identities != {"cryoplant:W153-COST", "cryoplant:W153-G5"}:
        fail(errors, "W153 same-repo collision must resolve to COST and G5 qualified identities")
    if not nav_paths:
        fail(errors, "legacy navigation alias must bind exact historical paths")
    return rows, pr_index, wave_index, nav_paths


def scan_repository_files(root: Path, nav_paths: set[str], errors: list[str], warnings: list[str]) -> int:
    checked = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in {".git", "node_modules", ".venv", "venv"} for part in path.parts):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        checked += 1
        rel = path.relative_to(root).as_posix()
        if rel in DESCRIPTOR_PATHS:
            continue
        if NAV_ID_RE.search(text) or NAV_GROUP_RE.search(text):
            if rel in nav_paths:
                warnings.append(f"grandfathered navigation G-prefix identifiers remain in {rel}")
            else:
                fail(errors, f"unregistered navigation G-prefix identifier in {rel}; use CH<n>")
    return checked


def registered_pr(pr_index: dict, repo: str, number: int, collision_class: str | None = None) -> bool:
    rows = pr_index.get((repo, number), [])
    if collision_class is None:
        return bool(rows)
    return any(row.get("collision_class") == collision_class for row in rows)


def scan_pr_records(records: list[dict], pr_index: dict, errors: list[str], warnings: list[str]) -> dict:
    wave_by_repo: dict[tuple[str, str], list[dict]] = defaultdict(list)
    wave_global: dict[str, list[dict]] = defaultdict(list)

    for pr in records:
        repo = str(pr.get("repository") or "")
        number = int(pr.get("number") or 0)
        title = str(pr.get("title") or "")
        body = str(pr.get("body") or "")

        for wave in {f"W{m}" for m in WAVE_RE.findall(title)}:
            wave_by_repo[(repo, wave.upper())].append(pr)
            wave_global[wave.upper()].append(pr)

        if NAV_G_RE.search(body) or NAV_G_RE.search(title):
            if not registered_pr(pr_index, repo, number, "GOVERNED_GATE_PREFIX_USED_FOR_NAVIGATION"):
                fail(errors, f"{repo}#{number}: bare G<n> used as navigation/chapter identifier")

        mission = MISSION_ROMAN_RE.search(title)
        if mission and "grand mission" not in title.lower():
            if not registered_pr(pr_index, repo, number, "GRAND_MISSION_DISPLAY_ALIAS_WITHOUT_GM_PREFIX"):
                fail(errors, f"{repo}#{number}: Mission {mission.group(1)} requires GM-* machine alias registration")

    for (repo, wave), prs in sorted(wave_by_repo.items()):
        if len(prs) < 2:
            continue
        uncovered = [pr for pr in prs if not registered_pr(pr_index, repo, int(pr.get("number") or 0))]
        if uncovered:
            nums = [int(pr.get("number") or 0) for pr in prs]
            fail(errors, f"{repo}: duplicate recent bare {wave} PR allocation not fully registered: {nums}")
        else:
            warnings.append(f"registered historical same-repo duplicate/family {repo}:{wave}")

    for wave, prs in sorted(wave_global.items()):
        repos = {str(pr.get("repository") or "") for pr in prs}
        if len(repos) < 2:
            continue
        uncovered = [
            pr
            for pr in prs
            if not registered_pr(pr_index, str(pr.get("repository") or ""), int(pr.get("number") or 0))
        ]
        if uncovered:
            ids = [f"{pr.get('repository')}#{pr.get('number')}" for pr in prs]
            fail(errors, f"cross-repo recent bare {wave} ambiguity not fully qualified/registered: {ids}")
        else:
            warnings.append(f"registered historical cross-repo duplicate/family {wave} across {sorted(repos)}")

    return {
        "recent_prs_scanned": len(records),
        "recent_wave_tokens": len(wave_global),
        "same_repo_duplicate_wave_groups": sum(1 for v in wave_by_repo.values() if len(v) > 1),
        "cross_repo_duplicate_wave_groups": sum(
            1 for v in wave_global.values() if len({str(p.get('repository') or '') for p in v}) > 1
        ),
    }


def fetch_recent_prs(owner: str, hours: int, token: str) -> list[dict]:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    stamp = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    query = f"user:{owner} is:pr updated:>={stamp}"
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode(
        {"q": query, "per_page": 100, "sort": "updated", "order": "desc"}
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "qps-w163-namespace-control",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    records: list[dict] = []
    for item in payload.get("items") or []:
        repo_url = str(item.get("repository_url") or "")
        marker = "/repos/"
        repo = repo_url.split(marker, 1)[1] if marker in repo_url else ""
        records.append(
            {
                "repository": repo,
                "number": item.get("number"),
                "title": item.get("title"),
                "body": item.get("body") or "",
                "updated_at": item.get("updated_at"),
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--taxonomy", default="controls/QPS_MISSION_CONTROL_NAMESPACE_TAXONOMY_v1.yaml")
    parser.add_argument("--aliases", default="controls/QPS_MISSION_CONTROL_LEGACY_ALIAS_REGISTRY_v1.yaml")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--recent-pr-json")
    parser.add_argument("--live-owner", default="GBOGEB")
    parser.add_argument("--recent-hours", type=int, default=48)
    parser.add_argument("--skip-live-pr-scan", action="store_true")
    parser.add_argument("--receipt")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    taxonomy = load_yaml(root / args.taxonomy)
    aliases = load_yaml(root / args.aliases)
    validate_taxonomy(taxonomy, errors)
    _, pr_index, _, nav_paths = validate_aliases(aliases, errors)
    files_scanned = scan_repository_files(root, nav_paths, errors, warnings)

    records: list[dict] = []
    pr_source = "NONE"
    if args.recent_pr_json:
        records = json.loads((root / args.recent_pr_json).read_text(encoding="utf-8"))
        pr_source = "BOUND_RECENT_PR_CENSUS"
    elif not args.skip_live_pr_scan:
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            records = fetch_recent_prs(args.live_owner, args.recent_hours, token)
            pr_source = "GITHUB_SEARCH"
        else:
            warnings.append("GITHUB_TOKEN absent: live recent-PR scan skipped")
            pr_source = "SKIPPED_NO_TOKEN"

    pr_stats = scan_pr_records(records, pr_index, errors, warnings) if records else {
        "recent_prs_scanned": 0,
        "recent_wave_tokens": 0,
        "same_repo_duplicate_wave_groups": 0,
        "cross_repo_duplicate_wave_groups": 0,
    }

    receipt = {
        "schema": "qps.w163.namespace_collision_receipt.v1",
        "status": "PASS_NAMESPACE_CONTROL" if not errors else "FAIL_NAMESPACE_CONTROL",
        "authority": "MISSION_CONTROL_DEVOPS_GOVERNANCE_ONLY",
        "head_sha": git_head(),
        "taxonomy": args.taxonomy,
        "aliases": args.aliases,
        "files_scanned": files_scanned,
        "pr_source": pr_source,
        "recent_hours": args.recent_hours,
        **pr_stats,
        "warnings": warnings,
        "errors": errors,
        "formal_credit_delta": {"engineering": 0, "compliance": 0, "negotiation": 0, "release": 0},
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        (root / args.receipt).write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
