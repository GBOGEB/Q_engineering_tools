<!-- markdownlint-disable MD024 -->

# Changelog




## v0.4.9
**Date:** 2026-05-05

### Added
- SSOT integration (ssot.json, ssot_launcher.html, index_slides.html)
- evalRational() alignment across SSOT presentation files
- NIST data lineage section in ssot.json
- NIST parity regression test suite (nist_parity.test.js, 823 assertions)
- CDN version pinning documentation (docs/CDN_PINNING.md)

### Changed
- All Copper RRR k(T) traces use canonical sqrt(T)-based rational evaluator
- Plotly.js standardized to 2.35.2 across all entry points

## v0.4.8
**Date:** 2026-05-05

## v0.4.7

### Added

- `dashboard_modular.html` + `js/app_modular.js`: Comparison view mode control
  (`raw`, `normalized`, `split`) for B1 overlays.
- `dashboard_modular.html`: New `B1N — Normalized Comparison View` panel shown
  in split mode.
- Explicit overlay limit (`MAX_COMPARISON_OVERLAYS = 4`) with user-facing status messaging.
- Comparison selector now includes all materials and marks unavailable-property entries as disabled.
- Theme toggle label now shows current state (`Theme: Light`/`Theme: Dark`).

### Changed

- version label/title bumped from v0.4.6 to v0.4.7.
- B1 comparison overlay logic now skips duplicate primary material trace.
- `VERSION`: updated to `v0.4.7`.

## v0.4.6

### Added

- **Debug mode toggle** — checkbox in Debug Panel. (GAP-01)
- **Active equation panel** — `equationText()` renders source, equation form, range, and coefficients. (GAP-02)
- **Method equation display** — `methodEquationNote()` helper. (GAP-03)
- **Range status validation indicator** — `rangeStatus()`. (GAP-04)
- **Y-axis min/max override** — two number inputs above `#mainPlot`. (GAP-05)
- **Plot point count control** — separate `plotPoints` input. (GAP-06)
- **Layered wall series-R screening panel**. (GAP-07)
- **VBA/NIST audit table**. (GAP-08)
- **Dark/light theme toggle**. (GAP-09)
- **Average definition note**. (GAP-10)
- **Thermal contraction Y(T) property** — new `tc` property type.

## v0.4.5

### Added

- Dedicated `Delta Summary` panel with `delta_k` and `integral_k`.

## v0.3.0

### Added

- Modular production-style structure.
- `data/materials.json` as material source of truth.
- `js/materials.js` for material models.
- `js/numerics.js` for numerical methods.
- `js/state.js` for state, validation, and calculations.
- `js/plots.js` for Plotly rendering.
- `js/export.js` for CSV/JSON/PNG export.
- `js/app.js` for orchestration.
- Documentation folder with engineering handover.
