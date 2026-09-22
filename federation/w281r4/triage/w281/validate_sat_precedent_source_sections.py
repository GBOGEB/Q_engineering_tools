#!/usr/bin/env python3
"""Fail-closed validation for W281 SAT precedent source-section membership."""

from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from pathlib import Path

try:
    import yaml
except Exception as exc:  # pragma: no cover - fail closed if dependency is absent
    raise SystemExit("PyYAML is required for W281 SAT validation") from exc

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "triage/w280/QPS_W280_VV_EXECUTION_SOURCE_REENTRY_v0.1.csv"
REGISTER = ROOT / "triage/w281/QPS_W281_SAT_VERIFICATION_PRECEDENT_REGISTER_v0.1.csv"
MEMBERSHIP = ROOT / "triage/w281/QPS_W281_SAT_PRECEDENT_MEMBERSHIP_v0.1.csv"
SUMMARY = ROOT / "triage/w281/QPS_W281_SAT_VERIFICATION_PRECEDENT_SUMMARY_v0.1.yaml"
VALIDATION = ROOT / "triage/w281/QPS_W281_SAT_VERIFICATION_PRECEDENT_VALIDATION_v0.1.yaml"

EXPECTED = {
    "VP-SAT-01": {
        "members": ["RTM-510", "RTM-511"],
        "sections": {"4.13.3.1", "4.13.3.2"},
        "register_section": "4.13.3.1 / 4.13.3.2",
        "summary_section": "VP-SAT-01: [4.13.3.1, 4.13.3.2]",
        "validation_members": "members: [RTM-510, RTM-511]",
        "validation_sections": "expected_sections: [4.13.3.1, 4.13.3.2]",
    },
    "VP-SAT-02": {
        "members": ["RTM-512", "RTM-513", "RTM-514", "RTM-517"],
        "sections": {"4.13.3.2"},
        "register_section": "4.13.3.2",
        "summary_section": "VP-SAT-02: [4.13.3.2]",
        "validation_members": "members: [RTM-512, RTM-513, RTM-514, RTM-517]",
        "validation_sections": "expected_sections: [4.13.3.2]",
    },
    "VP-SAT-11": {
        "members": [f"RTM-{n:03d}" for n in range(545, 550)],
        "sections": {"4.13.3.4"},
        "register_section": "4.13.3.4",
        "summary_section": "VP-SAT-11: [4.13.3.4]",
        "validation_members": "member_scope: RTM-545..RTM-549",
        "validation_sections": "expected_sections: [4.13.3.4]",
    },
    "VP-SAT-12": {
        "members": [f"RTM-{n:03d}" for n in range(550, 557)],
        "sections": {"4.13.3.5"},
        "register_section": "4.13.3.5",
        "summary_section": "VP-SAT-12: [4.13.3.5]",
        "validation_members": "member_scope: RTM-550..RTM-556",
        "validation_sections": "expected_sections: [4.13.3.5]",
    },
}


class ValidationError(RuntimeError):
    """Raised when a W281 fail-closed invariant is violated."""


def require(condition: bool, *detail: object) -> None:
    if not condition:
        raise ValidationError(*detail)


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate semantic mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ValidationError("unhashable_yaml_mapping_key", key) from exc
        require(not duplicate, "duplicate_yaml_mapping_key", key)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_unique_yaml(text: str, label: str) -> dict[object, object]:
    try:
        data = yaml.load(text, Loader=UniqueKeyLoader)
    except ValidationError:
        raise
    except yaml.YAMLError as exc:
        raise ValidationError("invalid_yaml", label, str(exc)) from exc
    require(isinstance(data, dict), "yaml_root_not_mapping", label)
    return data


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def require_exact_block(text: str, block: str, label: str) -> None:
    require(
        text.count(block) == 1,
        "missing_duplicate_or_drifted_published_block",
        label,
        text.count(block),
    )


def require_unique_marker(text: str, marker: str, label: str) -> None:
    require(
        text.count(marker) == 1,
        "missing_or_duplicate_published_marker",
        label,
        marker,
        text.count(marker),
    )


