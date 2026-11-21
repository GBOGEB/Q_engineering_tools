#!/usr/bin/env python3
"""Reproduce the arithmetic stated in the LKT and ALAT offers.

Figures and page locators come from offer_math_inputs.json (numbers only, source SHA-256
pinned). Owned functions are imported, not copied:
  - invcop()                        scripts/qps_w142_invcop_thermo_return_cold.py
  - HeliumPropertyRouter            tools/property_router/router.py (INDEPENDENT_CHECK role;
                                    the 2.0-4.5 K governing role stays with HEPAK)
New here: the isothermal 4.5 K exergy-equivalent load (Q_4.5K_eq). b04c4_energy.py marks it
'source_exergy_equivalent_load_not_recomputed'; this module recomputes it.

The output envelope follows the gg_MATH bridge conventions (pipeline-automation-hub
mission-control/qps-triage-ultra/ggmath_bridge.py): a threshold_kind per output and
authority_transfer false. A reproduction checks the bidder's arithmetic; it is not evidence
that the plant meets the number.

    python offer_math_repro.py --out <folder outside git> [--html]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
INPUTS = HERE / "offer_math_inputs.json"
SCHEMA = "offer-math-reproduction/v1"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


W142 = _load("qps_w142_invcop_thermo_return_cold", REPO / "scripts" / "qps_w142_invcop_thermo_return_cold.py")
ROUTER = _load("qps_property_router", REPO / "tools" / "property_router" / "router.py")


def rec(name: str, source: str, stated: Any, reproduced: Any, unit: str, kind: str,
        tol_rel: float = 0.01, note: str = "", limit: str | None = None) -> dict:
    """One output row. limit='max'/'min' compares against a limit instead of a stated value."""
    if limit in ("max", "min"):
        ok = reproduced <= stated if limit == "max" else reproduced >= stated
        verdict = "WITHIN_LIMIT" if ok else ("OVER_LIMIT" if limit == "max" else "BELOW_LIMIT")
        dev = (reproduced - stated) / stated
    elif isinstance(stated, (int, float)) and isinstance(reproduced, (int, float)) and stated:
        dev = (reproduced - stated) / stated
        verdict = "REPRODUCED" if abs(dev) <= tol_rel else "DISCREPANCY"
    else:
        dev, verdict = None, "INFO"
    if isinstance(reproduced, float):
        reproduced = round(reproduced, 4)
    return {"name": name, "source": source, "stated": stated, "reproduced": reproduced, "unit": unit,
            "rel_deviation": None if dev is None else round(dev, 4), "verdict": verdict,
            "threshold_kind": kind, "note": note}


def exergy_eq_W(m_kg_s: float, h_in: float, h_out: float, s_in: float, s_out: float,
                t0: float = 300.0, t_eq: float = 4.5) -> float:
    """Isothermal t_eq-equivalent of a load: |m[(h_in-h_out) - t0(s_in-s_out)]| * t_eq/(t0-t_eq)."""
    if m_kg_s < 0:
        raise ValueError("mass flow must be >= 0")
    if not 0 < t_eq < t0:
        raise ValueError("need 0 < t_eq < t0")
    dex = m_kg_s * ((h_in - h_out) - t0 * (s_in - s_out))
    return abs(dex) * t_eq / (t0 - t_eq)


def sound_sum_dB(levels: list[float]) -> float:
    """Energetic sum of sound pressure levels at equal distance (no room correction)."""
    if not levels:
        raise ValueError("need at least one level")
    return 10 * math.log10(sum(10 ** (lv / 10) for lv in levels))


def water_heat_W(v_m3_h: float, dt_K: float, cp: float = 4186.0, rho: float = 998.0) -> float:
    return v_m3_h / 3600 * rho * cp * dt_K


def alat_exergy(cfg: dict, out: list) -> dict:
    t0, teq = cfg["T0_K"], cfg["T_eq_K"]
    total = 0.0
    for name, d in cfg["loads"].items():
        m = d.get("m_kg_s") or d["Q_W"] / (d["h_out"] - d["h_in"])
        q = exergy_eq_W(m, d["h_in"], d["h_out"], d["s_in"], d["s_out"], t0, teq)
        total += q
        out.append(rec(f"ALAT Q_4.5K_eq {name}", cfg["locator"], d["stated_Q45_W"], q, "W",
                       "EXACT_IDENTITY", 0.005, f"mass flow {m * 1000:.2f} g/s"))
    out.append(rec("ALAT Q_4.5K_eq total", cfg["locator"], cfg["stated_total_Q45_W"], total, "W",
                   "EXACT_IDENTITY", 0.005))
    w_kw = sum(cfg["w_elec_kW"].values())
    inv = W142.invcop(w_kw, total / 1000.0)
    out.append(rec("ALAT invCOP from stated W_elec and Q_eq", cfg["locator"], cfg["invcop_contract"], inv,
                   "W/W", "MODEL_DERIVED", cfg["assumed_U_rel"],
                   "contract value sits above the computed value by about the assumed U"))
    headroom = cfg["invcop_contract"] / inv - 1
    out.append(rec("ALAT invCOP headroom vs assumed U", cfg["locator"], cfg["assumed_U_rel"], headroom, "-",
                   "MODEL_DERIVED", 0.05,
                   f"real margin with expected U {cfg['expected_U_rel']:.1%}: {headroom - cfg['expected_U_rel']:.1%}"))
    return {"total_W": total, "invcop": inv}


def interface_2k(cfg: dict, out: list) -> None:
    router = ROUTER.HeliumPropertyRouter()
    res = {}
    for pt in ("A", "B"):
        req = ROUTER.PropertyRequest(temperature_K=cfg[pt]["T_K"], pressure_Pa=cfg[pt]["P_Pa"],
                                     authority="INDEPENDENT_CHECK", point_id=pt)
        try:
            res[pt] = router.evaluate(req)
        except ImportError as exc:  # CoolProp not installed
            out.append(rec("2 K interface property check", cfg["locator"], None, f"DEFER {exc}", "-", "INFO"))
            return
    if any(r.status != "PASS" for r in res.values()):
        out.append(rec("2 K interface property check", cfg["locator"], None,
                       "DEFER " + "; ".join(f"{k}:{r.status}" for k, r in res.items()), "-", "INFO"))
        return
    dh = res["B"].values["enthalpy_J_kg"] - res["A"].values["enthalpy_J_kg"]
    ds = res["B"].values["entropy_J_kgK"] - res["A"].values["entropy_J_kgK"]
    out.append(rec("dh A->B, CoolProp (independent check)", cfg["locator"], cfg["stated_dh_J_kg"], dh, "J/kg",
                   "MODEL_DERIVED", 0.03))
    out.append(rec("ds A->B, CoolProp (independent check)", cfg["locator"], cfg["stated_ds_J_kgK"], ds, "J/kg/K",
                   "MODEL_DERIVED", 0.03))
    out.append(rec("2 K mass flow implied by Q", cfg["locator"], cfg["lkt_stated_B_min_g_s"],
                   cfg["Q_W"] / dh * 1000, "g/s", "MODEL_DERIVED", 0.10,
                   "LKT: this flow is not measured; acceptance is cold-compressor suction flow only"))


def cooling_water(cfg: dict, out: list) -> None:
    lk = cfg["lkt_recovery_per_unit"]
    one = water_heat_W(lk["m3_h"], lk["dT_K"])
    out.append(rec("LKT heat recovery per compressor", lk["locator"], lk["kW"] * 1e3, one, "W", "EXACT_IDENTITY", 0.02))
    out.append(rec("LKT heat recovery fleet", lk["locator"], lk["kW"] * lk["units"] * 1e3, one * lk["units"], "W",
                   "EXACT_IDENTITY", 0.02, "no RCW/PCW split or RCW-loss case offered"))
    al = cfg["alat_rcw"]
    out.append(rec("ALAT RCW recovery, pure water", al["locator"], al["kW"] * 1e3, water_heat_W(al["m3_h"], al["dT_K"]),
                   "W", "EXACT_IDENTITY", 0.02))
    out.append(rec("ALAT RCW recovery, glycol per own spec", al["glycol_locator"], al["kW"] * 1e3,
                   water_heat_W(al["m3_h"], al["dT_K"], al["glycol_cp_J_kgK"], al["glycol_rho_kg_m3"]), "W",
                   "MODEL_DERIVED", 0.02, "glycol lowers recovered heat at the stated flow"))
    pc = cfg["alat_pcw_wcs"]
    dv = pc["m3_h_without_recovery"] - pc["m3_h_with_full_recovery"]
    out.append(rec("ALAT PCW extra duty on RCW loss", pc["locator"], al["kW"] * 1e3, water_heat_W(dv, pc["dT_max_K"]),
                   "W", "MODEL_DERIVED", 0.06,
                   f"RCW loss: PCW flow steps +{dv} m3/h ({dv / pc['m3_h_with_full_recovery']:.0%}) without trip"))
    for a in cfg["lkt_arithmetic"]:
        out.append(rec(f"LKT '{a['factor']} x {a['unit_value']} = {a['stated']}' {a['label']}", a["locator"],
                       a["stated"], a["factor"] * a["unit_value"], "-", "EXACT_IDENTITY", 0.0))


def noise(cfg: dict, out: list) -> dict:
    res = {}
    lim = cfg["limit_dBA_at_1m"]
    for c in cfg["cases"]:
        out.append(rec(
            f"Per-compressor SPL, {c['label']}",
            c["locator"], lim, c["dBA"], "dB(A)", "CONTRACT_LIMIT",
            limit="max",
            note=f"{cfg['limit_locator']}; contractual criterion applies to each compressor at 1 m",
        ))
        for n in (3, 4):
            v = sound_sum_dB([c["dBA"]] * n)
            res[f"{c['label']} N={n}"] = v
            out.append(rec(
                f"Fleet SPL, {c['label']}, {n} units",
                c["locator"], None, v, "dB(A)", "INFORMATIONAL",
                note="equal-distance energetic sum, no reverberation; not compared with the per-compressor contractual limit",
            ))
    v = sound_sum_dB([cfg["cases"][0]["dBA"]] * 4 + [cfg["pvps_upper_dBA"]])
    out.append(rec(
        "Room SPL, 4 compressors + PVPS upper bound",
        cfg["pvps_locator"], None, v, "dB(A)", "INFORMATIONAL",
        note="informational energetic sum only; no aggregate-room contractual criterion is asserted here",
    ))
    return res


def guard_band(cfg: dict, out: list) -> None:
    for meas in cfg["measured_W"]:
        out.append(rec(f"Guard-band: measured {meas} W, U {cfg['U_rel']:.1%}", cfg["locator"], cfg["target_W"],
                       meas * (1 - cfg["U_rel"]), "W", "DISTRIBUTION_DERIVED", limit="min",
                       note="bidders' raw-mean rule passes; verdict shown is the guard-banded one"))


def _hs(router, T: float, P: float) -> tuple[float, float]:
    r = router.evaluate(ROUTER.PropertyRequest(temperature_K=T, pressure_Pa=P, authority="INDEPENDENT_CHECK"))
    if r.status != "PASS":
        raise RuntimeError(f"property DEFER at {T} K {P} Pa: {r.status}")
    return r.values["enthalpy_J_kg"], r.values["entropy_J_kgK"]


def qeq_from_states(router, states: dict, loads: dict, t0: float, t_eq: float) -> dict:
    """Q_4.5K_eq (W) from interface states: cavity A->B, shield D->E, couplers A->W."""
    a, b, d, e, w = (_hs(router, *states[k]) for k in ("A", "B", "D", "E", "W"))
    m_cav = loads["Qcav+QB_W"] / (b[0] - a[0])
    m_ts = loads["QTS_W"] / (e[0] - d[0])
    parts = {
        "Qcav+QB": exergy_eq_W(m_cav, a[0], b[0], a[1], b[1], t0, t_eq),
        "QTS": exergy_eq_W(m_ts, d[0], e[0], d[1], e[1], t0, t_eq),
        "mCPRL": exergy_eq_W(loads["mCPRL_kg_s"], a[0], w[0], a[1], w[1], t0, t_eq),
    }
    return {"parts_W": parts, "total_W": sum(parts.values()), "m_cav_g_s": m_cav * 1e3, "m_ts_g_s": m_ts * 1e3}


def exergy_balance(bid: dict, qeq_W: float, t0: float, t_eq: float) -> dict:
    """Exergy flows (kW) for a Sankey: electrical in -> compression losses -> cold box -> users."""
    hp, pv = bid["hp"], bid["pvps"]
    hp_iso = W142.ideal_isothermal_kW(W142.CompressionPoint(hp["m_kg_s"], hp["p1_bar_a"], hp["p2_bar_a"], t0))
    # PVPS carries the 2 K cavity flow; use the flow the cavity load implies
    m_vlp = bid["_m_cav_g_s"] / 1e3
    pv_iso = W142.ideal_isothermal_kW(W142.CompressionPoint(m_vlp, pv["p_suction_bar_a"], pv["p_discharge_bar_a"], t0))
    users = qeq_W / 1e3 * (t0 - t_eq) / t_eq
    kwe = bid["kWe"]
    cc = kwe.get("CC", 0.0)
    coldbox_in = hp_iso + pv_iso + cc
    return {
        "in_HP_kWe": kwe["HP"], "in_PVPS_kWe": kwe["PVPS"], "in_CC_kWe": cc,
        "HP_isothermal_kW": hp_iso, "HP_loss_kW": kwe["HP"] - hp_iso, "HP_isothermal_eff": hp_iso / kwe["HP"],
        "PVPS_isothermal_kW": pv_iso, "PVPS_loss_kW": kwe["PVPS"] - pv_iso, "PVPS_isothermal_eff": pv_iso / kwe["PVPS"],
        "coldbox_irreversibility_kW": coldbox_in - users, "users_exergy_kW": users,
        "exergetic_eff_HP_PVPS": users / (kwe["HP"] + kwe["PVPS"]),
        "m_vlp_g_s": m_vlp * 1e3, "hp_m_basis": hp["m_basis"], "pvps_basis": pv["basis"],
    }


def efficiency_2k(cfg: dict, out: list) -> dict:
    """Nominal 2K-OP invCOP on the HP+PVPS boundary, for both bidders, on four Q_eq bases."""
    t0, teq = cfg["T0_K"], cfg["T_eq_K"]
    carnot = (t0 - teq) / teq
    try:
        router = ROUTER.HeliumPropertyRouter()
        common = qeq_from_states(router, {k: v for k, v in cfg["rtm_common_states"].items() if k != "locator"},
                                 cfg["loads"], t0, teq)
    except (ImportError, RuntimeError) as exc:
        out.append(rec("2K efficiency", "efficiency_2k", None, f"DEFER {exc}", "-", "INFO"))
        return {}
    res = {"common_states_qeq_W": common["total_W"]}
    for name, bid in cfg["bidders"].items():
        own = qeq_from_states(router, bid["states"], cfg["loads"], t0, teq)
        bid = dict(bid, _m_cav_g_s=own["m_cav_g_s"])
        hp_pv = bid["kWe"]["HP"] + bid["kWe"]["PVPS"]
        all_in = bid.get("printed_total_kWe") or sum(bid["kWe"].values())
        bases = {"stated Q_eq": bid["stated_qeq_kW"] * 1e3, "recomputed own states": own["total_W"],
                 "recomputed RTM common states": common["total_W"], "cost-master common 3.43": cfg["common_qeq_kW"]["value"] * 1e3}
        out.append(rec(f"{name} Q_eq recomputed from own interface states", bid["locator"], bid["stated_qeq_kW"] * 1e3,
                       own["total_W"], "W", "MODEL_DERIVED", 0.03,
                       ", ".join(f"{k} {v:.0f}" for k, v in own["parts_W"].items())))
        for label, q in bases.items():
            out.append(rec(f"{name} invCOP (HP+PVPS) on {label}", bid["locator"], None, hp_pv / (q / 1e3), "W/W",
                           "MODEL_DERIVED", note=f"{hp_pv} kWe / {q / 1e3:.3f} kW"))
        out.append(rec(f"{name} invCOP all-in on own states", bid["locator"], bid["invcop_contract"],
                       W142.invcop(all_in, own["total_W"] / 1e3), "W/W", "MODEL_DERIVED", 0.03,
                       f"{all_in} kWe; contract value shown as stated"))
        q_for_ref = hp_pv / cfg["user_reference_invcop"]
        out.append(rec(f"{name} Q_eq needed for invCOP {cfg['user_reference_invcop']} (HP+PVPS)", bid["locator"], None,
                       q_for_ref, "kW", "MODEL_DERIVED"))
        bal = exergy_balance(bid, own["total_W"], t0, teq)
        out.append(rec(f"{name} exergetic efficiency HP+PVPS (= Carnot {carnot:.2f} / invCOP)", bid["locator"],
                       carnot / (hp_pv / (own["total_W"] / 1e3)), bal["exergetic_eff_HP_PVPS"], "-",
                       "EXACT_IDENTITY", 0.001))
        res[name] = {"qeq": own, "balance": bal, "hp_pvps_kWe": hp_pv}
    return res


def reproduce(inputs: dict) -> dict:
    recs: list = []
    alat_exergy(inputs["alat_exergy"], recs)
    interface_2k(inputs["interface_2k"], recs)
    eff = efficiency_2k(inputs["efficiency_2k"], recs)
    cooling_water(inputs["cooling_water"], recs)
    noise_res = noise(inputs["noise"], recs)
    guard_band(inputs["guard_band"], recs)
    return {"schema": SCHEMA, "authority_transfer": False, "evidence_class": "ARITHMETIC_REPRODUCTION",
            "inputs_schema": inputs["schema"], "sources": inputs["sources"], "outputs": recs,
            "efficiency_2k": eff, "_noise": noise_res}


def write_html(env: dict, path: Path) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Fleet sound pressure (informational energetic sum)",
                                                        "Exact-identity reproductions (% deviation)"))
    nz = env["_noise"]
    fig.add_bar(x=list(nz), y=list(nz.values()), row=1, col=1)
    rr = [r for r in env["outputs"] if r["threshold_kind"] == "EXACT_IDENTITY" and r["rel_deviation"] is not None]
    fig.add_bar(x=[r["name"][:40] for r in rr], y=[100 * r["rel_deviation"] for r in rr], row=1, col=2,
                marker_color=["#c0392b" if r["verdict"] == "DISCREPANCY" else "#2e86c1" for r in rr])
    fig.update_layout(height=520, showlegend=False, title="Offer math reproduction")
    fig.write_html(path, include_plotlyjs="cdn")


def sankey_links(bal: dict) -> tuple[list[str], list[int], list[int], list[float]]:
    labels = ["Electrical in", "HP compressors", "PVPS", "Cold compressors", "HP compression loss",
              "PVPS loss", "Cold box (HX, turbines, valves)", "Cold box irreversibility", "Exergy to users (4.5 K eq)"]
    flows = [(0, 1, bal["in_HP_kWe"]), (0, 2, bal["in_PVPS_kWe"]), (0, 3, bal["in_CC_kWe"]),
             (1, 4, bal["HP_loss_kW"]), (1, 6, bal["HP_isothermal_kW"]),
             (2, 5, bal["PVPS_loss_kW"]), (2, 6, bal["PVPS_isothermal_kW"]), (3, 6, bal["in_CC_kWe"]),
             (6, 7, bal["coldbox_irreversibility_kW"]), (6, 8, bal["users_exergy_kW"])]
    flows = [f for f in flows if f[2] > 0]
    return labels, [f[0] for f in flows], [f[1] for f in flows], [round(f[2], 1) for f in flows]


def write_sankey(eff: dict, path: Path) -> None:
    import plotly.graph_objects as go

    names = [k for k in eff if isinstance(eff[k], dict) and "balance" in eff[k]]
    # fixed columns: source | machines | cold box | sinks
    node_x = [0.01, 0.30, 0.30, 0.30, 0.99, 0.99, 0.62, 0.99, 0.99]
    node_y = [0.45, 0.30, 0.80, 0.93, 0.15, 0.97, 0.55, 0.50, 0.80]
    colors = ["#5b6c8f", "#c0504d", "#4bacc6", "#8064a2", "#e6a06b", "#9bd3e3", "#7f9fbf", "#bfbfbf", "#2e8b57"]
    fig = go.Figure()
    n = len(names)
    for i, name in enumerate(names):
        bal = eff[name]["balance"]
        labels, s, t, v = sankey_links(bal)
        totals = {}
        for src, val in zip(s, v):
            totals[src] = totals.get(src, 0) + val
        for tgt, val in zip(t, v):
            totals.setdefault(tgt, 0)
            if tgt not in s:
                totals[tgt] += val
        lo = 1 - (i + 1) / n
        fig.add_trace(go.Sankey(
            domain={"x": [0, 1], "y": [lo + 0.06, lo + 1 / n - 0.06]},
            arrangement="fixed", valueformat=".0f", valuesuffix=" kW",
            node={"label": [f"{lb} {totals.get(k, 0):.0f} kW" for k, lb in enumerate(labels)],
                  "x": node_x, "y": node_y, "color": colors, "pad": 12, "thickness": 16},
            link={"source": s, "target": t, "value": v}))
        hp_pv = bal["in_HP_kWe"] + bal["in_PVPS_kWe"]
        fig.add_annotation(x=0, y=lo + 1 / n - 0.01, xref="paper", yref="paper", showarrow=False, xanchor="left",
                           text=(f"<b>{name}</b>: HP+PVPS {hp_pv:.0f} kWe, exergy to users "
                                 f"{bal['users_exergy_kW']:.0f} kW, exergetic eff. {bal['exergetic_eff_HP_PVPS']:.1%}, "
                                 f"HP isothermal eff. {bal['HP_isothermal_eff']:.0%}"))
    fig.update_layout(height=430 * n, title="2K-OP exergy balance (kW), recomputed Q_eq on own interface states")
    fig.write_html(path, include_plotlyjs="cdn")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, default=INPUTS)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--html", action="store_true")
    a = ap.parse_args(argv)
    env = reproduce(json.loads(a.inputs.read_text(encoding="utf-8")))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "offer_math_reproduction.json").write_text(
        json.dumps({k: v for k, v in env.items() if not k.startswith("_")}, indent=1), encoding="utf-8")
    if a.html:
        write_html(env, a.out / "offer_math_reproduction.html")
        if env["efficiency_2k"]:
            write_sankey(env["efficiency_2k"], a.out / "exergy_sankey_2k.html")
    for r in env["outputs"]:
        print(f"{r['verdict']:<12} {r['name'][:60]:<60} stated={r['stated']} repro={r['reproduced']} {r['unit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
