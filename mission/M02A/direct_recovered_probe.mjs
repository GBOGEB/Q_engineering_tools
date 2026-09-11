import {
  adaptiveSimpson,
  gaussLegendre4,
  rombergIntegration,
  simpsonIntegralUniform,
  trapezoidIntegral
} from './recovered/numerics.mjs';

const close = (name, actual, expected, tol) => {
  const error = Math.abs(actual - expected);
  if (error > tol) throw new Error(`${name} failed: ${actual} vs ${expected}; error=${error}`);
  return { name, actual, expected, abs_error: error, tolerance: tol };
};

const x = [0, 0.25, 0.5, 0.75, 1.0];
const y = x.map(v => v * v);
const cases = [];
cases.push(close('simpson_x2_0_1', simpsonIntegralUniform(x, y), 1 / 3, 1e-12));
const trap = trapezoidIntegral(x, y);
if (!(trap > 1 / 3 && trap < 0.35)) throw new Error(`trapezoid envelope failed: ${trap}`);
cases.push({ name: 'trapezoid_x2_0_1', actual: trap, expected_relation: '1/3 < result < 0.35' });
cases.push(close('adaptive_sin_0_pi', adaptiveSimpson(Math.sin, 0, Math.PI, 1e-10), 2, 1e-9));
cases.push(close('romberg_exp_0_1', rombergIntegration(Math.exp, 0, 1, 7), Math.E - 1, 1e-10));
cases.push(close('gauss_legendre_x3_0_1', gaussLegendre4(v => v ** 3, 0, 1, 1), 0.25, 1e-14));

console.log(JSON.stringify({
  schema: 'qps-m02a-direct-recovered-receipt/v1',
  status: 'PASS',
  recovered_blob_sha: '2d23e1d0ac041d85e45ba157088c699b3f1c9fe6',
  recovered_source_repo: 'GBOGEB/document-organization-system',
  recovered_source_sha: 'cea7bfb533c246c797ef43652579fe00a39dcd4d',
  execution_mode: 'DIRECT_IMPORT_OF_BYTE_IDENTICAL_RECOVERED_GIT_BLOB',
  cases
}, null, 2));
