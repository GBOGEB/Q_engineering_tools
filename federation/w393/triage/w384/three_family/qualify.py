"""W384 source-pinned, fail-closed three-family review qualification.

Four DISTINCT Git-tracked artifacts across Electrical SLD, MINERVA P&ID and
E-07 T-s. This is an evidence/processor scaling pilot, NOT a controlled-source
rebuild, engineering sign-off or original-PDF visual proof.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
import statistics
import time
from typing import Any
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = Path(__file__).with_name("sources.json")
FAMILIES = {"ELECTRICAL_SLD", "MECHANICAL_PID", "THERMAL_TS"}
CLASSES = {"DERIVED_REVIEW", "AS_DRAWN_SOURCE_MIRROR_NOT_OWNER_APPROVED",
           "DERIVED_DIGITISED_EVIDENCE"}
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
# Freeze evidence class and format as well as path; derivatives must not
# be promoted into another owner-originated source by relabelling.
COHORT_ROLES = {
    "EDB-SLD-OWNER": ("ELECTRICAL_SLD", "svg", "DERIVED_REVIEW"),
    "MINERVA-QCELL-ASDRAWN": (
        "MECHANICAL_PID", "svg", "AS_DRAWN_SOURCE_MIRROR_NOT_OWNER_APPROVED"),
    "MINERVA-QCELL-MAINLINES": ("MECHANICAL_PID", "svg", "DERIVED_REVIEW"),
    "LKT-E07-TS": ("THERMAL_TS", "json", "DERIVED_DIGITISED_EVIDENCE"),
}
# Hashes are frozen at original W384; rebaseline must be explicit, reviewed
# and versioned, never an implicit promotion via a swapped path/blob pair.
COHORT_SOURCE_PINS = {
    "EDB-SLD-OWNER": (
        "triage/w364/qpsdeck_pack/inputs/icd_el_001_rev1_2/"
        "ICD-EL-001_Drawing_1_Owner_Baseline.svg",
        "5d1f42291beb5ec248aa2f668de9660e9ff4afec"),
    "MINERVA-QCELL-ASDRAWN": (
        "assets/minerva_pid/data/svg/PFD-PID MINERVA QCELL-LB.svg",
        "8dbaa94e57213cde45916879802eb403dfaadfff"),
    "MINERVA-QCELL-MAINLINES": (
        "assets/minerva_pid/output_v5/QCELL/QCELL-MAINLINES_VIEW.svg",
        "fe325ba2b9430a6b2640306f878c8917a21066c0"),
    "LKT-E07-TS": (
        "triage/w375/e07_ts_digitise/case_stream.json",
        "206385eb53dc2b47d9315d875039c016829c793f"),
}
SVG_NS = "{http://www.w3.org/2000/svg}"


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(path: Path = DEFAULT_MANIFEST) -> list[dict]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    require(spec.get("schema") == "qps-three-family-provenance/1", "BAD_MANIFEST_SCHEMA")
    require(spec.get("review_only") is True and
            spec.get("engineering_approval") is False and
            spec.get("publication_approval") is False and
            spec.get("owner_source_verified") is False, "AUTHORITY_PROMOTION_DENIED")
    entries = spec.get("documents")
    require(isinstance(entries, list) and len(entries) == 4, "DISTINCT_SOURCE_COHORT_REQUIRED")
    require(len({e.get("id") for e in entries}) == 4, "DUPLICATE_SOURCE_ID")
    require(len({e.get("path") for e in entries}) == 4, "DUPLICATE_SOURCE_PATH")
    require({e.get("family") for e in entries} == FAMILIES, "THREE_FAMILIES_REQUIRED")
    require({e.get("id") for e in entries} == set(COHORT_ROLES),
            "FROZEN_SOURCE_ROLE_SET_DRIFT")
    for e in entries:
        require(e.get("classification") in CLASSES, "BAD_SOURCE_CLASSIFICATION")
        require((e.get("family"), e.get("format"), e.get("classification"))
                == COHORT_ROLES[e["id"]], "SOURCE_ROLE_OR_FORMAT_DRIFT")
        require(e.get("format") in ("svg", "json"), "UNKNOWN_SOURCE_FORMAT")
        require((e.get("path"), e.get("git_blob_sha1")) == COHORT_SOURCE_PINS[e["id"]],
                "SOURCE_PATH_AND_PIN_ROLE_DRIFT")
        require(isinstance(e.get("git_blob_sha1"), str) and
                bool(SHA1.fullmatch(e["git_blob_sha1"])), "BAD_PIN")
        require(isinstance(e.get("path"), str), "BAD_SOURCE_PATH")
        rel = Path(e["path"])
        require(not rel.is_absolute() and ".." not in rel.parts, "PATH_ESCAPE_DENIED")
        resolved = (ROOT / rel).resolve()
        require(resolved.is_relative_to(ROOT.resolve()), "PATH_ESCAPE_DENIED")
        require(resolved.is_file(), "SOURCE_MISSING:" + e["id"])
    return entries


def source_bytes(entry: dict) -> bytes:
    path = (ROOT / entry["path"]).resolve()
    require(path.is_relative_to(ROOT.resolve()) and path.is_file(),
            "PATH_ESCAPE_DENIED")
    data = path.read_bytes()
    require(len(data) <= 16 * 1024 * 1024, "SOURCE_TOO_LARGE")
    require(blob_sha1(data) == entry["git_blob_sha1"],
            "SOURCE_BLOB_DRIFT:" + entry["id"])
    return data


def raster_collision_probe(data: bytes) -> dict:
    """Source-only ink census; does not assert engineering-readable placement."""
    try:
        import cairosvg
        from PIL import Image
        rendered = cairosvg.svg2png(bytestring=data, output_width=480)
        # CairoSVG emits RGBA for transparent SVG canvases. Converting RGBA
        # directly to RGB retains hidden (0,0,0) channel values, fabricating
        # a fully black page and a false ALL_RASTER_ZONES_OBSTRUCTED root.
        # Composite onto opaque white first; opaque black ink remains black.
        rgba = Image.open(BytesIO(rendered)).convert("RGBA")
        page = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        page.alpha_composite(rgba)
        image = page.convert("RGB")
    except Exception as exc:
        raise ValueError("SVG_RASTER_RENDER_HOLD") from exc
    width, height = image.size
    require(0 < width <= 480 and 0 < height <= 1600, "RASTER_BOUNDS_UNSAFE")
    px = image.load()
    # Fixed 4x4 samples; a white sheet does not imply every symbol is readable.
    w, h = max(8, width // 6), max(8, height // 12)
    densities = []
    for fy in (.12, .30, .48, .66):
        for fx in (.08, .30, .52, .74):
            x = min(width - w, int(width * fx))
            y = min(height - h, int(height * fy))
            if x < 0 or y < 0:
                continue
            used = sum(1 for yy in range(y, y + h)
                       for xx in range(x, x + w)
                       if sum(px[xx, yy]) < 3 * 245)
            densities.append(used / (w * h))
    require(bool(densities), "NO_RASTER_SAMPLE_ZONES")
    minimum = min(densities)
    require(minimum < .95, "ALL_RASTER_ZONES_OBSTRUCTED")
    return {"width": width, "height": height,
            "candidate_zones": len(densities),
            "minimum_ink_fraction": round(minimum, 6),
            "visual_collision_acceptance": "DEFER_HUMAN",
            "raster_background": "TRANSPARENT_OVER_WHITE_FOR_INK_CENSUS",
            "source_ink_proof_only": True}


def check_svg(data: bytes, family: str) -> dict:
    upper = data.upper()
    require(b"<!DOCTYPE" not in upper and b"<!ENTITY" not in upper,
            "SVG_EXTERNAL_ENTITY_DENIED")
    root = ET.fromstring(data)
    require(root.tag == SVG_NS + "svg", "NOT_SVG")
    view = root.attrib.get("viewBox")
    require(isinstance(view, str), "SVG_VIEWBOX_MISSING")
    dims = [float(v) for v in view.replace(",", " ").split()]
    require(len(dims) == 4 and all(math.isfinite(v) for v in dims)
            and dims[2] > 0 and dims[3] > 0, "BAD_SVG_VIEWBOX")
    tags = {}
    for elem in root.iter():
        local = elem.tag.split("}")[-1]
        require(local not in ("script", "foreignObject"), "ACTIVE_SVG_CONTENT_DENIED")
        tags[local] = tags.get(local, 0) + 1
        for k, val in elem.attrib.items():
            attr = k.split("}")[-1]
            require(not attr.lower().startswith("on"), "ACTIVE_SVG_HANDLER_DENIED")
            if attr == "href":
                require(val.startswith("#") or val.startswith("data:"),
                        "EXTERNAL_SVG_RESOURCE_DENIED")
    require(tags.get("text", 0) >= 4, "NO_TEXTUAL_DIAGRAM_EVIDENCE")
    if family == "ELECTRICAL_SLD":
        require(b"ABOVE each battery-limit marker" in data and
                b"BELOW each battery-limit marker" in data and
                b"REVIEW ONLY" in data and
                b"SCK CEN OWNER SCOPE / UPSTREAM" not in data,
                "SLD_INTERFACE_REGRESSION")
    else:
        require(family == "MECHANICAL_PID" and
                (tags.get("line", 0) + tags.get("path", 0) +
                 tags.get("polyline", 0) + tags.get("rect", 0) >= 5),
                "PID_TOPOLOGY_EMPTY")
    return {"format": "SVG", "element_count": sum(tags.values()),
            "text_elements": tags.get("text", 0),
            "viewbox": dims, "raster": raster_collision_probe(data)}


def _overlap(a: list[float], b: list[float]) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def check_ts(data: bytes) -> dict:
    model = json.loads(data)
    cases = model.get("cases")
    require(isinstance(cases, list) and len(cases) == 33,
            "TS_CASE_COHORT_DRIFT")
    require([c.get("case") for c in cases] == list(range(1, 34)) and
            [c.get("page") for c in cases] == list(range(5, 38)),
            "TS_CASE_PAGE_DRIFT")
    require(model.get("source", {}).get("label") == "E-07",
            "TS_SOURCE_IDENTITY_DRIFT")
    boxes_count = 0
    overlaps = []
    expected_ports = {"A", "B", "D", "E", "W"}
    for case in cases:
        ports = case.get("ports")
        require(isinstance(ports, dict) and ports.get("A", {}).get("status") ==
                "UNATTRIBUTED", "TS_SUPPLY_A_FALSE_BIND")
        require(set(ports) == expected_ports, "TS_PORT_COHORT_DRIFT")
        boxes = []
        for label, datum in ports.items():
            bbox = datum.get("state_bbox")
            if datum.get("status") in ("BOUND", "BOUND_FLOW_ONLY"):
                require(bbox is not None, "TS_BOUND_PORT_BBOX_MISSING")
            if bbox is None:
                require(datum.get("status") not in ("BOUND", "BOUND_FLOW_ONLY"),
                        "TS_BBOX_MISSING")
                continue
            require(datum.get("status") in ("BOUND", "BOUND_FLOW_ONLY"),
                    "TS_BBOX_ON_UNATTRIBUTED_PORT")
            require(isinstance(bbox, list) and len(bbox) == 4 and
                    all(isinstance(x, (int, float)) and
                        math.isfinite(x) for x in bbox) and
                    bbox[2] > bbox[0] and bbox[3] > bbox[1],
                    "TS_BBOX_INVALID")
            boxes.append((label, bbox))
            boxes_count += 1
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if _overlap(boxes[i][1], boxes[j][1]):
                    overlaps.append((case["case"], boxes[i][0], boxes[j][0]))
    require(boxes_count == 75, "TS_BOUNDED_LABEL_COHORT_DRIFT")
    require(not overlaps, "TS_LABEL_COLLISION:" + repr(overlaps[:2]))
    return {"format": "CASE_STREAM_JSON", "cases": len(cases),
            "figure_pages": 33, "bounded_state_labels": boxes_count,
            "label_overlaps": len(overlaps),
            "source_pdf_replay": "DEFER_PROTECTED_ORIGINAL_E07",
            "engineering_approval": False}


def qualify(entry: dict) -> dict:
    started = time.perf_counter()
    raw = source_bytes(entry)
    semantics = check_svg(raw, entry["family"]) if entry["format"] == "svg" else check_ts(raw)
    return {"id": entry["id"], "family": entry["family"],
            "classification": entry["classification"],
            "source": entry["path"], "git_blob_sha1": entry["git_blob_sha1"],
            "sha256": sha256(raw), "byte_count": len(raw),
            "source_verification": "GIT_BLOB_SHA1_EXACT",
            "semantics": semantics,
            "duration_seconds": round(time.perf_counter() - started, 4),
            "engineering_approval": False, "publication_approval": False}


def pilot(entries: list[dict], workers: int = 1, repeats: int = 1) -> dict:
    require(type(workers) is int and 1 <= workers <= 4, "WORKER_BOUNDS")
    require(type(repeats) is int and 1 <= repeats <= 4, "REPEAT_BOUNDS")
    states = []
    for attempt in range(repeats):
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(qualify, entries))
        digests = [row["sha256"] for row in rows]
        require(len(set(digests)) == len(digests), "REUSED_SOURCE_BYTE_IDENTITY")
        signature = sha256(json.dumps([{k: v for k, v in r.items()
                                        if k != "duration_seconds"}
                                       for r in rows], sort_keys=True).encode())
        states.append({"signature": signature,
                       "elapsed_seconds": round(time.perf_counter()-started, 4),
                       "documents": len(rows), "rows": rows})
    require(len({a["signature"] for a in states}) == 1,
            "NONDETERMINISTIC_SEMANTIC_REPLAY")
    return {"schema": "qps-three-family-pilot/1",
            "head_cohort": "CURRENT_CHECKOUT_SOURCE_BLOBS",
            # Compatibility field: distinct tracked artifacts, not originals.
            "distinct_documents": len({e["path"] for e in entries}),
            "distinct_git_artifacts": len({e["path"] for e in entries}),
            "distinct_source_byte_digests": len({r["sha256"] for r in states[0]["rows"]}),
            "source_mirror_count": sum(e["classification"] ==
                "AS_DRAWN_SOURCE_MIRROR_NOT_OWNER_APPROVED" for e in entries),
            "derived_review_or_model_count": sum(e["classification"] in
                ("DERIVED_REVIEW", "DERIVED_DIGITISED_EVIDENCE") for e in entries),
            "owner_approved_original_count": 0,
            "same_population_1_to_4_to_5_scale": "WITHHELD_MISSING_FIVE_OWNER_ORIGINALS",
            "family_count": len({e["family"] for e in entries}),
            "workers": workers, "repeats": repeats,
            "semantic_replay": "PASS", "signature": states[0]["signature"],
            "elapsed_seconds": [s["elapsed_seconds"] for s in states],
            "median_seconds": statistics.median(s["elapsed_seconds"] for s in states),
            "evidence_level": "READ_ONLY_GIT_DERIVATIVE_AND_MIRROR",
            "owner_source_acceptance": "DEFER",
            "independent_visual_review": "DEFER",
            "engineering_approval": False, "publication_approval": False,
            "documents": states[0]["rows"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=sorted(FAMILIES), default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--receipt", type=Path)
    args = ap.parse_args()
    entries = read_manifest()
    if args.family:
        entries = [entry for entry in entries if entry["family"] == args.family]
    report = pilot(entries, workers=args.workers, repeats=args.repeats)
    if args.receipt:
        # A receipt is a new output, never a writable alias of a source,
        # manifest or previous run receipt. "x" prevents clobber/races.
        dest = args.receipt.resolve()
        protected = {DEFAULT_MANIFEST.resolve()}
        protected.update((ROOT / item["path"]).resolve() for item in read_manifest())
        require(dest not in protected, "RECEIPT_SOURCE_ALIAS_DENIED")
        require(not dest.exists(), "RECEIPT_COLLISION_DENIED")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print(json.dumps({k: v for k, v in report.items() if k != "documents"},
                     sort_keys=True))
if __name__ == "__main__":
    main()
