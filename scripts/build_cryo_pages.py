#!/usr/bin/env python3
"""Build the hosted Engineering Outpost from an exact recovered source checkout.

The recovered dashboard remains authoritative in document-organization-system.
This builder verifies byte identity, copies the runtime closure, then applies a
small deterministic QPS provenance overlay to the derived Pages artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

SOURCE_REPO = "GBOGEB/document-organization-system"
SOURCE_SHA = "cea7bfb533c246c797ef43652579fe00a39dcd4d"
SOURCE_SUBTREE = "cryo_dashboard_v0_3_0/cryo_dashboard_v0_3_0"
OVERLAY_VERSION = "qps-m02a-w3-pages-overlay/v1"

EXPECTED_BLOBS = {
    "dashboard_modular.html": "87821e71561214f667bcba36f0531206001f3432",
    "style.css": "bae65e0fd1ed2e3ed4baef6cc6b734077767df68",
    "package.json": "34fe065a08876e758b4bf9ef704903b81e3a75a4",
    "ssot.json": "afa2a2f859779cd3cbea8d26fa96355630989c18",
    "bridge_manifest.json": "8e7e0bb4a597eb0f7710ca16bc6b5a335f5171e4",
    "VERSION": "a0099439809e86bfbb9e2e6dbc762c76bf3aec1b",
    "data/materials.json": "65be104be14dc694efb519c98e8939ae7184afec",
    "js/app_modular.js": "d85da55dc303f65dcac65c50ecebd3a53f3a4097",
    "js/materials.js": "2fff568b3b5f73874581a5004553f1046f7c15a4",
    "js/numerics.js": "2d23e1d0ac041d85e45ba157088c699b3f1c9fe6",
    "js/plots.js": "68aaa3947d728c4d59ab98b566e3149c799c663f",
    "js/export.js": "66ad3cc949b5c391cb9ce771422d35a269c7393a",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_source(source: Path) -> None:
    failures = []
    for rel, expected in EXPECTED_BLOBS.items():
        actual = git_blob_sha(source / rel)
        if actual != expected:
            failures.append({"path": rel, "expected": expected, "actual": actual})
    if failures:
        raise SystemExit("source blob mismatch: " + json.dumps(failures, indent=2))


def copy_portal(repo_root: Path, out: Path) -> None:
    ignored = {".git", ".github", ".qps-source", "_site", "mission", "scripts", "cryo_dashboard_v0_3_0"}
    for item in repo_root.iterdir():
        if item.name in ignored:
            continue
        target = out / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def patch_export(export_path: Path) -> None:
    text = export_path.read_text(encoding="utf-8")
    prelude = '''// QPS derived-artifact overlay; recovered source blob is recorded in qps_trace.json.\nfunction qpsTrace() { return globalThis.QPS_TRACE || null; }\nfunction qpsTraceCsvRows() {\n  const t = qpsTrace();\n  if (!t) return [];\n  return [\n    `QPS Trace Schema,${t.schema}`,\n    `QPS Target SHA,${t.target_sha}`,\n    `QPS Source SHA,${t.source_sha}`,\n    `QPS Materials Blob,${t.source_blobs["data/materials.json"]}`,\n    `QPS Numerics Blob,${t.source_blobs["js/numerics.js"]}`,\n    `QPS Material Evaluator Blob,${t.source_blobs["js/materials.js"]}`,\n    ""\n  ];\n}\n\n'''
    if not text.startswith("// QPS derived-artifact overlay"):
        text = prelude + text

    marker = '  const csvLines = [\n    "Metric,Value",'
    replacement = '  const csvLines = [\n    ...qpsTraceCsvRows(),\n    "Metric,Value",'
    if marker not in text:
        raise SystemExit("cannot patch modular CSV trace marker")
    text = text.replace(marker, replacement, 1)

    marker = '  return {\n    material: state.materialKey,'
    replacement = '  return {\n    trace: qpsTrace(),\n    material: state.materialKey,'
    if marker not in text:
        raise SystemExit("cannot patch modular JSON trace marker")
    text = text.replace(marker, replacement, 1)

    marker = 'export function exportJson(state) {\n  const payload = {\n    version: state.version,'
    replacement = 'export function exportJson(state) {\n  const payload = {\n    trace: qpsTrace(),\n    version: state.version,'
    if marker not in text:
        raise SystemExit("cannot patch legacy JSON trace marker")
    text = text.replace(marker, replacement, 1)

    export_path.write_text(text, encoding="utf-8")


def patch_html(index_path: Path) -> None:
    text = index_path.read_text(encoding="utf-8")
    inject = '  <script src="./qps_trace.js"></script>\n'
    if inject not in text:
        if "</head>" not in text:
            raise SystemExit("cannot inject qps_trace.js")
        text = text.replace("</head>", inject + "</head>", 1)
    index_path.write_text(text, encoding="utf-8")


def write_trace(dest: Path, target_sha: str) -> dict:
    trace = {
        "schema": "qps-engineering-outpost-trace/v1",
        "mission_id": "M02A",
        "product": "Q_engineering_tools/cryo_dashboard_v0_3_0",
        "target_repo": "GBOGEB/Q_engineering_tools",
        "target_sha": target_sha,
        "source_repo": SOURCE_REPO,
        "source_sha": SOURCE_SHA,
        "source_subtree": SOURCE_SUBTREE,
        "source_blobs": EXPECTED_BLOBS,
        "overlay_version": OVERLAY_VERSION,
        "authority_transfer": False,
        "engineering_acceptance": False,
        "evidence_class": "SOURCE_BOUND_HOSTED_ENGINEERING_TOOL",
    }
    payload = json.dumps(trace, indent=2, sort_keys=True) + "\n"
    (dest / "qps_trace.json").write_text(payload, encoding="utf-8")

    js_payload = json.dumps(trace, sort_keys=True, separators=(",", ":"))
    trace_js = f'''globalThis.QPS_TRACE = {js_payload};\n\ndocument.addEventListener("DOMContentLoaded", () => {{\n  const t = globalThis.QPS_TRACE;\n  const badge = document.createElement("aside");\n  badge.id = "qps-trace-badge";\n  badge.setAttribute("data-qps-trace-ready", "true");\n  badge.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:2000;padding:8px 10px;border-radius:8px;background:#0f172acc;color:#e2e8f0;font:12px/1.3 system-ui;border:1px solid #475569;box-shadow:0 4px 16px #0004";\n  badge.title = `Source ${{t.source_repo}}@${{t.source_sha}}`;\n  badge.textContent = `QPS trace · src ${{t.source_sha.slice(0,8)}} · build ${{t.target_sha.slice(0,8)}}`;\n  document.body.appendChild(badge);\n}});\n'''
    (dest / "qps_trace.js").write_text(trace_js, encoding="utf-8")
    return trace


def build_manifest(out: Path, trace: dict) -> dict:
    files = {}
    for path in sorted(p for p in out.rglob("*") if p.is_file() and p.name not in {"artifact_manifest.json", "qps-pages-build-receipt.json"}):
        files[path.relative_to(out).as_posix()] = sha256(path)
    manifest = {
        "schema": "qps-pages-artifact-manifest/v1",
        "target_sha": trace["target_sha"],
        "source_sha": trace["source_sha"],
        "files": files,
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path = out / "artifact_manifest.json"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    receipt = {
        "schema": "qps-pages-build-receipt/v1",
        "target_sha": trace["target_sha"],
        "source_sha": trace["source_sha"],
        "artifact_manifest_sha256": sha256(manifest_path),
        "file_count": len(files),
        "outcome": "SUCCESS",
        "authority_transfer": False,
        "engineering_acceptance": False,
    }
    (out / "qps-pages-build-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--out", default="_site")
    ap.add_argument("--target-sha", required=True)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    source = Path(args.source_root).resolve()
    out = Path(args.out).resolve()

    verify_source(source)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    copy_portal(repo_root, out)

    dest = out / "cryo_dashboard_v0_3_0"
    dest.mkdir(parents=True)
    shutil.copy2(source / "dashboard_modular.html", dest / "index.html")
    shutil.copy2(source / "style.css", dest / "style.css")
    shutil.copy2(source / "package.json", dest / "package.json")
    shutil.copy2(source / "ssot.json", dest / "source_ssot.json")
    shutil.copy2(source / "bridge_manifest.json", dest / "source_bridge_manifest.json")
    shutil.copy2(source / "VERSION", dest / "SOURCE_VERSION")
    shutil.copytree(source / "js", dest / "js")
    shutil.copytree(source / "data", dest / "data")

    trace = write_trace(dest, args.target_sha)
    patch_html(dest / "index.html")
    patch_export(dest / "js" / "export.js")

    required = [
        dest / "index.html",
        dest / "qps_trace.json",
        dest / "qps_trace.js",
        dest / "js" / "app_modular.js",
        dest / "js" / "materials.js",
        dest / "js" / "numerics.js",
        dest / "js" / "export.js",
        dest / "data" / "materials.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("missing built files: " + json.dumps(missing))
    if "Placeholder" in (dest / "index.html").read_text(encoding="utf-8"):
        raise SystemExit("placeholder survived product build")
    if "qpsTrace()" not in (dest / "js" / "export.js").read_text(encoding="utf-8"):
        raise SystemExit("export trace overlay missing")

    receipt = build_manifest(out, trace)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
