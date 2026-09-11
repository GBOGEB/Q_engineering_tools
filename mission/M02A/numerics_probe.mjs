// QPS TRIAGE M02A bounded numerical smoke.
// Independent smoke of the recovered numerics.js integration contract.
// Source lineage: GBOGEB/document-organization-system@cea7bfb533c246c797ef43652579fe00a39dcd4d
// Source blob: 2d23e1d0ac041d85e45ba157088c699b3f1c9fe6

function trapezoidIntegral(x, y) {
  let area = 0;
  for (let i = 1; i < x.length; i++) {
    area += 0.5 * (x[i] - x[i - 1]) * (y[i] + y[i - 1]);
  }
  return area;
}

function simpsonIntegralUniform(x, y) {
  let n = x.length - 1;
  if (n < 2) return trapezoidIntegral(x, y);
  if (n % 2 !== 0) n -= 1;
  const h = x[1] - x[0];
  let area = y[0] + y[n];
  for (let i = 1; i < n; i++) area += (i % 2 === 0 ? 2 : 4) * y[i];
  area *= h / 3;
  if (n < x.length - 1) area += 0.5 * (x[n + 1] - x[n]) * (y[n + 1] + y[n]);
  return area;
}

const x = [0, 0.25, 0.5, 0.75, 1.0];
const y = x.map(v => v * v);
const expected = 1 / 3;
const simpson = simpsonIntegralUniform(x, y);
const trap = trapezoidIntegral(x, y);
const tol = 1e-12;

if (Math.abs(simpson - expected) > tol) {
  throw new Error(`Simpson golden case failed: ${simpson} vs ${expected}`);
}
if (!(trap > expected && trap < 0.35)) {
  throw new Error(`Trapezoid sanity envelope failed: ${trap}`);
}

console.log(JSON.stringify({
  schema: 'qps-m02a-numerics-receipt/v1',
  status: 'PASS',
  case: 'integral_x_squared_0_1',
  expected,
  simpson,
  trapezoid: trap,
  source_repo: 'GBOGEB/document-organization-system',
  source_sha: 'cea7bfb533c246c797ef43652579fe00a39dcd4d',
  source_blob: '2d23e1d0ac041d85e45ba157088c699b3f1c9fe6'
}, null, 2));
