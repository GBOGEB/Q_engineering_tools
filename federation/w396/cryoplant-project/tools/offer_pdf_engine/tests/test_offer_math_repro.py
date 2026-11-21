"""Tests for the offer math reproduction. Uses the committed numeric inputs only."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


omr = _load("offer_math_repro", TOOL / "offer_math_repro.py")
INPUTS = json.loads((TOOL / "offer_math_inputs.json").read_text(encoding="utf-8"))


def test_owned_functions_are_imported_not_copied():
    assert Path(omr.W142.__file__).name == "qps_w142_invcop_thermo_return_cold.py"
    assert Path(omr.ROUTER.__file__).parent.name == "property_router"
    assert not hasattr(omr, "invcop")


def test_exergy_eq_reproduces_alat_table():
    out: list = []
    res = omr.alat_exergy(INPUTS["alat_exergy"], out)
    rows = {r["name"]: r for r in out}
    assert rows["ALAT Q_4.5K_eq total"]["verdict"] == "REPRODUCED"
    assert math.isclose(res["total_W"], 3166, rel_tol=0.001)
    assert math.isclose(res["invcop"], 1340 / 3.1658, rel_tol=0.001)


def test_exergy_eq_rejects_bad_input():
    with pytest.raises(ValueError):
        omr.exergy_eq_W(-1, 0, 1, 0, 1)
    with pytest.raises(ValueError):
        omr.exergy_eq_W(1, 0, 1, 0, 1, t0=300, t_eq=300)


def test_sound_sum_and_water_heat():
    assert math.isclose(omr.sound_sum_dB([75.0] * 4), 75 + 10 * math.log10(4), abs_tol=1e-9)
    with pytest.raises(ValueError):
        omr.sound_sum_dB([])
    assert math.isclose(omr.water_heat_W(7.9, 25), 229.2e3, rel_tol=0.002)


def test_limit_and_arithmetic_verdicts():
    out: list = []
    omr.cooling_water(INPUTS["cooling_water"], out)
    lkt = [r for r in out if r["name"].startswith("LKT '4 x 18.5")]
    assert lkt and all(r["verdict"] == "DISCREPANCY" and r["reproduced"] == 74.0 for r in lkt)
    out = []
    omr.noise(INPUTS["noise"], out)
    per = [r for r in out if r["name"].startswith("Per-compressor SPL")]
    fleet = [r for r in out if r["name"].startswith("Fleet SPL")]
    room = [r for r in out if r["name"].startswith("Room SPL")]
    assert per and all(r["threshold_kind"] == "CONTRACT_LIMIT" for r in per)
    assert all(r["verdict"] == "WITHIN_LIMIT" for r in per)
    assert fleet and all(r["verdict"] == "INFO" and r["stated"] is None for r in fleet)
    assert room and all(r["verdict"] == "INFO" and r["stated"] is None for r in room)
    assert max(r["reproduced"] for r in fleet) > INPUTS["noise"]["limit_dBA_at_1m"]
    out = []
    omr.guard_band(INPUTS["guard_band"], out)
    assert {r["verdict"] for r in out} == {"BELOW_LIMIT"}


def test_sankey_links_conserve_flow():
    bal = {"in_HP_kWe": 800, "in_PVPS_kWe": 80, "in_CC_kWe": 5, "HP_loss_kW": 300, "HP_isothermal_kW": 500,
           "PVPS_loss_kW": 50, "PVPS_isothermal_kW": 30, "coldbox_irreversibility_kW": 335, "users_exergy_kW": 200}
    labels, s, t, v = omr.sankey_links(bal)
    for node in range(1, 7):
        inflow = sum(val for src, tgt, val in zip(s, t, v) if tgt == node)
        outflow = sum(val for src, tgt, val in zip(s, t, v) if src == node)
        if inflow and outflow:
            assert math.isclose(inflow, outflow, abs_tol=0.11), labels[node]


def test_efficiency_2k_both_bidders():
    pytest.importorskip("CoolProp")
    out: list = []
    eff = omr.efficiency_2k(INPUTS["efficiency_2k"], out)
    rows = {r["name"]: r["reproduced"] for r in out}
    # HP+PVPS boundary on recomputed own-state Q_eq
    assert 385 < rows["ALAT invCOP (HP+PVPS) on recomputed own states"] < 410
    assert 280 < rows["LKT invCOP (HP+PVPS) on recomputed own states"] < 300
    # ~370 for ALAT needs Q_eq ~3.4 kW
    assert math.isclose(rows["ALAT Q_eq needed for invCOP 370 (HP+PVPS)"], 1258 / 370, rel_tol=1e-6)
    for name in ("ALAT", "LKT"):
        bal = eff[name]["balance"]
        carnot = (300 - 4.5) / 4.5
        inv = eff[name]["hp_pvps_kWe"] / (eff[name]["qeq"]["total_W"] / 1e3)
        assert math.isclose(bal["exergetic_eff_HP_PVPS"], carnot / inv, rel_tol=1e-9)
        assert 0 < bal["HP_isothermal_eff"] < 1 and bal["coldbox_irreversibility_kW"] > 0


def test_cli_writes_json_and_html(tmp_path: Path):
    pytest.importorskip("plotly")
    assert omr.main(["--out", str(tmp_path), "--html"]) == 0
    env = json.loads((tmp_path / "offer_math_reproduction.json").read_text(encoding="utf-8"))
    assert env["authority_transfer"] is False and env["schema"] == "offer-math-reproduction/v1"
    assert (tmp_path / "offer_math_reproduction.html").exists()
    if env["efficiency_2k"]:
        assert (tmp_path / "exergy_sankey_2k.html").exists()
