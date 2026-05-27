# Session Summary

## Project: Cryogenic Material Properties Dashboard (v0.4.9)

**Hosted on:** GitHub Pages via `GBOGEB/Q_engineering_tools`

## What This Is

A portable, standalone HTML/JS engineering dashboard for visualizing cryogenic
material properties (thermal conductivity, specific heat, thermal contraction)
against NIST reference equations. No backend required.

## Primary Entry Points

| File | Description |
|------|-------------|
| `index.html` | Landing page |
| `dashboard_modular.html` | Main dashboard (ES modules + fetch, requires HTTP context) |
| `ssot_launcher.html` | SSOT presentation with live Plotly charts |
| `index_slides.html` | Reveal.js slide deck |
| `material_properties_dashboard_v1_10.html` | Legacy fallback (works via file://) |

## Quick Start

```bash
# Install test dependencies
npm install

# Run all tests
npm test
```

Then open the hosted GitHub Pages URL in your browser.

## Materials Covered (10 NIST Materials)

- Aluminum 1100
- AISI 304, 316 Stainless Steel
- Titanium 6Al-4V
- Copper RRR 50, 100, 150, 300, 500
- Invar (FeNi36)
