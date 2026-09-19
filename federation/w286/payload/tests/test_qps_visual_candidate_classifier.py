import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qps_visual_candidate_classifier.py"
spec = importlib.util.spec_from_file_location("qps_visual_candidate_classifier", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GOLDEN = "efc646210debc1bf11e3027255c389b92e2de13883223ab6ff2f518a852b83c7"
INTENTIONAL = "2c08469879fd9d2bc7ad4b470ad95efc1dc7b7a543c090c90d87df55449ee578"
REGRESSION = "a6414617252f317230f4684c8f6c6ab790d3e9b96ba93f1285c27bc5f9d79131"


def base():
    return {
        "schema": "qps-w286-visual-candidate-classification-input/1.0",
        "sample_only": True,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "golden_replaced": False,
        "candidate_promoted": False,
        "golden_render_sha256": GOLDEN,
        "candidate_render_sha256": GOLDEN,
        "render_changed": False,
        "declared_visual_change": {"present": False, "changed_property_count": 0},
        "semantic_mismatch_count": 0,
        "text_mismatch_count": 0,
        "geometry_mismatch_count": 0,
        "out_of_bounds_shape_count": 0,
        "bounds_status": "PASS",
        "evidence_complete": True,
    }


def test_pass_exact_golden_replay():
    assert mod.classify_candidate(base()) == "PASS"


def test_intentional_visual_change_matches_observed_w286_candidate():
    data = base()
    data.update(
        candidate_render_sha256=INTENTIONAL,
        render_changed=True,
        declared_visual_change={"present": True, "changed_property_count": 1},
    )
    assert mod.classify_candidate(data) == "INTENTIONAL_VISUAL_CHANGE"


def test_regression_matches_observed_out_of_bounds_w286_candidate():
    data = base()
    data.update(
        candidate_render_sha256=REGRESSION,
        render_changed=True,
        declared_visual_change={"present": True, "changed_property_count": 3},
        geometry_mismatch_count=3,
        out_of_bounds_shape_count=3,
        bounds_status="FAIL",
    )
    assert mod.classify_candidate(data) == "REGRESSION"


def test_review_required_for_unexplained_render_change():
    data = base()
    data.update(candidate_render_sha256=INTENTIONAL, render_changed=True)
    assert mod.classify_candidate(data) == "REVIEW_REQUIRED"


def test_review_required_for_incomplete_evidence():
    data = base()
    data["evidence_complete"] = False
    assert mod.classify_candidate(data) == "REVIEW_REQUIRED"


def test_review_required_for_hash_render_change_inconsistency():
    data = base()
    data["candidate_render_sha256"] = INTENTIONAL
    assert mod.classify_candidate(data) == "REVIEW_REQUIRED"


def test_authority_inversion_fails():
    data = base()
    data["authority_transfer"] = True
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "authority_transfer" in str(exc)
    else:
        raise AssertionError("authority inversion must fail")


def test_invalid_hash_fails():
    data = base()
    data["candidate_render_sha256"] = "not-a-sha"
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "candidate_render_sha256" in str(exc)
    else:
        raise AssertionError("invalid hash must fail")
