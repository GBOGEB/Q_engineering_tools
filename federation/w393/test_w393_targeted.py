from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
QUALIFY = HERE / "triage/w384/three_family/qualify.py"
spec = importlib.util.spec_from_file_location("w393_qualify", QUALIFY)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def model():
    cases = []
    for idx in range(1, 34):
        ports = {
            "A": {"status": "UNATTRIBUTED"},
            "B": {"status": "BOUND", "state_bbox": [0.0, 0.0, 1.0, 1.0]},
            "D": {"status": "BOUND_FLOW_ONLY", "state_bbox": [2.0, 0.0, 3.0, 1.0]},
            "E": {"status": "UNATTRIBUTED"},
            "W": {"status": "UNATTRIBUTED"},
        }
        if idx <= 9:
            ports["E"] = {"status": "BOUND", "state_bbox": [4.0, 0.0, 5.0, 1.0]}
        cases.append({"case": idx, "page": idx + 4, "ports": ports})
    return {"source": {"label": "E-07"}, "cases": cases}


class ReverseInvariant(unittest.TestCase):
    def test_valid_75_bbox_cohort_passes(self):
        receipt = mod.check_ts(json.dumps(model()).encode())
        self.assertEqual(receipt["bounded_state_labels"], 75)

    def test_bbox_on_unattributed_port_fails(self):
        data = model()
        data["cases"][0]["ports"]["B"]["status"] = "UNATTRIBUTED"
        with self.assertRaisesRegex(ValueError, "TS_BBOX_ON_UNATTRIBUTED_PORT"):
            mod.check_ts(json.dumps(data).encode())


if __name__ == "__main__":
    unittest.main()
