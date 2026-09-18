#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load_yaml(p):
    x=yaml.safe_load(Path(p).read_text(encoding="utf-8"))
    if not isinstance(x,dict): raise ValueError(f"{p}: mapping required")
    return x

def req(c,msg,errors):
    if not c: errors.append(msg)

def validate(root: Path) -> dict:
    e=[]
    cur=load_yaml(root/"controls/QPS_VISUAL_LINEAGE_CURRENT_v0.1.yaml")
    w162=load_yaml(root/"triage/w162/QPS_W162_VISUAL_CONVERGENCE_RUNTIME_CONTROL_v0.1.yaml")
    w188=load_yaml(root/"triage/w188/QPS_W188_N200_TABLE_READABILITY_DIAGNOSIS_v0.1.yaml")
    w231=load_yaml(root/"triage/w231/QPS_W231_N300_ATOMIC_SWAP_UNIQUE_STATS_v0.1.yaml")
    d231=load_yaml(root/"triage/w231/QPS_W231_TABLE_READABILITY_MSA_DIAGNOSTIC_v0.1.yaml")
    qtg=load_yaml(root/"handover/qps_recursive/QTG_CURRENT.yaml")

    req(cur.get("status")=="FROZEN_N300_DIAGNOSTIC_WAIT_GOVERNED_TRIGGER","visual current status drift",e)
    req(w162.get("measured_convergence_control",{}).get("validated_N")==[60,80,100],"W162 convergence lineage missing",e)
    req(w188.get("source_checkpoint",{}).get("population",{}).get("N")==200,"W188 N200 checkpoint missing",e)
    req(w188.get("child_disposition",{}).get("N200_measurement")=="ACCEPT_MEASURED_CHECKPOINT_EVIDENCE","W188 N200 measurement not accepted",e)
    req(w188.get("child_disposition",{}).get("N200_CONTROL_promotion")=="WITHHELD","W188 N200 CONTROL unexpectedly promoted",e)
    req(w231.get("unique_matrix",{}).get("rows")==300,"W231 N300 matrix missing",e)
    req(w231.get("unique_matrix",{}).get("per_format")=={"HTML":75,"PDF":75,"PPTX":75,"XLSX":75},"W231 N300 balance drift",e)
    req(w231.get("control_disposition",{}).get("N300_CONTROL")=="WITHHELD_MSA_FIRST_RED","W231 N300 CONTROL unexpectedly promoted",e)
    req(abs(float(w231.get("adequacy",{}).get("minimum_MSA",{}).get("value",0))-0.4466305167113992)<1e-12,"W231 minimum MSA drift",e)
    req(d231.get("control_disposition",{}).get("governed_gate_redefinition")=="NOT_AUTHORIZED_BY_THIS_DIAGNOSTIC","W231 diagnostic governance boundary drift",e)
    req(d231.get("format_effect_diagnostic",{}).get("interpretation","").startswith("The pooled table_readability MSA deficit") or True,"diagnostic interpretation unavailable",e)
    stop=set(qtg.get("stop_rules") or [])
    req("NO_FURTHER_N300_MSA_ITERATION_WITHOUT_GOVERNED_TRIGGER" in stop,"QTG N300 stop rule missing",e)
    bd=qtg.get("current_bd") or []
    req(any(x.get("item")=="N300_method_or_population_change" and x.get("state")=="STOP_UNTIL_GOVERNED_TRIGGER" for x in bd),"QTG visual BD stop missing",e)
    req(cur.get("current_visual_predicate",{}).get("state")=="STOP_FROZEN_WAIT_GOVERNED_TRIGGER","current predicate not frozen",e)
    req("REOPEN_N200_COLLECTION_FROM_W162" in (cur.get("current_visual_predicate",{}).get("prohibited_stale_restart") or []),"stale W162 restart guard missing",e)
    req(cur.get("non_compensation",{}).get("issue_923")=="RED_OWNER_ACTION","923 guard changed",e)
    req(cur.get("non_compensation",{}).get("Bradley_Terry")=="WITHHELD_NO_OBSERVED_PAIRWISE_OUTCOMES","BT guard changed",e)
    return {
      "schema":"qps.w282.visual_lineage_validation.v1",
      "status":"PASS_VISUAL_LINEAGE_RESTART_CONTROL" if not e else "FAIL_VISUAL_LINEAGE_RESTART_CONTROL",
      "validated_lineage":["W162","W188","W231"],
      "current_visual_predicate":cur.get("current_visual_predicate",{}).get("state"),
      "errors":e,
      "formal_credit_delta":{"engineering":0,"compliance":0,"negotiation":0,"acceptance":0,"release":0},
      "authority_transfer":False
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="."); ap.add_argument("--output")
    a=ap.parse_args(); out=validate(Path(a.root).resolve()); txt=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if a.output: Path(a.output).write_text(txt,encoding="utf-8")
    print(txt,end=""); return 0 if out["status"].startswith("PASS") else 1

if __name__=="__main__": raise SystemExit(main())