def validate(
    source_rows: list[dict[str, str]],
    register_rows: list[dict[str, str]],
    membership_rows: list[dict[str, str]],
    summary_text: str,
    validation_text: str,
) -> None:
    source_section = {row["rtm_id"]: row["section_hint"] for row in source_rows}
    register = {row["precedent_id"]: row for row in register_rows}

    technical = [
        row for row in membership_rows
        if row["precedent_id"] != "VP-SAT-00"
    ]
    rtm_ids = [row["rtm_id"] for row in technical]
    expected_technical = [f"RTM-{n:03d}" for n in range(510, 557)]
    require(len(technical) == 47, "technical_member_count", len(technical))
    require(sorted(rtm_ids) == expected_technical, "technical_membership", rtm_ids)
    require(len(set(rtm_ids)) == 47, "duplicate technical primary membership")

    for precedent_id, expected in EXPECTED.items():
        actual_members = [
            row["rtm_id"] for row in technical
            if row["precedent_id"] == precedent_id
        ]
        require(
            actual_members == expected["members"],
            precedent_id,
            "members",
            actual_members,
            expected["members"],
        )
        actual_sections = {source_section[rtm] for rtm in actual_members}
        require(
            actual_sections == expected["sections"],
            precedent_id,
            "source_sections",
            actual_sections,
            expected["sections"],
        )
        row = register[precedent_id]
        register_members = [
            item.strip() for item in row["member_rtms"].split(";") if item.strip()
        ]
        require(
            register_members == expected["members"],
            precedent_id,
            "register_members",
            register_members,
            expected["members"],
        )
        require(
            int(row["member_count"]) == len(expected["members"]),
            precedent_id,
            "register_member_count",
            row["member_count"],
            len(expected["members"]),
        )
        require(
            row["contract_section"] == expected["register_section"],
            precedent_id,
            "register_section",
            row["contract_section"],
            expected["register_section"],
        )

    # Parse the published YAML with duplicate-key rejection before textual checks.
    # This catches quoted keys, flow mappings, comments/whitespace variants and
    # other YAML-equivalent shadowing that exact string counts cannot see.
    summary_doc = load_unique_yaml(summary_text, "summary")
    validation_doc = load_unique_yaml(validation_text, "validation")

    summary_partition = summary_doc.get("source_section_partition")
    require(
        isinstance(summary_partition, dict),
        "summary_source_section_partition_not_mapping",
    )
    for precedent_id, expected in EXPECTED.items():
        published_sections = summary_partition.get(precedent_id)
        require(
            isinstance(published_sections, list),
            precedent_id,
            "summary_sections_not_list",
            published_sections,
        )
        require(
            set(published_sections) == expected["sections"],
            precedent_id,
            "summary_source_sections",
            published_sections,
            expected["sections"],
        )

    consistency = validation_doc.get("source_section_consistency")
    require(
        isinstance(consistency, dict),
        "validation_source_section_consistency_not_mapping",
    )
    predicates = consistency.get("predicates")
    require(
        isinstance(predicates, dict),
        "validation_source_section_predicates_not_mapping",
    )
    for precedent_id, expected in EXPECTED.items():
        predicate = predicates.get(precedent_id)
        require(
            isinstance(predicate, dict),
            precedent_id,
            "validation_predicate_not_mapping",
        )
        published_sections = predicate.get("expected_sections")
        require(
            isinstance(published_sections, list),
            precedent_id,
            "validation_sections_not_list",
            published_sections,
        )
        require(
            set(published_sections) == expected["sections"],
            precedent_id,
            "validation_source_sections",
            published_sections,
            expected["sections"],
        )
        if "members" in expected["validation_members"]:
            require(
                predicate.get("members") == expected["members"],
                precedent_id,
                "validation_members",
                predicate.get("members"),
                expected["members"],
            )
        else:
            require(
                predicate.get("member_scope") == expected["validation_members"].split(": ", 1)[1],
                precedent_id,
                "validation_member_scope",
                predicate.get("member_scope"),
            )
        require(predicate.get("result") == "PASS", precedent_id, "validation_result")

    # Validate the published summary fields themselves, not merely member scopes.
    require_unique_marker(
        summary_text,
        "source_section_partition:\n",
        "summary_source_section_partition_marker",
    )
    summary_section_block = (
        "source_section_partition:\n"
        "  VP-SAT-01: [4.13.3.1, 4.13.3.2]\n"
        "  VP-SAT-02: [4.13.3.2]\n"
        "  VP-SAT-11: [4.13.3.4]\n"
        "  VP-SAT-12: [4.13.3.5]\n"
    )
    require_exact_block(
        summary_text,
        summary_section_block,
        "summary_source_section_partition",
    )
    require(
        "member_scope: RTM-545..RTM-549, count: 5" in summary_text,
        "summary_VP_SAT_11_scope",
    )
    require(
        "member_scope: RTM-550..RTM-556, count: 7" in summary_text,
        "summary_VP_SAT_12_scope",
    )

    # Validate the published validation predicates themselves.
    require_unique_marker(
        validation_text,
        "source_section_consistency:\n",
        "validation_source_section_consistency_marker",
    )
    for precedent_id, expected in EXPECTED.items():
        require_unique_marker(
            validation_text,
            f"    {precedent_id}:\n",
            f"validation_unique_precedent_{precedent_id}",
        )
        validation_block = (
            f"    {precedent_id}:\n"
            f"      {expected['validation_members']}\n"
            f"      {expected['validation_sections']}\n"
            "      result: PASS\n"
        )
        require_exact_block(
            validation_text,
            validation_block,
            f"validation_source_section_consistency_{precedent_id}",
        )

    require(
        "move_RTM_548_549_to_VP_SAT_12: true" in validation_text,
        "validation_known_bad_RTM_548_549",
    )
    require(
        "label_VP_SAT_01_as_4_13_3_1_only: true" in validation_text,
        "validation_known_bad_VP_SAT_01",
    )
    require(
        "label_VP_SAT_02_as_spanning_4_13_3_1_and_4_13_3_2: true" in validation_text,
        "validation_known_bad_VP_SAT_02",
    )


