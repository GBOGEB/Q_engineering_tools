import assert from "node:assert/strict";
import fs from "node:fs";

const db = JSON.parse(fs.readFileSync("./data/materials.json", "utf8"));

function validateCoefficients(coefficients, label) {
  assert.ok(Array.isArray(coefficients), `${label}: coefficients not array`);
  assert.ok(coefficients.length > 0, `${label}: coefficients empty`);
  coefficients.forEach((value, index) => {
    assert.equal(typeof value, "number", `${label}: coefficient ${index} is not number`);
  });
}

function validatePropertyDefinition(materialKey, propertyKey, propertyDef) {
  const label = `${materialKey}.${propertyKey}`;

  assert.ok(
    ["polylog", "piecewise-logpoly", "rational", "thermal-contraction"].includes(propertyDef.type),
    `${label}: invalid type`
  );
  assert.equal(typeof propertyDef.units, "string", `${label}: units missing`);
  assert.ok(Array.isArray(propertyDef.range), `${label}: range missing`);
  assert.equal(propertyDef.range.length, 2, `${label}: range must have two bounds`);
  propertyDef.range.forEach((value, index) => {
    assert.equal(typeof value, "number", `${label}: range bound ${index} is not number`);
  });

  if (propertyDef.type === "piecewise-logpoly") {
    assert.ok(Array.isArray(propertyDef.pieces), `${label}: pieces missing`);
    assert.ok(propertyDef.pieces.length > 0, `${label}: pieces empty`);

    propertyDef.pieces.forEach((piece, pieceIndex) => {
      assert.ok(Array.isArray(piece.range), `${label}: piece ${pieceIndex} range missing`);
      assert.equal(piece.range.length, 2, `${label}: piece ${pieceIndex} range must have two bounds`);
      piece.range.forEach((value, rangeIndex) => {
        assert.equal(typeof value, "number", `${label}: piece ${pieceIndex} range bound ${rangeIndex} is not number`);
      });
      validateCoefficients(piece.coefficients, `${label}: piece ${pieceIndex}`);
    });

    return;
  }

  validateCoefficients(propertyDef.coefficients, label);

  if (propertyDef.type === "thermal-contraction") {
    assert.equal(propertyDef.coefficients.length, 5, `${label}: thermal-contraction coefficients must have 5 terms [a,b,c,d,e]`);
    if (propertyDef.tlow != null) {
      assert.equal(typeof propertyDef.tlow, "number", `${label}: tlow must be number or null`);
    }
    if (propertyDef.f != null) {
      assert.equal(typeof propertyDef.f, "number", `${label}: f must be number or null`);
    }
  }
}

console.log("Running material database validation...");

assert.equal(typeof db.version, "string");
assert.ok(db.materials);
assert.ok(Object.keys(db.materials).length > 0);

for (const [key, material] of Object.entries(db.materials)) {
  assert.equal(typeof material.name, "string", `${key}: name missing`);
  assert.equal(typeof material.source, "string", `${key}: source missing`);
  assert.ok(material.properties, `${key}: properties missing`);
  assert.ok(Object.keys(material.properties).length > 0, `${key}: properties empty`);

  for (const [propertyKey, propertyDef] of Object.entries(material.properties)) {
    validatePropertyDefinition(key, propertyKey, propertyDef);
  }
}

console.log("Material database validation passed.");
