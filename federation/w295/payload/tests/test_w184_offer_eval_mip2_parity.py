from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qps_w184_validate_offer_eval_mip2_parity.py"

spec = importlib.util.spec_from_file_location("mip2d", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


def test_cross_output_equation_v1_parity_and_authority_guards(tmp_path):
    receipt = mod.validate(ROOT, tmp_path)
    assert receipt["status"] == "PASS_CROSS_OUTPUT_EQUATION_V1_PARITY_WITH_NATIVE_EXCEL_GATE_OPEN"
    assert receipt["equation_version"] == "OFFER_EVAL_EQ_v1"
    assert receipt["offer_count"] == 50
    assert receipt["cluster_count"] == 8
    assert receipt["same_doctrine_identity"] is True
    assert receipt["same_offer_cluster_map"] is True
    assert receipt["static_importance_before_bidder_comparison"] is True
    assert receipt["pairwise_and_risk_separate"] is True
    assert receipt["confidence_conditioning_parity"] is True
    assert receipt["NA_applicability_parity"] is True
    assert receipt["missing_defer_fail_preserved"] is True
    assert receipt["all_NA_cluster_unscorable"] is True
    assert receipt["incomplete_pairwise_totals_withheld"] is True
    assert receipt["risk_application_count"] == 1
    assert receipt["final_system_risk_subtraction"] is False
    assert receipt["source_gaps_not_invented"] is True
    assert receipt["authority_transfer"] is False
    assert receipt["formal_credit_delta"] == 0


def test_native_excel_gate_and_global_3p3_remain_fail_closed(tmp_path):
    receipt = mod.validate(ROOT, tmp_path)
    assert receipt["native_excel_clean_roundtrip"] == "WITHHELD_REQUIRES_EXCEL_RUNTIME"
    assert receipt["global_3p3_admission"] == "HOLD_NATIVE_EXCEL_ROUNDTRIP_AND_CHILD_REENTRY_RECEIPT"


def test_each_adapter_passes_inside_parity_transaction(tmp_path):
    receipt = mod.validate(ROOT, tmp_path)
    assert receipt["mip2a_status"] == "PASS_OPENPYXL_EQUATION_V1_ROUNDTRIP_NO_TABLE_PART"
    assert receipt["mip2b_status"] == "PASS_SOURCE_DRIVEN_NARRATIVE_EQUATION_V1_VISIBLE"
    assert receipt["mip2c_status"] == "PASS_EIGHT_SOURCE_DRIVEN_ONEPAGERS"
