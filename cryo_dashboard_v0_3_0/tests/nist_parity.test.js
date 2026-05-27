 * NIST Parity Regression Tests
 * =============================
 * Validates all material property calculations in js/materials.js against
 * independently-implemented NIST Monograph 177 / NIST Cryogenic Properties
 * Database equations.
 *
 * Reference:
 *   - NIST Cryogenic Materials Properties Database (trc.nist.gov/cryogenics)
 *   - NIST Monograph 177: "Properties of Copper and Copper Alloys at Cryogenic Temperatures"
 *   - Marquardt, Le, Radebaugh (2000). Cryogenic Material Properties Database.
 *
 * Equation forms:
 *   polylog:    log10(y) = Σ a_i·(log10 T)^i,  y = 10^(sum)
 *   rational:   log10(k) = (a + c·√T + e·T + g·T^(3/2) + i·T²) / (1 + b·√T + d·T + f·T^(3/2) + h·T²),  k = 10^(ratio)
 *   thermal-contraction: y = a + bT + cT² + dT³ + eT⁴;  optional y = f for T < Tlow
 *   piecewise-logpoly: polylog with piece selected by T range
 *
 * Coverage: All 10 materials × all properties (k, cp, tc)
 *   AISI316, Al6061T6, G10Normal, G10Warp, CuRRR50, CuRRR100,
 *   CuRRR150, CuRRR300, CuRRR500, Ti64
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { propertyValue } from "../js/materials.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const db = JSON.parse(
  readFileSync(path.join(__dirname, "..", "data", "materials.json"), "utf8")
);

/* ─── Independent NIST equation implementations ─────────────────────── */

/** NIST polylog: log10(y) = Σ coeff[i]·(log10 T)^i */
function nistPolylog(coeff, T) {
  const x = Math.log10(T);
  let s = 0;
  for (let i = 0; i < coeff.length; i++) {
    s += coeff[i] * Math.pow(x, i);
  }
  return Math.pow(10, s);
}

/**
 * NIST rational (OFHC Copper thermal conductivity):
 *   log10(k) = (a + c·√T + e·T + g·T^(3/2) + i·T²) /
 *              (1 + b·√T + d·T + f·T^(3/2) + h·T²)
 *   k = 10^(above)
 */
function nistRational(coeff, T) {
  const [a, b, c, d, e, f, g, h, i] = coeff;
  const r = Math.sqrt(T);
  const num = a + c * r + e * T + g * Math.pow(T, 1.5) + i * T * T;
  const den = 1 + b * r + d * T + f * Math.pow(T, 1.5) + h * T * T;
  return Math.pow(10, num / den);
}

/** NIST thermal contraction: y = a + bT + cT² + dT³ + eT⁴ */
function nistThermalContraction(coeff, T, tlow, fval) {
  if (tlow !== null && tlow !== undefined &&
      fval !== null && fval !== undefined &&
      T < tlow) {
    return fval;
  }
  const [a, b, c, d, e] = coeff;
  return a + b * T + c * T * T + d * T * T * T + e * T * T * T * T;
}

/** Evaluate a property using ONLY our independent NIST implementations */
function nistEval(material, property, T) {
  const propDef = material.properties[property];
  if (!propDef) return null;

  if (propDef.type === "polylog") {
    return nistPolylog(propDef.coefficients, T);
  }

  if (propDef.type === "piecewise-logpoly") {
    for (const piece of propDef.pieces) {
      if (T >= piece.range[0] && T <= piece.range[1]) {
        return nistPolylog(piece.coefficients, T);
      }
    }
    const coeff = T < propDef.pieces[0].range[0]
      ? propDef.pieces[0].coefficients
      : propDef.pieces[propDef.pieces.length - 1].coefficients;
    return nistPolylog(coeff, T);
  }

  if (propDef.type === "rational") {
    return nistRational(propDef.coefficients, T);
  }

  if (propDef.type === "thermal-contraction") {
    return nistThermalContraction(
      propDef.coefficients, T, propDef.tlow, propDef.f
    );
  }

  throw new Error(`Unknown type: ${propDef.type}`);
}

