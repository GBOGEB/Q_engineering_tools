# Dashboard Testing Guide

## Running All Tests

```bash
npm test
```

This runs Jest across all test files and then runs `version-coherence-check.js`.

## Individual Tests

```bash
# NIST regression (823 assertions)
npx node --experimental-vm-modules node_modules/.bin/jest tests/nist_parity.test.js

# Numerical methods
npx node --experimental-vm-modules node_modules/.bin/jest tests/numerics.test.js

# Export consistency
npx node --experimental-vm-modules node_modules/.bin/jest tests/export.test.js

# Material schema
node tests/materials.validate.js

# File index integrity
npx node --experimental-vm-modules node_modules/.bin/jest tests/file_index_integrity.test.js

# Static entrypoints
npx node --experimental-vm-modules node_modules/.bin/jest tests/static_entrypoints.test.js

# Version coherence
node scripts/version-coherence-check.js
```

## Manual Verification (GitHub Pages)

1. Open `index.html` — confirm link to `dashboard_modular.html` works.
2. Open `dashboard_modular.html` — select Copper RRR 300 → Thermal Conductivity (k).
3. Verify low-temperature peak visible in the 4–20 K range.
4. Confirm delta summary panel updates when changing T range.
5. Open `ssot_launcher.html` — verify material chart renders.
