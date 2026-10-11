from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "branch_hygiene_delete.py"
spec = importlib.util.spec_from_file_location("branch_hygiene_delete", SCRIPT)
bh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bh)

SHA = "a" * 40
OTHER = "b" * 40


class FakeApi:
    def __init__(self, branches, pulls=None, ahead=None, tags=None):
        self.branches = dict(branches)
        self.pulls = pulls or {}
        self.ahead = ahead or {}
        self.tags = dict(tags or {})
        self.calls = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path))
        if path == "":
            return {"default_branch": "main", "owner": {"login": "GBOGEB"}}
        if method == "GET" and path.startswith("/branches/"):
            name = bh.urllib.parse.unquote(path[len("/branches/") :])
            if name not in self.branches:
                return None
            sha, protected = self.branches[name]
            return {"commit": {"sha": sha}, "protected": protected}
        if method == "GET" and path.startswith("/pulls?"):
            head = bh.urllib.parse.unquote(path.split("head=")[1].split("&")[0]).split(
                ":", 1
            )[1]
            return self.pulls.get(head, [])
        if method == "GET" and path.startswith("/compare/"):
            name = bh.urllib.parse.unquote(path.split("...", 1)[1])
            return {"ahead_by": self.ahead.get(name, 0)}
        if method == "GET" and path.startswith("/git/ref/tags/"):
            tag = path[len("/git/ref/tags/") :]
            return {"object": {"sha": self.tags[tag]}} if tag in self.tags else None
        if method == "POST" and path == "/git/refs":
            self.tags[body["ref"][len("refs/tags/") :]] = body["sha"]
            return {}
        if method == "DELETE" and path.startswith("/git/refs/heads/"):
            self.branches.pop(bh.urllib.parse.unquote(path[len("/git/refs/heads/") :]))
            return {}
        raise AssertionError(f"unexpected call {method} {path}")


def run(api, rows, execute=True):
    return {r["branch"]: r for r in bh.run(api, "GBOGEB/X", rows, execute)["results"]}


def test_parse_list_defaults_to_delete_and_rejects_bad_lines():
    assert bh.parse_list(f"# c\nfoo\t{SHA}\nbar\t{SHA}\tarchive\n") == [
        ("foo", SHA, "delete"),
        ("bar", SHA, "archive"),
    ]
    with pytest.raises(SystemExit):
        bh.parse_list("foo\tshort\n")
    with pytest.raises(SystemExit):
        bh.parse_list(f"foo\t{SHA}\tpurge\n")


def test_fully_merged_branch_is_deleted_with_restore_command():
    api = FakeApi({"done": (SHA, False)})
    r = run(api, [("done", SHA, "delete")])["done"]
    assert r["deleted"] is True and r["proof"] == "fully_merged_into_default"
    assert r["restore"] == f"git push origin {SHA}:refs/heads/done"
    assert "done" not in api.branches


def test_guards_skip_moved_protected_open_and_unmerged():
    api = FakeApi(
        {
            "moved": (OTHER, False),
            "prot": (SHA, True),
            "open": (SHA, False),
            "ahead": (SHA, False),
            "main": (SHA, False),
        },
        pulls={
            "open": [
                {"number": 1, "state": "open", "merged_at": None, "head": {"sha": SHA}}
            ]
        },
        ahead={"ahead": 3},
    )
    rows = [
        (b, SHA, "delete") for b in ("moved", "prot", "open", "ahead", "main", "gone")
    ]
    res = run(api, rows)
    assert res["moved"]["reason"] == "head_moved_since_triage"
    assert res["prot"]["reason"] == "protected"
    assert res["open"]["reason"] == "open_pull_request"
    assert res["ahead"]["reason"] == "unmerged_commits_ahead_3"
    assert res["main"]["reason"] == "default_branch"
    assert res["gone"]["reason"] == "already_absent"
    assert set(api.branches) == {"moved", "prot", "open", "ahead", "main"}


def test_squash_merged_pr_head_counts_as_lossless_only_at_same_sha():
    pulls = {
        "sq": [
            {"number": 7, "state": "closed", "merged_at": "x", "head": {"sha": SHA}}
        ],
        "later": [
            {"number": 8, "state": "closed", "merged_at": "x", "head": {"sha": OTHER}}
        ],
    }
    api = FakeApi(
        {"sq": (SHA, False), "later": (SHA, False)},
        pulls=pulls,
        ahead={"sq": 2, "later": 1},
    )
    res = run(api, [("sq", SHA, "delete"), ("later", SHA, "delete")])
    assert res["sq"]["retained_ref"] == "refs/pull/7/head" and res["sq"]["deleted"]
    assert res["later"]["action"] == "skip"


def test_archive_mode_tags_before_delete_and_dry_run_changes_nothing():
    api = FakeApi({"wip": (SHA, False)}, ahead={"wip": 5})
    dry = run(api, [("wip", SHA, "archive")], execute=False)["wip"]
    assert dry["deleted"] is False and not api.tags and "wip" in api.branches
    res = run(api, [("wip", SHA, "archive")])["wip"]
    assert res["archive_tag"] == "archive/wip" and api.tags["archive/wip"] == SHA
    assert "wip" not in api.branches