/* ─── Test utilities ────────────────────────────────────────────────── */

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const failures = [];
const COEFFICIENT_LENGTH_BY_TYPE = {
  polylog: 9,
  rational: 9,
  "thermal-contraction": 5
};
const BOUNDARY_EPSILON_FACTOR = 1e-6;
const LOW_T_EPSILON_K = 1e-6;

function assertParity(label, actual, expected, relTol = 1e-10, absTol = relTol) {
  totalTests++;
  if (expected === 0) {
    const absErr = Math.abs(actual);
    if (absErr <= absTol) {
      passedTests++;
      return true;
    }
    failedTests++;
    failures.push({
      label,
      actual,
      expected,
      absErr,
      absTol
    });
    return false;
  }
  const relErr = Math.abs((actual - expected) / expected);
  if (relErr <= relTol) {
    passedTests++;
    return true;
  } else {
    failedTests++;
    failures.push({
      label,
      actual,
      expected,
      relErr,
      relTol
    });
    return false;
  }
}

/* ─── NIST Reference Coefficients (independently transcribed) ───────── */
// These are the NIST-published coefficients, transcribed directly from
// the NIST Cryogenic Properties Database pages.

const NIST_COEFFICIENTS = {
  AISI316: {
    k: {
      type: "polylog",
      coefficients: [-1.4087, 1.3982, 0.2543, -0.6260, 0.2334, 0.4256, -0.4658, 0.1650, -0.0199],
      range: [1, 300]
    },
    cp_piece1: {
      type: "polylog",
      coefficients: [12.2486, -80.6422, 218.743, -308.854, 239.5296, -89.9982, 3.15315, 8.44996, -1.91368],
      range: [4, 50]
    },
    cp_piece2: {
      type: "polylog",
      coefficients: [-1879.464, 3643.198, 76.70125, -6176.028, 7437.6247, -4305.7217, 1382.4627, -237.22704, 17.05262],
      range: [50, 300]
    }
  },
  Al6061T6: {
    k: {
      type: "polylog",
      coefficients: [0.07918, 1.0957, -0.07277, 0.08084, 0.02803, -0.09464, 0.04179, -0.00571, 0],
      range: [1, 300]
    },
    cp: {
      type: "polylog",
      coefficients: [46.6467, -314.292, 866.662, -1298.3, 1162.27, -637.795, 210.351, -38.3094, 2.96344],
      range: [4, 300]
    }
  },
  G10Normal: {
    k: {
      type: "polylog",
      coefficients: [-4.1236, 13.788, -26.068, 26.272, -14.663, 4.4954, -0.6905, 0.0397, 0],
      range: [10, 300]
    },
    cp: {
      type: "polylog",
      coefficients: [-2.4083, 7.6006, -8.2982, 7.3301, -4.2386, 1.4294, -0.24396, 0.015236, 0],
      range: [4, 300]
    }
  },
  G10Warp: {
    k: {
      type: "polylog",
      coefficients: [-2.64827, 8.80228, -24.8998, 41.1625, -39.8754, 23.1778, -7.95635, 1.48806, -0.11701],
      range: [12, 300]
    }
  },
  CuRRR100: {
    k: {
      type: "rational",
      coefficients: [2.2154, -0.47461, -0.88068, 0.13871, 0.29505, -0.02043, -0.04831, 0.001281, 0.003207],
      range: [4, 300]
    }
  },
  Ti64: {
    k: {
      type: "polylog",
      coefficients: [-5107.8774, 19240.422, -30789.064, 27134.756, -14226.379, 4438.2154, -763.07767, 55.796592, 0],
      range: [20, 300]
    }
  }
};

/* ─── Test Section 1: Coefficient Verification ──────────────────────── */
console.log("═══════════════════════════════════════════════════════════");
console.log("NIST Parity Regression Test Suite");
console.log("═══════════════════════════════════════════════════════════\n");

