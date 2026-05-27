# Feature → Test → File RTM (v0.4.9)

| Feature | Runtime Files | Validation/Test | Notes |
|---|---|---|---|
| Numerical integration | `js/numerics.js` | `tests/numerics.test.js` | Romberg canonical baseline |
| Export consistency | `js/app_modular.js` | `tests/export.test.js` | Delta summary parity |
| Material schema integrity | `data/materials.json` | `tests/materials.validate.js` | Canonical NIST coefficients |
| File index coherence | `file_index.yaml`, `file_index.json` | `tests/file_index_integrity.test.js` | Prevent fallback-only drift |
| Static GitHub Pages entrypoints | `index.html`, `files.html`, `dashboard_modular.html` | `tests/static_entrypoints.test.js` | Deployment/runtime validation |
| Version coherence | `README.md`, `VERSION`, `package.json` | `scripts/version-coherence-check.js` | Active runtime coherence |
| SSOT evaluator alignment | `ssot_launcher.html`, `index_slides.html`, `js/materials.js` | manual + CI regression | PR #21 canonical fix |
