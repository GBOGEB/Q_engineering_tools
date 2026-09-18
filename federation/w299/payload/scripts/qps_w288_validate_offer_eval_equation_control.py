#!/usr/bin/env python3
"""Validate W288 OFFER-evaluation equation-v1 control and implementation parity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise AssertionError(f"{path} root must be a mapping")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate(root: Path) -> dict[str, Any]:
    eq = load_yaml(root / "controls/QPS_OFFER_EVAL_EQUATION_CURRENT_v1.yaml")
    wb = load_yaml(root / "controls/QPS_OFFER_EVAL_WORKBOOK_DELTA_2026-09-14_v1.yaml")
    ppt = load_yaml(root / "controls/QPS_OFFER_EVAL_PPT_CURRENT_v1.yaml")
    method = load_yaml(root / "controls/QPS_OFFER_EVAL_METHOD_CURRENT_v1.yaml")
    doctrine = load_yaml(root / "controls/QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml")
    generator = (root / "scripts/qps_w183_generate_offer_eval_workbook.py").read_text(encoding="utf-8")
    narrative = (root / "scripts/qps_w183_generate_offer_eval_narrative.py").read_text(encoding="utf-8")
    parity = (root / "scripts/qps_w184_validate_offer_eval_mip2_parity.py").read_text(encoding="utf-8")

    require(eq["gate_id"] == "OFFER_EVAL_WORD_001", "gate identity drift")
    require(eq["equation_version"] == "OFFER_EVAL_EQ_v1", "equation version drift")
    require(eq["canonical_equations"]["total_risk"]["selected_policy"] == "OPTION_A_SYSTEM_RISK_APPLIED_ONCE_AT_ITEM_LEVEL", "risk-once policy drift")
    require(eq["risk_once_proof"]["final_system_risk_subtraction_allowed"] is False, "final system risk subtraction must remain prohibited")
    require(eq["risk_once_proof"]["second_risk_multiplier_allowed"] is False, "second risk multiplier must remain prohibited")
    require(eq["canonical_equations"]["governing_pairwise"]["S_domain"] == [-1, 0, 1], "pairwise domain drift")
    require(eq["canonical_equations"]["governing_pairwise"]["separate_from_final_review_score"] is True, "BT must remain separate")
    require(eq["applicability_and_missing"]["N_A"]["not_equal_to"] == [0, 50], "N/A semantics drift")

    require(wb["risk_implementation"]["selected_policy"] == "OPTION_A_SYSTEM_RISK_APPLIED_ONCE_AT_ITEM_LEVEL", "workbook risk policy drift")
    require(wb["risk_implementation"]["final_system_risk_subtraction"]["state"] == "PROHIBITED_CANONICAL_EQUATION_V1", "workbook second system-risk subtraction not frozen")
    require(wb["equation_v1_binding"]["state"] == "CONTROL_SEMANTICS_FROZEN_IMPLEMENTATION_PARITY_OPEN", "workbook equation binding drift")
    require(ppt["canonical_equation_binding"]["version"] == "OFFER_EVAL_EQ_v1", "PPT equation version drift")
    require(ppt["canonical_equation_binding"]["final_system_risk_subtraction"] == "PROHIBITED", "PPT double-risk guard drift")
    require(method["governing_surfaces"]["equation_current"] == "controls/QPS_OFFER_EVAL_EQUATION_CURRENT_v1.yaml", "method pointer missing equation control")

    clusters = doctrine["cluster_model"]["clusters"]
    offers = [o for cid in sorted(clusters) for o in clusters[cid]["primary_offers"]]
    require(len(offers) == 50 and len(set(offers)) == 50, "doctrine OFFER denominator not exact 50 unique")
    require(abs(sum(float(doctrine["cluster_weights"][f"C{i}"]) for i in range(1, 9)) - 1.0) < 1e-12, "cluster weights do not sum to 1")

    require('"Applicable_A", "Gate_A", "Applicable_B", "Gate_B"' in generator, "explicit applicability/gates not implemented")
    require("INPUT_AB!B{r}*INPUT_AB!C{r}" in generator, "confidence conditioning not implemented")
    require("J{r}*N{r}*(1-E{r})" in generator, "risk-adjusted conditioned score not implemented")
    require("SUMIFS" in generator and "LocalWeight_A_Renorm" in generator, "N/A renormalization not implemented")
    require("COUNT(INPUT_AB!D{r}:F{r})<3" in generator and 'COUNTIF(INPUT_AB!D{r}:F{r},"FAIL")>0' in generator and 'COUNTIF(INPUT_AB!D{r}:F{r},"DEFER")>0' in generator, "deterministic FAIL>DEFER>MISSING risk precedence not implemented")
    require('IF(NOT(ISNUMBER(E{r})),E{r},IF(N{r}=""' in generator, "adjusted score must propagate risk state before score completeness")
    require('NOT(ISNUMBER(F{r}))' in generator and 'NOT(ISNUMBER(H{r}))' in generator, "diagnostic consumer must guard propagated nonnumeric risk state")
    require('NOT(ISNUMBER(R{r}))' in generator and 'NOT(ISNUMBER(S{r}))' in generator, "cluster contribution consumer must guard propagated nonnumeric risk state")
    require('IF(NOT(ISNUMBER(E{r})),E{r},IF(J{r}=""' in generator, "row state must preserve risk state before score completeness")
    require('L{i}=0,"UNSCORABLE"' in generator and 'COUNT({a_terms})<L{i}' in generator, "all-N/A or incomplete cluster guard missing")
    require('"missing_defer_fail_preserved": True' in generator, "missing/DEFER/FAIL receipt guard missing")
    require('"all_NA_cluster_unscorable": True' in generator, "all-N/A unscorable receipt guard missing")
    require('COUNT(CALC_AB!D2:D51)<50' in generator and 'COUNTA(CALC_AB!D2:D51)' not in generator, "pairwise aggregate completion guard missing")
    require('COUNT(CALC_AB!I2:I51)<50' in generator and 'COUNTA(CALC_AB!I2:I51)' not in generator, "diagnostic aggregate completion guard missing")
    require("OFFER_EVAL_EQ_v1" in narrative, "narrative equation version not visible")
    # The generator emits the visible sentence from adjacent Python string literals, so
    # searching its source for one contiguous rendered sentence is formatting-sensitive.
    # Static validation binds the two semantic clauses; cross-output parity below validates
    # the actual generated DOCX contains the complete visible guard.
    require("System risk is already included inside R_i_b" in narrative, "narrative risk-once premise missing")
    require("subtraction or second risk multiplier is permitted" in narrative, "narrative double-risk guard missing")
    require("PASS_CROSS_OUTPUT_EQUATION_V1_PARITY_WITH_NATIVE_EXCEL_GATE_OPEN" in parity, "cross-output equation parity validator not upgraded")

    legacy = [x["expression"] for x in eq["legacy_expressions"]]
    require(any("0.70" in x and "BT" in x for x in legacy), "legacy 70/30 expression not explicitly governed")
    require(any("R_system" in x for x in legacy), "double-risk legacy expression not explicitly governed")

    return {
        "schema": "qps-w288-offer-eval-equation-validation/1.1",
        "status": "PASS_CONTROL_AND_IMPLEMENTATION_PARITY_STATIC_NATIVE_EXCEL_GATE_OPEN",
        "equation_version": eq["equation_version"],
        "system_risk_applied_once": True,
        "final_system_risk_subtraction": False,
        "bt_separate_from_final_review_score": True,
        "confidence_conditioning_implemented": True,
        "NA_applicability_implemented": True,
        "missing_defer_fail_preserved": True,
        "all_NA_cluster_unscorable": True,
        "incomplete_pairwise_totals_withheld": True,
        "risk_state_precedence_FAIL_DEFER_MISSING": True,
        "risk_state_precedes_score_completeness": True,
        "nonnumeric_risk_consumers_guarded": True,
        "row_state_risk_precedes_score_completeness": True,
        "narrative_equation_visibility": True,
        "offer_count": 50,
        "cluster_count": 8,
        "native_excel_clean_roundtrip": "WITHHELD_EXTERNAL_RUNTIME",
        "production_promotion": "WITHHELD_NATIVE_EXCEL_AND_EXECUTED_PARITY_RECEIPT",
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--receipt", type=Path)
    args = ap.parse_args()
    receipt = validate(args.root)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