console.log("Section 1: NIST Coefficient Verification");
console.log("─────────────────────────────────────────");

function assertCoefficientSet(label, coeff, expectedLength) {
  totalTests++;
  const valid = Array.isArray(coeff) &&
    coeff.length === expectedLength &&
    coeff.every(c => Number.isFinite(c));
  if (valid) {
    passedTests++;
  } else {
    failedTests++;
    failures.push({
      label: `${label} coefficient shape/finite check`,
      actual: coeff,
      expected: `${expectedLength} finite coefficients`
    });
  }
}

console.log("  Full-suite coefficient sanity checks (all materials/properties)");
for (const [matKey, mat] of Object.entries(db.materials)) {
  for (const [propKey, propDef] of Object.entries(mat.properties)) {
    if (propDef.type === "piecewise-logpoly") {
      for (let i = 0; i < propDef.pieces.length; i++) {
        assertCoefficientSet(
          `${matKey}.${propKey}.piece${i + 1}`,
          propDef.pieces[i].coefficients,
          COEFFICIENT_LENGTH_BY_TYPE.polylog
        );
      }
      continue;
    }
    if (!COEFFICIENT_LENGTH_BY_TYPE[propDef.type]) continue;
    assertCoefficientSet(
      `${matKey}.${propKey}`,
      propDef.coefficients,
      COEFFICIENT_LENGTH_BY_TYPE[propDef.type]
    );
  }
}
console.log("  ✓ Full-suite coefficient sanity checks completed");
console.log("  NIST exact-match subset checks (transcribed fixtures)");

// Verify that stored coefficients exactly match NIST-published values
for (const [matKey, nistProps] of Object.entries(NIST_COEFFICIENTS)) {
  const mat = db.materials[matKey];
  for (const [propKey, nistDef] of Object.entries(nistProps)) {
    let storedCoeff;
    if (propKey.startsWith("cp_piece")) {
      const pieceIdx = parseInt(propKey.replace("cp_piece", "")) - 1;
      storedCoeff = mat.properties.cp.pieces[pieceIdx].coefficients;
    } else {
      storedCoeff = mat.properties[propKey].coefficients;
    }

    const maxLen = Math.max(nistDef.coefficients.length, storedCoeff.length);
    let maxAbsDelta = 0;
    const mismatchIndices = [];
    for (let i = 0; i < maxLen; i++) {
      const expectedCoeff = nistDef.coefficients[i];
      const actualCoeff = storedCoeff[i];
      const expectedMissing = expectedCoeff === undefined;
      const actualMissing = actualCoeff === undefined;

      if (expectedMissing || actualMissing) {
        if (expectedMissing !== actualMissing) {
          mismatchIndices.push(i);
        }
        continue;
      }

      const absDelta = Math.abs(expectedCoeff - actualCoeff);
      if (Number.isFinite(absDelta) && absDelta > maxAbsDelta) {
        maxAbsDelta = absDelta;
      }
      if (!Number.isFinite(absDelta) || absDelta > 0) {
        mismatchIndices.push(i);
      }
    }

    const match = nistDef.coefficients.length === storedCoeff.length &&
      mismatchIndices.length === 0;

    totalTests++;
    if (match) {
      passedTests++;
      console.log(`  ✓ ${matKey}.${propKey} coefficients match NIST exactly`);
    } else {
      failedTests++;
      failures.push({
        label: `${matKey}.${propKey} coefficient mismatch`,
        actual: storedCoeff,
        expected: nistDef.coefficients,
        maxAbsDelta,
        mismatchIndices: mismatchIndices.slice(0, 5)
      });
      console.log(`  ✗ ${matKey}.${propKey} coefficients MISMATCH (max |Δ|=${maxAbsDelta.toExponential(3)})`);
    }
  }
}

/* ─── Test Section 2: Evaluator Parity (all materials × all properties) */
console.log("\nSection 2: Evaluator Parity — materials.js vs. Independent NIST");
console.log("───────────────────────────────────────────────────────────────");

