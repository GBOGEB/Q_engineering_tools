import copy
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qps_visual_candidate_classifier.py"
spec = importlib.util.spec_from_file_location("qps_visual_candidate_classifier", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

BASELINE_SHA = "038054735c11a71c64d08a398532c4e014766b7ef5efdd5f6b71e61733857c61"
INTENTIONAL_SHA = "a57bfae661f44bb10e0cc0fd3a3730fc95fa09d5cd06273e1d3c72a14bb6d044"
HISTORICAL_INTENTIONAL_PPTX_SHA = "7a92e73c21def5d5c9126141638f4a2caad0fcf7f194a94d04788a3159a86ba0"


def guards():
    return {
        "schema": "qps-w286-visual-candidate-classification-input/3.0",
        "sample_only": True,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "golden_replaced": False,
        "candidate_promoted": False,
        "runtime_gold_923": "INDEPENDENT_NON_COMPENSATING",
        "N300_method_population": "UNCHANGED",
        "project_global_PCA": "WITHHELD",
    }


def contract(evidence_id, sha=None):
    data = guards()
    data.update(evidence_mode="CONTRACT_REPLAY", evidence_id=evidence_id)
    if sha is not None:
        data["candidate_artifact_sha256"] = sha
    return data


def external(candidate_sha=HISTORICAL_INTENTIONAL_PPTX_SHA):
    data = guards()
    data.update(
        evidence_mode="EXTERNAL_UNBOUND",
        candidate_artifact_sha256=candidate_sha,
        semantic_mismatch_count=0,
        text_mismatch_count=0,
        geometry_mismatch_count=0,
        out_of_bounds_shape_count=0,
        bounds_status="PASS",
        evidence_complete=True,
    )
    return data


def test_pass_hashes_actual_committed_candidate_bytes():
    assert mod.classify_candidate(contract("CONTRACT_PASS_01", BASELINE_SHA)) == "PASS"


def test_intentional_hashes_actual_committed_candidate_bytes_and_diffs_property():
    assert mod.classify_candidate(contract("CONTRACT_INTENTIONAL_01", INTENTIONAL_SHA)) == "INTENTIONAL_VISUAL_CHANGE"


def test_submitted_hash_cannot_disagree_with_actual_candidate_bytes():
    try:
        mod.classify_candidate(contract("CONTRACT_PASS_01", "0" * 64))
    except ValueError as exc:
        assert "classified artifact bytes" in str(exc)
    else:
        raise AssertionError("caller hash mismatch must fail")


def test_contract_candidate_bytes_mismatch_fails():
    original = mod._sha256
    mod._sha256 = lambda path: "0" * 64 if "INTENTIONAL" in path.name else original(path)
    try:
        try:
            mod.classify_candidate(contract("CONTRACT_INTENTIONAL_01"))
        except ValueError as exc:
            assert "candidate artifact bytes" in str(exc)
        else:
            raise AssertionError("candidate byte mismatch must fail")
    finally:
        mod._sha256 = original


def test_observed_diff_is_derived_not_read_from_contract():
    original = mod._load_contract_evidence
    forged = copy.deepcopy(original())
    forged["entries"]["CONTRACT_INTENTIONAL_01"]["declared_property_changes"] = ["shape.text:'stable'->'invented'"]
    mod._load_contract_evidence = lambda: forged
    try:
        try:
            mod.classify_candidate(contract("CONTRACT_INTENTIONAL_01"))
        except ValueError as exc:
            assert "observed artifact diff" in str(exc)
        else:
            raise AssertionError("declared change cannot redefine observation")
    finally:
        mod._load_contract_evidence = original


def test_external_historical_intentional_binary_is_not_auto_intentional():
    assert mod.classify_candidate(external()) == "REVIEW_REQUIRED"


def test_external_fake_golden_hash_is_not_auto_pass():
    assert mod.classify_candidate(external(BASELINE_SHA)) == "REVIEW_REQUIRED"


def test_external_hard_defect_is_regression():
    data = external()
    data["geometry_mismatch_count"] = 1
    assert mod.classify_candidate(data) == "REGRESSION"


def test_unknown_contract_evidence_fails():
    try:
        mod.classify_candidate(contract("DOES_NOT_EXIST"))
    except ValueError as exc:
        assert "unknown contract evidence_id" in str(exc)
    else:
        raise AssertionError("unknown contract evidence must fail")


def test_path_escape_fails():
    original = mod._load_contract_evidence
    forged = copy.deepcopy(original())
    forged["entries"]["CONTRACT_PASS_01"]["candidate_artifact_path"] = "../../outside.json"
    mod._load_contract_evidence = lambda: forged
    try:
        try:
            mod.classify_candidate(contract("CONTRACT_PASS_01"))
        except ValueError as exc:
            assert "escapes repository root" in str(exc)
        else:
            raise AssertionError("path escape must fail")
    finally:
        mod._load_contract_evidence = original


def test_pass_contract_cannot_declare_change():
    original = mod._load_contract_evidence
    forged = copy.deepcopy(original())
    forged["entries"]["CONTRACT_PASS_01"]["declared_property_changes"] = ["shape.fill_rgb:38BDF8->A855F7"]
    mod._load_contract_evidence = lambda: forged
    try:
        try:
            mod.classify_candidate(contract("CONTRACT_PASS_01"))
        except ValueError as exc:
            assert "cannot declare" in str(exc)
        else:
            raise AssertionError("PASS contract change declaration must fail")
    finally:
        mod._load_contract_evidence = original


def test_authority_inversion_fails():
    data = contract("CONTRACT_PASS_01")
    data["authority_transfer"] = True
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "authority_transfer" in str(exc)
    else:
        raise AssertionError("authority inversion must fail")


def test_runtime_gold_compensation_fails():
    data = contract("CONTRACT_PASS_01")
    data["runtime_gold_923"] = "COMPENSATED_BY_VISUAL_PASS"
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "runtime_gold_923" in str(exc)
    else:
        raise AssertionError("#923 compensation must fail")


def test_n300_mutation_fails():
    data = contract("CONTRACT_PASS_01")
    data["N300_method_population"] = "PROMOTED"
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "N300" in str(exc)
    else:
        raise AssertionError("N300 mutation must fail")


def test_project_global_pca_promotion_fails():
    data = contract("CONTRACT_PASS_01")
    data["project_global_PCA"] = "PROMOTED"
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "PCA" in str(exc)
    else:
        raise AssertionError("project/global PCA promotion must fail")


def test_old_governed_replay_mode_is_rejected():
    data = guards()
    data["evidence_mode"] = "GOVERNED_REPLAY"
    data["evidence_id"] = "GOLDEN_REPLAY_A_DARK_EXEC"
    try:
        mod.classify_candidate(data)
    except ValueError as exc:
        assert "evidence_mode" in str(exc)
    else:
        raise AssertionError("superseded evidence mode must fail")


def test_fixture_surface_cannot_claim_visual_authority():
    original = mod._load_fixture
    def forged(path):
        data = original(path)
        data = copy.deepcopy(data)
        data["surface"] = "visual_authority"
        return data
    mod._load_fixture = forged
    try:
        try:
            mod.classify_candidate(contract("CONTRACT_PASS_01"))
        except ValueError as exc:
            assert "visual-authority" in str(exc)
        else:
            raise AssertionError("fixture authority promotion must fail")
    finally:
        mod._load_fixture = original


def _write_fixture_variant(mutator):
    baseline = json.loads(
        (ROOT / "triage" / "w286" / "fixtures" / "QPS_W286_CLASSIFIER_BASELINE_FIXTURE_v0.1.json")
        .read_text(encoding="utf-8")
    )
    mutator(baseline)
    td = tempfile.TemporaryDirectory()
    path = Path(td.name) / "fixture.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    return td, path


def test_fixture_rejects_unknown_top_level_field():
    td, path = _write_fixture_variant(lambda data: data.__setitem__("unmodeled", "drift"))
    try:
        try:
            mod._load_fixture(path)
        except ValueError as exc:
            assert "top-level fields outside closed-world contract" in str(exc)
        else:
            raise AssertionError("unknown top-level field must fail closed")
    finally:
        td.cleanup()


def test_fixture_rejects_unknown_nested_shape_field():
    td, path = _write_fixture_variant(
        lambda data: data["shape"].__setitem__("shadow", {"blur": 4})
    )
    try:
        try:
            mod._load_fixture(path)
        except ValueError as exc:
            assert "shape fields outside closed-world contract" in str(exc)
        else:
            raise AssertionError("unknown nested shape field must fail closed")
    finally:
        td.cleanup()
