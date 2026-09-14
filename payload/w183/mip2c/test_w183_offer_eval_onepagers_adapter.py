from pathlib import Path
import importlib.util

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qps_w183_generate_offer_eval_onepagers.py"
DOCTRINE = ROOT / "controls" / "QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml"

spec = importlib.util.spec_from_file_location("mip2c", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


def build_tmp(tmp_path):
    out_dir = tmp_path / "pages"
    receipt = mod.build(DOCTRINE, out_dir)
    return out_dir, receipt


def text(path):
    d = Document(path)
    return "\n".join(p.text for p in d.paragraphs)


def test_exactly_eight_outputs_and_50_unique_offers(tmp_path):
    out_dir, receipt = build_tmp(tmp_path)
    files = sorted(out_dir.glob("*.docx"))
    assert len(files) == 8
    assert receipt["output_count"] == 8
    offers = [o for row in receipt["outputs"] for o in row["primary_offers"]]
    assert len(offers) == 50
    assert len(set(offers)) == 50


def test_fixed_blocks_and_gap_markers(tmp_path):
    out_dir, receipt = build_tmp(tmp_path)
    payloads = []
    for cid in mod.EXPECTED_CLUSTERS:
        t = text(out_dir / f"OFFER_EVAL_REVIEWER_ONEPAGER_{cid}.docx")
        assert "Score scale" in t
        assert "Confidence scale" in t
        assert "Reviewer score is not compliance status" in t
        assert f"NOT_SPECIFIED_IN_DOCTRINE:{cid}.reviewer_focus" in t
        assert f"NOT_SPECIFIED_IN_DOCTRINE:{cid}.what_good_looks_like" in t
        assert f"NOT_SPECIFIED_IN_DOCTRINE:{cid}.primary_scoring_trap" in t
        payloads.append(t)
    assert receipt["fixed_blocks_identical"] is True


def test_authority_boundary(tmp_path):
    _, receipt = build_tmp(tmp_path)
    assert receipt["authority_transfer"] is False
    assert receipt["formal_credit_delta"] == 0
    assert receipt["not_specified_markers_preserved"] is True
