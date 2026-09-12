#!/usr/bin/env node
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import crypto from "node:crypto";

const publicBase = (process.env.PUBLIC_BASE_URL || "").replace(/\/$/, "");
const localRoot = process.env.LOCAL_SITE_ROOT || "";
const expectedTarget = process.env.EXPECTED_TARGET_SHA || "";
const receiptPath = process.env.RECEIPT_PATH || "qps-public-calculation-receipt.json";
const toolRel = "cryo_dashboard_v0_3_0";

if (!publicBase && !localRoot) {
  throw new Error("Set PUBLIC_BASE_URL or LOCAL_SITE_ROOT");
}

async function fetchWithRetry(url, attempts = 12) {
  let last;
  for (let i = 0; i < attempts; i++) {
    try {
      const r = await fetch(url, { cache: "no-store" });
      if (r.ok) return Buffer.from(await r.arrayBuffer());
      last = new Error(`${url} -> HTTP ${r.status}`);
    } catch (e) {
      last = e;
    }
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
  throw last;
}

async function readAsset(rel) {
  if (publicBase) {
    return fetchWithRetry(`${publicBase}/${toolRel}/${rel}`);
  }
  return fs.readFile(path.join(localRoot, toolRel, rel));
}

const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "qps-pages-calc-"));
await fs.mkdir(path.join(tmp, "js"), { recursive: true });
await fs.writeFile(path.join(tmp, "package.json"), '{"type":"module"}\n');

const [traceBytes, manifestBytes, materialsBytes, materialsJsBytes, numericsJsBytes] = await Promise.all([
  readAsset("qps_trace.json"),
  readAsset("../artifact_manifest.json"),
  readAsset("data/materials.json"),
  readAsset("js/materials.js"),
  readAsset("js/numerics.js"),
]);

await fs.writeFile(path.join(tmp, "js", "materials.js"), materialsJsBytes);
await fs.writeFile(path.join(tmp, "js", "numerics.js"), numericsJsBytes);

const trace = JSON.parse(traceBytes.toString("utf8"));
const manifest = JSON.parse(manifestBytes.toString("utf8"));
const db = JSON.parse(materialsBytes.toString("utf8"));
if (expectedTarget && trace.target_sha !== expectedTarget) {
  throw new Error(`target SHA mismatch: ${trace.target_sha} != ${expectedTarget}`);
}
if (trace.source_sha !== "cea7bfb533c246c797ef43652579fe00a39dcd4d") {
  throw new Error(`unexpected source SHA ${trace.source_sha}`);
}

const materialsModule = await import(pathToFileURL(path.join(tmp, "js", "materials.js")));
const numericsModule = await import(pathToFileURL(path.join(tmp, "js", "numerics.js")));
const { propertyValue, rangeStatus } = materialsModule;
const { linspace, trapezoidIntegral, rombergIntegration } = numericsModule;

const materialKey = "CuRRR100";
const material = db.materials[materialKey];
const property = "k";
const Tmin = 4;
const Tmax = 20;
const areaM2 = 1e-4;
const lengthM = 1.0;

if (rangeStatus(material, property, Tmin, Tmax) !== "PASS") {
  throw new Error("public calculation inputs are outside source validity range");
}

const f = T => propertyValue(material, property, T);
const romberg = rombergIntegration(f, Tmin, Tmax, 6);
const grid = linspace(Tmin, Tmax, 2001);
const values = grid.map(f);
const trapezoid = trapezoidIntegral(grid, values);
const relDelta = Math.abs(romberg - trapezoid) / Math.abs(romberg);
const qdotW = (areaM2 / lengthM) * romberg;

if (![romberg, trapezoid, relDelta, qdotW].every(Number.isFinite)) {
  throw new Error("non-finite engineering calculation result");
}
if (romberg <= 0 || qdotW <= 0) {
  throw new Error("non-positive engineering calculation result");
}
if (relDelta > 0.005) {
  throw new Error(`cross-method delta too large: ${relDelta}`);
}

const manifestDigest = crypto.createHash("sha256").update(manifestBytes).digest("hex");
const receipt = {
  schema: "qps-pages-public-calculation-receipt/v1",
  mission_id: "M02A",
  execution_surface: publicBase ? "PUBLIC_GITHUB_PAGES" : "LOCAL_BUILT_ARTIFACT",
  public_base_url: publicBase || null,
  target_sha: trace.target_sha,
  source_sha: trace.source_sha,
  artifact_manifest_sha256: manifestDigest,
  trace,
  calculation: {
    material: materialKey,
    material_name: material.name,
    property,
    Tmin_K: Tmin,
    Tmax_K: Tmax,
    geometry: { area_m2: areaM2, length_m: lengthM },
    method_primary: "Romberg level 6",
    method_crosscheck: "Composite trapezoid 2000 intervals",
    integral_W_per_m: romberg,
    crosscheck_integral_W_per_m: trapezoid,
    relative_method_delta: relDelta,
    qdot_W: qdotW,
    validity_range_status: "PASS"
  },
  outcome: "SUCCESS",
  authority_transfer: false,
  engineering_acceptance: false
};

await fs.writeFile(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
console.log(JSON.stringify(receipt));
