#!/usr/bin/env python3
"""Validate W176 OFFER evaluation scoring doctrine invariants.

This validator is deliberately narrow. It proves the reviewer-conditioning model covers
exactly OFFER-01..OFFER-50 once as primary cluster members, preserves cluster-weight sum,
and keeps authority boundaries explicit. It does not score bidders or create compliance,
acceptance, negotiation, or award credit.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

EXPECTED = [f"OFFER-{i:02d}" for i in range(1, 51)]


def load_control(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("control root must be a mapping")
    return data


def validate(data: dict[str, Any]) -> dict[str, Any]:
    clusters = (((data.get("cluster_model") or {}).get("clusters")) or {})
    if not clusters:
        raise AssertionError("cluster_model.clusters missing")

    primary: list[str] = []
    for cid, cluster in clusters.items():
        offers = (cluster or {}).get("primary_offers") or []
        if not offers:
            raise AssertionError(f"{cid} has no primary_offers")
        primary.extend(str(x) for x in offers)

    counts = Counter(primary)
    duplicates = sorted([k for k, v in counts.items() if v > 1])
    unique = sorted(counts)
    omissions = sorted(set(EXPECTED) - set(unique))
    extras = sorted(set(unique) - set(EXPECTED))

    if len(primary) != 50:
        raise AssertionError(f"primary assignments={len(primary)} expected=50")
    if len(unique) != 50:
        raise AssertionError(f"unique primary offers={len(unique)} expected=50")
    if duplicates:
        raise AssertionError(f"duplicate primary offers: {duplicates}")
    if omissions:
        raise AssertionError(f"omitted offers: {omissions}")
    if extras:
        raise AssertionError(f"unexpected offers: {extras}")

    weights = data.get("cluster_weights") or {}
    weight_values = [float(weights[c]) for c in sorted(clusters) if c in weights]
    if len(weight_values) != len(clusters):
        raise AssertionError("cluster_weights do not cover every cluster")
    total = sum(weight_values)
    if abs(total - 1.0) > 1e-9:
        raise AssertionError(f"cluster weight sum={total} expected=1.0")

    boundary = data.get("model_boundary") or {}
    required_false_authority = {
        "confidence_is_not_evidence_maturity": True,
        "reviewer_score_is_not_compliance_status": True,
        "pairwise_preference_is_not_award_authority": True,
        "cluster_dominance_is_not_SCK_acceptance": True,
        "generated_narrative_is_not_source_authority": True,
    }
    for key, expected in required_false_authority.items():
        if boundary.get(key) is not expected:
            raise AssertionError(f"authority guard {key} must be true")

    return {
        "status": "PASS",
        "primary_assignments": len(primary),
        "unique_primary_offers": len(unique),
        "duplicates": duplicates,
        "omissions": omissions,
        "cluster_count": len(clusters),
        "cluster_weight_sum": total,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "control",
        nargs="?",
        type=Path,
        default=Path("controls/QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml"),
    )
    args = ap.parse_args()
    result = validate(load_control(args.control))
    print(yaml.safe_dump(result, sort_keys=False).strip())


if __name__ == "__main__":
    main()
