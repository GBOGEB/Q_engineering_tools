import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qps_visual_candidate_classifier.py"
spec = importlib.util.spec_from_file_location("qps_visual_candidate_classifier", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GOLDEN = "efc646210debc1bf11e3027255c389b92e2de13883223ab6ff2f518a852b83c7"
INTENTIONAL = "2c08469879fd9d2bc7ad4b470ad95efc1dc7b7a543c090c90d87df55449ee578"


def guards():
    return {
        "schema": "qps-w286-visual-candidate-classification-input/2.0",
        "sample_only": True,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "golden_replaced": False,
        "candidate_promoted": False,
        "runtime_gold_923": "INDEPENDENT_NON_COMPENSATING",
        "N300_method_population": "UNCHANGED",
        "project_global_PCA": "WITHHELD",
    }


def replay(evidence_id):
    data = guards()
    data.update(evidence_mode="GOVERNED_REPLAY", evidence_id=evidence_id)
    return data


def external(candidate_hash=INTENTIONAL):
    data = guards()
    data.update(
        evidence_mode="EXTERNAL_UNBOUND",
        candidate_render_sha256=candidate_hash,
        semantic_mismatch_count=0,
        text_mismatch_count=0,
        geometry_mismatch_count=0,
        out_of_bounds_shape_count=0,
        bounds_status="PASS",
        evidence_complete=True,
    )
    return data


def test_pass_requires_registered_golden_replay():
    assert mod.classify_candidate(replay("GOLDEN_REPLAY_A_DARK_EXEC")) == "PASS"


def test_intentional_requires_registered_comparison_receipt():
    assert mod.classify_candidate(replay("INTENTIONAL_DIFF_01")) == "INTENTIONAL_VISUAL_CHANGE"


def test_regression_registered_receipt():
    assert mod.classify_candidate(replay("REGRESSION_01")) == "REGRESSION"


def test_external_equal_golden_hash_cannot_pass():
    assert mod.classify_candidate(external(GOLDEN)) == "REVIEW_REQUIRED"


def test_external_intentional_hash_cannot_self_attest_intent():
    assert mod.classify_candidate(external(INTENTIONAL)) == "REVIEW_REQUIRED"


def test_external_invented_property_lists_are_ignored_for_promotion():
    data = external(INTENTIONAL)
    data["declared_visual_change"] = {
        "present": True,
        "declared_property_changes": ["invented"],
        "observed_property_changes": ["invented"],
    }
    assert mod.classify_candidate(data) == "REVIEW_REQUIRED"


def test_external_hard_defect_may_only_fail_more_closed():
    data = external()
    data["geometry_mismatch_count"] = 1
    assert mod.classify_candidate(data) == "REGRESSION"


def test_unknown_governed_evidence_fails():
    try:
        mod.classify_candidate(replay("DOES_NOT_EXIST"))
    except ValueError as exc:
        assert "unknown governed evidence_id" in str(exc)
    else:
        raise AssertionError("unknown evidence must fail")


def test_catalog_source_blob_mismatch_fails(monkeypatch=None):
    original = mod._git_blob_sha1
    mod._git_blob_sha1 = lambda path: "0" * 40
    try:
        try:
            mod.classify_candidate(replay("GOLDEN_REPLAY_A_DARK_EXEC"))
        except ValueError as exc:
            assert "Git blob mismatch" in str(exc)
        else:
            raise AssertionError("source blob mismatch must fail")
    finally:
        mod._git_blob_sha1 = original


def test_authority_inversion_fails():
    data = replay("GOLDEN_REPLAY_A_DARK_EXEC")
    data["authority_transfer"] = True
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "authority_transfer" in str(exc)
    else:
        raise AssertionError("authority inversion must fail")


def test_runtime_gold_compensation_fails():
    data = replay("GOLDEN_REPLAY_A_DARK_EXEC")
    data["runtime_gold_923"] = "COMPENSATED_BY_VISUAL_PASS"
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "runtime_gold_923" in str(exc)
    else:
        raise AssertionError("#923 compensation must fail")


def test_n300_mutation_fails():
    data = replay("GOLDEN_REPLAY_A_DARK_EXEC")
    data["N300_method_population"] = "PROMOTED"
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "N300" in str(exc)
    else:
        raise AssertionError("N300 mutation must fail")


def test_project_global_pca_promotion_fails():
    data = replay("GOLDEN_REPLAY_A_DARK_EXEC")
    data["project_global_PCA"] = "PROMOTED"
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "PCA" in str(exc)
    else:
        raise AssertionError("project/global PCA promotion must fail")


def test_catalog_cannot_redefine_golden_hash():
    original = mod._load_catalog
    data = original()
    forged = copy.deepcopy(data)
    forged["entries"]["GOLDEN_REPLAY_A_DARK_EXEC"]["candidate_render_sha256"] = "0" * 64
    mod._load_catalog = lambda: forged
    try:
        try:
            mod.classify_candidate(replay("GOLDEN_REPLAY_A_DARK_EXEC"))
        except ValueError as exc:
            assert "bound registry" in str(exc)
        else:
            raise AssertionError("catalog must not redefine governed golden hash")
    finally:
        mod._load_catalog = original


def test_catalog_cannot_redefine_observed_intentional_change():
    original = mod._load_catalog
    data = original()
    forged = copy.deepcopy(data)
    forged["entries"]["INTENTIONAL_DIFF_01"]["observed_property_changes"] = ["invented"]
    mod._load_catalog = lambda: forged
    try:
        try:
            mod.classify_candidate(replay("INTENTIONAL_DIFF_01"))
        except ValueError as exc:
            assert "bound diff receipt" in str(exc)
        else:
            raise AssertionError("catalog must not redefine observed change")
    finally:
        mod._load_catalog = original
