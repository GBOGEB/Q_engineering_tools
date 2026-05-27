# PR Release Notes — v0.4.9

## PR Title

`release(v0.4.9): SSOT integration, NIST parity test suite, CDN pin, and canonical file refresh`

## Description

This release integrates the SSOT presentation layer and adds rigorous regression coverage to ensure NIST equation alignment is maintained permanently.

## Changes

### Added
- `ssot_launcher.html` — SSOT presentation entry point
- `index_slides.html` — slide deck built on Reveal.js 4.6.1
- `tests/nist_parity.test.js` — 823 assertions covering NIST parity regression
- `docs/CDN_PINNING.md` — explicit version pinning documentation
- `docs/SSOT_REGENERATION_PIPELINE_v0.4.9.md` — pipeline documentation

### Fixed
- All Copper RRR k(T) traces aligned to canonical evaluator (sqrt(T)-based rational)
- evalRational() alignment verified across all SSOT presentation files

## Merge Checklist
- [ ] `npm test` passes (all 6 test files + version-coherence)
- [ ] SSOT launcher loads on GitHub Pages
- [ ] Copper RRR k(T) low-T peaks visible on hosted renders
- [ ] CDN URLs for Plotly 2.35.2 and Reveal.js 4.6.1 load correctly
