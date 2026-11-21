#!/usr/bin/env python3
"""Offer PDF binary engine: page atoms, tables to CSV, drawings to SVG, OCR queue.

Built from existing GBOGEB pieces, not a fork of them:
  - page-marker projection "<PARSED TEXT FOR PAGE: n / N>" is the input format of
    cryoplant-project triage/jade_temple_qps/bb_lkt_offer_v1/native_pdf_source_binding.py
  - SHA-256 source identity and idempotent re-runs follow
    DOCX_RTM_Automation src/core/extraction_manifest.py
  - table rows keep page + table_index + row_index as in
    DOCX_RTM_Automation src/extractors/extract_offer_pdf_tables.py (PyMuPDF find_tables here)

Usage:
    python -I offer_pdf_engine.py <pdf> --bidder LKT --out out/

Outputs (under out/<bidder>/):
    manifest.json        source sha256, page count, bookmarks, per-page classification
    projection.txt       page-marked text (one block per page)
    pages.csv            page, section, chars, images, drawings, tables, class
    tables/              p<page>_t<k>.csv, plus tables_index.csv
    svg/                 p<page>.svg for vector drawing pages (PFD, P&ID, layout, SLD)
    png/                 p<page>.png renders for drawing and scanned pages (visual / OCR queue)
    ocr_queue.csv        pages with little or no text layer that need OCR or visual read

The output holds bidder text, so the engine refuses an --out folder inside a git checkout
(CONTRIBUTING.md section 1-3: offer content and binaries stay out of git history).

The engine gives locators, never compliance credit: absence of an exception is not evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

import fitz  # PyMuPDF

SCHEMA = "gbogeb.offer-pdf-engine/0.2"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inside_git_checkout(path: Path) -> Path | None:
    """Return the checkout root if path lies inside a git working tree, else None."""
    p = path.resolve()
    for parent in (p, *p.parents):
        if (parent / ".git").exists():
            return parent
    return None


def section_map(toc: list, n: int) -> dict[int, str]:
    """Page -> deepest bookmark path covering it."""
    starts = sorted(((p, lvl, t) for lvl, t, p in toc if p >= 1), key=lambda x: (x[0], x[1]))
    out: dict[int, str] = {}
    stack: list[tuple[int, str]] = []
    i = 0
    for page in range(1, n + 1):
        while i < len(starts) and starts[i][0] == page:
            _, lvl, title = starts[i]
            stack = [s for s in stack if s[0] < lvl] + [(lvl, title)]
            i += 1
        out[page] = " > ".join(t for _, t in stack) if stack else "(front matter)"
    return out


DRAWING_SECTION = re.compile(r"\b(BFD|PFD|P&ID|PID|Diagram|Drawing|Layout|Architecture|Single Line)\b", re.I)


def classify(chars: int, images: int, drawings: int, tables: int, area_img: float, section: str = "") -> str:
    leaf = section.split(" > ")[-1]
    drawing_context = bool(DRAWING_SECTION.search(leaf) or drawings >= 1500)
    if drawing_context:
        return "drawing_scanned" if ((chars < 40 and images) or (area_img > 0.6 and chars < 300)) else "drawing"
    if chars < 40 and images:
        return "scanned"
    if area_img > 0.6 and chars < 300:
        return "scanned_partial"
    if tables:
        return "table"
    return "text"


def run(pdf: Path, bidder: str, out_root: Path, dpi: int, allow_in_repo: bool = False) -> dict:
    root = inside_git_checkout(out_root)
    if root is not None and not allow_in_repo:
        raise SystemExit(f"refusing --out inside git checkout {root}: bidder text must stay out of git")
    out = out_root / bidder
    src_sha = sha256(pdf)
    man_path = out / "manifest.json"
    if man_path.exists():
        old = json.loads(man_path.read_text(encoding="utf-8"))
        if old.get("source_sha256") == src_sha and old.get("schema") == SCHEMA:
            print(f"{bidder}: source unchanged ({src_sha[:12]}), skipping")
            return old

    # A changed source gets a clean bidder output tree. Leaving prior table/SVG/PNG
    # atoms in place would make stale files indistinguishable from the current manifest.
    if out.exists():
        shutil.rmtree(out)
    for d in ("tables", "svg", "png"):
        (out / d).mkdir(parents=True, exist_ok=True)
    man_path = out / "manifest.json"

    doc = fitz.open(pdf)
    n = doc.page_count
    toc = doc.get_toc()
    sections = section_map(toc, n)
    pages, tindex, ocrq = [], [], []
    proj = []
    for pno in range(n):
        page = doc[pno]
        p1 = pno + 1
        text = page.get_text("text", sort=True)
        chars = len(text.strip())
        imgs = page.get_images(full=True)
        parea = abs(page.rect)
        area_img = 0.0
        for info in page.get_image_info():
            r = fitz.Rect(info["bbox"]) & page.rect
            area_img += abs(r) / parea if parea else 0
        drawings = len(page.get_drawings())
        ntab = 0
        try:
            found = page.find_tables()
            for k, tab in enumerate(found.tables):
                rows = tab.extract()
                if not rows or len(rows) < 2 or max(len(r) for r in rows) < 2:
                    continue
                ntab += 1
                fn = out / "tables" / f"p{p1:04d}_t{k}.csv"
                with fn.open("w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    for r in rows:
                        w.writerow([" ".join(str(c or "").split()) for c in r])
                tindex.append({"page": p1, "table_index": k, "rows": len(rows),
                               "cols": max(len(r) for r in rows), "section": sections[p1],
                               "header": " | ".join(" ".join(str(c or "").split()) for c in rows[0])[:200],
                               "file": fn.name})
        except Exception as exc:  # table finder is best effort
            tindex.append({"page": p1, "table_index": -1, "rows": 0, "cols": 0,
                           "section": sections[p1], "header": f"ERROR {exc}", "file": ""})
        cls = classify(chars, len(imgs), drawings, ntab, min(area_img, 1.0), sections[p1])
        if cls.startswith("drawing"):
            (out / "svg" / f"p{p1:04d}.svg").write_text(page.get_svg_image(text_as_path=False), encoding="utf-8")
            # drawing text with coordinates: tags, stream tables, title block
            with (out / "svg" / f"p{p1:04d}_words.csv").open("w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["x0", "y0", "x1", "y1", "word", "block", "line"])
                for x0, y0, x1, y1, word, block, line, _ in page.get_text("words"):
                    w.writerow([round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1), word, block, line])
        if cls.startswith("drawing") or cls in ("scanned", "scanned_partial"):
            page.get_pixmap(dpi=dpi * 2 if cls.startswith("drawing") else dpi).save(out / "png" / f"p{p1:04d}.png")
        if cls in ("scanned", "scanned_partial", "drawing_scanned"):
            ocrq.append({"page": p1, "class": cls, "chars": chars, "image_area": round(area_img, 2),
                         "section": sections[p1], "png": f"p{p1:04d}.png"})
        pages.append({"page": p1, "section": sections[p1], "chars": chars, "images": len(imgs),
                      "image_area": round(min(area_img, 1.0), 2), "drawings": drawings,
                      "tables": ntab, "class": cls})
        proj.append(f"<PARSED TEXT FOR PAGE: {p1} / {n}>\n{text}")

    (out / "projection.txt").write_text("\n".join(proj), encoding="utf-8")
    for name, rows in (("pages.csv", pages), ("tables/tables_index.csv", tindex), ("ocr_queue.csv", ocrq)):
        with (out / name).open("w", newline="", encoding="utf-8-sig") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    counts: dict[str, int] = {}
    for p in pages:
        counts[p["class"]] = counts.get(p["class"], 0) + 1
    manifest = {"schema": SCHEMA, "bidder": bidder, "source_name": pdf.name, "source_sha256": src_sha,
                "source_bytes": pdf.stat().st_size, "pages": n,
                "bookmarks": [{"level": lvl, "title": t, "page": p} for lvl, t, p in toc],
                "class_counts": counts, "tables_extracted": sum(1 for t in tindex if t["table_index"] >= 0),
                "ocr_queue": len(ocrq), "credit": "NONE - locators only"}
    man_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"{bidder}: {n} pages, classes {counts}, tables {manifest['tables_extracted']}, ocr {len(ocrq)}")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--bidder", required=True)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--allow-in-repo", action="store_true",
                    help="write output inside a git checkout (synthetic inputs only)")
    a = ap.parse_args()
    run(a.pdf, a.bidder, a.out, a.dpi, a.allow_in_repo)


if __name__ == "__main__":
    main()
