#!/usr/bin/env python3
"""Validate W164 MissionControl federation and crew-control contracts.

Governance/DevOps only. This validator grants no engineering, compliance,
negotiation or release credit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTROL_DEFAULT = Path("controls/QPS_MISSION_FEDERATION_CURRENT_v1.json")
CREW_DEFAULT = Path("controls/QPS_CREW_REGISTRY_CURRENT_v1.json")

REQUIRED_CREW_FIELDS = {
    "CREW_ID", "home_base", "roles", "competency_vector", "authority",
    "tools_resources", "active_mission", "secondment", "runtime_receipts",
    "accepted_work", "rejected_work", "REX_learned", "REX_generated",
    "current_load", "PCA_contribution", "last_evidence_sha", "maturity",
    "CONTROL_eligibility",
}
REQUIRED_SPECIAL_ROLES = {
    "AMBASSADOR", "GEOGRAPHER", "GEOLOGIST", "CALLIGRAPHER",
    "NEURON_GRAPH_DECOMPOSER", "HISTORIAN", "SCOUT", "READER",
    "FEDERATION_INTEGRATOR",
}
EXPECTED_LOOP = [
    "DISCOVER", "PRIME", "AUTHORISE", "EXECUTE", "PROVE", "RETURN",
    "FEDERATE", "LEARN", "TRIAGE", "REDEPLOY",
]
EXPECTED_PRELAUNCH = ["HELD", "SCOUTED", "READ", "MAPPED", "PRIMED"]
FORBIDDEN_PRELAUNCH = {"CANONICAL_CHILD", "RUNTIME_RECEIPT", "ACCEPTANCE", "MISSION_COMPLETE"}
EXPECTED_HORIZONTAL = {"H1_QPS", "H2_KEB", "H3_DOW", "H4_QPS_TRIAGE"}
EXPECTED_GM = {"GM-I", "GM-II", "GM-III", "GM-IV", "GM-V"}
EXPECTED_GATES = {
    "QPS_REPO_LOCAL_RUNNER_923",
    "G6_CURRENT_RELEASE_IDENTITY_AND_PARITY",
    "EXTERNAL_SOURCE_AND_AUTHORITY_GATES",
    "VISUAL_N200_INDEPENDENT_COLLECTION",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: root must be an object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_control(control: dict[str, Any]) -> None:
    require(control.get("schema") == "qps-mission-federation-control/v1.0", "wrong control schema")
    require(control.get("authority") == "MISSION_CONTROL_DEVOPS_EXECUTION_ONLY", "wrong authority")
    require(control.get("wave") == "W164", "W164 wave binding missing")

    gm = control.get("grand_mission_boundary", {})
    require(set(gm.get("machine_namespace", [])) == EXPECTED_GM, "GM-I..GM-V namespace must be exact")
    require(gm.get("rule") == "REFERENCE_ONLY_DO_NOT_REDEFINE_HERE", "Grand Mission boundary weakened")
    require(gm.get("early_learning_does_not_equal_launch") is True, "early-learning guard missing")

    points = control.get("ten_point_control", [])
    require(len(points) == 10, "ten-point control must contain exactly 10 items")
    require({p.get("point") for p in points} == set(range(1, 11)), "ten-point numbering must be exactly 1..10")
    require(all(p.get("state") == "BOUND" for p in points), "all ten control points must be BOUND")
    require(len({p.get("id") for p in points}) == 10, "ten-point IDs must be unique")

    horizontal = control.get("horizontal_missions", {})
    require(set(horizontal) == EXPECTED_HORIZONTAL, "horizontal mission set must be H1-H4 exactly")
    require(horizontal["H4_QPS_TRIAGE"].get("scheduling_rule") == "VETO_GT_BT_GT_VALUE", "triage scheduling precedence changed")
    require(horizontal["H4_QPS_TRIAGE"].get("global_pca_policy") == "WITHHOLD_UNTIL_MEASURED_MATRIX_ADEQUATE", "global PCA guard weakened")

    fed = control.get("federation_mission", {})
    require(fed.get("id") == "MISSION_FED", "federation mission ID missing")
    require(fed.get("class") == "CROSS_FLEET_PLANE_NOT_GM_VI", "federation must not become GM-VI")
    require(set(fed.get("crew", [])) >= REQUIRED_SPECIAL_ROLES, "federation specialist roles incomplete")
    require(fed.get("authority_guard") == "FEDERATION_SOLVES_EXCHANGE_NOT_SOURCE_AUTHORITY_OR_CHILD_AUTHORITY", "federation authority guard weakened")

    penetration = control.get("penetration_model", {})
    require(penetration.get("formula") == "PEN=B*D", "penetration formula must be PEN=B*D")
    require(penetration.get("breadth_owner") == "GEOGRAPHER", "Geographer must own breadth")
    require(penetration.get("depth_owner") == "GEOLOGIST", "Geologist must own depth")
    measures = set(penetration.get("required_measures", []))
    require({"repo_coverage", "folder_coverage", "runtime_coverage", "depth_level", "dependency_depth"} <= measures, "penetration measurement coverage incomplete")

    lifecycle = control.get("early_learning_state_machine", {})
    require(lifecycle.get("prelaunch_states") == EXPECTED_PRELAUNCH, "prelaunch state sequence changed")
    require(lifecycle.get("launch_state") == "AUTHORISED", "launch must be explicit AUTHORISED")
    require(set(lifecycle.get("forbidden_prelaunch_claims", [])) == FORBIDDEN_PRELAUNCH, "prelaunch forbidden claims changed")
    require(lifecycle.get("invariant") == "EARLY_LEARNING_NEVER_IMPLIES_EARLY_LAUNCH", "prelaunch invariant missing")

    bidi = control.get("bidirectional_control", {})
    require(bidi.get("control_cycle") == ["RECEIVE", "VALIDATE", "NORMALISE", "ASSIMILATE", "FEDERATE", "REPRIORITISE", "REDEPLOY"], "bidirectional control cycle changed")
    outbound = set(bidi.get("mission_control_to_mission", []))
    inbound = set(bidi.get("mission_to_mission_control", []))
    require({"MISSION_BRIEF", "REX", "CREW", "PRIORITY", "LAUNCH_STATE"} <= outbound, "MissionControl feedforward incomplete")
    require({"RUNTIME_RECEIPTS", "REX", "QUEUE_TIME", "EXECUTION_TIME", "INFORMATION_GAIN", "UNCERTAINTY"} <= inbound, "mission feedback incomplete")

    require(control.get("canonical_operating_loop") == EXPECTED_LOOP, "canonical operating loop changed")
    require(set(control.get("preserved_non_compensating_gates", [])) == EXPECTED_GATES, "non-compensating gates changed")
    require(control.get("formal_credit_delta") == {"engineering": 0, "compliance": 0, "negotiation": 0, "release": 0}, "W164 must remain zero-credit")

    cross = control.get("cross_feed", {})
    require(cross.get("non_promotion_guard") == "REUSE_DOES_NOT_IMPLY_ACCEPTANCE", "cross-feed non-promotion guard missing")
    triage = control.get("triage_federation", {})
    require(triage.get("federation_question") == "WHAT_HAS_THE_FLEET_LEARNED", "federation question changed")
    require(triage.get("triage_question") == "WHAT_SHOULD_THE_FLEET_DO_NEXT", "triage question changed")


def validate_crew(crew: dict[str, Any]) -> None:
    require(crew.get("schema") == "qps-crew-registry/v1.0", "wrong crew schema")
    members = crew.get("members", [])
    require(isinstance(members, list) and members, "crew registry must not be empty")
    ids = [member.get("CREW_ID") for member in members]
    require(len(ids) == len(set(ids)), "CREW_ID values must be unique")

    all_roles: set[str] = set()
    for member in members:
        missing = REQUIRED_CREW_FIELDS - set(member)
        require(not missing, f"{member.get('CREW_ID')}: missing fields {sorted(missing)}")
        all_roles.update(member.get("roles", []))
        vector = member.get("competency_vector", {})
        require(vector, f"{member['CREW_ID']}: competency_vector empty")
        require(all(isinstance(v, int) and 0 <= v <= 5 for v in vector.values()), f"{member['CREW_ID']}: competency values must be integers 0..5")
        if member.get("CONTROL_eligibility"):
            evidence = bool(member.get("runtime_receipts") or member.get("accepted_work"))
            require(evidence, f"{member['CREW_ID']}: CONTROL eligibility requires evidence")
            require(member.get("maturity") != "SEEDED", f"{member['CREW_ID']}: seeded crew cannot be CONTROL eligible")

    require(REQUIRED_SPECIAL_ROLES <= all_roles, "specialist federation roles missing from crew registry")
    require({"PCA_ANALYST", "BT_ANALYST", "TRIAGE_OFFICER", "RESOURCE_ALLOCATOR"} <= all_roles, "triage analytics/resource roles incomplete")


def validate_cross_binding(control: dict[str, Any], crew: dict[str, Any]) -> None:
    required = set(control.get("crew_learning", {}).get("fields", []))
    require(required == REQUIRED_CREW_FIELDS, "control crew field contract differs from validator contract")
    crew_required = set(crew.get("required_fields", []))
    require(crew_required == REQUIRED_CREW_FIELDS, "crew registry required_fields differs from validator contract")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", type=Path, default=CONTROL_DEFAULT)
    parser.add_argument("--crew", type=Path, default=CREW_DEFAULT)
    args = parser.parse_args()

    control = load_json(args.control)
    crew = load_json(args.crew)
    validate_control(control)
    validate_crew(crew)
    validate_cross_binding(control, crew)
    print("W164 PASS: 10/10 control points; H1-H4; MISSION_FED; PEN=B*D; crew registry; bidirectional loop; zero-credit guards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