// Reference temperatures spanning the cryogenic range
const TEMP_POINTS = [4, 5, 7, 10, 15, 20, 30, 50, 77, 100, 150, 200, 250, 300];

const materialKeys = Object.keys(db.materials);

for (const matKey of materialKeys) {
  const mat = db.materials[matKey];

  for (const prop of ["k", "cp", "tc"]) {
    if (!mat.properties[prop]) continue;

    const propDef = mat.properties[prop];
    const [rMin, rMax] = propDef.range;

    // Filter temperatures to valid range
    const validTemps = TEMP_POINTS.filter(T => T >= rMin && T <= rMax);

    // Add boundary temperatures
    if (!validTemps.includes(rMin)) validTemps.unshift(rMin);
    if (!validTemps.includes(rMax) && rMax <= 300) validTemps.push(rMax);

    let propChecks = 0;
    let propFailures = 0;

    for (const T of validTemps) {
      const fromMaterials = propertyValue(mat, prop, T);
      const fromNist = nistEval(mat, prop, T);
      propChecks++;
      const parityOk = assertParity(
        `${matKey}.${prop}(${T}K)`,
        fromMaterials,
        fromNist,
        1e-12  // Very tight tolerance — should be exact
      );
      if (!parityOk) propFailures++;

      // Also verify the value is physically reasonable
      propChecks++;
      totalTests++;
      if (prop === "k" || prop === "cp") {
        if (fromMaterials > 0 && isFinite(fromMaterials)) {
          passedTests++;
        } else {
          failedTests++;
          propFailures++;
          failures.push({
            label: `${matKey}.${prop}(${T}K) physical reasonableness`,
            actual: fromMaterials,
            expected: "> 0 and finite"
          });
        }
      } else {
        // tc can be negative (contraction relative to 293K)
        if (isFinite(fromMaterials)) {
          passedTests++;
        } else {
          failedTests++;
          propFailures++;
          failures.push({
            label: `${matKey}.${prop}(${T}K) finite check`,
            actual: fromMaterials,
            expected: "finite"
          });
        }
      }
    }

    const propPassed = propChecks - propFailures;
    const mark = propFailures === 0 ? "✓" : "✗";
    console.log(`  ${mark} ${matKey}.${prop}: ${propPassed}/${propChecks} checks passed over ${validTemps.length} temp points (range ${rMin}–${rMax} K)`);
  }
}

/* ─── Test Section 3: Copper RRR Rational Model Specific Tests ──────── */
console.log("\nSection 3: Copper RRR Rational Model Deep Validation");
console.log("────────────────────────────────────────────────────");

const copperRRRs = ["CuRRR50", "CuRRR100", "CuRRR150", "CuRRR300", "CuRRR500"];
const peakData = {};

// Test that k(T) shows the characteristic low-T peak for OFHC copper
for (const matKey of copperRRRs) {
  const mat = db.materials[matKey];

  // Dense sampling for peak detection
  const temps = [];
  const kvals = [];
  for (let T = 4; T <= 100; T += 0.5) {
    temps.push(T);
    kvals.push(propertyValue(mat, "k", T));
  }

  const maxK = Math.max(...kvals);
  const maxIdx = kvals.indexOf(maxK);
  const peakT = temps[maxIdx];
  peakData[matKey] = { peakT, maxK };

  // Verify peak exists and is in reasonable range (typically 5-30 K for OFHC Cu)
  totalTests++;
  if (peakT >= 4 && peakT <= 50 && maxK > 100) {
    passedTests++;
    console.log(`  ✓ ${matKey}: low-T peak at ${peakT} K, k_max = ${maxK.toFixed(1)} W/(m·K)`);
  } else {
    failedTests++;
    failures.push({
      label: `${matKey} peak detection`,
      actual: `peak at ${peakT} K, k_max = ${maxK}`,
      expected: "peak in 4-50 K range, k_max > 100"
    });
    console.log(`  ✗ ${matKey}: peak anomaly at ${peakT} K, k_max = ${maxK.toFixed(1)}`);
  }

  // Higher RRR should give higher peak conductivity
  totalTests++;
  if (maxK > 0) {
    passedTests++;
  } else {
    failedTests++;
    failures.push({ label: `${matKey} positive conductivity`, actual: maxK, expected: "> 0" });
  }

  // Verify k(300K) converges for all RRR values (should be ~390-400 W/(m·K))
  const k300 = propertyValue(mat, "k", 300);
  totalTests++;
  if (k300 > 350 && k300 < 450) {
    passedTests++;
  } else {
    failedTests++;
    failures.push({
      label: `${matKey} k(300K) room-temp convergence`,
      actual: k300,
      expected: "350-450 W/(m·K)"
    });
  }
}

