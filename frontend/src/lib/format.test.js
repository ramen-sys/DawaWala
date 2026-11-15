import test from "node:test";
import assert from "node:assert/strict";
import { describeFactors, formatDate, plural } from "./format.js";

test("plural", () => {
  assert.equal(plural(1, "medicine"), "1 medicine");
  assert.equal(plural(3, "medicine"), "3 medicines");
});

test("formatDate handles bad input", () => {
  assert.equal(formatDate("nonsense"), "");
  assert.match(formatDate("2026-10-25T06:00:00Z"), /25 Oct 2026/);
});

test("describeFactors shows Unknown by default", () => {
  const rows = describeFactors({ age_range: "65_plus", kidney_function: "unknown", liver_function: "impaired" });
  assert.deepEqual(rows.map((r) => r.value), ["65 or over", "Unknown", "Impaired"]);
});
