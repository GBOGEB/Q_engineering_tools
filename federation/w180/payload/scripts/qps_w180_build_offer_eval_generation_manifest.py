#!/usr/bin/env python3
"""Build the M08 MIP-2 generation manifest from the governed OFFER doctrine.

This first generator-integration slice does not render XLSX/DOCX binaries. It proves
that every downstream generator family can consume one doctrine identity and one exact
50-item cluster map instead of hand-copying method semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

EXPECTED_OFFERS = [f"OFFER-{i:02d}" for i in range(1, 51)]
EXPECTED_CLUSTERS = [f"C{i}" for i in range(1, 9)]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_doctrine(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise AssertionError("doctrine root must be a mapping")
    return data, sha256_bytes(raw)


def validate_doctrine(data: dict[str, Any]) -> tuple[dict[str, list[str]], dict[str, float]]:
    clusters = ((data.get("cluster_model") or {}).get("clusters")) or {}
    if sorted(clusters) != EXPECTED_CLUSTERS:
        raise AssertionError(f"clusters={sorted(clusters)} expected={EXPECTED_CLUSTERS}")

    primary_map: dict[str, list[str]] = {}
    assigned: list[str] = []
    for cid in EXPECTED_CLUSTERS:
        offers = [str(x) for x in (clusters[cid].get("primary_offers") or [])]
        if not offers:
            raise AssertionError(f"{cid} has no primary offers")
        primary_map[cid] = offers
        assigned.extend(offers)

    counts = Counter(assigned)
    duplicates = sorted(k for k, v in counts.items() if v > 1)
    omissions = sorted(set(EXPECTED_OFFERS) - set(counts))
    extras = sorted(set(counts) - set(EXPECTED_OFFERS))
    if len(assigned) != 50 or len(counts) != 50 or duplicates or omissions or extras:
        raise AssertionError(
            f"invalid primary map assignments={len(assigned)} unique={len(counts)} "
            f"duplicates={duplicates} omissions={omissions} extras={extras}"
        )

    configured_weights = data.get("cluster_weights") or {}
    weights = {cid: float(configured_weights[cid]) for cid in EXPECTED_CLUSTERS}
    if abs(sum(weights.values()) - 1.0) > 1e-12:
        raise AssertionError(f"cluster weights sum={sum(weights.values())}, expected=1.0")

    boundary = data.get("model_boundary") or {}
    required_true = [
        "confidence_is_not_evidence_maturity",
        "reviewer_score_is_not_compliance_status",
        "pairwise_preference_is_not_award_authority",
        "cluster_dominance_is_not_SCK_acceptance",
        "generated_narrative_is_not_source_authority",
    ]
    bad = [name for name in required_true if boundary.get(name) is not True]
    if bad:
        raise AssertionError(f"authority guards not true: {bad}")
    return primary_map, weights


def build_manifest(doctrine_path: Path) -> dict[str, Any]:
    doctrine, doctrine_sha = load_doctrine(doctrine_path)
    primary_map, weights = validate_doctrine(doctrine)

    outputs: list[dict[str, Any]] = [
        {
            "id": "M08-WORKBOOK",
            "family": "workbook",
            "logical_name": "OFFER_EVAL_WORKBOOK",
            "binary_kind": "XLSX",
            "state": "GENERATOR_ADAPTER_REQUIRED",
            "doctrine_sha256": doctrine_sha,
        },
        {
            "id": "M08-NARRATIVE",
            "family": "narrative",
            "logical_name": "FULL_RECURSIVE_V6_NARRATIVE",
            "binary_kind": "DOCX",
            "state": "GENERATOR_ADAPTER_REQUIRED",
            "doctrine_sha256": doctrine_sha,
        },
    ]
    for cid in EXPECTED_CLUSTERS:
        outputs.append(
            {
                "id": f"M08-ONEPAGER-{cid}",
                "family": "reviewer_onepager",
                "cluster": cid,
                "logical_name": f"OFFER_EVAL_REVIEWER_ONEPAGER_{cid}",
                "binary_kind": "DOCX",
                "state": "GENERATOR_ADAPTER_REQUIRED",
                "doctrine_sha256": doctrine_sha,
                "primary_offers": primary_map[cid],
                "cluster_weight": weights[cid],
            }
        )

    return {
        "schema": "qps.m08.offer_eval_generation_manifest.v1",
        "mission": "M08_OFFER_EVAL_METHOD",
        "wave": "W180_MIP2_SEED",
        "classification": "GENERATOR_INPUT_CONTRACT_NOT_ENGINEERING_AUTHORITY",
        "doctrine": {
            "path": doctrine_path.as_posix(),
            "sha256": doctrine_sha,
            "offer_count": 50,
            "cluster_count": 8,
            "cluster_weight_sum": sum(weights.values()),
        },
        "primary_cluster_map": primary_map,
        "outputs": outputs,
        "output_count": len(outputs),
        "authority_guards": {
            "generated_output_is_source_authority": False,
            "generated_output_creates_compliance_credit": False,
            "generated_output_creates_sck_acceptance": False,
            "generated_output_creates_award_authority": False,
            "repo_local_issue_923_compensated": False,
        },
        "next_gate": "BIND_REAL_WORKBOOK_NARRATIVE_AND_8_ONEPAGER_ADAPTERS_TO_THIS_MANIFEST",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doctrine", type=Path, default=Path("controls/QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    manifest = build_manifest(args.doctrine)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "output_count": manifest["output_count"]}))


if __name__ == "__main__":
    main()
