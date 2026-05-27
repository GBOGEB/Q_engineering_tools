import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  linspace,
  gradient,
  trapezoidIntegral,
  simpsonIntegralUniform,
  adaptiveSimpson,
  normalize,
  nearestIndex,
  gaussLegendre4,
  rombergIntegration
} from "../js/numerics.js";
import { propertyValue } from "../js/materials.js";

function approx(actual, expected, tolerance = 1e-8) {
  assert.ok(
    Math.abs(actual - expected) <= tolerance,
    `Expected ${actual} \u2248 ${expected} within ${tolerance}`
  );
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const materialDatabase = JSON.parse(
  readFileSync(path.join(__dirname, "..", "data", "materials.json"), "utf8")
);

function computeMethodResults(materialKey, property, Tmin, Tmax, nsteps) {
  const material = materialDatabase.materials[materialKey];
  const temperatures = linspace(Tmin, Tmax, nsteps);
  const evaluator = temperature => propertyValue(material, property, temperature) || 0;
  const values = temperatures.map(evaluator);

  return {
    trapezoid: trapezoidIntegral(temperatures, values),
    simpson: simpsonIntegralUniform(temperatures, values),
    romberg: rombergIntegration(evaluator, Tmin, Tmax, 8),
    gauss: gaussLegendre4(evaluator, Tmin, Tmax, nsteps - 1)
  };
}

function assertMethodFixture(name, actual, expected, tolerance = 1e-8) {
  for (const [method, expectedValue] of Object.entries(expected)) {
    approx(actual[method], expectedValue, tolerance);
  }
  console.log(`Verified regression fixture: ${name}`);
}

function assertLowTPeakShape(materialKey, Tmin = 4, Tmax = 20) {
  const material = materialDatabase.materials[materialKey];
  const temperatures = [];
  const values = [];

  for (let T = Tmin; T <= Tmax; T += 1) {
    temperatures.push(T);
    values.push(propertyValue(material, "k", T));
  }

  const peakValue = Math.max(...values);
  const peakIndex = values.indexOf(peakValue);
  const hasAnyIncreaseBeforePeak = values
    .slice(1, peakIndex + 1)
    .some((value, index) => value > values[index]);
  const hasAnyDecreaseAfterPeak = values
    .slice(peakIndex + 1)
    .some((value, index) => value < values[peakIndex + index]);

  assert.ok(peakIndex > 0 && peakIndex < values.length - 1, `${materialKey}: low-T peak must be interior to ${Tmin}-${Tmax} K`);
  assert.ok(values[0] < peakValue, `${materialKey}: k(${temperatures[0]}K) must be below low-T peak`);
  assert.ok(values[values.length - 1] < peakValue, `${materialKey}: k(${temperatures[temperatures.length - 1]}K) must be below low-T peak`);
  assert.ok(hasAnyIncreaseBeforePeak, `${materialKey}: low-T segment should include a rising interval toward peak`);
  assert.ok(hasAnyDecreaseAfterPeak, `${materialKey}: low-T segment should include a falling interval after peak`);
  console.log(`Verified low-T copper peak shape: ${materialKey} (peak at ${temperatures[peakIndex]} K)`);
}

console.log("Running numerics tests...");

const xs = linspace(0, 4, 5);
assert.deepEqual(xs, [0, 1, 2, 3, 4]);

const yLinear = xs.map(x => 2 * x + 1);
approx(trapezoidIntegral(xs, yLinear), 20, 1e-12);

const yQuad = xs.map(x => x * x);
approx(simpsonIntegralUniform(xs, yQuad), 64 / 3, 1e-12);

approx(gaussLegendre4(x => x * x, 0, 4), 64 / 3, 1e-12);
approx(gaussLegendre4(x => x * x, 0, 4, 4), 64 / 3, 1e-12);

approx(adaptiveSimpson(x => x * x, 0, 4, 1e-10, 20), 64 / 3, 1e-8);

const g = gradient(yLinear, xs);
g.forEach(value => approx(value, 2, 1e-12));

assert.deepEqual(normalize([0, 2, 4]), [0, 0.5, 1]);
assert.equal(nearestIndex([0, 10, 20], 12), 1);

assertMethodFixture(
  "AISI316 k 20-300K 100 steps",
  computeMethodResults("AISI316", "k", 20, 300, 100),
  {
    trapezoid: 3012.07974446,
    simpson: 3012.14986534,
    romberg: 3012.14980568,
    gauss: 3012.14980570
  }
);

assertMethodFixture(
  "AISI316 cp 20-300K 100 steps",
  computeMethodResults("AISI316", "cp", 20, 300, 100),
  {
    trapezoid: 93189.94859257,
    simpson: 93190.23539085,
    romberg: 93190.18638001,
    gauss: 93190.28911180
  }
);

assertMethodFixture(
  "CuRRR100 k 4-300K 100 steps",
  computeMethodResults("CuRRR100", "k", 4, 300, 100),
  {
    trapezoid: 194228.84485906,
    simpson: 194331.91282443,
    romberg: 194330.56784481,
    gauss: 194330.63341523
  }
);

assertMethodFixture(
  "CuRRR300 k 4-20K 100 steps",
  computeMethodResults("CuRRR300", "k", 4, 20, 100),
  {
    trapezoid: 69640.38803246,
    simpson: 69641.67425544,
    romberg: 69641.68347849,
    gauss: 69641.68347849
  }
);

assertMethodFixture(
  "CuRRR500 k 4-20K 100 steps",
  computeMethodResults("CuRRR500", "k", 4, 20, 100),
  {
    trapezoid: 104092.38213004,
    simpson: 104094.52201929,
    romberg: 104094.52823822,
    gauss: 104094.52823821
  }
);

assertLowTPeakShape("CuRRR300");
assertLowTPeakShape("CuRRR500");

console.log("All numerics tests passed.");
