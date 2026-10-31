"""Contract tests for the Pages bundle that scripts/build_cryo_pages.py builds.

They run with only pytest installed and check the source the Pages build consumes: the portal
entry page, the hidden-file rule the JADE deploy readback relies on, the provenance overlay and
the artifact manifest. The full build (which needs GBOGEB/document-organization-system at the
recovered SHA) runs in the build-command of .github/workflows/pages.yml.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_cryo_pages.py"
EXERCISE = ROOT / "scripts" / "exercise_engineering_calc.mjs"
WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_cryo_pages", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bcp = _load_builder()


def test_entry_page_is_the_dashboard_portal():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert re.search(r"<title>\s*Q Engineering Tools — Dashboard Portal\s*</title>", html)
    assert "cryo_dashboard_v0_3_0" in html


def test_source_sha_is_the_same_in_builder_exercise_and_workflow():
    sha = bcp.SOURCE_SHA
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert f'"{sha}"' in EXERCISE.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert sha in workflow
    assert bcp.SOURCE_SUBTREE in workflow


def test_copy_portal_drops_hidden_names_and_build_inputs(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "pages.yml").write_text("x", encoding="utf-8")
    (repo / ".nojekyll").write_text("", encoding="utf-8")
    (repo / ".qps-source").mkdir()
    (repo / "index.html").write_text("<title>portal</title>", encoding="utf-8")
    (repo / "mission").mkdir()
    (repo / "mission" / "m.json").write_text("{}", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "s.py").write_text("", encoding="utf-8")
    payload = repo / "federation" / "w1" / "payload"
    (payload / ".github" / "workflows").mkdir(parents=True)
    (payload / ".github" / "workflows" / "carrier.yml").write_text("x", encoding="utf-8")
    (payload / "carrier.json").write_text("{}", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()

    bcp.copy_portal(repo, out)

    copied = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert copied == ["federation/w1/payload/carrier.json", "index.html"]
    assert not any(part.startswith(".") for p in out.rglob("*") for part in p.relative_to(out).parts)


def test_verify_source_rejects_a_drifted_blob(tmp_path):
    for rel in bcp.EXPECTED_BLOBS:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"not the recovered source\n")
    with pytest.raises(SystemExit, match="source blob mismatch"):
        bcp.verify_source(tmp_path)


def test_overlay_injects_trace_once_and_patches_exports(tmp_path):
    index = tmp_path / "index.html"
    index.write_text("<html><head><title>t</title></head><body></body></html>", encoding="utf-8")
    bcp.patch_html(index)
    bcp.patch_html(index)
    assert index.read_text(encoding="utf-8").count('src="./qps_trace.js"') == 1

    export = tmp_path / "export.js"
    export.write_text(
        "export function exportJson(state) {\n  const payload = {\n    version: state.version,\n  };\n}\n"
        "function csv() {\n  const csvLines = [\n    \"Metric,Value\",\n  ];\n}\n"
        "function json(state) {\n  return {\n    material: state.materialKey,\n  };\n}\n",
        encoding="utf-8",
    )
    bcp.patch_export(export)
    text = export.read_text(encoding="utf-8")
    assert text.startswith("// QPS derived-artifact overlay")
    assert "...qpsTraceCsvRows()," in text
    assert text.count("trace: qpsTrace(),") == 2


def test_trace_and_manifest_are_consistent(tmp_path):
    out = tmp_path / "_site"
    dest = out / "cryo_dashboard_v0_3_0"
    dest.mkdir(parents=True)
    (out / "index.html").write_text("<title>portal</title>", encoding="utf-8")
    target = "1" * 40

    trace = bcp.write_trace(dest, target)
    receipt = bcp.build_manifest(out, trace)

    stored = json.loads((dest / "qps_trace.json").read_text(encoding="utf-8"))
    assert stored["target_sha"] == target and stored["source_sha"] == bcp.SOURCE_SHA
    manifest_path = out / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert sorted(manifest["files"]) == [
        "cryo_dashboard_v0_3_0/qps_trace.js",
        "cryo_dashboard_v0_3_0/qps_trace.json",
        "index.html",
    ]
    assert receipt["file_count"] == 3
    assert receipt["artifact_manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert receipt["outcome"] == "SUCCESS"
