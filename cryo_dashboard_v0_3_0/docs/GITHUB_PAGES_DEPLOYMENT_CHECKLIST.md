# GitHub Pages Deployment Checklist — Cryogenic Material Dashboard v0.4.9

## Pre-Deployment Verification

### 1. Test Suite (all must pass)
```bash
npm test
```

| Test | Coverage Focus |
|------|----------------|
| `numerics.test.js` | Integral methods and curve fixture stability |
| `export.test.js` | CSV/JSON export consistency |
| `materials.validate.js` | `materials.json` structure and required fields |
| `file_index_integrity.test.js` | SSOT index/reference consistency |
| `static_entrypoints.test.js` | Required HTML/JS entry points exist |
| `version-coherence-check.js` | Version string coherence |
| `nist_parity.test.js` | 823 assertion checks across NIST parity |

### 2. Asset Verification
- [ ] `.nojekyll` file exists at repository root
- [ ] All relative paths are correct
- [ ] CDN links for Plotly.js and Reveal.js are valid HTTPS URLs

## Post-Deployment Validation

- [ ] Landing page loads without console errors
- [ ] SSOT launcher renders Plotly charts correctly
- [ ] Copper RRR k(T) curves show characteristic low-T peaks
- [ ] Modular dashboard loads material data and computes integrals
- [ ] Theme toggle (dark/light) works on launcher
