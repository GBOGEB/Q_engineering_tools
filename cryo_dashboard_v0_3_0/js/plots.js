import { normalize, linspace, cumulativeTrapezoid } from "./numerics.js";
import { propertyValue, hasProperty } from "./materials.js";

function verticalLineTrace(x, ymin, ymax, name) {
  return {
    x: [x, x],
    y: [ymin, ymax],
    mode: "lines",
    name,
    line: { dash: "dot" }
  };
}

function tangentLine(state) {
  const T0 = state.T[state.idx];
  const y0 = state.values[state.idx];
  const slope = state.dydT[state.idx];
  return state.T.map(t => y0 + slope * (t - T0));
}

export function updateEngineering(state) {
  const shadeX = state.T;
  const shadeY = state.values;
  const propLabel = state.property === "k" ? "k(T)" : "cp(T)";
  const derivLabel = state.property === "k" ? "dk/dT" : "dcp/dT";
  const integralLabel = state.property === "k" ? "∫k(T)dT" : "∫cp(T)dT";
  const derivUnits = state.property === "k" ? "W/(m·K²)" : "J/(kg·K²)";

  Plotly.react("engineeringPlot", [
    { x: state.T, y: state.values, mode: "lines", name: `${propLabel} [${state.units}]` },
    { x: state.T, y: state.dydT, mode: "lines", name: `${derivLabel} [${derivUnits}]`, yaxis: "y2" },
    { x: state.T, y: state.cumulativeIntegral, mode: "lines", name: `${integralLabel} [${state.integralUnits}]`, yaxis: "y3" },
    { x: shadeX, y: shadeY, fill: "tozeroy", mode: "none", name: "integral region", opacity: 0.2 },
    verticalLineTrace(state.T[state.idx], 0, Math.max(...state.values), "cursor T"),
    { x: [state.T[state.idx]], y: [state.values[state.idx]], mode: "markers", name: `selected ${propLabel}`, marker: { size: 12 } }
  ], {
    title: `${state.material.name}: Engineering Values`,
    xaxis: { title: "Temperature [K]" },
    yaxis: { title: `${propLabel} [${state.units}]` },
    yaxis2: { title: `${derivLabel} [${derivUnits}]`, overlaying: "y", side: "right" },
    yaxis3: { title: `${integralLabel} [${state.integralUnits}]`, overlaying: "y", side: "right", anchor: "free", position: 0.95 },
    hovermode: "x unified",
    margin: { r: 95 }
  });
}

export function updateEngineeringReadouts(state, documentRef) {
  const fraction = state.cumulativeIntegral[state.idx] / state.denseReference * 100;
  const propLabel = state.property === "k" ? "k(T)" : "cp(T)";
  const derivLabel = state.property === "k" ? "dk/dT" : "dcp/dT";
  const derivUnits = state.property === "k" ? "W/(m·K²)" : "J/(kg·K²)";

  documentRef.getElementById("engineeringReadout").textContent =
`Version: ${state.version}
Material: ${state.material.name}
Property: ${state.property}
T cursor = ${state.T[state.idx].toFixed(3)} K
${propLabel} = ${state.values[state.idx].toFixed(6)} ${state.units}
${derivLabel} = ${state.dydT[state.idx].toFixed(6)} ${derivUnits}
∫Tmin→Tcursor ${propLabel}dT = ${state.cumulativeIntegral[state.idx].toFixed(6)} ${state.integralUnits}
Fraction of selected-range integral = ${fraction.toFixed(3)} %`;

  if (state.property === "k") {
    const qCursor = (state.A / state.L) * state.cumulativeIntegral[state.idx];
    documentRef.getElementById("heatLoadReadout").textContent =
`Selected method: ${state.integrationMethod}
T range = ${state.Tmin} K → ${state.Tmax} K
A = ${state.A} m²
L = ${state.L} m

Integral used = ${state.selectedIntegral.toFixed(6)} W/m
Qdot = (A/L) × integral
Qdot = ${state.qdot.toFixed(9)} W

Cursor partial heat load:
Qdot(Tmin→Tcursor) = ${qCursor.toFixed(9)} W`;
  } else {
    documentRef.getElementById("heatLoadReadout").textContent =
`Selected method: ${state.integrationMethod}
T range = ${state.Tmin} K → ${state.Tmax} K
mass = ${state.mass} kg

Integral used = ${state.selectedIntegral.toFixed(6)} J/kg
Energy = mass × integral
Energy = ${state.energy.toFixed(6)} J

Cursor partial energy:
E(Tmin→Tcursor) = ${(state.mass * state.cumulativeIntegral[state.idx]).toFixed(6)} J`;
  }
}

