import assert from "node:assert/strict";
import fs from "node:fs";

const requiredFiles = [
  "index.html",
  "files.html",
  "dashboard_modular.html",
  "ssot_launcher.html",
  "index_slides.html",
  "data/materials.json",
  "js/app_modular.js",
  "js/materials.js",
  "VERSION",
];

for (const file of requiredFiles) {
  assert.ok(fs.existsSync(file), `Missing required static entrypoint/artifact: ${file}`);
}

const indexHtml = fs.readFileSync("index.html", "utf8");
const filesHtml = fs.readFileSync("files.html", "utf8");
const dashboardHtml = fs.readFileSync("dashboard_modular.html", "utf8");

assert.match(indexHtml, /dashboard_modular\.html/, "index.html should link to modular dashboard");
assert.match(indexHtml, /files\.html/, "index.html should link to file navigator");
assert.match(filesHtml, /dashboard_modular\.html/, "files.html should link to modular dashboard");
assert.match(dashboardHtml, /type=["']module["']/, "dashboard_modular.html should load ES module entrypoint");
assert.match(dashboardHtml, /js\/app_modular\.js/, "dashboard_modular.html should load js/app_modular.js");

console.log("Static entrypoint validation passed.");