def test_archive_refuses_when_tag_points_elsewhere():
    api = FakeApi({"wip": (SHA, False)}, tags={"archive/wip": OTHER})
    res = run(api, [("wip", SHA, "archive")])["wip"]
    assert res["reason"] == "archive_tag_exists_at_other_sha" and "wip" in api.branches


def test_failing_branch_is_kept_and_reported_without_aborting_run():
    class Flaky(FakeApi):
        def __call__(self, method, path, body=None):
            if method == "DELETE" and path.endswith("/bad"):
                raise bh.urllib.error.URLError("boom")
            return super().__call__(method, path, body)

    api = Flaky({"bad": (SHA, False), "good": (SHA, False)})
    receipt = bh.run(
        api, "GBOGEB/X", [("bad", SHA, "delete"), ("good", SHA, "delete")], True
    )
    res = {r["branch"]: r for r in receipt["results"]}
    assert res["bad"]["action"] == "error" and res["bad"]["deleted"] is False
    assert res["good"]["deleted"] is True
    assert receipt["errors"] == 1 and "bad" in api.branches


def test_rate_limit_wait_uses_retry_after_or_reset_header():
    from email.message import Message

    def err(code, **headers):
        msg = Message()
        for k, v in headers.items():
            msg[k.replace("_", "-")] = v
        return bh.urllib.error.HTTPError("u", code, "x", msg, None)

    assert bh.rate_limit_wait(err(429, retry_after="30"), 0) == 30
    assert (
        bh.rate_limit_wait(
            err(403, x_ratelimit_remaining="0", x_ratelimit_reset="100"), 40
        )
        == 65
    )
    assert bh.rate_limit_wait(err(403), 0) is None
    assert bh.rate_limit_wait(err(500, retry_after="5"), 0) is None


def test_committed_lists_are_well_formed_and_unique():
    lists = sorted((SCRIPT.parents[1] / "governance" / "branch_hygiene").glob("*.tsv"))
    seen: set[str] = set()
    for path in lists:
        for branch, _sha, _mode in bh.parse_list(path.read_text(encoding="utf-8")):
            assert branch not in ("main", "master"), path
            assert branch not in seen, f"{branch} listed twice"
            seen.add(branch)


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.payload


def http_error(code, **headers):
    from email.message import Message

    msg = Message()
    for k, v in headers.items():
        msg[k.replace("_", "-")] = v
    return bh.urllib.error.HTTPError("u", code, "x", msg, None)


def test_make_api_sends_auth_parses_json_and_maps_404_to_none(monkeypatch):
    seen = []

    def fake_urlopen(req, timeout):
        seen.append(req)
        if req.full_url.endswith("/missing"):
            raise http_error(404)
        if req.full_url.endswith("/boom"):
            raise http_error(500)
        return FakeResponse(b'{"ok": true}' if req.get_method() == "GET" else b"")

    monkeypatch.setattr(bh.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(bh.time, "sleep", lambda s: None)
    api = bh.make_api("GBOGEB/X", "tok")
    assert api("GET", "/branches/a") == {"ok": True}
    assert api("GET", "/missing") is None
    assert api("DELETE", "/git/refs/heads/a") == {}
    with pytest.raises(bh.urllib.error.HTTPError):
        api("GET", "/boom")
    assert seen[0].full_url == "https://api.github.com/repos/GBOGEB/X/branches/a"
    assert seen[0].get_header("Authorization") == "Bearer tok"


def test_make_api_waits_out_rate_limit_then_retries(monkeypatch):
    calls = {"n": 0}
    slept = []

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise http_error(429, retry_after="7")
        return FakeResponse(b"{}")

    monkeypatch.setattr(bh.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(bh.time, "sleep", slept.append)
    assert bh.make_api("GBOGEB/X", "tok")("GET", "") == {}
    assert calls["n"] == 2 and slept == [7.0]


def test_archive_readback_mismatch_keeps_branch():
    class NoTag(FakeApi):
        def __call__(self, method, path, body=None):
            if method == "POST":
                return {}
            return super().__call__(method, path, body)

    api = NoTag({"wip": (SHA, False)}, ahead={"wip": 1})
    receipt = bh.run(api, "GBOGEB/X", [("wip", SHA, "archive")], True)
    assert receipt["results"][0]["action"] == "error"
    assert "wip" in api.branches


def test_main_writes_receipt_and_needs_token(monkeypatch, tmp_path):
    lst = tmp_path / "list.tsv"
    lst.write_text(f"done\t{SHA}\n", encoding="utf-8")
    receipt = tmp_path / "out" / "receipt.json"
    api = FakeApi({"done": (SHA, False)})
    monkeypatch.setattr(bh, "make_api", lambda repo, token: api)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(bh.sys, "argv", ["x", str(lst), "--repo", "GBOGEB/X"])
    with pytest.raises(SystemExit):
        bh.main()
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(
        bh.sys, "argv", ["x", str(lst), "--repo", "GBOGEB/X", "--receipt", str(receipt)]
    )
    assert bh.main() == 0
    data = bh.json.loads(receipt.read_text(encoding="utf-8"))
    assert (
        data["mode"] == "dry_run" and data["eligible"] == 1 and "done" in api.branches
    )
