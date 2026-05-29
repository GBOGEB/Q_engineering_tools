export function renderDebugPanel(documentRef, state, logger) {
  const target = documentRef.getElementById("debugReadout");
  if (!target) return;

  const latestLog = logger.entries.slice(0, 8);
  const resultLine = state.property === "k"
    ? `Qdot: ${state.qdot} W`
    : `Energy: ${state.energy} J`;

  target.textContent =
`Debug Panel
Version: ${state.version}
Material: ${state.materialKey}
Property: ${state.property}
Units: ${state.units}
Integral units: ${state.integralUnits}
T range: ${state.Tmin} K → ${state.Tmax} K
Cursor T: ${state.cursorT} K
Integration method: ${state.integrationMethod}
Data mode: ${state.dataMode}
Comparison mode: ${state.comparisonMode}
Array length: ${state.T.length}
Selected integral: ${state.selectedIntegral} ${state.integralUnits}
${resultLine}

Recent log entries:
${latestLog.map(e => `[${e.timestamp}] ${e.eventType}`).join("\n")}`;
}
