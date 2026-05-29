import { loadMaterialDatabase } from "./materials.js";
import { computeMaterialState, DASHBOARD_VERSION } from "./state.js";
import {
  updateEngineering,
  updateEngineeringReadouts,
  updateSensitivity,
  updateComparison,
  updateMethods
} from "./plots.js";
import { exportCsv, exportJson, exportActivePlotPng } from "./export.js";
import { CalculationLogger } from "./logger.js";
import { renderDebugPanel } from "./debug.js";

const changeNotes = [
  ["01", "Architecture", "Physically split dashboard into index.html, style.css, js modules, data JSON, and docs."],
  ["02", "Heat Load", "Preserved A, L, Tmin, Tmax and Qdot = (A/L) * integral(k(T)dT)."],
  ["03", "Temperature Range", "Preserved user-selectable Tmin and Tmax."],
  ["04", "Adaptive Simpson", "Preserved adaptive Simpson method for continuous material models."],
  ["05", "Noise Handling", "Preserved clean, noisy, and smoothed data modes."],
  ["06", "Units", "Preserved explicit units in axes and readouts."],
  ["07", "Error Estimation", "Preserved method comparison against dense reference."],
  ["08", "Comparison Mode", "Preserved normalized vs absolute comparison modes."],
  ["09", "Cursor Snapshot", "Preserved k(T), dk/dT, cumulative integral fraction, and partial Qdot at cursor."],
  ["10", "Performance", "Preserved compute cache and switched plots to Plotly.react for stable updates."],
  ["11", "Visuals", "Preserved vertical cursor line, selected point, shaded integral region, and tangent plot."],
  ["12", "Export", "Preserved CSV, JSON, and PNG export."],
  ["13", "Traceability", "Preserved traceability tab and moved material data into auditable JSON."],
  ["14", "Advanced Hooks", "Added modular file structure for future multi-stage integration and optimization modules."]
];

let materialDatabase = null;
let latestState = null;
const logger = new CalculationLogger();
let activeTab = localStorage.getItem("activeCryoTab") || "engineering";

function populateMaterialSelect() {
  const select = document.getElementById("materialSelect");
  select.innerHTML = "";

  Object.entries(materialDatabase.materials).forEach(([key, material]) => {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = material.name;
    select.appendChild(opt);
  });
}

function setValidationMessage(state) {
  const el = document.getElementById("validationMessage");
  if (state.validationMessages.length) {
    el.innerHTML = `<span class="warning">${state.validationMessages.join(" ")}</span>`;
  } else {
    el.innerHTML = `<span class="ok">Inputs valid. Dashboard is idempotent for identical inputs.</span>`;
  }
}

function updateTrace(state) {
  const propInfo = state.property === "k"
    ? `Thermal Conductivity (k)\nUnits: ${state.units}\nIntegral units: ${state.integralUnits}\nQdot: ${state.qdot !== null ? state.qdot.toFixed(12) : 'N/A'} W`
    : `Specific Heat (cp)\nUnits: ${state.units}\nIntegral units: ${state.integralUnits}\nEnergy: ${state.energy !== null ? state.energy.toFixed(12) : 'N/A'} J`;

  document.getElementById("traceReadout").textContent =
`Dashboard version: ${state.version}
Timestamp: ${state.timestamp}
Material key: ${state.materialKey}
Material name: ${state.material.name}
Source: ${state.material.source}
Property: ${state.property}

${propInfo}

Temperature range: ${state.Tmin} K → ${state.Tmax} K
Cursor temperature: ${state.cursorT} K
Integration method: ${state.integrationMethod}
Data mode: ${state.dataMode}
Comparison mode: ${state.comparisonMode}

Geometry:
Area A: ${state.A} m²
Length L: ${state.L} m
Mass m: ${state.mass} kg

Selected integral: ${state.selectedIntegral.toFixed(8)} ${state.integralUnits}

Idempotency note:
Same inputs recreate same state, plots, and exports.`;

  const rows = changeNotes.map(r => `
    <tr>
      <td>${r[0]}</td>
      <td>${r[1]}</td>
      <td>${r[2]}</td>
    </tr>
  `).join("");

  document.getElementById("changeNotes").innerHTML = `
    <table>
      <thead><tr><th>Item</th><th>Change Area</th><th>Implemented Change</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function updateDashboard() {
  latestState = computeMaterialState(document, materialDatabase);
  logger.add("updateDashboard", {
    material: latestState.materialKey,
    Tmin: latestState.Tmin,
    Tmax: latestState.Tmax,
    method: latestState.integrationMethod,
    qdot: latestState.qdot
  });

  setValidationMessage(latestState);
  updateEngineering(latestState);
  updateEngineeringReadouts(latestState, document);
  updateSensitivity(latestState, document);
  updateComparison(latestState, materialDatabase);
  updateMethods(latestState, document);
  updateTrace(latestState);
  renderDebugPanel(document, latestState, logger);
}

function showTab(tabId) {
  activeTab = tabId;
  localStorage.setItem("activeCryoTab", tabId);

  document.querySelectorAll(".tab-page").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".tab-button").forEach(el => el.classList.remove("active"));

  document.getElementById(tabId).classList.add("active");
  document.getElementById("btn-" + tabId).classList.add("active");

  setTimeout(updateDashboard, 50);
}

function wireEvents() {
  document.querySelectorAll(".tab-button").forEach(button => {
    button.addEventListener("click", () => showTab(button.dataset.tab));
  });

  [
    "materialSelect",
    "propertySelect",
    "Tmin",
    "Tmax",
    "cursorT",
    "areaInput",
    "lengthInput",
    "massInput",
    "integrationMethod",
    "dataMode",
    "comparisonMode"
  ].forEach(id => {
    document.getElementById(id).addEventListener("input", updateDashboard);
    document.getElementById(id).addEventListener("change", updateDashboard);
  });

  document.getElementById("updateButton").addEventListener("click", updateDashboard);
  document.getElementById("exportCsvButton").addEventListener("click", () => exportCsv(latestState));
  document.getElementById("exportJsonButton").addEventListener("click", () => exportJson(latestState));
  document.getElementById("exportPngButton").addEventListener("click", () => exportActivePlotPng(latestState, activeTab));
}

async function init() {
  try {
    materialDatabase = await loadMaterialDatabase();
    populateMaterialSelect();
    wireEvents();
    showTab(activeTab);
    updateDashboard();
  } catch (error) {
    document.body.insertAdjacentHTML(
      "afterbegin",
      `<div class="panel warning"><strong>Startup error:</strong> ${error.message}<br>
      Tip: because v0.4.0 uses JS modules and fetch(), open it through a local server, e.g.
      <code>python -m http.server</code> from the dashboard folder.</div>`
    );
  }
}

console.log(`Cryogenic Material Dashboard ${DASHBOARD_VERSION}`);
logger.add("startup", { version: DASHBOARD_VERSION });
init();
