# SSOT Regeneration Pipeline — v0.4.9

## SSOT Files

| File | Role |
|------|------|
| `ssot.json` | Source of truth: material coefficients, formula keys, metadata |
| `ssot_launcher.html` | SSOT entry point with live Plotly chart |
| `index_slides.html` | Slide deck using Reveal.js rendering SSOT content |
| `js/materials.js` | Equation evaluators matching SSOT formulas |

## Regeneration Steps

1. **Update `ssot.json`**: Edit material coefficients or add a new material entry.
2. **Verify evaluators**: Ensure `js/materials.js` evaluators correctly implement all formula types referenced in `ssot.json` (`logpoly`, `rational`, `thermalContraction`).
3. **Run parity tests**: `npx node --experimental-vm-modules node_modules/.bin/jest tests/nist_parity.test.js`.
4. **Visual check**: Open `ssot_launcher.html` on GitHub Pages, confirm Copper RRR low-T peaks visible.
5. **Update version**: Bump `VERSION`, `package.json`, `README.md`.
6. **Commit** using the release script: `.\scripts\prepare-release.ps1 -NewVersion vX.Y.Z`.

## Evaluator Alignment Rule

For Copper RRR thermal conductivity, the authoritative formula is:

```
k(T) = 10^P(log10(T)) / (1 + ρ_0 * 10^P(log10(T)) / (sqrt(T) * β))
```

where `P(x) = a0 + a1·x + a2·x² + ... + a6·x⁶` (NIST logpoly coefficients).
