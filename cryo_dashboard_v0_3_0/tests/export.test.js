import assert from "node:assert/strict";
import { buildModularCsvText, buildModularJsonData } from "../js/export.js";

function parseCsvMetrics(csvText) {
  const metrics = new Map();
  const lines = csvText.trimEnd().split("\n");

  for (const line of lines.slice(1)) {
    if (line === "") {
      break;
    }

    const separatorIndex = line.indexOf(",");
    const key = line.slice(0, separatorIndex);
    const value = line.slice(separatorIndex + 1);
    metrics.set(key, value);
  }

  return metrics;
}

function createKSingleState() {
  return {
    materialKey: "AISI316",
    material: { name: "AISI 316 Stainless Steel" },
    property: "k",
    Tmin: 20,
    Tmax: 300,
    nsteps: 100,
    method: "trapezoid",
    integral: 3012.07974446,
    methodResults: {
      trapezoid: 3012.07974446,
      simpson: 3012.14986534,
      romberg: 3012.14980568,
      gauss: 3012.14980570
    },
    methodDeltasPct: {
      trapezoid: -0.002326,
      simpson: 0.000002,
      romberg: 0,
      gauss: 0
    },
    T: [20, 300],
    values: [2.168622, 15.308653]
  };
}

function createCpCompareState() {
  return {
    materialKey: "AISI316",
    material: { name: "AISI 316 Stainless Steel" },
    property: "cp",
    Tmin: 20,
    Tmax: 300,
    nsteps: 100,
    method: "romberg",
    integral: 93190.18638013,
    methodResults: {
      trapezoid: 93189.94859216,
      simpson: 93190.23539069,
      romberg: 93190.18638013,
      gauss: 93190.28911191
    },
    methodDeltasPct: {
      trapezoid: -0.000255,
      simpson: 0.000053,
      romberg: 0,
      gauss: 0.000110
    },
    T: [20, 300],
    values: [13.607259, 490.213382]
  };
}

function createRateOfIntegralCompareState() {
  return {
    materialKey: "AISI316",
    material: { name: "AISI 316 Stainless Steel" },
    property: "rateChange",
    Tmin: 25,
    Tmax: 300,
    nsteps: 300,
    method: "simpson",
    integral: 40202.06900000,
    methodResults: {
      trapezoid: 40201.85230000,
      simpson: 40202.06900000,
      romberg: 40202.01340000,
      gauss: 40202.09110000
    },
    methodDeltasPct: {
      trapezoid: -0.000539,
      simpson: 0.000138,
      romberg: 0,
      gauss: 0.000193
    },
    T: [25, 300],
    values: [0.521220, 18.413440]
  };
}

console.log("Running export consistency tests...");

{
  const state = createKSingleState();
  const csvMetrics = parseCsvMetrics(buildModularCsvText(state, "single"));
  const jsonData = buildModularJsonData(state, "single");

  assert.equal(csvMetrics.get("delta_k"), jsonData.deltaSummary.delta_k);
  assert.equal(csvMetrics.get("integral_k"), jsonData.deltaSummary.integral_k);
  assert.equal(csvMetrics.get("Selected Integral (W/m)"), jsonData.selectedIntegral);
  assert.equal(jsonData.deltaSummary.integral_k, jsonData.selectedIntegral);
  assert.equal(jsonData.methodComparison.trapezoid.integral, jsonData.selectedIntegral);
}

{
  const state = createCpCompareState();
  const csvMetrics = parseCsvMetrics(buildModularCsvText(state, "compare"));
  const jsonData = buildModularJsonData(state, "compare");

  assert.equal(csvMetrics.get("delta_k"), jsonData.deltaSummary.delta_k);
  assert.equal(csvMetrics.get("integral_k"), jsonData.deltaSummary.integral_k);
  assert.equal(csvMetrics.get("Romberg Integral (J/kg)"), jsonData.methodComparison.romberg.integral);
  assert.equal(csvMetrics.get("Trapezoid Integral (J/kg)"), jsonData.methodComparison.trapezoid.integral);
  assert.equal(csvMetrics.get("Simpson fixed Integral (J/kg)"), jsonData.methodComparison.simpson.integral);
  assert.equal(csvMetrics.get("Gauss-Legendre 4-pt Integral (J/kg)"), jsonData.methodComparison.gauss.integral);
  assert.equal(csvMetrics.get("Trapezoid % vs Romberg"), jsonData.methodComparison.trapezoid.percentVsRomberg);
  assert.equal(csvMetrics.get("Simpson fixed % vs Romberg"), jsonData.methodComparison.simpson.percentVsRomberg);
  assert.equal(csvMetrics.get("Gauss-Legendre 4-pt % vs Romberg"), jsonData.methodComparison.gauss.percentVsRomberg);
  assert.equal(jsonData.deltaSummary.integral_k, jsonData.selectedIntegral);
  assert.equal(jsonData.methodComparison.romberg.integral, jsonData.selectedIntegral);
}

{
  const state = createRateOfIntegralCompareState();
  const csvMetrics = parseCsvMetrics(buildModularCsvText(state, "compare"));
  const jsonData = buildModularJsonData(state, "compare");

  assert.equal(csvMetrics.get("delta_Y"), jsonData.deltaSummary.delta_Y);
  assert.equal(csvMetrics.get("integral_Y"), jsonData.deltaSummary.integral_Y);
  assert.equal(csvMetrics.get("Romberg Integral (x1e-5*K)"), jsonData.methodComparison.romberg.integral);
  assert.equal(csvMetrics.get("Trapezoid Integral (x1e-5*K)"), jsonData.methodComparison.trapezoid.integral);
  assert.equal(csvMetrics.get("Simpson fixed Integral (x1e-5*K)"), jsonData.methodComparison.simpson.integral);
  assert.equal(csvMetrics.get("Gauss-Legendre 4-pt Integral (x1e-5*K)"), jsonData.methodComparison.gauss.integral);
  assert.equal(csvMetrics.get("Trapezoid % vs Romberg"), jsonData.methodComparison.trapezoid.percentVsRomberg);
  assert.equal(csvMetrics.get("Simpson fixed % vs Romberg"), jsonData.methodComparison.simpson.percentVsRomberg);
  assert.equal(csvMetrics.get("Gauss-Legendre 4-pt % vs Romberg"), jsonData.methodComparison.gauss.percentVsRomberg);
}

console.log("All export consistency tests passed.");
