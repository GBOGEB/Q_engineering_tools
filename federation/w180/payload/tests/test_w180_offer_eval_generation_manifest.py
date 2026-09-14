from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qps_w180_build_offer_eval_generation_manifest.py"
DOCTRINE = ROOT / "controls" / "QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml"

spec = importlib.util.spec_from_file_location("w180_manifest", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def build():
    return mod.build_manifest(DOCTRINE)


def test_exact_denominators_and_ten_output_contracts():
    m = build()
    assert m["doctrine"]["offer_count"] == 50
    assert m["doctrine"]["cluster_count"] == 8
    assert m["doctrine"]["cluster_weight_sum"] == 1.0
    assert m["output_count"] == 10
    assert {x["family"] for x in m["outputs"]} == {"workbook", "narrative", "reviewer_onepager"}


def test_every_offer_is_primary_exactly_once():
    m = build()
    flat = [offer for cid in sorted(m["primary_cluster_map"]) for offer in m["primary_cluster_map"][cid]]
    assert len(flat) == 50
    assert len(set(flat)) == 50
    assert set(flat) == {f"OFFER-{i:02d}" for i in range(1, 51)}


def test_all_outputs_bind_same_doctrine_identity():
    m = build()
    doctrine_sha = m["doctrine"]["sha256"]
    assert doctrine_sha
    assert all(x["doctrine_sha256"] == doctrine_sha for x in m["outputs"])


def test_exactly_eight_onepagers_bind_cluster_specific_rows():
    m = build()
    pages = [x for x in m["outputs"] if x["family"] == "reviewer_onepager"]
    assert len(pages) == 8
    assert {x["cluster"] for x in pages} == {f"C{i}" for i in range(1, 9)}
    for page in pages:
        cid = page["cluster"]
        assert page["primary_offers"] == m["primary_cluster_map"][cid]
        assert page["cluster_weight"] > 0


def test_generated_outputs_remain_fail_closed():
    assert build()["authority_guards"] == {
        "generated_output_is_source_authority": False,
        "generated_output_creates_compliance_credit": False,
        "generated_output_creates_sck_acceptance": False,
        "generated_output_creates_award_authority": False,
        "repo_local_issue_923_compensated": False,
    }
