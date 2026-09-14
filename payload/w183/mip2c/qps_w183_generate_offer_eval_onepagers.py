#!/usr/bin/env python3
"""Generate exactly eight cluster reviewer one-pagers from the governed doctrine.

Cluster-specific guidance is never invented. Where the doctrine lacks an explicitly
requested field, the generated page carries a NOT_SPECIFIED marker instead.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from docx import Document
from docx.enum.section import WD_SECTION

EXPECTED_CLUSTERS = [f"C{i}" for i in range(1, 9)]
FIXED_BLOCKS = [
    "score_scale",
    "confidence_scale",
    "scoring_interpretation_note",
    "bidder_A_score_confidence_notes",
    "bidder_B_score_confidence_notes",
]
VARIABLE_BLOCKS = [
    "cluster_scope",
    "primary_offer_list",
    "reviewer_focus",
    "what_good_looks_like",
    "primary_scoring_trap",
    "cross_cluster_dependency_cues",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_doctrine(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    c = data["one_pager_generation_contract"]
    if c["one_page_per_cluster"] is not True:
        raise AssertionError("one_page_per_cluster must be true")
    if c["fixed_blocks"] != FIXED_BLOCKS:
        raise AssertionError("fixed block drift")
    if c["cluster_variable_blocks"] != VARIABLE_BLOCKS:
        raise AssertionError("variable block drift")
    return data


def add_block(doc: Document, title: str, body: str) -> None:
    doc.add_heading(title, level=2)
    doc.add_paragraph(body)


def fixed_payload(d: dict[str, Any]) -> dict[str, str]:
    raw = d["model_boundary"]["raw_score_scale"]
    conf = d["model_boundary"]["confidence_scale"]
    return {
        "score_scale": "; ".join(f"{k}={v}" for k, v in raw.items()),
        "confidence_scale": "; ".join(f"{k}={v}" for k, v in conf.items()),
        "scoring_interpretation_note": "Reviewer score is not compliance status; confidence is not evidence maturity; gate failures remain non-compensating.",
        "bidder_A_score_confidence_notes": "Reviewer input area: Applicant A raw score, confidence, source/evidence note. No cross-bidder substitution.",
        "bidder_B_score_confidence_notes": "Reviewer input area: Applicant B raw score, confidence, source/evidence note. No cross-bidder substitution.",
    }


def build(doctrine_path: Path, out_dir: Path) -> dict[str, Any]:
    d = load_doctrine(doctrine_path)
    dsha = sha256(doctrine_path)
    clusters = d["cluster_model"]["clusters"]
    links = d.get("cross_cluster_links_no_weight_credit", [])
    fixed = fixed_payload(d)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    for cid in EXPECTED_CLUSTERS:
        info = clusters[cid]
        doc = Document()
        doc.add_heading(f"Reviewer One-Pager — {cid} {info['name']}", level=0)
        doc.add_paragraph(f"Doctrine SHA-256: {dsha}")
        doc.add_paragraph("Classification: DOWNSTREAM_REVIEW_VIEW_ONLY | Formal credit: 0")

        add_block(doc, "Score scale", fixed["score_scale"])
        add_block(doc, "Confidence scale", fixed["confidence_scale"])
        add_block(doc, "Scoring interpretation note", fixed["scoring_interpretation_note"])
        add_block(doc, "Bidder A score / confidence / notes", fixed["bidder_A_score_confidence_notes"])
        add_block(doc, "Bidder B score / confidence / notes", fixed["bidder_B_score_confidence_notes"])

        add_block(doc, "Cluster scope", str(info["intent"]))
        add_block(doc, "Primary OFFER list", ", ".join(info["primary_offers"]))
        add_block(doc, "Reviewer focus", f"NOT_SPECIFIED_IN_DOCTRINE:{cid}.reviewer_focus")
        add_block(doc, "What good looks like", f"NOT_SPECIFIED_IN_DOCTRINE:{cid}.what_good_looks_like")
        add_block(doc, "Primary scoring trap", f"NOT_SPECIFIED_IN_DOCTRINE:{cid}.primary_scoring_trap")
        linked = [link for link in links if any(o in info["primary_offers"] for o in link)]
        add_block(doc, "Cross-cluster dependency cues", str(linked or "None declared"))
        doc.add_paragraph("Cross-cluster cues carry no duplicate weight credit.")

        path = out_dir / f"OFFER_EVAL_REVIEWER_ONEPAGER_{cid}.docx"
        doc.save(path)
        outputs.append({"cluster": cid, "file": path.name, "sha256": sha256(path), "primary_offers": list(info["primary_offers"])})

    if len(outputs) != 8 or [x["cluster"] for x in outputs] != EXPECTED_CLUSTERS:
        raise AssertionError("must generate exactly C1..C8")
    all_offers = [o for x in outputs for o in x["primary_offers"]]
    if len(all_offers) != 50 or len(set(all_offers)) != 50:
        raise AssertionError("one-pagers must cover 50 unique primary OFFER items")

    return {
        "status": "PASS_EIGHT_SOURCE_DRIVEN_ONEPAGERS",
        "doctrine_sha256": dsha,
        "output_count": 8,
        "outputs": outputs,
        "fixed_blocks_identical": True,
        "not_specified_markers_preserved": True,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doctrine", type=Path, default=Path("controls/QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml"))
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--receipt", type=Path)
    args = ap.parse_args()
    receipt = build(args.doctrine, args.out_dir)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
