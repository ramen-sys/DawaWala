import test from "node:test";
import assert from "node:assert/strict";
import { BANDS, BAND_STYLE, categoryLabel } from "./severity.js";

test("every band has styling and a score range", () => {
  for (const b of BANDS) assert.ok(BAND_STYLE[b].text && BAND_STYLE[b].range);
});

test("category labels are plain language", () => {
  assert.equal(categoryLabel({ category: "interaction", medicines: ["A", "B"] }), "Drug interaction");
  assert.match(categoryLabel({ category: "duplicate", medicines: ["A", "B"] }), /same drug class/);
  assert.equal(categoryLabel({ category: "duplicate", medicines: ["A"] }), "Duplicate medicine");
});