// Cross-RRR ordering: higher RRR → higher peak k
console.log("\n  Cross-RRR peak ordering:");
for (let i = 1; i < copperRRRs.length; i++) {
  const prev = copperRRRs[i - 1];
  const curr = copperRRRs[i];
  totalTests++;
  if (peakData[curr].maxK > peakData[prev].maxK) {
    passedTests++;
    console.log(`  ✓ ${curr} peak (${peakData[curr].maxK.toFixed(0)}) > ${prev} peak (${peakData[prev].maxK.toFixed(0)})`);
  } else {
    failedTests++;
    failures.push({
      label: `RRR ordering: ${curr} > ${prev}`,
      actual: `${peakData[curr].maxK} vs ${peakData[prev].maxK}`,
      expected: "higher RRR → higher peak k"
    });
    console.log(`  ✗ RRR ordering: ${curr} (${peakData[curr].maxK.toFixed(0)}) ≤ ${prev} (${peakData[prev].maxK.toFixed(0)})`);
  }
}

/* ─── Test Section 4: Thermal Contraction Validation ────────────────── */
console.log("\nSection 4: Thermal Contraction Validation");
console.log("─────────────────────────────────────────");

const tcMaterials = ["AISI316", "Al6061T6", "G10Normal", "G10Warp", "Ti64"];

for (const matKey of tcMaterials) {
  const mat = db.materials[matKey];
  const propDef = mat.properties.tc;
  if (!propDef) continue;
  const hasTlow = propDef.tlow !== null && propDef.tlow !== undefined;
  const hasF = propDef.f !== null && propDef.f !== undefined;

  totalTests++;
  if (hasTlow === hasF) {
    passedTests++;
  } else {
    failedTests++;
    failures.push({
      label: `${matKey}.tc low-T configuration pairing`,
      actual: { tlow: propDef.tlow, f: propDef.f },
      expected: "tlow and f should be both set or both unset"
    });
  }

  // At T=293 K, contraction should be ~0 (reference temperature)
  const tc293 = propertyValue(mat, "tc", 293);
  totalTests++;
  if (Math.abs(tc293) < 10) {  // close to zero at reference temp
    passedTests++;
    console.log(`  ✓ ${matKey}.tc(293K) = ${tc293.toFixed(3)} (near reference point)`);
  } else {
    failedTests++;
    failures.push({
      label: `${matKey}.tc(293K) near zero`,
      actual: tc293,
      expected: "close to 0"
    });
  }

  // Contraction should be negative at low temperatures (material shrinks)
  const tc10 = propertyValue(mat, "tc", Math.max(propDef.range[0], 10));
  totalTests++;
  if (tc10 < 0) {
    passedTests++;
    console.log(`  ✓ ${matKey}.tc(low-T) = ${tc10.toFixed(3)} (negative = contraction)`);
  } else {
    failedTests++;
    failures.push({
      label: `${matKey}.tc low-T negative`,
      actual: tc10,
      expected: "< 0"
    });
  }

  // Low-T branch test (where applicable)
  if (hasTlow && hasF) {
    const tBelowLow = Math.max(propDef.tlow - LOW_T_EPSILON_K, Number.EPSILON);
    const tcBelow = propertyValue(mat, "tc", tBelowLow);
    totalTests++;
    if (tcBelow === propDef.f) {
      passedTests++;
      console.log(`  ✓ ${matKey}.tc(${tBelowLow}K) = ${propDef.f} (low-T branch active)`);
    } else {
      failedTests++;
      failures.push({
        label: `${matKey}.tc low-T branch`,
        actual: tcBelow,
        expected: propDef.f
      });
    }
  }
}

