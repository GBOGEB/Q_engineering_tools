import fs from 'node:fs';
import {
  propertyValue,
  rangeStatus,
  getPropertyRange,
  getPropertyUnits,
  hasProperty
} from './recovered/materials.mjs';

const db = JSON.parse(fs.readFileSync(new URL('./recovered/materials.json', import.meta.url), 'utf8'));
const materials = db.materials;

function require(condition, message) {
  if (!condition) throw new Error(message);
}

function close(name, actual, expected, relTol = 1e-10, absTol = 1e-12) {
  const err = Math.abs(actual - expected);
  const lim = Math.max(absTol, relTol * Math.max(1, Math.abs(expected)));
  require(err <= lim, `${name}: ${actual} vs ${expected}; error=${err}; limit=${lim}`);
  return { name, actual, expected, abs_error: err, tolerance: lim };
}

require(db.version === 'v0.4.6', `unexpected db version ${db.version}`);
require(Object.keys(materials).length === 10, `expected 10 materials, got ${Object.keys(materials).length}`);
require(db.temperature_validity_K.min === 1 && db.temperature_validity_K.max === 300, 'global temperature envelope mismatch');

const A = materials.AISI316;
const Al = materials.Al6061T6;
const G10 = materials.G10Normal;
const Cu = materials.CuRRR100;
const Ti = materials.Ti64;

require(getPropertyUnits(A, 'k') === 'W/(m·K)', '316 k units mismatch');
require(getPropertyUnits(A, 'cp') === 'J/(kg·K)', '316 cp units mismatch');
require(JSON.stringify(getPropertyRange(A, 'cp')) === JSON.stringify([4, 300]), '316 cp range mismatch');
require(rangeStatus(A, 'cp', 4, 300) === 'PASS', '316 cp valid range should PASS');
require(rangeStatus(A, 'cp', 3, 300) === 'OUT OF RANGE', '316 cp lower extrapolation should be rejected');
require(rangeStatus(Ti, 'k', 20, 300) === 'PASS', 'Ti k valid range should PASS');
require(rangeStatus(Ti, 'k', 19, 300) === 'OUT OF RANGE', 'Ti k lower extrapolation should be rejected');
require(hasProperty(Ti, 'cp') === false, 'Ti cp should be absent');
require(propertyValue(Ti, 'cp', 77) === null, 'missing property should return null');

const cases = [
  close('AISI316_k_77K', propertyValue(A, 'k', 77), 7.920651602258382),
  close('AISI316_k_300K', propertyValue(A, 'k', 300), 15.308653824348552),
  close('AISI316_cp_20K_piece1', propertyValue(A, 'cp', 20), 13.607259317486317),
  close('AISI316_cp_100K_piece2', propertyValue(A, 'cp', 100), 273.0234812973212),
  close('AISI316_tc_10K_low_branch', propertyValue(A, 'tc', 10), -300.04),
  close('AISI316_tc_77K_polynomial', propertyValue(A, 'tc', 77), -279.890468279793),
  close('Al6061T6_k_20K', propertyValue(Al, 'k', 20), 28.4275476264488),
  close('Al6061T6_cp_20K', propertyValue(Al, 'cp', 20), 8.854270288592081),
  close('G10Normal_k_77K', propertyValue(G10, 'k', 77), 0.27996541317077966),
  close('CuRRR100_k_20K', propertyValue(Cu, 'k', 20), 2422.5102645364886, 1e-9),
  close('CuRRR100_cp_20K', propertyValue(Cu, 'cp', 20), 7.50607290450624),
  close('Ti64_k_77K', propertyValue(Ti, 'k', 77), 3.4705140840839115)
];

console.log(JSON.stringify({
  schema: 'qps-m02a-material-adapter-receipt/v1',
  status: 'PASS',
  source_repo: 'GBOGEB/document-organization-system',
  source_sha: 'cea7bfb533c246c797ef43652579fe00a39dcd4d',
  evaluator_blob_sha: '2fff568b3b5f73874581a5004553f1046f7c15a4',
  database_blob_sha: '65be104be14dc694efb519c98e8939ae7184afec',
  database_material_count: Object.keys(materials).length,
  reference_basis: 'independent calculations from authoritative NIST-published equations/coefficients',
  cases,
  range_guard_cases: ['316_cp_4_300_PASS', '316_cp_3_300_OUT', 'Ti_k_20_300_PASS', 'Ti_k_19_300_OUT'],
  engineering_acceptance: false
}, null, 2));