export function updateSensitivity(state, documentRef) {
  const tangent = tangentLine(state);
  const ymin = Math.min(...state.values);
  const ymax = Math.max(...state.values);
  const propLabel = state.property === "k" ? "k(T)" : "cp(T)";
  const propName = state.property === "k" ? "Thermal Conductivity" : "Specific Heat";

  Plotly.react("sensitivityPlot", [
    { x: state.T, y: state.values, mode: "lines", name: propLabel },
    { x: state.T, y: tangent, mode: "lines", name: "local tangent", line: { dash: "dash" } },
    verticalLineTrace(state.T[state.idx], ymin, ymax, "cursor T"),
    { x: [state.T[state.idx]], y: [state.values[state.idx]], mode: "markers", name: "selected operating point", marker: { size: 12 } }
  ], {
    title: `${state.material.name}: Local Sensitivity / Tangent`,
    xaxis: { title: "Temperature [K]" },
    yaxis: { title: `${propName} [${state.units}]` },
    hovermode: "x unified"
  });

  const sensitivityClass =
    Math.abs(state.dydT[state.idx]) > 0.08 ? "high sensitivity" :
    Math.abs(state.dydT[state.idx]) > 0.04 ? "moderate sensitivity" :
    "lower sensitivity";

  const derivLabel = state.property === "k" ? "dk/dT" : "dcp/dT";
  const derivUnits = state.property === "k" ? "W/(m·K²)" : "J/(kg·K²)";

  documentRef.getElementById("sensitivityReadout").textContent =
`Selected T = ${state.T[state.idx].toFixed(3)} K
Local ${propLabel} = ${state.values[state.idx].toFixed(6)} ${state.units}
Local ${derivLabel} = ${state.dydT[state.idx].toFixed(6)} ${derivUnits}
Classification = ${sensitivityClass}

Meaning:
- ${derivLabel} is local material sensitivity
- tangent line is a local linear approximation
- useful for cooldown response and operating-point perturbations`;
}

