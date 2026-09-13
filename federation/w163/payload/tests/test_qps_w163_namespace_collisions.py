import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "w163", ROOT / "scripts" / "qps_w163_validate_namespace_collisions.py"
)
w163 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(w163)


class NamespaceControlTests(unittest.TestCase):
    def setUp(self):
        self.taxonomy = w163.load_yaml(ROOT / "controls" / "QPS_MISSION_CONTROL_NAMESPACE_TAXONOMY_v1.yaml")
        self.aliases = w163.load_yaml(ROOT / "controls" / "QPS_MISSION_CONTROL_LEGACY_ALIAS_REGISTRY_v1.yaml")
        errors = []
        w163.validate_taxonomy(self.taxonomy, errors)
        _, self.pr_index, _, self.nav_paths = w163.validate_aliases(self.aliases, errors)
        self.assertEqual(errors, [])

    def test_known_recent_collisions_are_registered(self):
        records = [
            {"repository": "GBOGEB/cryoplant-project", "number": 1050, "title": "W153: cost", "body": ""},
            {"repository": "GBOGEB/cryoplant-project", "number": 1061, "title": "W153: G5", "body": ""},
            {"repository": "GBOGEB/cryoplant-project", "number": 1043, "title": "W152: reliability", "body": ""},
            {"repository": "GBOGEB/cryoplant-project", "number": 1044, "title": "W152: RTM", "body": ""},
            {
                "repository": "GBOGEB/cryoplant-project",
                "number": 1052,
                "title": "W152: navigation",
                "body": "W152 is added as first drill-down in G3 Evidence / Delivery",
            },
            {"repository": "GBOGEB/ABACUS", "number": 1171, "title": "W70/MC-2 repair", "body": ""},
            {"repository": "GBOGEB/pipeline-automation-hub", "number": 40, "title": "W70 MIP", "body": ""},
            {"repository": "GBOGEB/Q_engineering_tools", "number": 14, "title": "W70 MIP", "body": ""},
            {"repository": "GBOGEB/cryogenic-accelerator-workspace", "number": 18, "title": "W70 MIP", "body": ""},
            {"repository": "GBOGEB/CoolProp", "number": 11, "title": "Mission I W4: repair", "body": ""},
        ]
        errors, warnings = [], []
        stats = w163.scan_pr_records(records, self.pr_index, errors, warnings)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(stats["same_repo_duplicate_wave_groups"], 2)
        self.assertGreaterEqual(stats["cross_repo_duplicate_wave_groups"], 1)
        self.assertTrue(any("W153" in item for item in warnings))

    def test_new_same_repo_duplicate_wave_fails_closed(self):
        records = [
            {"repository": "GBOGEB/cryoplant-project", "number": 2001, "title": "W199: alpha", "body": ""},
            {"repository": "GBOGEB/cryoplant-project", "number": 2002, "title": "W199: beta", "body": ""},
        ]
        errors, warnings = [], []
        w163.scan_pr_records(records, self.pr_index, errors, warnings)
        self.assertTrue(any("duplicate recent bare W199" in item for item in errors))

    def test_new_navigation_bare_g_fails_closed(self):
        records = [
            {
                "repository": "GBOGEB/cryoplant-project",
                "number": 2003,
                "title": "dashboard update",
                "body": "Add G3 Evidence / Delivery as a new chapter",
            }
        ]
        errors, warnings = [], []
        w163.scan_pr_records(records, self.pr_index, errors, warnings)
        self.assertTrue(any("navigation/chapter" in item for item in errors))

    def test_unregistered_mission_display_alias_fails_closed(self):
        records = [
            {
                "repository": "GBOGEB/OtherRepo",
                "number": 7,
                "title": "Mission II W1: start",
                "body": "",
            }
        ]
        errors, warnings = [], []
        w163.scan_pr_records(records, self.pr_index, errors, warnings)
        self.assertTrue(any("requires GM-*" in item for item in errors))

    def test_file_scanner_grandfathers_registered_path_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registered = root / "docs" / "QPS_DASHBOARD_LAUNCHER_CURRENT.html"
            registered.parent.mkdir(parents=True)
            registered.write_text("const x={id:'G3'};", encoding="utf-8")
            errors, warnings = [], []
            count = w163.scan_repository_files(root, self.nav_paths, errors, warnings)
            self.assertEqual(count, 1)
            self.assertEqual(errors, [])
            self.assertEqual(len(warnings), 1)

            bad = root / "docs" / "new_dashboard.html"
            bad.write_text("const x={id:'G4'};", encoding="utf-8")
            errors, warnings = [], []
            w163.scan_repository_files(root, self.nav_paths, errors, warnings)
            self.assertTrue(any("unregistered navigation bare-G" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
