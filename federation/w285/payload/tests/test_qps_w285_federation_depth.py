#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/qps_w285_validate_federation_depth.py"
spec = importlib.util.spec_from_file_location("w285_depth_validator", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class W285DepthTests(unittest.TestCase):
    def test_exact_candidate_passes(self):
        r = mod.validate()
        self.assertEqual(r["result"], "PASS_EXACT_DEPTH_DENOMINATOR_AND_MEASUREMENT")
        self.assertEqual(r["functions"], 12)
        self.assertEqual(r["all_current_use_atoms"], 29)
        self.assertEqual(r["depth_numerator"], 5)
        self.assertEqual(r["depth_denominator"], 16)
        self.assertAlmostEqual(r["function_depth"], 5/16)
        self.assertAlmostEqual(r["global_fleet_penetration"], 5/48)
        self.assertFalse(r["authority_transfer"])
        self.assertEqual(r["formal_credit_delta"], 0)

    def test_exact_source_blobs_are_bound(self):
        self.assertEqual(mod.git_blob_sha(mod.DEPTH), mod.EXPECTED_DEPTH_BLOB)
        self.assertEqual(mod.git_blob_sha(mod.TOPOLOGY), mod.EXPECTED_TOPOLOGY_BLOB)
        self.assertEqual(mod.git_blob_sha(mod.CROSSWALK), mod.EXPECTED_CROSSWALK_BLOB)

    def test_topology_decomposition_is_complete_and_nonoverlapping(self):
        topo = mod.topology_current_use(mod.TOPOLOGY.read_text(encoding="utf-8"))
        self.assertEqual(len(topo), 12)
        depth = mod.load_json(mod.DEPTH)
        rows = {x["function"]: x for x in depth["functions"]}
        self.assertEqual(set(rows), set(topo))
        keys = []
        for function, row in rows.items():
            keys.extend(f'{function}::{x["atom_id"]}' for x in row["subsurfaces"])
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 29)

    def test_depth_is_conditioned_on_breadth_not_double_counted(self):
        depth = mod.load_json(mod.DEPTH)
        m = depth["measurement"]
        self.assertAlmostEqual(m["breadth"]["value"], 4/12)
        self.assertAlmostEqual(m["depth_conditioned_on_breadth"]["value"], 5/16)
        self.assertAlmostEqual(m["global_fleet_penetration"]["value"], (4/12)*(5/16))

    def test_zero_current_use_functions_do_not_create_implicit_atoms(self):
        depth = mod.load_json(mod.DEPTH)
        rows = {x["function"]: x for x in depth["functions"]}
        self.assertEqual(rows["DEVELOPER_RUNTIME_HELIUM_PROPERTIES"]["subsurfaces"], [])
        self.assertEqual(rows["DOCUMENT_ORGANISATION_ARTIFACT_INDEX"]["subsurfaces"], [])
        self.assertEqual(rows["PRIVATE_BYTE_PROVENANCE_VAULT"]["subsurfaces"], [])

    def test_maintenance_none_row_is_not_a_routing_function(self):
        topo = mod.topology_current_use(mod.TOPOLOGY.read_text(encoding="utf-8"))
        self.assertNotIn("NONE", topo)
        self.assertEqual(len(topo), 12)


if __name__ == "__main__":
    unittest.main()
