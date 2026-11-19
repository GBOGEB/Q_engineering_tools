"""Add independently switchable review layers to controlled SLD PDF copies.

Preserves original EPLAN PDF pages and optional-content groups (OCGs), and
adds OFF-by-default review OCGs, source-bound PDF notes, and outline entries.
No engineering approval, owner-source edits, silent feeder correction or ZIP
publication occurs. Deliberately additive to qpsdeck's interactive PDF engine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from itertools import combinations
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # PyMuPDF also exposes ``fitz`` on older releases
    import fitz  # type: ignore

SCHEMA = "qps.icd.layered-sld-review-map.v1"
RECEIPT = "qps.icd.layered-sld-qa.v1"
DOCUMENTS = ("general", "detailed")
COLORS = {
    "FEEDER": (0.53, 0.16, 0.40),
    "RATING": (0.70, 0.17, 0.40),
    "SCOPE": (0.20, 0.48, 0.30),
}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
# SLD-Q is W382's own series. EL-R numbers belong to the ICD-EL-001/W363 return
# list and mean different things, so they must not validate here.
RFI_ID = re.compile(r"^SLD-Q\d{2}$")


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _document_has_ocmd(doc: "fitz.Document") -> bool:
    """Detect optional-content membership dictionaries after PDF parsing.

    xref_object resolves indirect objects even when the original object lived
    inside a compressed object stream, avoiding raw-byte false negatives.
    Fail closed if any parsed object declares /Type /OCMD.
    """
    for xref in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(xref, compressed=False)
        except Exception as exc:
            raise ValueError("SOURCE_OCMD_OBJECT_SCAN_FAILED") from exc
        if re.search(r"/Type\s*/OCMD\b", obj):
            return True
    return False


def validated_map(data: dict) -> list[dict]:
    require(type(data) is dict and data.get("schema") == SCHEMA,
            "UNSUPPORTED_REVIEW_MAP")
    require(data.get("review_only") is True and
            data.get("engineering_approval") is False and
            data.get("authority_transfer") is False, "OWNER_AUTHORITY_INVARIANT")
    items = data.get("items")
    require(type(items) is list and items, "EMPTY_REVIEW_MAP")
    identities = set()
    for item in items:
        require(type(item) is dict and set(item) == {"id", "document", "page",
                "layer", "title", "evidence", "note"}, "BAD_REVIEW_ITEM")
        require(type(item["id"]) is str and RFI_ID.fullmatch(item["id"]), "BAD_RFI_ID")
        require(item["id"] not in identities, "DUPLICATE_RFI_ID")
        identities.add(item["id"])
        require(item["document"] in DOCUMENTS, "UNSUPPORTED_DOCUMENT")
        require(type(item["page"]) is int and item["page"] >= 1,
                "INVALID_SOURCE_PAGE")
        require(item["layer"] in COLORS, "UNAPPROVED_REVIEW_LAYER")
        for field, limit in (("title", 110), ("evidence", 200), ("note", 1000)):
            require(type(item[field]) is str and 2 <= len(item[field]) <= limit
                    and not any(c in item[field] for c in "\r\x00"),
                    "INVALID_REVIEW_TEXT:" + field)
    return items


def check_pins(pins: dict, documents: dict[str, Path], annex: Path | None,
               required: tuple[str, ...] | None = None) -> dict:
    """Hash-check every supplied source against the manifest.

    `required` names the roles this consumer reads; by default every role the manifest pins, so the
    layered build cannot leave out the Annex (#2226 review). A consumer that never reads a pinned role,
    such as the interactive view and the Annex, names the roles it does read (#2256 collision)."""
    require(type(pins) is dict and type(pins.get("sources")) is dict,
            "INVALID_PIN_MANIFEST")
    present = dict(documents)
    if annex is not None:
        present["annex"] = annex
    # Every required role must be supplied: an omitted source is unchecked drift (#2226 review).
    for role in (pins["sources"] if required is None else required):
        require(role in present, "SOURCE_NOT_SUPPLIED:" + role)
    hashes = {}
    for role, source in present.items():
        require(source.is_file(), "SOURCE_MISSING:" + role)
        expected = pins["sources"].get(role, {}).get("sha256")
        require(type(expected) is str and HEX64.fullmatch(expected),
                "BAD_SOURCE_PIN:" + role)
        actual = digest(source)
        require(actual == expected, "SOURCE_SHA256_DRIFT:" + role)
        hashes[role] = actual
    return hashes


def review_anchor(page: "fitz.Page", count: int,
                  state_pixmaps: tuple = ()) -> dict:
    """Place OFF-by-default review callouts in a low-ink source region.

    The previous fixed top-left position covered native EPLAN feeder graphics
    on some sheets when the review layers were ON. Score the *original* page
    raster before adding any review objects, keeping a source-image occupancy
    metric in the QA receipt. This does not move or edit any owner object.

    Fail closed if no acceptably blank candidate exists. The small 0.15x
    raster and fixed candidate order make the selection deterministic.
    """
    require(type(count) is int and 1 <= count <= 24, "INVALID_REVIEW_COUNT")
    rect = page.rect
    factor = 0.15
    pix = page.get_pixmap(matrix=fitz.Matrix(factor, factor), alpha=False, annots=False)
    require(pix.n >= 3, "UNSUPPORTED_REVIEW_RASTER")
    # Conservative union over visibility states, not the last composited
    # all-ON view: opaque white OCGs may mask black art in that view.
    rasters = (pix, *state_pixmaps)
    require(all(p.n >= 3 and p.width == pix.width and p.height == pix.height
                for p in rasters), "SOURCE_OCG_RASTER_MISMATCH")
    samples_by_state = [p.samples for p in rasters]
    width = min(355, rect.width * 0.40)
    height = 32 + (count - 1) * 39

    def occupancy(x: float, y: float) -> float:
        left = max(0, int(x * factor))
        top = max(0, int(y * factor))
        right = min(pix.width, int((x + width) * factor))
        bottom = min(pix.height, int((y + height) * factor))
        occupied = 0
        sampled = 0
        # Low-resolution source-only ink census, independent of OCR/text labels.
        for yy in range(top, bottom):
            for xx in range(left, right):
                i = (yy * pix.width + xx) * pix.n
                if any(sample[(yy * pix.width + xx) * raster.n] +
                       sample[(yy * pix.width + xx) * raster.n + 1] +
                       sample[(yy * pix.width + xx) * raster.n + 2] < 3 * 245
                       for raster, sample in zip(rasters, samples_by_state)):
                    occupied += 1
                sampled += 1
        return occupied / sampled if sampled else 1.0

    detailed = rect.width < 1800
    pref_x, pref_y = (76, rect.height * 0.48) if detailed else (200, 90)
    xs = sorted({50, 76, 200, *(int(rect.width * t) for t in
                                   (0.08, 0.16, 0.25, 0.40, 0.53, 0.65, 0.75))})
    ys = sorted({90, 160, *(int(rect.height * t) for t in
                                 (0.10, 0.20, 0.30, 0.40, 0.48, 0.55, 0.60, 0.66, 0.72, 0.78))})
    choices = []
    for x in xs:
        for y in ys:
            if x + width > rect.width - 36 or y + height > rect.height * 0.86:
                continue
            density = occupancy(x, y)
            distance = abs(x - pref_x) / rect.width + abs(y - pref_y) / rect.height
            choices.append((round(density, 6), distance, x, y))
    require(bool(choices), "NO_REVIEW_LABEL_ZONE")
    density, _, x, y = min(choices)
    require(density <= 0.03, "REVIEW_CALLOUT_COLLISION_HOLD")
    original_density = occupancy(min(rect.width * 0.085, 76),
                                 min(rect.height * 0.10, 67))
    return {"x": x, "y": y, "labels": count,
            "previous_ink_fraction": round(original_density, 5),
            "current_ink_fraction": round(density, 5),
            "source_view_state_count": len(rasters)}



def preflight_anchors(source: Path, relevant: list[dict]) -> dict[int, dict]:
    """Compute *all* anchors before producing outward review PDFs.

    Render the union of original source OCGs from a disposable in-memory
    source copy; PyMuPDF requires serialization/reopen before the changed OCG
    default takes effect in page rasterization. Inspect unrotated drawing
    coordinates (the coordinate space used by draw_rect/insert_text). The
    original PDF, its default layer visibility and its page rotations are
    never changed.
    """
    if not relevant:
        return {}
    pages: dict[int, int] = Counter(item["page"] for item in relevant)
    original_bytes = source.read_bytes()
    source_sha = hashlib.sha256(original_bytes).hexdigest()
    with fitz.open(stream=original_bytes, filetype="pdf") as source_copy:
        require(source_copy.is_pdf and not source_copy.needs_pass, "UNSUPPORTED_SOURCE_PDF")
        ocgs = source_copy.get_ocgs()
        # Exhaustive visibility-state proof grows as 2^N. Keep the bound small
        # and fail closed rather than sample an unsafe subset of larger OCG sets.
        require(len(ocgs) <= 8, "SOURCE_OCG_COMBINATIONS_EXCEED_EXHAUSTIVE_PROBE")
        # Optional-content membership dictionaries can encode arbitrary boolean
        # visibility expressions. Inspect parsed PDF objects rather than raw
        # bytes so OCMDs inside compressed object streams cannot bypass the hold.
        require(not _document_has_ocmd(source_copy),
                "SOURCE_OCMD_COMBINATION_UNSUPPORTED")
        if ocgs:
            source_copy.set_layer(-1, on=list(ocgs), off=[])
        preview_bytes = source_copy.tobytes(no_new_id=True)
    # A composed all-ON view is insufficient: hidden white OCGs can mask
    # source ink. For the bounded cohort, enumerate every visibility subset.
    # The all-ON state is preview_bytes, so state_bytes contains all remaining
    # 2^N - 1 states, including all-OFF and higher-order combinations.
    state_bytes = []
    ordered_ocgs = sorted(ocgs)

    def add_state(on_ids):
        on_ids = list(on_ids)
        off_ids = [i for i in ordered_ocgs if i not in on_ids]
        with fitz.open(stream=original_bytes, filetype="pdf") as layer_copy:
            layer_copy.set_layer(-1, on=on_ids, off=off_ids)
            state_bytes.append(layer_copy.tobytes(no_new_id=True))

    if ordered_ocgs:
        for size in range(0, len(ordered_ocgs) + 1):
            for subset in combinations(ordered_ocgs, size):
                if size == len(ordered_ocgs):
                    continue  # preview_bytes already represents all-ON.
                add_state(subset)
    result: dict[int, dict] = {}
    with fitz.open(stream=preview_bytes, filetype="pdf") as all_on:
        if ocgs:
            require(all(group["on"] for group in all_on.get_ocgs().values()),
                    "SOURCE_OCG_UNION_UNAVAILABLE")
        for pageno, count in sorted(pages.items()):
            require(1 <= pageno <= all_on.page_count, "REVIEW_PAGE_OUT_OF_BOUNDS")
            page = all_on[pageno - 1]
            source_rotation = page.rotation
            page.set_rotation(0)
            extra = []
            for original_state in state_bytes:
                with fitz.open(stream=original_state, filetype="pdf") as state_doc:
                    require(state_doc.page_count == all_on.page_count,
                            "SOURCE_OCG_RASTER_MISMATCH")
                    state_page = state_doc[pageno - 1]
                    state_page.set_rotation(0)
                    extra.append(state_page.get_pixmap(
                        matrix=fitz.Matrix(.15, .15), alpha=False, annots=False))
            record = review_anchor(page, count, tuple(extra))
            record["source_rotation"] = source_rotation
            record["source_sha256"] = source_sha
            record["census_rotation"] = 0
            record["source_ocg_union"] = len(ocgs)
            record["source_ocg_probe_policy"] = (
                "EXHAUSTIVE_ALL_VISIBILITY_SUBSETS_MAX_8_OCGS"
            )
            result[pageno] = record
    return result


def _review_label(page: "fitz.Page", layer: str, sequence: int,
                  item: dict, ocg: int, origin: dict | None = None) -> None:
    """Small optional label in page margin; source artwork is always retained."""
    rect = page.rect
    # Place within page bounds, not in the source title-block corner.
    left = origin["x"] if origin is not None else min(rect.width * 0.085, 76)
    top = (origin["y"] if origin is not None else min(rect.height * 0.10, 67)) + (sequence * 39)
    width = min(355, rect.width * 0.40)
    stripe = fitz.Rect(left, top, left + width, top + 32)
    color = COLORS[layer]
    page.draw_rect(stripe, color=color, width=1.2, fill=(1, 1, 1),
                   fill_opacity=0.90, oc=ocg)
    page.insert_text((left + 8, top + 13),
                     item["id"] + "  |  REVIEW ONLY / NOT APPROVED",
                     fontsize=8.4, color=color, oc=ocg)
    caption = item["title"][:54]
    page.insert_text((left + 8, top + 25), caption,
                     fontsize=9.2, color=(0.18, 0.13, 0.18), oc=ocg)
    note = page.add_text_annot((left + 2, top + 34),
                              item["id"] + "  |  " + item["title"] + "\n\n" +
                              "EVIDENCE: " + item["evidence"] + "\n\n" +
                              item["note"] + "\n\n" +
                              "REVIEW ONLY - owner engineering disposition required.")
    note.set_info(title="QPS Electrical ICD review", subject=item["id"] + " " + item["title"])
    note.set_oc(ocg)
    note.update()


def _source_ocg_inventory(doc: "fitz.Document") -> Counter:
    return Counter(v["name"] for v in doc.get_ocgs().values())


def build_copy(source: Path, destination: Path, kind: str,
               items: list[dict], prepared: dict[int, dict] | None = None) -> dict:
    """Create one layered PDF without writing or flattening its source."""
    require(not destination.exists(), "OUTPUT_ALREADY_EXISTS:" + str(destination))
    source_size = source.stat().st_size
    source_sha = digest(source)
    relevant = [i for i in items if i["document"] == kind]
    positions = preflight_anchors(source, relevant) if prepared is None else prepared
    require(set(positions) == {row["page"] for row in relevant}, "ANCHOR_PREFLIGHT_MISSING")
    require(all(row.get("source_sha256") == source_sha and
                row.get("census_rotation") == 0 and
                0 <= row.get("current_ink_fraction", 1) <= .03
                for row in positions.values()), "UNBOUND_OR_UNQUALIFIED_ANCHOR")
    require(digest(source) == source_sha, "SOURCE_DRIFT_AFTER_PREFLIGHT")
    with fitz.open(source) as doc:
        require(not doc.needs_pass and doc.is_pdf, "UNSUPPORTED_SOURCE_PDF")
        initial_layers = _source_ocg_inventory(doc)
        initial_toc = doc.get_toc()
        source_text = [p.get_text() for p in doc]
        source_annots = [len(list(p.annots() or [])) for p in doc]
        relevant = [i for i in items if i["document"] == kind]
        for row in relevant:
            require(row["page"] <= doc.page_count,
                    "MISSING_SOURCE_PAGE:" + row["id"])
        layer_ids = {name: doc.add_ocg("QPS REVIEW | " +
                            {"FEEDER": "Feeder tags", "RATING": "Ratings and protection",
                             "SCOPE": "Scope and decisions"}[name], on=0)
                     for name in COLORS}
        placed = Counter()
        for pageno in sorted(positions):
            page = doc[pageno - 1]
            original_rotation = page.rotation
            require(original_rotation == positions[pageno]["source_rotation"],
                    "SOURCE_ROTATION_DRIFT")
            try:
                page.set_rotation(0)  # SVG/raster census and drawing share one coordinate frame.
                for item in (item for item in relevant if item["page"] == pageno):
                    count = placed[pageno]
                    _review_label(page, item["layer"], count, item,
                                  layer_ids[item["layer"]], origin=positions[pageno])
                    placed[pageno] += 1
            finally:
                page.set_rotation(original_rotation)
        # Preserve existing bookmarks and append a clearly separated review section.
        toc = list(initial_toc)
        toc.append([1, "QPS REVIEW ONLY - pending RFIs", 1])
        for row in sorted(relevant, key=lambda r: (r["page"], r["id"])):
            toc.append([2, row["id"] + " - " + row["title"], row["page"]])
        doc.set_toc(toc)
        original_meta = dict(doc.metadata)
        original_meta["title"] = ((original_meta.get("title") or kind.upper() + " SLD")
                                  + " | QPS REVIEW ONLY - layered")
        original_meta["keywords"] = "QPS ICD-EL-001; REVIEW ONLY; no owner-source correction"
        doc.set_metadata(original_meta)
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc.save(destination, garbage=0, deflate=True, no_new_id=True)
        page_count = doc.page_count
    require(digest(source) == source_sha and source.stat().st_size == source_size,
            "SOURCE_MODIFIED")
    with fitz.open(destination) as derivative:
        final_layers = _source_ocg_inventory(derivative)
        for name, count in initial_layers.items():
            require(final_layers[name] >= count, "SOURCE_LAYER_LOSS:" + name)
        require(derivative.page_count == page_count, "SOURCE_PAGE_COUNT_DRIFT")
        require(all(row["name"].startswith("QPS REVIEW | ") and not row["on"]
                    for row in derivative.get_ocgs().values()
                    if row["name"].startswith("QPS REVIEW | ")),
                "REVIEW_LAYER_DEFAULT_NOT_OFF")
        require(all(source_text[i] in p.get_text() for i, p in enumerate(derivative)),
                "SOURCE_TEXT_LOST")
        n_annots = sum(len(list(p.annots() or [])) - source_annots[i]
                       for i, p in enumerate(derivative))
        require(n_annots == len(relevant), "REVIEW_ANNOTATION_COUNT")
        require(len(derivative.get_toc()) >= len(initial_toc) + len(relevant) + 1,
                "REVIEW_OUTLINE_MISSING")
        return {"input_sha256": source_sha, "output_sha256": digest(destination),
                "output_bytes": destination.stat().st_size,
                "original_layers": sum(initial_layers.values()),
                "review_layers": len(layer_ids),
                "all_layers": sum(final_layers.values()),
                "page_count": page_count, "review_annotations": n_annots,
                "source_text_preserved": True, "default_review_layers_off": True,
                "filename": destination.name,
                "callout_placements": {str(k): v for k, v in positions.items()}}


def run(general: Path, detailed: Path, annex: Path | None, pins_path: Path,
        spec_path: Path, out_dir: Path) -> dict:
    require(not out_dir.exists() or not list(out_dir.iterdir()), "OUTPUT_NOT_EMPTY")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    entries = validated_map(spec)
    sources = {"general": general, "detailed": detailed}
    hashes = check_pins(pins, sources, annex)

    # Check source page numbers and preflight both source roles before creating
    # any outward bytes. A second-document collision must not strand the first.
    for kind, source in sources.items():
        with fitz.open(source) as doc:
            require(all(e["page"] <= doc.page_count for e in entries
                        if e["document"] == kind), "REVIEW_PAGE_OUT_OF_BOUNDS")
    prepared = {
        kind: preflight_anchors(source, [e for e in entries if e["document"] == kind])
        for kind, source in sources.items()
    }
    require(all(digest(source) == hashes[kind] for kind, source in sources.items()),
            "SOURCE_DRIFT_AFTER_PREFLIGHT")

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".w393-icd-stage-", dir=out_dir.parent))
    try:
        pdfs = {}
        for kind, source in sources.items():
            out = staging / ("EDB700_GENERAL" if kind == "general" else "EDB701_BFA31-32-33")
            out = out.with_name(out.name + "_LAYERED_REVIEW_ONLY.pdf")
            pdfs[kind] = build_copy(source, out, kind, entries, prepared=prepared[kind])

        result = {"schema": RECEIPT, "source_map_sha256": digest(spec_path),
                  "pin_manifest_sha256": digest(pins_path), "sources_sha256": hashes,
                  "pdfs": pdfs, "review_ids": [x["id"] for x in entries],
                  "source_authority": "OWNER_PDF_BYTES_UNCHANGED",
                  "engineering_approval": False, "authority_transfer": False,
                  "owner_dispositions": "OPEN", "publisher_approval": False,
                  "test_level": "LOCAL_REPRODUCIBILITY",
                  "ocg_explanation": "Three switchable REVIEW layers are OFF by default; all original layer names retained"}
        receipt = staging / "W382_LAYERED_PDF_RECEIPT.json"
        receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")

        require(not out_dir.exists() or not any(out_dir.iterdir()), "OUTPUT_NOT_EMPTY")
        if out_dir.exists():
            out_dir.rmdir()
        os.replace(staging, out_dir)
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("general", "detailed", "annex", "pins", "spec", "out"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    r = run(args.general, args.detailed, args.annex, args.pins, args.spec, args.out)
    print(json.dumps({"status": "REVIEW_ONLY", "count": len(r["review_ids"]),
                      "pdfs": {k: v["filename"] for k, v in r["pdfs"].items()}},
                     sort_keys=True))


if __name__ == "__main__":
    main()
