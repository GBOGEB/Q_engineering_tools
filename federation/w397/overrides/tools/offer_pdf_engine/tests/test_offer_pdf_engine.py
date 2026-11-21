"""Synthetic-PDF tests for the offer PDF engine. No bidder material is used."""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
REPO = TOOL.parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


eng = _load("offer_pdf_engine", TOOL / "offer_pdf_engine.py")
reader = _load("offer_page_reader", TOOL / "page_reader.py")


def _synthetic_pdf(path: Path) -> Path:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "Project Quality Plan. Requirements verification matrix is optional.")
    p2 = doc.new_page()
    x0, y0, w, h = 72, 100, 150, 24
    for r in range(4):
        for c in range(3):
            p2.draw_rect(fitz.Rect(x0 + c * w, y0 + r * h, x0 + (c + 1) * w, y0 + (r + 1) * h), color=(0, 0, 0))
            p2.insert_text((x0 + c * w + 4, y0 + r * h + 16), f"R{r}C{c}" if r else ["ID", "Requirement", "Reply"][c])
    p3 = doc.new_page()
    for i in range(60):
        p3.draw_line((50 + i * 8, 100), (50 + i * 8, 700))
    p3.insert_text((60, 90), "HP compressor heat recovery water")
    p4 = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 200), False)
    pix.set_rect(pix.irect, (200, 200, 200))
    p4.insert_image(p4.rect, pixmap=pix)
    doc.set_toc([[1, "Quality Plan", 1], [1, "Compliance Matrix", 2], [1, "TAX02 - Process Flow Diagram (PFD)", 3],
                 [1, "ISO 9001 Certificate", 4]])
    doc.save(path)
    return path


@pytest.fixture()
def run_out(tmp_path: Path):
    pdf = _synthetic_pdf(tmp_path / "offer.pdf")
    out = tmp_path / "out"
    man = eng.run(pdf, "SYN", out, dpi=40)
    return pdf, out / "SYN", man


def test_manifest_classes_and_hash(run_out):
    pdf, out, man = run_out
    assert man["pages"] == 4
    assert man["source_sha256"] == eng.sha256(pdf)
    assert man["credit"].startswith("NONE")
    rows = {int(r["page"]): r for r in csv.DictReader(open(out / "pages.csv", encoding="utf-8-sig"))}
    assert rows[1]["class"] == "text"
    assert rows[2]["class"] == "table"
    assert rows[3]["class"] == "drawing"
    assert rows[4]["class"] == "scanned"
    assert rows[3]["section"].endswith("(PFD)")


def test_table_csv_and_drawing_outputs(run_out):
    _, out, _ = run_out
    idx = list(csv.DictReader(open(out / "tables" / "tables_index.csv", encoding="utf-8-sig")))
    assert any(r["page"] == "2" and "Requirement" in r["header"] for r in idx)
    table = [r for r in csv.reader(open(out / "tables" / idx[0]["file"], encoding="utf-8-sig"))]
    assert table[0] == ["ID", "Requirement", "Reply"] and len(table) == 4
    assert (out / "svg" / "p0003.svg").read_text(encoding="utf-8").startswith("<svg")
    words = list(csv.DictReader(open(out / "svg" / "p0003_words.csv", encoding="utf-8-sig")))
    assert any(w["word"] == "recovery" for w in words)
    assert (out / "png" / "p0004.png").exists()
    q = list(csv.DictReader(open(out / "ocr_queue.csv", encoding="utf-8-sig")))
    assert [r["page"] for r in q] == ["4"]


def test_image_only_drawing_ancestor_bookmark_precedes_generic_scan_classification():
    assert eng.classify(
        chars=0, images=1, drawings=0, tables=0, area_img=0.95,
        section="Drawings > P&ID > Sheet 001",
    ) == "drawing_scanned"


def test_changed_source_rebuild_removes_stale_artifacts(run_out, tmp_path: Path):
    _, out, _ = run_out
    stale = [
        out / "tables" / "stale.csv",
        out / "svg" / "stale.svg",
        out / "png" / "stale.png",
    ]
    for path in stale:
        path.write_text("STALE", encoding="utf-8")

    replacement = tmp_path / "replacement.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Replacement source with one page only.")
    doc.set_toc([[1, "Replacement", 1]])
    doc.save(replacement)

    man = eng.run(replacement, "SYN", out.parent, dpi=40)
    assert man["pages"] == 1
    assert man["source_sha256"] == eng.sha256(replacement)
    assert all(not path.exists() for path in stale)
    rows = list(csv.DictReader(open(out / "pages.csv", encoding="utf-8-sig")))
    assert len(rows) == 1


def test_projection_is_native_binding_compatible(run_out):
    _, out, man = run_out
    text = (out / "projection.txt").read_text(encoding="utf-8")
    binding = REPO / "triage" / "jade_temple_qps" / "bb_lkt_offer_v1" / "native_pdf_source_binding.py"
    if not binding.exists():
        pytest.skip("native_pdf_source_binding.py not in this checkout")
    nb = _load("native_pdf_source_binding", binding)
    pages = nb.decode_projection(text, man["pages"])
    assert sorted(pages) == [1, 2, 3, 4]
    assert "verification matrix" in pages[1]
    assert reader.pages(out / "projection.txt")[1].strip() == pages[1].strip()


def test_rerun_on_same_bytes_is_skipped(run_out, capsys):
    pdf, out, man = run_out
    again = eng.run(pdf, "SYN", out.parent, dpi=40)
    assert again == json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "skipping" in capsys.readouterr().out


def test_same_source_changed_dpi_invalidates_cache(run_out, capsys):
    pdf, out, first = run_out
    assert first["dpi"] == 40
    again = eng.run(pdf, "SYN", out.parent, dpi=55)
    captured = capsys.readouterr().out
    assert "skipping" not in captured
    assert again["dpi"] == 55
    assert again["engine_sha256"] == eng.sha256(Path(eng.__file__))
    assert again["pymupdf_version"] == fitz.VersionBind
    stored = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert stored["dpi"] == 55


def test_refuses_output_inside_git_checkout(tmp_path: Path):
    pdf = _synthetic_pdf(tmp_path / "offer.pdf")
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(SystemExit, match="refusing"):
        eng.run(pdf, "SYN", repo / "out", dpi=40)
    man = eng.run(pdf, "SYN", repo / "out", dpi=40, allow_in_repo=True)
    assert man["pages"] == 4


def test_section_map_nesting():
    toc = [[1, "A", 1], [2, "A.1", 2], [1, "B", 4]]
    m = eng.section_map(toc, 5)
    assert m == {1: "A", 2: "A > A.1", 3: "A > A.1", 4: "B", 5: "B"}


def test_page_reader_filters(run_out, capsys):
    _, out, _ = run_out
    assert reader.main([str(out / "projection.txt"), "1", "4", "heat recovery"]) == 0
    printed = capsys.readouterr().out
    assert "=== p3" in printed and "=== p1" not in printed
    assert reader.main([]) == 2
