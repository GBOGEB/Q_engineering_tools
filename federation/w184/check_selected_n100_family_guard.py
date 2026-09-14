#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

POST_INPUTS = [
    "ocd-adr/40_implementation/QPS_VISUAL_N104_PILOT_PROVENANCE.csv",
    "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W169_PROVENANCE.csv",
    "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W170_PROVENANCE.csv",
    "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W173_AUTH_RECONCILED.csv",
    "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W174_PROVENANCE.csv",
    "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W176_PPTX_AUTH_RECONCILED.csv",
    "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W176_XLSX_AUTH_RECONCILED.csv",
    "ocd-adr/40_implementation/QPS_VISUAL_N200_COLLECTION_W176_HTML_AUTH_RECONCILED.csv",
]
N100_SELECTED = "ocd-adr/40_implementation/QPS_VISUAL_CENSUS_DERIVED_ARTIFACT_N100.generated.csv"


def norm(value: object) -> str:
    return re.sub(r"\s+", "_", str(value).strip().lower())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.execution_root.resolve()

    n100 = pd.read_csv(root / N100_SELECTED)
    if len(n100) != 100:
        raise SystemExit(f"W184_FAMILY_GUARD_FAIL: selected N100 row count {len(n100)} != 100")
    if n100["artifact_format"].value_counts().to_dict() != {"HTML": 25, "PDF": 25, "PPTX": 25, "XLSX": 25}:
        raise SystemExit("W184_FAMILY_GUARD_FAIL: selected N100 is not exactly 25 per format")

    post = pd.concat([pd.read_csv(root / rel) for rel in POST_INPUTS], ignore_index=True)
    if len(post) != 100:
        raise SystemExit(f"W184_FAMILY_GUARD_FAIL: post-N100 row count {len(post)} != 100")

    # Frozen-control keys must come from the selected/generated N100 artifact population,
    # not all 112 eligible raw candidate rows. The selected matrix has exact artifact IDs.
    n100_keys = {
        f"{str(row['artifact_format']).strip().upper()}::{norm(row['artifact_id'])}"
        for _, row in n100.iterrows()
    }

    # Post-N100 cohorts may carry a governed explicit family_key. Preserve that key and
    # also the exact artifact-id alias so exact repeats cannot bypass the family guard.
    post_keys: set[str] = set()
    for _, row in post.iterrows():
        fmt = str(row["artifact_format"]).strip().upper()
        artifact = norm(row["artifact_id"])
        post_keys.add(f"{fmt}::{artifact}")
        explicit = str(row.get("family_key", "")).strip()
        if explicit and explicit.lower() != "nan":
            post_keys.add(f"{fmt}::{norm(explicit)}")

    collisions = sorted(n100_keys & post_keys)
    result = {
        "schema": "qtools-w184f-selected-n100-family-guard/0.2",
        "n100_basis": "GENERATED_BALANCED_N100_SELECTED_ARTIFACT_POPULATION",
        "n100_selected_rows": len(n100),
        "n100_family_key_count": len(n100_keys),
        "post_rows": len(post),
        "post_family_key_count": len(post_keys),
        "cross_selected_n100_family_collisions": collisions,
        "cross_selected_n100_family_collision_count": len(collisions),
        "status": "PASS" if not collisions else "FAIL",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    if collisions:
        raise SystemExit(f"W184_FAMILY_GUARD_FAIL: selected-N100 collisions {collisions}")


if __name__ == "__main__":
    main()
