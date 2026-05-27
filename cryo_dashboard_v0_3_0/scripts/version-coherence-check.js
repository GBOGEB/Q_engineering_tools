import fs from "node:fs";

const expected = "0.4.9";

const activeFiles = [
  "README.md",
  "VERSION",
  "package.json",
];

for (const file of activeFiles) {
  const text = fs.readFileSync(file, "utf8");

  if (!text.includes(expected)) {
    throw new Error(`Version coherence failure in ${file}. Expected active version ${expected}`);
  }
}

console.log(`Version coherence check passed for v${expected}.`);
