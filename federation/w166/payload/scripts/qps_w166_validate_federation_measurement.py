#!/usr/bin/env python3
"""Validate W166 bounded federation measurement and crew-REX pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTROL_DEFAULT = Path("controls/QPS_FEDERATION_MEASUREMENT_CURRENT_v1.json")
CENSUS_DEFAULT = Path("triage/w166/QPS_W166_FEDERATION_PILOT_CENSUS_v0.1.json")

SPECIALISTS = {
    "CREW-FED-AMBASSADOR",
    "CREW-FED-GEOGRAPHER",
    "CREW-FED-GEOLOGIST",
    "CREW-FED-CALLIGRAPHER",
    "CREW-FED-NEURON",
    "CREW-H2-HISTORIAN",
}
PRESERVED_GATES = {
    "QPS_REPO_LOCAL_RUNNER_923",
    "G6_CURRENT_RELEASE_IDENTITY_AND_PARITY",
    "W165_EDGE_K8S_MEASUREMENT_GATE",
    "EXTERNAL_SOURCE_AND_AUTHORITY_GATES",
    "VISUAL_N200_INDEPENDENT_COLLECTION",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: root must be object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_control(control: dict[str, Any]) -> None:
    require(control.get("schema") == "qps-federation-measurement-control/v1.0", "wrong control schema")
    require(control.get("wave") == "W166", "wrong wave")
    require(control.get("authority") == "MISSION_CONTROL_MEASUREMENT_AND_CREW_REX_ONLY", "wrong authority")
    guard = control.get("scope_guard", {})
    require(guard.get("pilot_scope") == "W164_CONTROL_SURFACE_ONLY", "pilot scope widened")
    require(guard.get("global_fleet_penetration_claim") is False, "global penetration claim forbidden")
    require(guard.get("grand_mission_coverage_claim") is False, "GM coverage claim forbidden")
    require(guard.get("grand_mission_authority_changed") is False, "GM authority change forbidden")
    require(guard.get("formal_credit_delta") == {"engineering": 0, "compliance": 0, "negotiation": 0, "release": 0}, "formal credit must remain zero")

    rules = control.get("measurement_rules", {})
    require(rules.get("penetration_formula") == "PEN=B*D", "penetration formula changed")
    require(rules.get("unknown_rule") == "NULL_NOT_ZERO", "unknown rule must be NULL_NOT_ZERO")
    require(rules.get("breadth_owner") == "GEOGRAPHER", "breadth owner changed")
    require(rules.get("depth_owner") == "GEOLOGIST", "depth owner changed")

    promotion = control.get("crew_promotion_rule", {})
    require(promotion.get("static_binding") == "NO_PROMOTION", "static binding cannot promote crew")
    require(promotion.get("control_eligibility_never_inferred_from_role_name") is True, "role-name promotion forbidden")
    require(set(control.get("preserved_non_compensating_gates", [])) == PRESERVED_GATES, "preserved gates changed")


def validate_census(census: dict[str, Any]) -> None:
    require(census.get("schema") == "qps-w166-federation-pilot-census/v0.1", "wrong census schema")
    require(census.get("scope") == "W164_CONTROL_SURFACE_ONLY", "census scope widened")

    breadth = census.get("breadth", {})
    dimensions = ["repositories", "exact_payload_classes", "runtime_vectors", "specialist_outputs"]
    declared = 0
    covered = 0
    for key in dimensions:
        dimension = breadth.get(key, {})
        den = dimension.get("denominator")
        num = dimension.get("numerator")
        require(isinstance(den, int) and den > 0, f"{key}: invalid denominator")
        require(isinstance(num, int) and 0 <= num <= den, f"{key}: invalid numerator")
        units = dimension.get("units", [])
        require(len(units) == den, f"{key}: unit list must equal denominator")
        declared += den
        covered += num
    require(declared == breadth.get("declared_units") == 16, "breadth denominator must be 16")
    require(covered == breadth.get("covered_units") == 16, "breadth numerator must be 16")
    expected_b = covered / declared
    require(abs(float(breadth.get("B")) - expected_b) < 1e-12, "B does not match explicit numerator/denominator")

    depth = census.get("depth", {})
    layers = depth.get("layers", [])
    require(len(layers) == depth.get("declared_layers") == 7, "depth denominator must be 7")
    observed = sum(1 for item in layers if item.get("observed") is True)
    require(observed == depth.get("observed_layers") == 7, "depth numerator must be 7")
    require([item.get("level") for item in layers] == list(range(1, 8)), "depth levels must be 1..7")
    expected_d = observed / len(layers)
    require(abs(float(depth.get("D")) - expected_d) < 1e-12, "D does not match explicit numerator/denominator")

    penetration = census.get("penetration", {})
    require(penetration.get("formula") == "PEN=B*D", "census PEN formula changed")
    require(penetration.get("global_fleet_penetration") is None, "global fleet penetration must remain null")
    require(penetration.get("grand_mission_penetration") is None, "GM penetration must remain null")
    expected_pen = float(breadth["B"]) * float(depth["D"])
    require(abs(float(penetration.get("PEN")) - expected_pen) < 1e-12, "PEN != B*D")

    ambassador = census.get("ambassador_round_trip", {})
    require(ambassador.get("round_trip_complete") is True, "ambassador round trip incomplete")
    require(ambassador.get("authority_transfer") is False, "federation cannot transfer authority")
    require(ambassador.get("source_authority") == ambassador.get("return_authority"), "authority must return to source")

    lineage = census.get("historian_lineage", {})
    nodes = lineage.get("nodes", [])
    edges = lineage.get("edges", [])
    require(len(nodes) == 9 and len(set(nodes)) == 9, "historian lineage must contain 9 unique nodes")
    require(len(edges) == 8, "historian lineage must contain 8 edges")
    node_set = set(nodes)
    require(all(edge[0] in node_set and edge[1] in node_set for edge in edges), "lineage edge references unknown node")

    graph = census.get("neuron_graph", {})
    require(graph.get("node_count") == len(nodes), "neuron node count mismatch")
    require(graph.get("edge_count") == len(edges), "neuron edge count mismatch")
    require(graph.get("connected_components") == 1, "pilot lineage must be one connected component")

    calligrapher = census.get("calligrapher", {})
    require("PR1081" in calligrapher.get("ascii", "") and "PR1082" in calligrapher.get("ascii", ""), "ASCII flow incomplete")
    require(calligrapher.get("mermaid", "").startswith("flowchart LR;"), "Mermaid flow missing")

    receipts = census.get("crew_candidate_receipts", [])
    ids = {item.get("CREW_ID") for item in receipts}
    require(ids == SPECIALISTS, "specialist receipt set incomplete")
    require(all(item.get("state") == "CANDIDATE_PENDING_W166_RUNTIME" for item in receipts), "static census cannot prematurely promote specialist")

    unknowns = census.get("unknowns", {})
    require(unknowns and all(value is None for value in unknowns.values()), "unknown global denominators must remain null")
    require(census.get("formal_credit_delta") == {"engineering": 0, "compliance": 0, "negotiation": 0, "release": 0}, "census credit must remain zero")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", type=Path, default=CONTROL_DEFAULT)
    parser.add_argument("--census", type=Path, default=CENSUS_DEFAULT)
    args = parser.parse_args()
    control = load(args.control)
    census = load(args.census)
    validate_control(control)
    validate_census(census)
    print("W166 PASS: bounded W164 pilot B=16/16 D=7/7 PEN=1.0; 6 specialist candidate receipts; global denominators NULL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
