export async function loadMaterialDatabase() {
  const response = await fetch("data/materials.json?v=" + Date.now(), { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Could not load data/materials.json. Use a local server if opening from filesystem fails.");
  }
  return await response.json();
}

function logpoly(coeff, T) {
  const x = Math.log10(T);
  let s = 0;
  for (let i = 0; i < coeff.length; i++) {
    s += coeff[i] * Math.pow(x, i);
  }
  return Math.pow(10, s);
}

function rational(coeff, T) {
  const [a, b, c, d, e, f, g, h, i] = coeff;
  const r = Math.sqrt(T);
  const num = a + c * r + e * T + g * Math.pow(T, 1.5) + i * T * T;
  const den = 1 + b * r + d * T + f * Math.pow(T, 1.5) + h * T * T;
  return Math.pow(10, num / den);
}

function thermalContraction(coeff, T) {
  const [a, b, c, d, e] = coeff;
  return a + b * T + c * T * T + d * T * T * T + e * T * T * T * T;
}

function getCoefficients(propDef, T) {
  if (propDef.type === "piecewise-logpoly" && propDef.pieces) {
    for (const piece of propDef.pieces) {
      if (T >= piece.range[0] && T <= piece.range[1]) {
        return piece.coefficients;
      }
    }
    return T < propDef.pieces[0].range[0]
      ? propDef.pieces[0].coefficients
      : propDef.pieces[propDef.pieces.length - 1].coefficients;
  }
  return propDef.coefficients;
}

export function propertyValue(material, property, T) {
  if (!material.properties || !material.properties[property]) {
    return null;
  }

  const propDef = material.properties[property];
  const coeff = getCoefficients(propDef, T);

  if (propDef.type === "polylog" || propDef.type === "piecewise-logpoly") {
    return logpoly(coeff, T);
  }

  if (propDef.type === "rational") {
    return rational(coeff, T);
  }

  if (propDef.type === "thermal-contraction") {
    if (propDef.tlow != null && propDef.f != null && T < propDef.tlow) {
      return propDef.f;
    }
    return thermalContraction(coeff, T);
  }

  throw new Error(`Unknown property equation type: ${propDef.type}`);
}

export function kValue(material, T) {
  if (material.properties) {
    return propertyValue(material, "k", T);
  }

  const c = material.coefficients;

  if (material.type === "polylog") {
    return logpoly(c, T);
  }

  if (material.type === "copper" || material.type === "rational") {
    return rational(c, T);
  }

  throw new Error(`Unknown material model type: ${material.type}`);
}

export function cpValue(material, T) {
  return propertyValue(material, "cp", T);
}

export function hasProperty(material, property) {
  return material.properties && material.properties[property] !== undefined;
}

export function getPropertyUnits(material, property) {
  if (!material.properties || !material.properties[property]) {
    return "";
  }
  return material.properties[property].units || "";
}

export function getPropertyRange(material, property) {
  if (!material.properties || !material.properties[property]) {
    return [1, 300];
  }
  return material.properties[property].range || [1, 300];
}

export function rangeStatus(material, property, T1, T2) {
  const [lo, hi] = getPropertyRange(material, property);
  const tMin = Math.min(T1, T2);
  const tMax = Math.max(T1, T2);
  return (tMin >= lo && tMax <= hi) ? "PASS" : "OUT OF RANGE";
}

export function equationText(material, property) {
  if (!material.properties || !material.properties[property]) {
    return `${material.name}\nNo ${property} data available.`;
  }
  const propDef = material.properties[property];
  const eqLabel = {
    polylog: "log\u2081\u2080(y) = a + b\u00b7log\u2081\u2080(T) + c\u00b7(log\u2081\u2080T)\u00b2 + \u2026 + i\u00b7(log\u2081\u2080T)\u2078  \u2192  y = 10^(above)",
    rational: "log\u2081\u2080(k) = (a + c\u00b7T\u00bd + e\u00b7T + g\u00b7T\u00b3\u1d30\u00b2 + i\u00b7T\u00b2) / (1 + b\u00b7T\u00bd + d\u00b7T + f\u00b7T\u00b3\u1d30\u00b2 + h\u00b7T\u00b2)  \u2192  k = 10^(above)",
    "piecewise-logpoly": "Piecewise log\u2081\u2080-polynomial (region selected by T)",
    "thermal-contraction": "Y(T) = a + b\u00b7T + c\u00b7T\u00b2 + d\u00b7T\u00b3 + e\u00b7T\u2074; optional low-T branch: Y = f for T < Tlow"
  }[propDef.type] || `Type: ${propDef.type}`;

  let coeffLines;
  if (propDef.type === "piecewise-logpoly" && propDef.pieces) {
    coeffLines = propDef.pieces
      .map((p, i) => `  Region ${i + 1}: ${p.range[0]}\u2013${p.range[1]} K\n  [${p.coefficients.join(", ")}]`)
      .join("\n");
  } else if (propDef.type === "thermal-contraction") {
    const base = `  [${propDef.coefficients.join(", ")}]`;
    const branch = (propDef.tlow != null && propDef.f != null)
      ? `\n  Low-T branch: Y = ${propDef.f} for T < ${propDef.tlow} K`
      : "\n  Low-T branch: none";
    coeffLines = `${base}${branch}`;
  } else {
    coeffLines = `  [${propDef.coefficients.join(", ")}]`;
  }

  return [
    `Source: ${material.source}`,
    `Material: ${material.name}`,
    `Property: ${property === "k" ? "Thermal conductivity k" : property === "cp" ? "Specific heat cp" : "Thermal contraction Y(T) relative to 293 K"} [${propDef.units}]`,
    `Valid range: ${propDef.range[0]}\u2013${propDef.range[1]} K`,
    ``,
    `Equation form:`,
    `  ${eqLabel}`,
    ``,
    `Coefficients [a, b, c, d, e, f, g, h, i]:`,
    coeffLines
  ].join("\n");
}