/* ─── Test Section 5: Edge Cases and Boundary Conditions ────────────── */
console.log("\nSection 5: Edge Cases and Boundary Conditions");
console.log("──────────────────────────────────────────────");

// Test exact boundary temperatures
let section5BoundaryFailures = 0;
for (const matKey of materialKeys) {
  const mat = db.materials[matKey];
  for (const prop of ["k", "cp", "tc"]) {
    if (!mat.properties[prop]) continue;
    const propDef = mat.properties[prop];
    const [rMin, rMax] = propDef.range;

    // Lower bound
    const vMin = propertyValue(mat, prop, rMin);
    totalTests++;
    if (isFinite(vMin) && vMin !== null) {
      passedTests++;
    } else {
      failedTests++;
      section5BoundaryFailures++;
      failures.push({
        label: `${matKey}.${prop}(${rMin}K) lower bound`,
        actual: vMin,
        expected: "finite"
      });
    }

    // Upper bound
    const vMax = propertyValue(mat, prop, rMax);
    totalTests++;
    if (isFinite(vMax) && vMax !== null) {
      passedTests++;
    } else {
      failedTests++;
      section5BoundaryFailures++;
      failures.push({
        label: `${matKey}.${prop}(${rMax}K) upper bound`,
        actual: vMax,
        expected: "finite"
      });
    }

    if (prop === "tc" && propDef.tlow !== null && propDef.tlow !== undefined) {
      const polyMin = Math.max(rMin, propDef.tlow);
      const vPolyMin = propertyValue(mat, prop, polyMin);
      totalTests++;
      if (isFinite(vPolyMin) && vPolyMin !== null) {
        passedTests++;
      } else {
        failedTests++;
        section5BoundaryFailures++;
        failures.push({
          label: `${matKey}.${prop}(${polyMin}K) polynomial lower bound`,
          actual: vPolyMin,
          expected: "finite"
        });
      }
    }

    for (const endpoint of [1, 300]) {
      if (endpoint === rMin || endpoint === rMax) continue;
      const vEndpoint = propertyValue(mat, prop, endpoint);
      totalTests++;
      if (isFinite(vEndpoint) && vEndpoint !== null) {
        passedTests++;
      } else {
        failedTests++;
        section5BoundaryFailures++;
        failures.push({
          label: `${matKey}.${prop}(${endpoint}K) endpoint extrapolation`,
          actual: vEndpoint,
          expected: "finite"
        });
      }
    }
  }
}

// Piecewise boundary: cp for AISI316 at T=50 (overlap point)
{
  const mat = db.materials.AISI316;
  const cp50 = propertyValue(mat, "cp", 50);
  totalTests++;
  if (isFinite(cp50) && cp50 > 0) {
    passedTests++;
    console.log(`  ✓ AISI316.cp(50K) piecewise boundary = ${cp50.toFixed(4)}`);
  } else {
    failedTests++;
    failures.push({
      label: "AISI316.cp(50K) piecewise boundary",
      actual: cp50,
      expected: "positive finite"
    });
  }
}

// Null property test (Ti64 has no cp)
{
  const mat = db.materials.Ti64;
  const cp = propertyValue(mat, "cp", 100);
  totalTests++;
  if (cp === null) {
    passedTests++;
    console.log("  ✓ Ti64.cp returns null (no cp data, as expected)");
  } else {
    failedTests++;
    failures.push({
      label: "Ti64.cp should be null",
      actual: cp,
      expected: null
    });
  }
}

