#!/usr/bin/env python3
"""Validate W283 federation function-breadth mapping and BT admissibility."""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CROSS=ROOT/"triage/w283/QPS_W283_FEDERATION_SAMPLE_ROUTING_CROSSWALK_v0.1.json"
BT=ROOT/"triage/w283/QPS_W283_BT_BRIDGE_ADMISSIBILITY_WATCH_v0.1.json"
CONTROL=ROOT/"triage/w283/QPS_W283_FEDERATION_SURFACE_3PSTAR_MIP_CONTROL_v0.1.json"

def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def validate():
    c=load(CROSS); b=load(BT); ctl=load(CONTROL)

    assert c["wave"]=="W283"
    assert c["source_denominator"]["governed_surface_denominator"]==12
    samples=c["accepted_samples"]
    assert len(samples)==5
    assert len({x["sample_id"] for x in samples})==5
    assert all(x["secondary_credit"]==0 for x in samples)
    mapped=[x["mapped_function"] for x in samples]
    uniq=sorted(set(mapped))
    assert uniq==sorted(c["measured_result"]["unique_functions_covered"])
    assert len(uniq)==4
    breadth=c["measured_result"]["function_breadth"]
    assert breadth["numerator"]==4 and breadth["denominator"]==12
    assert abs(breadth["value"]-(4/12))<1e-12
    assert c["measured_result"]["accepted_sample_mapping"]=={"numerator":5,"denominator":5,"value":1.0}
    assert c["measured_result"]["global_function_depth"] is None
    assert c["measured_result"]["global_fleet_penetration"] is None
    assert len(c["measured_result"]["uncovered_functions"])==8
    assert set(c["measured_result"]["uncovered_functions"]).isdisjoint(set(uniq))
    assert c["measured_result"]["state"]=="BREADTH_MEASURED_DEPTH_WITHHELD"

    assert b["current_repair_component"]["finite_unregularized_mle"] is False
    assert b["refresh_search"]["result"]=="NO_NEW_QUALIFYING_REVERSE_TIE_OR_DIRECT_CROSS_REPAIR_OBSERVATION_FOUND"
    assert len(b["admissible_next_events"])==3
    assert b["separate_observed_component"]["observed_pairs"]==12
    assert b["separate_observed_component"]["finite_local_mle"] is True
    assert b["separate_observed_component"]["bridge_to_repair_component"] is False
    assert b["global_bt"]=="WITHHELD_DISCONNECTED_HETEROGENEOUS_COMPARISON_GRAPH"

    assert ctl["wave"]=="W283"
    assert ctl["three_pr"]["refresh"].startswith("PASS")
    assert ctl["mip"]["modernize"]=="SEPARATE_FUNCTION_REACH_BREADTH_FROM_FUNCTION_INTERNAL_DEPTH"
    assert ctl["three_pc"]["prepare"]=="PASS_PAYLOAD_MATERIALISED"
    assert ctl["three_pc"]["prove"]=="WAIT_EXACT_EXTERNAL_PR_HEAD_AND_DISTINCT_REPEAT"
    assert ctl["measured_candidate"]["sample_mapping"]=="5_OF_5"
    assert ctl["measured_candidate"]["unique_routing_functions_covered"]=="4_OF_12"
    assert abs(ctl["measured_candidate"]["function_breadth"]-(4/12))<1e-12
    assert ctl["measured_candidate"]["function_depth"] is None
    assert ctl["measured_candidate"]["global_fleet_penetration"] is None
    assert "QPS_REPO_LOCAL_RUNNER_923" in ctl["preserved_noncompensating"]
    assert all(v==0 for v in ctl["formal_credit_delta"].values())
    assert ctl["authority_transfer"] is False

    return {
      "schema":"qps-w283-federation-surface-validation/v0.1",
      "wave":"W283",
      "result":"PASS_CANDIDATE_FUNCTION_BREADTH_ONLY",
      "mapped_samples":5,
      "governed_functions":12,
      "covered_functions":4,
      "function_breadth":4/12,
      "function_depth":None,
      "global_fleet_penetration":None,
      "bt_repair_finite_mle":False,
      "global_bt":b["global_bt"],
      "formal_credit_delta":0,
      "authority_transfer":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out")
    a=p.parse_args()
    r=validate()
    t=json.dumps(r,indent=2,sort_keys=True)+"\n"
    if a.out:
        Path(a.out).write_text(t,encoding="utf-8")
    print(t,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
