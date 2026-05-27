# Session Drop-In Handover - v0.4.7

## Session Title

Cryogenic Dashboard v0.4.7 - Comparison UX normalization controls, overlay
limits, and release-canonical update.

## Current State (2026-05-05)

v0.4.7 introduces comparison-view controls and resolves comparison usability
regressions:

- B1 comparison mode selector: `raw`, `normalized`, `split`.
- Optional B1N panel in split mode for normalized side-by-side shape comparison.
- Comparison selector now keeps all materials visible and disables entries with
  no data for the selected property.
- Maximum comparison overlays enforced at 4 to preserve readability.
- Primary selected material duplication is prevented in comparison overlays.
- Theme toggle clarity improved with explicit `Theme: Light/Dark` label.

## Merge/PR Notes

Suggested PR title:

`release(v0.4.7): comparison normalization modes + canonical artifact refresh`