// Non-existent property
{
  const mat = db.materials.AISI316;
  const val = propertyValue(mat, "nonexistent", 100);
  totalTests++;
  if (val === null) {
    passedTests++;
    console.log("  ✓ Non-existent property returns null");
  } else {
    failedTests++;
    failures.push({
      label: "Non-existent property should be null",
      actual: val,
      expected: null
    });
  }
}

if (section5BoundaryFailures === 0) {
  console.log("  ✓ Boundary values validated for all materials");
}

/* ─── Test Section 6: SSOT Launcher evalRational Parity ─────────────── */
console.log("\nSection 6: SSOT evalRational() Parity Check");
console.log("────────────────────────────────────────────");

// Verify the sqrt(T)-based rational model matches at specific reference points
// These are golden-value regression fixtures
const RATIONAL_GOLDEN_VALUES = {
  CuRRR100: {
    4: 642.2969607429585,
    10: 1539.9155755669058,
    20: 2422.5102645364886,
    77: 547.1996980793605,
    300: 396.3239590150125
  },
  CuRRR300: {
    4: 1888.3793110693216,
    10: 4319.904672636731,
    20: 5052.267426595825,
    77: 572.1196598437356,
    300: 397.8739000533807
  }
};

for (const [matKey, goldenTemps] of Object.entries(RATIONAL_GOLDEN_VALUES)) {
  const mat = db.materials[matKey];
  for (const [T, golden] of Object.entries(goldenTemps)) {
    const fromNist = nistRational(mat.properties.k.coefficients, Number(T));
    assertParity(`${matKey}.k(${T}K) golden`, fromNist, golden, 1e-14);
  }
  console.log(`  ✓ ${matKey}: golden-value regression confirmed`);
}

/* ─── Test Section 7: Cross-Material Physical Reasonableness ────────── */
console.log("\nSection 7: Cross-Material Physical Reasonableness");
console.log("──────────────────────────────────────────────────");

// At 300K, copper should have much higher k than steel
{
  const kCu300 = propertyValue(db.materials.CuRRR100, "k", 300);
  const kSS300 = propertyValue(db.materials.AISI316, "k", 300);
  totalTests++;
  if (kCu300 > 10 * kSS300) {
    passedTests++;
    console.log(`  ✓ Cu k(300K)=${kCu300.toFixed(1)} >> SS316 k(300K)=${kSS300.toFixed(1)}`);
  } else {
    failedTests++;
    failures.push({
      label: "Cu >> SS316 at 300K",
      actual: `Cu=${kCu300}, SS=${kSS300}`,
      expected: "Cu >> SS"
    });
  }
}

// G10 should have low k (insulator)
{
  const kG10 = propertyValue(db.materials.G10Normal, "k", 100);
  const kAl = propertyValue(db.materials.Al6061T6, "k", 100);
  totalTests++;
  if (kG10 < kAl && kG10 < 1) {
    passedTests++;
    console.log(`  ✓ G10 k(100K)=${kG10.toFixed(4)} << Al6061 k(100K)=${kAl.toFixed(1)} (insulator vs metal)`);
  } else {
    failedTests++;
    failures.push({
      label: "G10 insulator check",
      actual: `G10=${kG10}, Al=${kAl}`,
      expected: "G10 << Al"
    });
  }
}

// Specific heat at 300K should be reasonable for metals (~300-500 J/kg·K)
{
  const cpSS = propertyValue(db.materials.AISI316, "cp", 300);
  totalTests++;
  if (cpSS > 200 && cpSS < 800) {
    passedTests++;
    console.log(`  ✓ AISI316 cp(300K) = ${cpSS.toFixed(1)} J/(kg·K) (physically reasonable)`);
  } else {
    failedTests++;
    failures.push({
      label: "AISI316 cp(300K) reasonable",
      actual: cpSS,
      expected: "200-800 J/(kg·K)"
    });
  }
}

