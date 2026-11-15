// Parity test: the JS mock engine must match the real Python module.
// Run with:  npm test   (uses Node's built-in test runner)
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { analysePayload, bandFor, kbNotice, forbiddenPhrases } from "./engine.js";

const golden = JSON.parse(
  readFileSync(new URL("./golden.json", import.meta.url), "utf8")
);

for (const { name, payload, expected } of golden) {
  test(`matches Python output: ${name}`, () => {
    assert.deepEqual(analysePayload(payload), expected);
  });
}

test("band boundaries", () => {
  const cases = { 0: "Low", 24: "Low", 25: "Moderate", 49: "Moderate",
                  50: "High", 74: "High", 75: "Critical", 100: "Critical" };
  for (const [score, band] of Object.entries(cases)) {
    assert.equal(bandFor(Number(score)), band);
  }
});

test("breakdown always sums to raw_total (QA-EXP-02)", () => {
  for (const { expected } of golden) {
    for (const w of expected.warnings) {
      const sum = w.factors.reduce((s, f) => s + f.points, 0);
      assert.equal(sum, w.raw_total);
      assert.equal(w.score, Math.min(w.raw_total, 100));
    }
  }
});

test("forbidden wording detector", () => {
  assert.ok(forbiddenPhrases("Stop taking aspirin.").length);
  assert.ok(forbiddenPhrases("This is safe.").length);
  assert.equal(forbiddenPhrases("It may lower the risk of harm.").length, 0);
});

test("stale knowledge base notice (SAF-07)", () => {
  const today = new Date("2026-10-25");
  assert.equal(kbNotice("2026-09-01", today), null);
  assert.match(kbNotice("2026-01-01", today), /out of date/);
});

test("invalid input is rejected, not scored as zero", () => {
  assert.throws(() =>
    analysePayload({ warnings: [{ category: "interaction", medicines: ["A"],
      rule_id: "R", kb_version: "K", severity: "catastrophic" }] }));
  assert.throws(() =>
    analysePayload({ warnings: [{ category: "interaction", medicines: ["A"],
      rule_id: "R", kb_version: "K" }] }));
});