export function updateComparison(state, materialDatabase) {
  let y1 = state.values;
  let y2 = state.dydT;
  let y3 = state.cumulativeIntegral;
  let yTitle = "Engineering value";
  const propLabel = state.property === "k" ? "k(T)" : "cp(T)";
  const derivLabel = state.property === "k" ? "dk/dT" : "dcp/dT";
  const integralLabel = state.property === "k" ? "∫k(T)dT" : "∫cp(T)dT";

  if (state.comparisonMode === "normalized") {
    y1 = normalize(state.values);
    y2 = normalize(state.dydT);
    y3 = normalize(state.cumulativeIntegral);
    yTitle = "Normalized value";
  }

  Plotly.react("comparisonPlot", [
    { x: state.T, y: y1, mode: "lines", name: propLabel },
    { x: state.T, y: y2, mode: "lines", name: derivLabel },
    { x: state.T, y: y3, mode: "lines", name: integralLabel },
    { x: [state.T[state.idx]], y: [y1[state.idx]], mode: "markers", name: "cursor", marker: { size: 12 } }
  ], {
    title: `${state.material.name}: ${state.comparisonMode} comparison`,
    xaxis: { title: "Temperature [K]" },
    yaxis: { title: yTitle },
    hovermode: "x unified"
  });

  const overlayTraces = [];
  const integralLabels = [];
  const integralValues = [];

  Object.keys(materialDatabase.materials).forEach(key => {
    const material = materialDatabase.materials[key];
    if (!hasProperty(material, state.property)) return;

    const T = linspace(state.Tmin, state.Tmax, 700);
    const values = T.map(t => propertyValue(material, state.property, t));
    const integral = cumulativeTrapezoid(values, T);

    overlayTraces.push({
      x: T,
      y: state.comparisonMode === "normalized" ? normalize(values) : values,
      mode: "lines",
      name: material.name
    });

    integralLabels.push(material.name);
    integralValues.push(integral[integral.length - 1]);
  });

  const overlayYTitle = state.comparisonMode === "normalized"
    ? `Normalized ${propLabel}`
    : `${propLabel} [${state.units}]`;

  Plotly.react("materialOverlayPlot", overlayTraces, {
    title: `${state.comparisonMode} multi-material ${propLabel}`,
    xaxis: { title: "Temperature [K]" },
    yaxis: { title: overlayYTitle },
    hovermode: "x unified"
  });

  Plotly.react("integralBarPlot", [{
    x: integralLabels,
    y: integralValues,
    type: "bar",
    name: integralLabel
  }], {
    title: `Integrated ${state.property === "k" ? "conductivity" : "specific heat"} over selected range`,
    xaxis: { title: "Material" },
    yaxis: { title: `${integralLabel} [${state.integralUnits}]` },
    margin: { b: 120 }
  });
}

export function updateMethods(state, documentRef) {
  Plotly.react("errorPlot", [{
    x: state.methodResults.map(r => r.method),
    y: state.methodResults.map(r => r.pctError),
    type: "bar",
    name: "Percent error"
  }], {
    title: "Integration Method Error vs Dense Reference",
    xaxis: { title: "Method" },
    yaxis: { title: "Error [%]" }
  });

  const rows = state.methodResults.map(r => `
    <tr>
      <td>${r.method}</td>
      <td>${r.value.toFixed(8)} ${state.integralUnits}</td>
      <td>${r.absError.toFixed(8)} ${state.integralUnits}</td>
      <td>${r.pctError.toFixed(6)} %</td>
    </tr>
  `).join("");

  documentRef.getElementById("methodTable").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Method</th>
          <th>Integral</th>
          <th>Absolute Error</th>
          <th>Percent Error</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="note">Dense Model is used as the local numerical reference for dashboard comparison.</p>
  `;
}

function timestampForFilename(now = new Date()) {
  const pad = value => String(value).padStart(2, "0");
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`;
}

export async function downloadMainPlotPng(documentRef = document) {
  const plotElement = documentRef.getElementById("mainPlot");
  if (!plotElement || !plotElement.data || plotElement.data.length === 0) {
    alert("Please calculate first");
    return;
  }

  const layout = plotElement.layout || {};
  const originalPaperBackground = layout.paper_bgcolor ?? "rgba(0,0,0,0)";
  const originalPlotBackground = layout.plot_bgcolor ?? "rgba(0,0,0,0)";

  await Plotly.relayout(plotElement, {
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#ffffff"
  });

  const width = Math.max(1, Math.round(plotElement.clientWidth || 0));
  const height = Math.max(1, Math.round(plotElement.clientHeight || 0));

  try {
    const imageDataUrl = await Plotly.toImage(plotElement, {
      format: "png",
      width,
      height,
      scale: 1
    });

    const link = documentRef.createElement("a");
    link.href = imageDataUrl;
    link.download = `cryo_plot_${timestampForFilename()}.png`;
    link.click();
  } finally {
    await Plotly.relayout(plotElement, {
      paper_bgcolor: originalPaperBackground,
      plot_bgcolor: originalPlotBackground
    });
  }
}