def expect_rejected(label: str, fn) -> None:
    try:
        fn()
    except ValidationError:
        print(label)
    else:
        raise ValidationError("known bad mutation escaped validation", label)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    source_rows = rows(SOURCE)
    register_rows = rows(REGISTER)
    membership_rows = rows(MEMBERSHIP)
    summary_text = SUMMARY.read_text(encoding="utf-8")
    validation_text = VALIDATION.read_text(encoding="utf-8")

    validate(source_rows, register_rows, membership_rows, summary_text, validation_text)
    print("PASS_W281_SAT_PRECEDENT_SOURCE_SECTION_MEMBERSHIP")

    if args.self_test:
        mutated_membership = deepcopy(membership_rows)
        for row in mutated_membership:
            if row["rtm_id"] == "RTM-548":
                row["precedent_id"] = "VP-SAT-12"
                break
        expect_rejected(
            "PASS_W281_REJECTS_RTM548_BAD_PARTITION",
            lambda: validate(
                source_rows,
                register_rows,
                mutated_membership,
                summary_text,
                validation_text,
            ),
        )

        mutated_register = deepcopy(register_rows)
        for row in mutated_register:
            if row["precedent_id"] == "VP-SAT-01":
                row["contract_section"] = "4.13.3.1"
                break
        expect_rejected(
            "PASS_W281_REJECTS_VP_SAT_01_SECTION_TRUNCATION",
            lambda: validate(
                source_rows,
                mutated_register,
                membership_rows,
                summary_text,
                validation_text,
            ),
        )

        mutated_summary = summary_text.replace(
            "VP-SAT-01: [4.13.3.1, 4.13.3.2]",
            "VP-SAT-01: [4.13.3.1]",
        ).replace(
            "VP-SAT-02: [4.13.3.2]",
            "VP-SAT-02: [4.13.3.1, 4.13.3.2]",
        )
        mutated_validation = validation_text.replace(
            "expected_sections: [4.13.3.1, 4.13.3.2]",
            "expected_sections: [4.13.3.1]",
            1,
        ).replace(
            "expected_sections: [4.13.3.2]",
            "expected_sections: [4.13.3.1, 4.13.3.2]",
            1,
        )
        expect_rejected(
            "PASS_W281_REJECTS_PUBLISHED_SECTION_FIELD_DRIFT",
            lambda: validate(
                source_rows,
                register_rows,
                membership_rows,
                mutated_summary,
                mutated_validation,
            ),
        )

        shadowed_summary = summary_text + (
            "\nsource_section_partition:\n"
            "  VP-SAT-01: [4.13.3.1]\n"
            "  VP-SAT-02: [4.13.3.1, 4.13.3.2]\n"
            "  VP-SAT-11: [4.13.3.4]\n"
            "  VP-SAT-12: [4.13.3.5]\n"
        )
        expect_rejected(
            "PASS_W281_REJECTS_DUPLICATE_SUMMARY_SECTION_PARTITION",
            lambda: validate(
                source_rows,
                register_rows,
                membership_rows,
                shadowed_summary,
                validation_text,
            ),
        )

        shadowed_validation = validation_text + (
            "\nsource_section_consistency:\n"
            "  predicates:\n"
            "    VP-SAT-01:\n"
            "      members: [RTM-510, RTM-511]\n"
            "      expected_sections: [4.13.3.1]\n"
            "      result: PASS\n"
            "    VP-SAT-02:\n"
            "      members: [RTM-512, RTM-513, RTM-514, RTM-517]\n"
            "      expected_sections: [4.13.3.1, 4.13.3.2]\n"
            "      result: PASS\n"
            "    VP-SAT-11:\n"
            "      member_scope: RTM-545..RTM-549\n"
            "      expected_sections: [4.13.3.4]\n"
            "      result: PASS\n"
            "    VP-SAT-12:\n"
            "      member_scope: RTM-550..RTM-556\n"
            "      expected_sections: [4.13.3.5]\n"
            "      result: PASS\n"
        )
        expect_rejected(
            "PASS_W281_REJECTS_DUPLICATE_VALIDATION_PREDICATES",
            lambda: validate(
                source_rows,
                register_rows,
                membership_rows,
                summary_text,
                shadowed_validation,
            ),
        )

        # YAML-equivalent duplicate keys must also fail closed even when their
        # spelling/format does not match the canonical block marker literally.
        shadowed_summary_flow = summary_text + (
            "\nsource_section_partition: {VP-SAT-01: [4.13.3.1]}\n"
        )
        expect_rejected(
            "PASS_W281_REJECTS_FLOW_STYLE_DUPLICATE_SUMMARY_KEY",
            lambda: validate(
                source_rows,
                register_rows,
                membership_rows,
                shadowed_summary_flow,
                validation_text,
            ),
        )

        shadowed_validation_flow = validation_text + (
            "\nsource_section_consistency: {result: FAIL}\n"
        )
        expect_rejected(
            "PASS_W281_REJECTS_FLOW_STYLE_DUPLICATE_VALIDATION_KEY",
            lambda: validate(
                source_rows,
                register_rows,
                membership_rows,
                summary_text,
                shadowed_validation_flow,
            ),
        )

        quoted_duplicate_predicate = validation_text.replace(
            "    VP-SAT-02:\n",
            "    'VP-SAT-01': {result: FAIL}\n    VP-SAT-02:\n",
            1,
        )
        expect_rejected(
            "PASS_W281_REJECTS_QUOTED_DUPLICATE_PREDICATE_KEY",
            lambda: validate(
                source_rows,
                register_rows,
                membership_rows,
                summary_text,
                quoted_duplicate_predicate,
            ),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