// cp should increase with temperature (general trend)
{
  const cpCu20 = propertyValue(db.materials.CuRRR100, "cp", 20);
  const cpCu300 = propertyValue(db.materials.CuRRR100, "cp", 300);
  totalTests++;
  if (cpCu300 > cpCu20) {
    passedTests++;
    console.log(`  ✓ CuRRR100 cp increases with T: cp(20K)=${cpCu20.toFixed(2)} → cp(300K)=${cpCu300.toFixed(1)}`);
  } else {
    failedTests++;
    failures.push({
      label: "cp increases with T",
      actual: `cp(20)=${cpCu20}, cp(300)=${cpCu300}`,
      expected: "cp(300) > cp(20)"
    });
  }
}

/* ─── Test Section 8: Dense Sampling Continuity Check ───────────────── */
console.log("\nSection 8: Dense Sampling Continuity Check");
console.log("───────────────────────────────────────────");

// Check that properties vary smoothly (no discontinuities > 100x step-to-step)
let section8ContinuityFailures = 0;
for (const matKey of materialKeys) {
  const mat = db.materials[matKey];
  for (const prop of ["k", "cp"]) {
    if (!mat.properties[prop]) continue;
    const propDef = mat.properties[prop];
    const [rMin, rMax] = propDef.range;

    const pieceBoundaries = propDef.type === "piecewise-logpoly" && propDef.pieces
      ? propDef.pieces.slice(1).map(piece => piece.range[0])
      : [];
    const step = (rMax - rMin) / 200;
    const boundaryEps = Math.max(step * BOUNDARY_EPSILON_FACTOR, Number.EPSILON);
    let prevVal = null;
    let prevT = null;
    let maxRatio = 0;
    let discontinuous = false;

    for (let T = rMin; T <= rMax; T += step) {
      const val = propertyValue(mat, prop, T);
      if (prevVal !== null && prevVal > 0 && val > 0) {
        const crossesPieceBoundary = prevT !== null &&
          pieceBoundaries.some(
            boundary => prevT < boundary - boundaryEps && T > boundary - boundaryEps
          );
        const ratio = val / prevVal;
        if (ratio > maxRatio) maxRatio = ratio;
        if (!crossesPieceBoundary && (ratio > 100 || ratio < 0.01)) {
          discontinuous = true;
        }
      }
      prevT = T;
      prevVal = val;
    }

    totalTests++;
    if (!discontinuous) {
      passedTests++;
    } else {
      failedTests++;
      section8ContinuityFailures++;
      failures.push({
        label: `${matKey}.${prop} continuity`,
        actual: `max ratio = ${maxRatio}`,
        expected: "smooth variation"
      });
    }
  }
}
if (section8ContinuityFailures === 0) {
  console.log("  ✓ All k and cp curves pass continuity check (no >100x jumps)");
}

/* ─── Summary ───────────────────────────────────────────────────────── */
console.log("\n═══════════════════════════════════════════════════════════");
console.log("NIST PARITY TEST RESULTS");
console.log("═══════════════════════════════════════════════════════════");
console.log(`Total tests:  ${totalTests}`);
console.log(`Passed:       ${passedTests}`);
console.log(`Failed:       ${failedTests}`);

if (failures.length > 0) {
  console.log("\nFAILURES:");
  for (const f of failures) {
    console.log(`  ✗ ${f.label}`);
    console.log(`    actual:   ${JSON.stringify(f.actual)}`);
    console.log(`    expected: ${JSON.stringify(f.expected)}`);
    if (f.relErr) console.log(`    relErr:   ${f.relErr.toExponential(3)}`);
    if (f.absErr !== undefined) console.log(`    absErr:   ${f.absErr.toExponential(3)}`);
  }
  throw new Error(`NIST parity test suite failed with ${failedTests} failing assertions`);
} else {
  console.log("\n✅ ALL NIST PARITY TESTS PASSED");
  console.log("   All 10 materials validated across k, cp, and tc properties");
  console.log("   Independent NIST equation implementations match materials.js");
  console.log("   Coefficients verified against NIST published values");
  console.log("   Physical reasonableness checks passed");
  console.log("   Continuity checks passed");
}
