import importlib.util
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
