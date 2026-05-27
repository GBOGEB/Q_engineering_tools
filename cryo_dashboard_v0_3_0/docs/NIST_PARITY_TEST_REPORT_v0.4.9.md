# NIST Parity Test Report — v0.4.9

## Summary

| Metric | Value |
|--------|-------|
| Total assertions | 823 |
| Test file | `tests/nist_parity.test.js` |
| Pass rate | 100% (as of v0.4.9) |

## What Is Tested

For each of the 10 NIST materials and relevant properties:
- Spot-check at canonical reference temperatures from NIST CRYOCOMP/Property tables
- Tolerances: 5% relative tolerance at each reference point
- Equation forms verified: `logpoly`, `rational`, `thermalContraction`

## Materials Covered

1. Aluminum 1100
2. AISI 304 Stainless Steel
3. AISI 316 Stainless Steel
4. Titanium 6Al-4V
5. Copper RRR 50
6. Copper RRR 100
7. Copper RRR 150
8. Copper RRR 300
9. Copper RRR 500
10. Invar (FeNi36)

## Running the Test

```bash
npx node --experimental-vm-modules node_modules/.bin/jest tests/nist_parity.test.js
```
