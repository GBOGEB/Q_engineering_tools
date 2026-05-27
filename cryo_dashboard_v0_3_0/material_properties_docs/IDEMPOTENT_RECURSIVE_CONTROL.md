# Idempotent Recursive Control

## Principle

The cryogenic dashboard follows an **idempotent recursive control** discipline:

> Each artifact can be regenerated from its declared source without external state dependencies.

## Application to Data

`data/materials.json` is regenerated from NIST reference coefficients.
No interpolated or derived values are stored in the source; all derived outputs are computed at runtime.

## Application to Tests

All tests are stateless. Running `npm test` twice gives identical results with no side effects.

## Application to Versioning

`scripts/prepare-release.ps1` performs version bumps idempotently — running it twice with the same target version produces no net change.

## Application to SSOT

`ssot.json` is the canonical source for material metadata. Any derived presentation file (`ssot_launcher.html`, `index_slides.html`) is regenerated from `ssot.json` content.
