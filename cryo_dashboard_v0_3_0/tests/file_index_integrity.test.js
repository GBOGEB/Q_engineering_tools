import assert from "node:assert/strict";
import fs from "node:fs";

function escapeRegexLiteral(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function parseYamlList(yamlText, key) {
  const escapedKey = escapeRegexLiteral(key);
  const pattern = new RegExp(`^${escapedKey}:\\n((?:  - .+\\n)+)`, "m");
  const match = yamlText.match(pattern);
  assert.ok(match, `Missing YAML list for key: ${key}`);
  return match[1]
    .trimEnd()
    .split("\n")
    .map(line => line.replace(/^  -\s*/, ""));
}

function parseYamlNestedScalar(yamlText, parentKey, childKey) {
  const escapedParentKey = escapeRegexLiteral(parentKey);
  const escapedChildKey = escapeRegexLiteral(childKey);
  const pattern = new RegExp(`^${escapedParentKey}:\\n(?:  .+\\n)*?  ${escapedChildKey}:\\s*(.+)$`, "m");
  const match = yamlText.match(pattern);
  assert.ok(match, `Missing YAML nested scalar: ${parentKey}.${childKey}`);
  return match[1].trim();
}

function collectFolderBuckets(paths) {
  const buckets = new Set();
  for (const relativePath of paths) {
    const slashIndex = relativePath.indexOf("/");
    if (slashIndex === -1) {
      buckets.add(".");
      continue;
    }
    buckets.add(relativePath.slice(0, slashIndex));
  }
  return buckets;
}

const yamlText = fs.readFileSync("./file_index.yaml", "utf8");
const jsonIndex = JSON.parse(fs.readFileSync("./file_index.json", "utf8"));

console.log("Running file index integrity checks...");

const yamlMinimumArtifacts = parseYamlList(yamlText, "minimum_artifacts");
const yamlRuntimeFiles = parseYamlList(yamlText, "runtime_files");
const yamlLegacyFallbackFile = parseYamlNestedScalar(yamlText, "legacy_fallback", "file");

assert.deepEqual(yamlMinimumArtifacts, jsonIndex.minimum_artifacts);
assert.deepEqual(yamlRuntimeFiles, jsonIndex.runtime_files);
assert.equal(yamlLegacyFallbackFile, jsonIndex.legacy_fallback.file);

const primaryRuntimeFile = jsonIndex.primary_runtime.file;
assert.notEqual(primaryRuntimeFile, yamlLegacyFallbackFile);
assert.ok(yamlMinimumArtifacts.includes(primaryRuntimeFile));
assert.ok(yamlRuntimeFiles.includes(primaryRuntimeFile));

const nonFallbackArtifacts = yamlMinimumArtifacts.filter(path => path !== yamlLegacyFallbackFile);
assert.ok(nonFallbackArtifacts.length > 0, "Fallback-only artifact set is not allowed");

const folderBuckets = collectFolderBuckets(yamlMinimumArtifacts);
assert.ok(folderBuckets.has("."), "Expected root-level artifacts");
assert.ok(folderBuckets.has("data"), "Expected data/ artifacts in consolidation");
assert.ok(folderBuckets.has("js"), "Expected js/ artifacts in consolidation");
assert.ok(folderBuckets.has("docs"), "Expected docs/ artifacts in consolidation");

console.log("File index integrity checks passed.");
