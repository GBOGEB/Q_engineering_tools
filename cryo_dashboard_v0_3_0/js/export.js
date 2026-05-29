export function currentCSV(state) {
  const propLabel = state.property === "k" ? "k" : "cp";
  const propUnits = state.property === "k" ? "W_per_mK" : "J_per_kgK";
  const derivUnits = state.property === "k" ? "W_per_mK2" : "J_per_kgK2";
  const integralUnits = state.property === "k" ? "W_per_m" : "J_per_kg";

  let csv = `T_K,${propLabel}_${propUnits},d${propLabel}dT_${derivUnits},cumulative_integral_${integralUnits}\n`;
  for (let i = 0; i < state.T.length; i++) {
    csv += `${state.T[i]},${state.values[i]},${state.dydT[i]},${state.cumulativeIntegral[i]}\n`;
  }
  return csv;
}

export function formatModularTemperature(value) {
  return value.toFixed(2);
}

export function formatModularPropertyValue(value) {
  return value.toFixed(6);
}

export function formatModularIntegralValue(value) {
  return value.toFixed(8);
}

export function formatModularPercent(value) {
  return Number.isFinite(value) ? value.toFixed(6) : "N/A";
}

export function getModularDeltaSummaryValues(state) {
  if (!state) {
    return { deltaK: 0, integralK: 0 };
  }

  const valueAtT1 = state.values[0] || 0;
  const valueAtT2 = state.values[state.values.length - 1] || 0;

  return {
    deltaK: valueAtT2 - valueAtT1,
    integralK: state.integral
  };
}

export function buildModularCsvText(state, mode) {
  const unit = state.property === "k" ? "W/m" : state.property === "cp" ? "J/kg" : "x1e-5*K";
  const propertySymbol = state.property === "k" ? "k" : state.property === "cp" ? "cp" : "Y";
  const deltaSummaryValues = getModularDeltaSummaryValues(state);
  const csvLines = [
    "Metric,Value",
    `Result Mode,${mode === "single" ? "Single Method" : "Compare All"}`,
    `Selected Method,${state.method}`,
    `delta_k,${formatModularPropertyValue(deltaSummaryValues.deltaK)}`,
    `integral_k,${formatModularIntegralValue(deltaSummaryValues.integralK)}`,
    `delta_${propertySymbol},${formatModularPropertyValue(deltaSummaryValues.deltaK)}`,
    `integral_${propertySymbol},${formatModularIntegralValue(deltaSummaryValues.integralK)}`
  ];

  if (mode === "single") {
    csvLines.push(`Selected Integral (${unit}),${formatModularIntegralValue(state.integral)}`);
  } else {
    csvLines.push(`Trapezoid Integral (${unit}),${formatModularIntegralValue(state.methodResults.trapezoid)}`);
    csvLines.push(`Simpson fixed Integral (${unit}),${formatModularIntegralValue(state.methodResults.simpson)}`);
    csvLines.push(`Romberg Integral (${unit}),${formatModularIntegralValue(state.methodResults.romberg)}`);
    csvLines.push(`Gauss-Legendre 4-pt Integral (${unit}),${formatModularIntegralValue(state.methodResults.gauss)}`);
    csvLines.push(`Trapezoid % vs Romberg,${formatModularPercent(state.methodDeltasPct.trapezoid)}`);
    csvLines.push(`Simpson fixed % vs Romberg,${formatModularPercent(state.methodDeltasPct.simpson)}`);
    csvLines.push(`Gauss-Legendre 4-pt % vs Romberg,${formatModularPercent(state.methodDeltasPct.gauss)}`);
  }

  csvLines.push("");
  csvLines.push("Temperature [K],Value");

  state.T.forEach((temperature, index) => {
    csvLines.push(`${formatModularTemperature(temperature)},${formatModularPropertyValue(state.values[index])}`);
  });

  return `${csvLines.join("\n")}\n`;
}

export function buildModularJsonData(state, mode) {
  const deltaSummaryValues = getModularDeltaSummaryValues(state);
  const propertySymbol = state.property === "k" ? "k" : state.property === "cp" ? "cp" : "Y";

  return {
    material: state.materialKey,
    materialName: state.material.name,
    property: state.property,
    resultMode: mode,
    temperatureRange: {
      min: formatModularTemperature(state.Tmin),
      max: formatModularTemperature(state.Tmax)
    },
    nsteps: state.nsteps,
    integrationMethod: state.method,
    deltaSummary: {
      delta_k: formatModularPropertyValue(deltaSummaryValues.deltaK),
      integral_k: formatModularIntegralValue(deltaSummaryValues.integralK),
      [`delta_${propertySymbol}`]: formatModularPropertyValue(deltaSummaryValues.deltaK),
      [`integral_${propertySymbol}`]: formatModularIntegralValue(deltaSummaryValues.integralK)
    },
    selectedIntegral: formatModularIntegralValue(state.integral),
    methodComparison: {
      trapezoid: {
        integral: formatModularIntegralValue(state.methodResults.trapezoid),
        percentVsRomberg: formatModularPercent(state.methodDeltasPct.trapezoid)
      },
      simpson: {
        integral: formatModularIntegralValue(state.methodResults.simpson),
        percentVsRomberg: formatModularPercent(state.methodDeltasPct.simpson)
      },
      romberg: {
        integral: formatModularIntegralValue(state.methodResults.romberg),
        percentVsRomberg: formatModularPercent(state.methodDeltasPct.romberg)
      },
      gauss: {
        integral: formatModularIntegralValue(state.methodResults.gauss),
        percentVsRomberg: formatModularPercent(state.methodDeltasPct.gauss)
      }
    },
    data: state.T.map((temperature, index) => ({
      T: formatModularTemperature(temperature),
      value: formatModularPropertyValue(state.values[index])
    }))
  };
}

export function downloadText(filename, text, mime) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");

  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  URL.revokeObjectURL(url);
}

export function exportCsv(state) {
  downloadText(`cryo_dashboard_${state.version}_${state.property}.csv`, currentCSV(state), "text/csv");
}

export function exportJson(state) {
  const payload = {
    version: state.version,
    timestamp: new Date().toISOString(),
    materialKey: state.materialKey,
    material: state.material,
    property: state.property,
    units: state.units,
    integralUnits: state.integralUnits,
    Tmin: state.Tmin,
    Tmax: state.Tmax,
    cursorT: state.cursorT,
    A: state.A,
    L: state.L,
    mass: state.mass,
    integrationMethod: state.integrationMethod,
    dataMode: state.dataMode,
    comparisonMode: state.comparisonMode,
    selectedIntegral: state.selectedIntegral,
    qdot: state.qdot,
    energy: state.energy,
    methodResults: state.methodResults,
    arrays: {
      T: state.T,
      values: state.values,
      dydT: state.dydT,
      cumulativeIntegral: state.cumulativeIntegral
    }
  };

  downloadText(`cryo_dashboard_${state.version}_${state.property}.json`, JSON.stringify(payload, null, 2), "application/json");
}

export function exportActivePlotPng(state, activeTab) {
  let plotId = "engineeringPlot";
  if (activeTab === "sensitivity") plotId = "sensitivityPlot";
  if (activeTab === "comparison") plotId = "comparisonPlot";
  if (activeTab === "methods") plotId = "errorPlot";

  Plotly.downloadImage(plotId, {
    format: "png",
    filename: `cryo_dashboard_${state.version}_${activeTab}`
  });
}
