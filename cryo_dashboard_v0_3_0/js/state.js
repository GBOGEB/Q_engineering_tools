import { propertyValue, hasProperty, getPropertyUnits } from "./materials.js";
import {
  linspace,
  clamp,
  gradient,
  cumulativeTrapezoid,
  trapezoidIntegral,
  simpsonIntegralUniform,
  adaptiveSimpson,
  rombergIntegration,
  gaussLegendre4,
  nearestIndex,
  deterministicNoise,
  movingAverage
} from "./numerics.js";

export const DASHBOARD_VERSION = "v0.4.0";

const computeCache = new Map();

export function validateInputs(documentRef) {
  let Tmin = Number(documentRef.getElementById("Tmin").value);
  let Tmax = Number(documentRef.getElementById("Tmax").value);
  let cursorT = Number(documentRef.getElementById("cursorT").value);
  let A = Number(documentRef.getElementById("areaInput").value);
  let L = Number(documentRef.getElementById("lengthInput").value);
  let mass = Number(documentRef.getElementById("massInput").value);

  const messages = [];

  Tmin = clamp(Tmin, 1, 300);
  Tmax = clamp(Tmax, 1, 300);

  if (Tmin >= Tmax) {
    messages.push("Tmin must be lower than Tmax. Auto-adjusted Tmax.");
    Tmax = Math.min(300, Tmin + 1);
  }

  cursorT = clamp(cursorT, Tmin, Tmax);

  if (A < 0) {
    A = 0;
    messages.push("Area cannot be negative. Auto-set to 0.");
  }

  if (L <= 0) {
    L = 1;
    messages.push("Length must be positive. Auto-set to 1 m.");
  }

  if (mass < 0) {
    mass = 0;
    messages.push("Mass cannot be negative. Auto-set to 0.");
  }

  documentRef.getElementById("Tmin").value = Tmin;
  documentRef.getElementById("Tmax").value = Tmax;
  documentRef.getElementById("cursorT").value = cursorT;
  documentRef.getElementById("areaInput").value = A;
  documentRef.getElementById("lengthInput").value = L;
  documentRef.getElementById("massInput").value = mass;

  return { Tmin, Tmax, cursorT, A, L, mass, messages };
}

export function computeMaterialState(documentRef, materialDatabase) {
  const materialKey = documentRef.getElementById("materialSelect").value;
  const material = materialDatabase.materials[materialKey];
  const property = documentRef.getElementById("propertySelect").value;
  const integrationMethod = documentRef.getElementById("integrationMethod").value;
  const dataMode = documentRef.getElementById("dataMode").value;
  const comparisonMode = documentRef.getElementById("comparisonMode").value;
  const { Tmin, Tmax, cursorT, A, L, mass, messages } = validateInputs(documentRef);

  if (!hasProperty(material, property)) {
    messages.push(`Material ${material.name} does not have ${property} data.`);
  }

  const cacheKey = JSON.stringify({ materialKey, property, integrationMethod, dataMode, comparisonMode, Tmin, Tmax, cursorT, A, L, mass });
  if (computeCache.has(cacheKey)) {
    return { ...computeCache.get(cacheKey), validationMessages: messages };
  }

  const T = linspace(Tmin, Tmax, 900);
  let values = T.map(t => propertyValue(material, property, t) || 0);

  if (dataMode === "noisy") {
    values = values.map((v, i) => Math.max(0, v * (1 + deterministicNoise(T[i]))));
  }

  if (dataMode === "smoothed") {
    const noisy = values.map((v, i) => Math.max(0, v * (1 + deterministicNoise(T[i]))));
    values = movingAverage(noisy, 17);
  }

  const dydT = gradient(values, T);
  const cumulativeIntegral = cumulativeTrapezoid(values, T);
  const idx = nearestIndex(T, cursorT);

  const denseReference = cumulativeIntegral[cumulativeIntegral.length - 1];
  const methodGrid = linspace(Tmin, Tmax, 101);
  const methodValues = methodGrid.map(t => propertyValue(material, property, t) || 0);

  const trap = trapezoidIntegral(methodGrid, methodValues);
  const simpson = simpsonIntegralUniform(methodGrid, methodValues);
  const adaptive = adaptiveSimpson(t => propertyValue(material, property, t) || 0, Tmin, Tmax, 1e-6, 20);
  const romberg = rombergIntegration(t => propertyValue(material, property, t) || 0, Tmin, Tmax, 8);
  const gauss = gaussLegendre4(t => propertyValue(material, property, t) || 0, Tmin, Tmax);
  const dense = denseReference;

  let selectedIntegral = dense;
  if (integrationMethod === "trapezoid") selectedIntegral = trap;
  if (integrationMethod === "simpson") selectedIntegral = simpson;
  if (integrationMethod === "adaptiveSimpson") selectedIntegral = adaptive;
  if (integrationMethod === "romberg") selectedIntegral = romberg;
  if (integrationMethod === "gauss") selectedIntegral = gauss;
  if (integrationMethod === "denseModel") selectedIntegral = dense;

  const qdot = property === "k" ? (A / L) * selectedIntegral : null;
  const energy = property === "cp" ? mass * selectedIntegral : null;
  const qdotDense = property === "k" ? (A / L) * dense : null;
  const energyDense = property === "cp" ? mass * dense : null;

  const units = getPropertyUnits(material, property);
  const integralUnits = property === "k" ? "W/m" : "J/kg";

  const state = {
    version: DASHBOARD_VERSION,
    timestamp: new Date().toISOString(),
    materialKey,
    material,
    property,
    integrationMethod,
    dataMode,
    comparisonMode,
    Tmin,
    Tmax,
    cursorT,
    A,
    L,
    mass,
    T,
    values,
    dydT,
    cumulativeIntegral,
    idx,
    denseReference,
    selectedIntegral,
    qdot,
    energy,
    qdotDense,
    energyDense,
    units,
    integralUnits,
    validationMessages: messages,
    methodResults: [
      { method: "Trapezoid", value: trap, absError: Math.abs(trap - dense), pctError: Math.abs(trap - dense) / Math.abs(dense) * 100 },
      { method: "Simpson", value: simpson, absError: Math.abs(simpson - dense), pctError: Math.abs(simpson - dense) / Math.abs(dense) * 100 },
      { method: "Adaptive Simpson", value: adaptive, absError: Math.abs(adaptive - dense), pctError: Math.abs(adaptive - dense) / Math.abs(dense) * 100 },
      { method: "Romberg", value: romberg, absError: Math.abs(romberg - dense), pctError: Math.abs(romberg - dense) / Math.abs(dense) * 100 },
      { method: "Gauss-Legendre", value: gauss, absError: Math.abs(gauss - dense), pctError: Math.abs(gauss - dense) / Math.abs(dense) * 100 },
      { method: "Dense Model", value: dense, absError: 0, pctError: 0 }
    ]
  };

  computeCache.set(cacheKey, state);
  return state;
}
