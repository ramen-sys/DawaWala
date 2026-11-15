import test from "node:test";
import assert from "node:assert/strict";
import { parseHash, paths } from "./router.js";

test("parses every route", () => {
  assert.equal(parseHash("#/login").name, "login");
  assert.equal(parseHash("#/history").name, "history");
  assert.equal(parseHash("#/new").name, "new");
  assert.deepEqual(parseHash("#/lists/list3/confirm").params, { listId: "list3" });
  assert.equal(parseHash("#/lists/list3/factors").name, "factors");
  assert.deepEqual(parseHash("#/analyses/an9").params, { analysisId: "an9" });
});

test("empty hash goes to history; unknown paths are not found", () => {
  assert.equal(parseHash("").name, "history");
  assert.equal(parseHash("#/nope").name, "notfound");
  assert.equal(parseHash("#/lists/x/unknown").name, "notfound");
});

test("path builders round-trip through the parser", () => {
  assert.equal(parseHash("#" + paths.medicines("a1")).name, "medicines");
  assert.equal(parseHash("#" + paths.results("an2")).params.analysisId, "an2");
});
