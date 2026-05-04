# Cryo Dashboard v0.3.0

**Status:** Live — fully functional standalone dashboard  
**Data source:** NIST REFPROP 10 (Helium-4 & Liquid Nitrogen)  
**Domain:** Cryogenic / Superconducting LINAC systems  
**Live URL:** https://gbogeb.github.io/Q_engineering_tools/cryo_dashboard_v0_3_0/

---

## Overview

**Cryo Dashboard v0.3.0** is an interactive, standalone browser-based reference tool
for cryogenic and superconducting LINAC system design. It provides interactive
visualisation of thermodynamic properties for the two most commonly used cryogenic
fluids in accelerator facilities:

- **Helium-4** — cavity cooling at 4.2 K (1 atm) and 2 K (superfluid)
- **Liquid Nitrogen (LN₂)** — thermal shielding at 77 K

No backend, no build step — a single `index.html` file (with Chart.js via CDN).

## Dashboard tabs

| Tab | Content |
| --- | --- |
| **Overview** | KPI stat cards + four summary charts (P–T, density, latent heat, LN₂ P–T) |
| **Saturation Curve** | Full He-4 P–T log-scale diagram with key operating points + NIST data table |
| **Property Lookup** | Interactive temperature slider → live property readout for He-4 or LN₂ |
| **Method Comparison** | NIST tabulated vs Clausius–Clapeyron vs ideal-gas model; error table |
| **About** | Data sources, critical constants, disclaimer |

## Data sources

| Fluid | EOS | Reference |
| --- | --- | --- |
| He-4 | Helmholtz (Ortiz-Vega *et al.* 2015) | NIST REFPROP 10, Donnelly & Barenghi (1998) |
| N₂ | Helmholtz (Span *et al.* 2000) | NIST REFPROP 10 / NIST WebBook |

## Files

| File | Purpose |
| --- | --- |
| `index.html` | Complete dashboard — HTML + CSS + JavaScript, self-contained |
| `README.md` | This file |
