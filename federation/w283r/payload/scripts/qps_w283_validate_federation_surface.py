#!/usr/bin/env python3
"""Validate W283R federation function breadth against exact external authority bytes."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CROSS=ROOT/"triage/w283/QPS_W283_FEDERATION_SAMPLE_ROUTING_CROSSWALK_v0.1.json"
BT=ROOT/"triage/w283/QPS_W283_BT_BRIDGE_ADMISSIBILITY_WATCH_v0.1.json"
CONTROL=ROOT/"triage/w283/QPS_W283_FEDERATION_SURFACE_3PSTAR_MIP_CONTROL_v0.1.json"
CENSUS=ROOT/"triage/w280/QPS_W280_GOVERNED_SURFACE_CENSUS_v0.2.json"
TOPOLOGY=ROOT/"triage/w283/upstream/QPS_REPO_FUNCTION_TOPOLOGY_v1.yaml"

EXPECTED_TOPOLOGY_BLOB="df0ee845697578cd644691b81eafb2465249d772"
EXPECTED_CENSUS_BLOB="967205bb52ce9c7c43771b63641df6d714d7ca07"

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def git_blob_sha(path: Path) -> str:
    data=path.read_bytes()
    header=f"blob {len(data)}\0".encode()
    return hashlib.sha1(header+data).hexdigest()

def topology_functions(text: str) -> set[str]:
    vals=set(re.findall(r"^\s*function:\s*([A-Z0-9_\-]+)\s*$", text, flags=re.MULTILINE))
    vals.discard("NONE")
    return vals

def validate():
    c=load_json(CROSS); b=load_json(BT); ctl=load_json(CONTROL); census=load_json(CENSUS)
    assert c["wave"]=="W283R"
    assert ctl["wave"]=="W283R"

    assert git_blob_sha(TOPOLOGY)==EXPECTED_TOPOLOGY_BLOB
    assert git_blob_sha(CENSUS)==EXPECTED_CENSUS_BLOB
    topo_set=topology_functions(TOPOLOGY.read_text(encoding="utf-8"))
    census_set=set(census["denominator"]["unique_functions"])
    assert census["denominator"]["governed_surface_denominator"]==12
    assert len(topo_set)==12
    assert topo_set==census_set

    samples=c["accepted_samples"]
    assert len(samples)==5
    assert len({x["sample_id"] for x in samples})==5
    assert all(x["secondary_credit"]==0 for x in samples)
    mapped=[x["mapped_function"] for x in samples]
    mapped_set=set(mapped)
    uncovered=set(c["measured_result"]["uncovered_functions"])
    claimed=set(c["measured_result"]["unique_functions_covered"])

    assert mapped_set==claimed
    assert mapped_set <= topo_set
    assert uncovered <= topo_set
    assert mapped_set.isdisjoint(uncovered)
    assert mapped_set | uncovered == topo_set
    assert len(mapped_set)==4
    assert len(uncovered)==8

    breadth=c["measured_result"]["function_breadth"]
    assert breadth["numerator"]==len(mapped_set)==4
    assert breadth["denominator"]==len(topo_set)==12
    assert abs(breadth["value"]-(4/12))<1e-12
    assert c["measured_result"]["accepted_sample_mapping"]=={"numerator":5,"denominator":5,"value":1.0}
    assert c["measured_result"]["global_function_depth"] is None
    assert c["measured_result"]["global_fleet_penetration"] is None

    assert c["authoritative_function_proof"]["topology_blob"]==EXPECTED_TOPOLOGY_BLOB
    assert c["authoritative_function_proof"]["census_blob"]==EXPECTED_CENSUS_BLOB
    assert c["review_repair"]["defect"]=="SELF_REFERENTIAL_FUNCTION_SET_VALIDATION"

    assert b["current_repair_component"]["finite_unregularized_mle"] is False
    assert b["refresh_search"]["result"]=="NO_NEW_QUALIFYING_REVERSE_TIE_OR_DIRECT_CROSS_REPAIR_OBSERVATION_FOUND"
    assert b["separate_observed_component"]["observed_pairs"]==12
    assert b["separate_observed_component"]["finite_local_mle"] is True
    assert b["separate_observed_component"]["bridge_to_repair_component"] is False
    assert b["global_bt"]=="WITHHELD_DISCONNECTED_HETEROGENEOUS_COMPARISON_GRAPH"

    assert ctl["state"]=="CANDIDATE_REPAIR_P1_AUTHORITY_BINDING_WAIT_EXACT_PROOF"
    assert ctl["rex"]["id"]=="W283_REX_SELF_REFERENTIAL_FUNCTION_SET_VALIDATION"
    assert ctl["rex"]["prior_green_proof_disposition"]=="INSUFFICIENT_FOR_CONTROL_AFTER_P1"
    assert ctl["three_pc"]["prepare"]=="PASS_REPAIR_PAYLOAD_MATERIALISED"
    assert ctl["three_pc"]["prove"]=="WAIT_REPAIRED_EXACT_EXTERNAL_PR_HEAD_AND_DISTINCT_REPEAT"
    assert abs(ctl["measured_candidate"]["function_breadth"]-(4/12))<1e-12
    assert ctl["measured_candidate"]["function_depth"] is None
    assert ctl["measured_candidate"]["global_fleet_penetration"] is None
    assert "QPS_REPO_LOCAL_RUNNER_923" in ctl["preserved_noncompensating"]
    assert all(v==0 for v in ctl["formal_credit_delta"].values())
    assert ctl["authority_transfer"] is False

    return {
      "schema":"qps-w283r-federation-surface-validation/v0.2",
      "wave":"W283R",
      "result":"PASS_REPAIRED_CANDIDATE_EXTERNAL_FUNCTION_SET_BOUND",
      "topology_blob":EXPECTED_TOPOLOGY_BLOB,
      "census_blob":EXPECTED_CENSUS_BLOB,
      "authoritative_functions":len(topo_set),
      "mapped_samples":5,
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
    p=argparse.ArgumentParser(); p.add_argument("--out"); a=p.parse_args()
    r=validate(); t=json.dumps(r,indent=2,sort_keys=True)+"\n"
    if a.out: Path(a.out).write_text(t,encoding="utf-8")
    print(t,end=""); return 0

if __name__=="__main__":
    raise SystemExit(main())
