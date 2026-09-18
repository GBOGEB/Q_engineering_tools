#!/usr/bin/env python3
"""Generate the governed OFFER-evaluation workbook.

The workbook is a downstream review surface only. It preserves static requirement
importance separately from bidder-response scoring, applies risk once at item level,
and fails closed on missing applicability/gate/confidence inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

EXPECTED_OFFERS = [f"OFFER-{i:02d}" for i in range(1, 51)]
EXPECTED_CLUSTERS = [f"C{i}" for i in range(1, 9)]
SHEETS = ["CONFIG", "STATIC_BT", "INPUT_AB", "CALC_AB", "CATEGORY_COMPARE", "DASHBOARD"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise AssertionError(f"{path} root must be mapping")
    return data


def offer_map(doctrine: dict[str, Any]) -> dict[str, dict[str, Any]]:
    clusters = doctrine["cluster_model"]["clusters"]
    weights = doctrine["cluster_weights"]
    out: dict[str, dict[str, Any]] = {}
    for cid in EXPECTED_CLUSTERS:
        offers = list(clusters[cid]["primary_offers"])
        for offer in offers:
            if offer in out:
                raise AssertionError(f"duplicate offer {offer}")
            out[offer] = {
                "cluster": cid,
                "cluster_name": clusters[cid]["name"],
                "cluster_weight": float(weights[cid]),
                "cluster_size": len(offers),
                "local_weight_default": 1.0 / len(offers),
            }
    if sorted(out) != EXPECTED_OFFERS:
        raise AssertionError("doctrine does not cover OFFER-01..50 exactly")
    return out


def autosize(ws) -> None:
    for col in range(1, ws.max_column + 1):
        values = [str(ws.cell(r, col).value or "") for r in range(1, ws.max_row + 1)]
        ws.column_dimensions[get_column_letter(col)].width = min(max(10, max(map(len, values), default=10) + 2), 42)
    ws.freeze_panes = "A2"


def build(
    doctrine_path: Path,
    control_path: Path,
    out: Path,
    equation_path: Path | None = None,
) -> dict[str, Any]:
    doctrine = load_yaml(doctrine_path)
    control = load_yaml(control_path)
    equation_path = equation_path or (control_path.parent / "QPS_OFFER_EVAL_EQUATION_CURRENT_v1.yaml")
    equation = load_yaml(equation_path)
    omap = offer_map(doctrine)
    doctrine_sha = sha256(doctrine_path)
    control_sha = sha256(control_path)
    equation_sha = sha256(equation_path)

    risk = control["risk_implementation"]
    if risk["selected_policy"] != "OPTION_A_SYSTEM_RISK_APPLIED_ONCE_AT_ITEM_LEVEL":
        raise AssertionError("risk-once policy drift")
    if equation["equation_version"] != "OFFER_EVAL_EQ_v1":
        raise AssertionError("equation version drift")
    if equation["risk_once_proof"]["final_system_risk_subtraction_allowed"] is not False:
        raise AssertionError("second system-risk subtraction is prohibited")
    if control["weighting_alignment"]["canonical_field"] != "BT_Weight":
        raise AssertionError("BT_Weight must remain the single canonical field")
    if control["pairwise_alignment"]["governing_S_domain"] != [-1, 0, 1]:
        raise AssertionError("pairwise sign domain drift")

    wb = Workbook()
    wb.remove(wb.active)
    for name in SHEETS:
        wb.create_sheet(name)

    cfg = wb["CONFIG"]
    cfg.append(["Parameter", "Value", "Authority/role"])
    cfg.append(["Max_risk_factor", float(risk["observed_config"]["value"]), "risk cap; Option-A once at item level"])
    cfg.append(["Equation_Version", equation["equation_version"], "canonical equation family"])
    cfg.append(["Equation_Control_SHA256", equation_sha, "equation semantic identity"])
    cfg.append(["Doctrine_SHA256", doctrine_sha, "semantic input identity"])
    cfg.append(["Workbook_Control_SHA256", control_sha, "workbook implementation control identity"])
    cfg.append(["Generated_Output_Authority", "DOWNSTREAM_VIEW_ONLY", "zero formal credit"])

    st = wb["STATIC_BT"]
    st.append(["OFFER", "Cluster", "Cluster_Name", "Cluster_Weight", "Local_Weight_Default", "BT_Weight", "BT_Weight_State"])
    for offer in EXPECTED_OFFERS:
        m = omap[offer]
        st.append([offer, m["cluster"], m["cluster_name"], m["cluster_weight"], m["local_weight_default"], None, "PENDING_SOURCE_OR_REVIEW"])

    inp = wb["INPUT_AB"]
    inp.append([
        "OFFER",
        "RawScore_A", "Confidence_A", "BaseRisk_A", "BidderRisk_A", "SystemRisk_A",
        "RawScore_B", "Confidence_B", "BaseRisk_B", "BidderRisk_B", "SystemRisk_B",
        "Reviewer_Notes",
        "Applicable_A", "Gate_A", "Applicable_B", "Gate_B",
    ])
    for offer in EXPECTED_OFFERS:
        inp.append([offer] + [None] * 15)

    calc = wb["CALC_AB"]
    calc.append([
        "OFFER", "BT_Weight", "Pairwise_S", "BT_Contribution",
        "TotalRisk_A", "Adjusted_A", "TotalRisk_B", "Adjusted_B",
        "WeightedDelta_Diagnostic",
        "Conditioned_A", "Conditioned_B",
        "Applicable_A", "Applicable_B", "Gate_A", "Gate_B",
        "ApplicableLocalWeight_A", "ApplicableLocalWeight_B",
        "LocalWeight_A_Renorm", "LocalWeight_B_Renorm",
        "ClusterContribution_A", "ClusterContribution_B",
        "RowState_A", "RowState_B",
    ])
    for r, offer in enumerate(EXPECTED_OFFERS, start=2):
        cluster_ref = f"STATIC_BT!B{r}"
        denom_a = f'SUMIFS($P$2:$P$51,STATIC_BT!$B$2:$B$51,{cluster_ref})'
        denom_b = f'SUMIFS($Q$2:$Q$51,STATIC_BT!$B$2:$B$51,{cluster_ref})'
        calc.append([
            offer,
            f"=STATIC_BT!F{r}",
            f'=IF(OR(INPUT_AB!B{r}="",INPUT_AB!G{r}=""),"",SIGN(INPUT_AB!B{r}-INPUT_AB!G{r}))',
            f'=IF(OR(B{r}="",C{r}=""),"",B{r}*C{r})',
            f'=IF(INPUT_AB!M{r}=0,"",IF(INPUT_AB!M{r}="","",IF(COUNT(INPUT_AB!D{r}:F{r})<3,IF(COUNTIF(INPUT_AB!D{r}:F{r},"FAIL")>0,"FAIL",IF(COUNTIF(INPUT_AB!D{r}:F{r},"DEFER")>0,"DEFER","MISSING")),MIN(CONFIG!$B$2,SUM(INPUT_AB!D{r}:F{r})))))',
            f'=IF(INPUT_AB!M{r}=0,"",IF(NOT(ISNUMBER(E{r})),E{r},IF(N{r}="","MISSING",IF(NOT(ISNUMBER(N{r})),N{r},IF(J{r}="","MISSING",J{r}*N{r}*(1-E{r}))))) )',
            f'=IF(INPUT_AB!O{r}=0,"",IF(INPUT_AB!O{r}="","",IF(COUNT(INPUT_AB!I{r}:K{r})<3,IF(COUNTIF(INPUT_AB!I{r}:K{r},"FAIL")>0,"FAIL",IF(COUNTIF(INPUT_AB!I{r}:K{r},"DEFER")>0,"DEFER","MISSING")),MIN(CONFIG!$B$2,SUM(INPUT_AB!I{r}:K{r})))))',
            f'=IF(INPUT_AB!O{r}=0,"",IF(NOT(ISNUMBER(G{r})),G{r},IF(O{r}="","MISSING",IF(NOT(ISNUMBER(O{r})),O{r},IF(K{r}="","MISSING",K{r}*O{r}*(1-G{r}))))) )',
            f'=IF(OR(B{r}="",NOT(ISNUMBER(F{r})),NOT(ISNUMBER(H{r})),SUM($B$2:$B$51)=0),"",(B{r}/SUM($B$2:$B$51))*(F{r}-H{r}))',
            f'=IF(OR(INPUT_AB!M{r}<>1,INPUT_AB!B{r}="",INPUT_AB!C{r}=""),"",INPUT_AB!B{r}*INPUT_AB!C{r})',
            f'=IF(OR(INPUT_AB!O{r}<>1,INPUT_AB!G{r}="",INPUT_AB!H{r}=""),"",INPUT_AB!G{r}*INPUT_AB!H{r})',
            f"=INPUT_AB!M{r}",
            f"=INPUT_AB!O{r}",
            f"=INPUT_AB!N{r}",
            f"=INPUT_AB!P{r}",
            f'=IF(L{r}=1,STATIC_BT!E{r},0)',
            f'=IF(M{r}=1,STATIC_BT!E{r},0)',
            f'=IF(L{r}<>1,"",IF({denom_a}=0,"",P{r}/{denom_a}))',
            f'=IF(M{r}<>1,"",IF({denom_b}=0,"",Q{r}/{denom_b}))',
            f'=IF(OR(NOT(ISNUMBER(R{r})),NOT(ISNUMBER(F{r}))),"",R{r}*F{r})',
            f'=IF(OR(NOT(ISNUMBER(S{r})),NOT(ISNUMBER(H{r}))),"",S{r}*H{r})',
            f'=IF(L{r}=0,"NA",IF(L{r}="","UNSET",IF(N{r}=0,"GATE_FAIL",IF(N{r}="","MISSING",IF(N{r}<>1,IF(ISTEXT(N{r}),N{r},"DEFER"),IF(NOT(ISNUMBER(E{r})),E{r},IF(J{r}="","MISSING","READY")))))))',
            f'=IF(M{r}=0,"NA",IF(M{r}="","UNSET",IF(O{r}=0,"GATE_FAIL",IF(O{r}="","MISSING",IF(O{r}<>1,IF(ISTEXT(O{r}),O{r},"DEFER"),IF(NOT(ISNUMBER(G{r})),G{r},IF(K{r}="","MISSING","READY")))))))',
        ])

    cat = wb["CATEGORY_COMPARE"]
    cat.append([
        "Cluster", "Cluster_Name", "Cluster_Weight", "BT_Sum",
        "ClusterScore_A", "ClusterScore_B",
        "GlobalContribution_A", "GlobalContribution_B",
        "Diagnostic_Delta", "GateFail_A", "GateFail_B",
        "Applicable_A_Count", "Applicable_B_Count",
    ])
    clusters = doctrine["cluster_model"]["clusters"]
    for i, cid in enumerate(EXPECTED_CLUSTERS, start=2):
        offers = list(clusters[cid]["primary_offers"])
        rows = [EXPECTED_OFFERS.index(o) + 2 for o in offers]
        bt_terms = ",".join(f"CALC_AB!D{r}" for r in rows)
        a_terms = ",".join(f"CALC_AB!T{r}" for r in rows)
        b_terms = ",".join(f"CALC_AB!U{r}" for r in rows)
        gate_a = "+".join(f'--(CALC_AB!V{r}="GATE_FAIL")' for r in rows)
        gate_b = "+".join(f'--(CALC_AB!W{r}="GATE_FAIL")' for r in rows)
        app_a = "+".join(f'--(CALC_AB!L{r}=1)' for r in rows)
        app_b = "+".join(f'--(CALC_AB!M{r}=1)' for r in rows)
        cat.append([
            cid,
            clusters[cid]["name"],
            float(doctrine["cluster_weights"][cid]),
            f'=IF(COUNT({bt_terms})<{len(offers)},"",SUM({bt_terms}))',
            f'=IF(L{i}=0,"UNSCORABLE",IF(COUNT({a_terms})<L{i},"",SUM({a_terms})))',
            f'=IF(M{i}=0,"UNSCORABLE",IF(COUNT({b_terms})<M{i},"",SUM({b_terms})))',
            f'=IF(ISNUMBER(E{i}),C{i}*E{i},"")',
            f'=IF(ISNUMBER(F{i}),C{i}*F{i},"")',
            f'=IF(AND(ISNUMBER(G{i}),ISNUMBER(H{i})),G{i}-H{i},"")',
            f"={gate_a}",
            f"={gate_b}",
            f"={app_a}",
            f"={app_b}",
        ])

    dash = wb["DASHBOARD"]
    dash.append(["Metric", "Value", "Interpretation"])
    dash.append(["Equation_Version", equation["equation_version"], "one canonical score/risk equation family"])
    dash.append(["Pairwise_BT_Total", '=IF(COUNT(CALC_AB!D2:D51)<50,"",SUM(CALC_AB!D2:D51))', "sign-based fixed-weight pairwise; withheld until all 50 contributions are numeric; separate from final review score"])
    dash.append([
        "FinalReviewScore_A",
        '=IF(COUNTIF(CALC_AB!V2:V51,"GATE_FAIL")>0,"GATE_FAIL",IF(COUNTIF(CALC_AB!V2:V51,"FAIL")>0,"FAIL",IF(COUNTIF(CALC_AB!V2:V51,"DEFER")>0,"DEFER",IF(OR(COUNTIF(CALC_AB!V2:V51,"MISSING")>0,COUNTIF(CALC_AB!V2:V51,"UNSET")>0),"MISSING",IF(COUNTIF(CATEGORY_COMPARE!L2:L9,0)>0,"UNSCORABLE",IF(COUNTIF(CALC_AB!V2:V51,"READY")+COUNTIF(CALC_AB!V2:V51,"NA")<50,"WITHHELD",SUM(CATEGORY_COMPARE!G2:G9)))))))',
        "cluster-weighted review support; invalidated by gate failure; not award authority",
    ])
    dash.append([
        "FinalReviewScore_B",
        '=IF(COUNTIF(CALC_AB!W2:W51,"GATE_FAIL")>0,"GATE_FAIL",IF(COUNTIF(CALC_AB!W2:W51,"FAIL")>0,"FAIL",IF(COUNTIF(CALC_AB!W2:W51,"DEFER")>0,"DEFER",IF(OR(COUNTIF(CALC_AB!W2:W51,"MISSING")>0,COUNTIF(CALC_AB!W2:W51,"UNSET")>0),"MISSING",IF(COUNTIF(CATEGORY_COMPARE!M2:M9,0)>0,"UNSCORABLE",IF(COUNTIF(CALC_AB!W2:W51,"READY")+COUNTIF(CALC_AB!W2:W51,"NA")<50,"WITHHELD",SUM(CATEGORY_COMPARE!H2:H9)))))))',
        "cluster-weighted review support; invalidated by gate failure; not award authority",
    ])
    dash.append(["WeightedDelta_Diagnostic_Total", '=IF(COUNT(CALC_AB!I2:I51)<50,"",SUM(CALC_AB!I2:I51))', "diagnostic only; withheld until all 50 contributions are numeric; MUST NOT be called Bradley-Terry"])
    dash.append(["System_Risk_Final_Subtraction", "PROHIBITED", "system risk is already applied once inside TotalRisk"])
    dash.append(["Formal_Credit", 0, "engineering/compliance/negotiation/acceptance/release/award"])

    for ws in wb.worksheets:
        autosize(ws)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)

    reloaded = load_workbook(out, data_only=False)
    if reloaded.sheetnames != SHEETS:
        raise AssertionError(f"sheet drift {reloaded.sheetnames}")
    with zipfile.ZipFile(out) as zf:
        table_parts = [n for n in zf.namelist() if n.startswith("xl/tables/")]
    if table_parts:
        raise AssertionError(f"unexpected Excel table parts: {table_parts}")

    receipt = {
        "status": "PASS_OPENPYXL_EQUATION_V1_ROUNDTRIP_NO_TABLE_PART",
        "output": out.name,
        "output_sha256": sha256(out),
        "doctrine_sha256": doctrine_sha,
        "workbook_control_sha256": control_sha,
        "equation_control_sha256": equation_sha,
        "equation_version": equation["equation_version"],
        "offer_count": 50,
        "sheets": SHEETS,
        "table_parts": [],
        "confidence_conditioning_implemented": True,
        "explicit_applicability_NA_implemented": True,
        "missing_defer_fail_preserved": True,
        "all_NA_cluster_unscorable": True,
        "incomplete_pairwise_totals_withheld": True,
        "risk_state_precedence_FAIL_DEFER_MISSING": True,
        "risk_state_precedes_score_completeness": True,
        "nonnumeric_risk_consumers_guarded": True,
        "row_state_risk_precedes_score_completeness": True,
        "risk_application_count": 1,
        "final_system_risk_subtraction": False,
        "excel_native_clean_roundtrip": "WITHHELD_REQUIRES_EXCEL_RUNTIME",
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }
    return receipt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doctrine", type=Path, default=Path("controls/QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml"))
    ap.add_argument("--control", type=Path, default=Path("controls/QPS_OFFER_EVAL_WORKBOOK_DELTA_2026-09-14_v1.yaml"))
    ap.add_argument("--equation", type=Path, default=Path("controls/QPS_OFFER_EVAL_EQUATION_CURRENT_v1.yaml"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--receipt", type=Path)
    args = ap.parse_args()
    receipt = build(args.doctrine, args.control, args.out, args.equation)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
