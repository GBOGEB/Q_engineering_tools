"""W384 adversarial regressions for the three unresolved #2350 review findings.

These are synthetic source PDFs. They do not change or represent an owner SLD.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import pymupdf as fitz

PACK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("layered_sld", PACK / "src" / "layered_sld_review.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def create_pdf(path: Path, *, rotation: int = 0, hidden_box: bool = False,
               fully_inked: bool = False) -> None:
    with fitz.open() as doc:
        p = doc.new_page(width=600, height=360)
        visible = doc.add_ocg("SOURCE VISIBLE", on=1)
        hidden = doc.add_ocg("SOURCE HIDDEN", on=1)
        p.insert_text((390, 270), "SOURCE ORIGINAL", fontsize=10, oc=visible)
        if hidden_box:
            p.draw_rect(fitz.Rect(20, 20, 330, 145), color=(0, 0, 0),
                        fill=(0, 0, 0), oc=hidden)
        if fully_inked:
            p.draw_rect(p.rect, color=(0, 0, 0), fill=(0, 0, 0), oc=hidden)
        p.set_rotation(rotation)
        doc.set_layer(-1, on=[visible], off=[hidden])
        doc.save(path)


def item(role: str) -> dict:
    return {"id": "SLD-Q01" if role == "general" else "SLD-Q02",
            "document": role, "page": 1, "layer": "FEEDER",
            "title": "Synthetic provenance review", "evidence": "synthetic sample",
            "note": "Do not transfer authority from this test fixture."}


class W384OcgsAndRotation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="w384-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_hidden_source_layer_is_part_of_ink_census(self):
        source = self.root / "hidden.pdf"
        create_pdf(source, hidden_box=True)
        original_sha = mod.digest(source)
        with fitz.open(source) as default:
            self.assertTrue(any(not v["on"] for v in default.get_ocgs().values()))
            old = mod.review_anchor(default[0], 1)
            self.assertLess(old["previous_ink_fraction"], .01)
        corrected = mod.preflight_anchors(source, [item("general")])[1]
        self.assertGreater(corrected["previous_ink_fraction"], .05)
        self.assertLessEqual(corrected["current_ink_fraction"], .03)
        self.assertEqual(corrected["source_ocg_union"], 2)
        self.assertEqual(mod.digest(source), original_sha)

    def test_hidden_full_page_fails_not_false_green(self):
        source = self.root / "all_black_when_on.pdf"
        create_pdf(source, fully_inked=True)
        with self.assertRaisesRegex(ValueError, "REVIEW_CALLOUT_COLLISION_HOLD"):
            mod.preflight_anchors(source, [item("general")])

    def test_hidden_white_ocg_cannot_erase_default_black_source_census(self):
        for rotation in (0, 90, 270):
            with self.subTest(rotation=rotation):
                source = self.root / f"white_mask_{rotation}.pdf"
                with fitz.open() as doc:
                    page = doc.new_page(width=600, height=360)
                    black = doc.add_ocg("BLACK SOURCE", on=1)
                    white = doc.add_ocg("WHITE MASK", on=1)
                    page.draw_rect(page.rect, color=(0, 0, 0),
                                   fill=(0, 0, 0), oc=black)
                    page.draw_rect(page.rect, color=(1, 1, 1),
                                   fill=(1, 1, 1), oc=white)
                    page.set_rotation(rotation)
                    doc.set_layer(-1, on=[black], off=[white])
                    doc.save(source)
                source_sha = mod.digest(source)
                with fitz.open(source) as opened:
                    opened.set_layer(-1, on=list(opened.get_ocgs()), off=[])
                    flattened = opened.tobytes(no_new_id=True)
                with fitz.open(stream=flattened, filetype="pdf") as all_on:
                    all_on[0].set_rotation(0)
                    # Unsafe all-on composite presents a blank white page.
                    naive = mod.review_anchor(all_on[0], 1)
                    self.assertLessEqual(naive["current_ink_fraction"], .03)
                with self.assertRaisesRegex(ValueError, "REVIEW_CALLOUT_COLLISION_HOLD"):
                    mod.preflight_anchors(source, [item("general")])
                self.assertEqual(mod.digest(source), source_sha)

    def test_combined_ocg_states_are_included_in_source_census(self):
        source = self.root / "combined_states.pdf"
        with fitz.open() as doc:
            page = doc.new_page(width=600, height=360)
            art_a = doc.add_ocg("ART A", on=1)
            art_b = doc.add_ocg("ART B", on=1)
            mask = doc.add_ocg("WHITE MASK", on=1)
            page.draw_rect(fitz.Rect(30, 30, 90, 55), color=(0, 0, 0),
                           fill=(0, 0, 0), oc=art_a)
            page.draw_rect(fitz.Rect(90, 30, 150, 55), color=(0, 0, 0),
                           fill=(0, 0, 0), oc=art_b)
            page.draw_rect(fitz.Rect(30, 30, 150, 55), color=(1, 1, 1),
                           fill=(1, 1, 1), oc=mask)
            doc.set_layer(-1, on=[art_a, art_b], off=[mask])
            doc.save(source)
        receipt = mod.preflight_anchors(source, [item("general")])[1]
        self.assertEqual(
            receipt["source_ocg_probe_policy"],
            "DEFAULT_ALL_ON_SINGLE_ON_SINGLE_OFF_PAIR_ON",
        )
        # all-ON base + default + 3 single-ON + 3 single-OFF + 3 pair-ON
        self.assertEqual(receipt["source_view_state_count"], 11)

    def test_parsed_ocmd_dictionary_fails_closed_even_without_raw_marker(self):
        class FakeDoc:
            def xref_length(self):
                return 4
            def xref_object(self, xref, compressed=False):
                self.last_compressed = compressed
                if xref == 2:
                    return "<< /Type /OCMD /P /AllOn >>"
                return "<< /Type /Other >>"
        doc = FakeDoc()
        self.assertTrue(mod._document_has_ocmd(doc))
        self.assertFalse(doc.last_compressed)

    def test_page_rotation_preserved_and_default_view_is_source_identical(self):
        for rotation in (90, 270):
            with self.subTest(rotation=rotation):
                source = self.root / f"rotation_{rotation}.pdf"
                output = self.root / f"review_{rotation}.pdf"
                create_pdf(source, rotation=rotation, hidden_box=True)
                frozen = mod.digest(source)
                receipt = mod.build_copy(source, output, "general", [item("general")])
                self.assertEqual(receipt["callout_placements"]["1"]["source_rotation"], rotation)
                self.assertEqual(receipt["callout_placements"]["1"]["census_rotation"], 0)
                with fitz.open(source) as a, fitz.open(output) as b:
                    self.assertEqual(a[0].rotation, b[0].rotation)
                    self.assertEqual(a[0].get_pixmap(matrix=fitz.Matrix(.6, .6),
                                    annots=False).samples,
                                     b[0].get_pixmap(matrix=fitz.Matrix(.6, .6),
                                    annots=False).samples)
                self.assertEqual(frozen, mod.digest(source))

    def test_layer_on_callout_footprint_tracks_unrotated_anchor(self):
        # Default OFF-layer comparison alone cannot detect misplaced callouts.
        for rotation in (90, 270):
            with self.subTest(rotation=rotation):
                source = self.root / f"on_source_{rotation}.pdf"
                output = self.root / f"on_review_{rotation}.pdf"
                create_pdf(source, rotation=rotation, hidden_box=True)
                frozen = mod.digest(source)
                receipt = mod.build_copy(
                    source, output, "general", [item("general")])
                anchor = receipt["callout_placements"]["1"]
                width = min(355, 600 * .40)
                clip = fitz.Rect(anchor["x"], anchor["y"],
                                 anchor["x"] + width, anchor["y"] + 32)
                with fitz.open(source) as original:
                    original.set_layer(-1, on=list(original.get_ocgs()), off=[])
                    before = original.tobytes(no_new_id=True)
                with fitz.open(output) as reviewed:
                    reviewed.set_layer(-1, on=list(reviewed.get_ocgs()), off=[])
                    after = reviewed.tobytes(no_new_id=True)
                with (fitz.open(stream=before, filetype="pdf") as a,
                      fitz.open(stream=after, filetype="pdf") as b):
                    a[0].set_rotation(0)
                    b[0].set_rotation(0)
                    old = a[0].get_pixmap(matrix=fitz.Matrix(.8, .8),
                                         clip=clip, annots=False, alpha=False)
                    new = b[0].get_pixmap(matrix=fitz.Matrix(.8, .8),
                                         clip=clip, annots=False, alpha=False)
                    self.assertEqual((old.width, old.height, old.n),
                                     (new.width, new.height, new.n))
                    changed = sum(x != y for x, y in zip(old.samples, new.samples))
                    self.assertGreater(changed, 80,
                                       "ON-layer callout did not appear at preflight anchor")
                self.assertLessEqual(anchor["current_ink_fraction"], .03)
                self.assertEqual(mod.digest(source), frozen)

    def test_replayed_anchor_must_be_bound_to_current_source_sha(self):
        source = self.root / "forged_preflight.pdf"
        create_pdf(source, hidden_box=True)
        positions = mod.preflight_anchors(source, [item("general")])
        positions[1]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "UNBOUND_OR_UNQUALIFIED_ANCHOR"):
            mod.build_copy(source, self.root / "forged.pdf", "general",
                           [item("general")], prepared=positions)
        self.assertFalse((self.root / "forged.pdf").exists())

    def test_second_writer_failure_does_not_publish_first_pdf(self):
        general = self.root / "atomic_general.pdf"
        detailed = self.root / "atomic_detailed.pdf"
        annex = self.root / "atomic_annex.xlsx"
        create_pdf(general)
        create_pdf(detailed)
        annex.write_bytes(b"SYNTHETIC ANNEX")
        pins = self.root / "atomic_pins.json"
        pins.write_text(json.dumps({"sources": {
            role: {"sha256": mod.digest(path)}
            for role, path in (("general", general), ("detailed", detailed), ("annex", annex))
        }}))
        review = self.root / "atomic_review.json"
        review.write_text(json.dumps({"schema": mod.SCHEMA, "review_only": True,
            "engineering_approval": False, "authority_transfer": False,
            "items": [item("general"), item("detailed")]}))
        output = self.root / "atomic_no_partial"

        original = mod.build_copy
        sequence = []
        def failing_writer(source_path, dest, kind, items, **kwargs):
            sequence.append(kind)
            if kind == "detailed":
                raise RuntimeError("SYNTHETIC_DETAILED_WRITE_FAILED")
            return original(source_path, dest, kind, items, **kwargs)

        with mock.patch.object(mod, "build_copy", side_effect=failing_writer):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_DETAILED_WRITE_FAILED"):
                mod.run(general, detailed, annex, pins, review, output)
        self.assertEqual(sequence, ["general", "detailed"])
        self.assertFalse(output.exists(), "No partial outward review issue may survive")

    def test_second_pdf_collision_is_preflight_before_any_output(self):
        general = self.root / "general.pdf"
        detailed = self.root / "detailed.pdf"
        annex = self.root / "annex.xlsx"
        create_pdf(general)
        create_pdf(detailed, fully_inked=True)
        annex.write_bytes(b"SYNTHETIC ANNEX")
        pins = self.root / "pins.json"
        pins.write_text(json.dumps({"sources": {
            role: {"sha256": mod.digest(path)}
            for role, path in (("general", general), ("detailed", detailed), ("annex", annex))
        }}))
        review = self.root / "review.json"
        review.write_text(json.dumps({"schema": mod.SCHEMA, "review_only": True,
            "engineering_approval": False, "authority_transfer": False,
            "items": [item("general"), item("detailed")]}))
        output = self.root / "no_orphan"
        with self.assertRaisesRegex(ValueError, "REVIEW_CALLOUT_COLLISION_HOLD"):
            mod.run(general, detailed, annex, pins, review, output)
        self.assertFalse(output.exists(), "An unqualified first PDF must not survive")


if __name__ == "__main__":
    unittest.main()
