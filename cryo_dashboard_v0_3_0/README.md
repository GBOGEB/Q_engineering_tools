# Cryo Dashboard v0.3.0

**Status:** Live — standalone interactive dashboard  
**Data source:** NIST Chemistry WebBook, SRD 69 (He-4 saturation properties)  
**Domain:** Cryogenic / Superconducting LINAC systems

---

## Overview

**Cryo Dashboard v0.3.0** is a fully interactive, standalone HTML dashboard built
from NIST He-4 reference data for superconducting RF (SRF) LINAC cryogenic systems.
It is hosted as a static site via GitHub Pages at:

```
https://gbogeb.github.io/Q_engineering_tools/cryo_dashboard_v0_3_0/
```

No backend, build step, or server is required — pure HTML / CSS / JavaScript.

---

## Dashboard Features

| Tab | Contents |
| --- | --- |
| 📊 **Method Comparison** | Bar charts and table comparing 4.2 K bath, 2 K He-II, 1.8 K He-II, and supercritical 4.5 K cooling. COP, pressure, Q₀ trade-offs. |
| 🔬 **He-4 Properties** | Four NIST-sourced line charts: saturation pressure P-T, liquid/vapour density, latent heat h_fg, liquid specific heat c_p. |
| ⚙️ **Parameter Sweep** | Interactive sliders for temperature, RF frequency, gradient, cavity length, cavity count, residual resistance. Computes R_BCS, Q₀, P_diss, wall-plug power. |
| 🔥 **Heat Budget** | Doughnut charts for 2 K and 70 K heat-load breakdown; bar chart of AC wall-plug power vs temperature level. |
| 📋 **Data Reference** | Full NIST He-4 saturation table: T, P, ρ_L, ρ_V, h_fg, c_p, μ, λ. Lambda point and critical point highlighted. |

---

## Technical Notes

- **BCS model:** `R_BCS ≈ A·(f/GHz)²/T · exp(−Δ/kT)` with Δ/k = 17.67 K (Nb), A = 1.72 × 10⁻⁴ Ω at 1 GHz
- **Cavity model:** G = 270 Ω, R/Q = 1036 Ω (TESLA-type 1.3 GHz TM₀₁₀)
- **Chart library:** [Chart.js v4.4.0](https://www.chartjs.org/) via CDN
- **Single file:** entire dashboard in `index.html`, no external assets

---

## Contents

| File | Purpose |
| --- | --- |
| `index.html` | Complete dashboard — all HTML, CSS, JS embedded |
| `README.md` | This file |
