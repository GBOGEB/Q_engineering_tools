import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "qps_w285_validate_federation_depth.py"
spec = importlib.util.spec_from_file_location("w285_depth", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_w285_depth_contract_passes():
    result = mod.validate()
    assert result["status"] == "PASS"
    assert result["authoritative_functions"] == 12
    assert result["covered_functions"] == 4
    assert result["credited_atoms"] == 9
    assert result["covered_atom_denominator"] == 16
    assert abs(result["function_depth"] - 0.6) < 1e-12
    assert abs(result["breadth"] - (4 / 12)) < 1e-12
    assert abs(result["global_fleet_penetration"] - 0.2) < 1e-12


def test_exact_crosswalk_and_evidence_bindings_are_byte_bound():
    result = mod.validate()
    assert result["crosswalk_blob"] == mod.EXPECTED_CROSSWALK_BLOB
    candidate = json.loads(mod.DEPTH.read_text(encoding="utf-8"))
    for binding in candidate["evidence_bindings"].values():
        path = mod.ROOT / binding["path"]
        assert path.is_file()
        assert mod.git_blob_sha(path.read_bytes()) == binding["blob"]


def test_duplicate_covered_function_fails_closed():
    candidate = json.loads(mod.DEPTH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(candidate)
    mutated["covered_functions"].append(copy.deepcopy(mutated["covered_functions"][0]))
    try:
        mod.validate(mutated)
    except AssertionError as exc:
        assert "duplicate covered-function" in str(exc) or "exactly four" in str(exc)
    else:
        raise AssertionError("duplicate covered-function mutation unexpectedly passed")


def test_drifted_evidence_binding_fails_closed():
    candidate = json.loads(mod.DEPTH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(candidate)
    sample = "FED-SAMPLE-001-W164-CONTROL"
    mutated["evidence_bindings"][sample]["path"] = "triage/w164/DOES_NOT_EXIST.yaml"
    mutated["evidence_bindings"][sample]["blob"] = "0" * 40
    try:
        mod.validate(mutated)
    except AssertionError as exc:
        assert "binding differs from exact crosswalk" in str(exc)
    else:
        raise AssertionError("drifted evidence binding unexpectedly passed")
