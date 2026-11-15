import test from "node:test";
import assert from "node:assert/strict";
import { createMockApi, memoryStorage } from "./mockApi.js";
import { ApiError } from "./errors.js";

const USER = { name: "Aisha Khan", email: "aisha@example.com", password: "secret123", role: "User" };

async function loggedIn(opts = {}) {
  const api = createMockApi({ storage: memoryStorage(), ...opts });
  await api.register(USER);
  await api.login(USER);
  return api;
}
const rejects = (p, code) =>
  assert.rejects(p, (e) => e instanceof ApiError && (!code || e.code === code));

test("FR-1 registration validates fields and rejects duplicate email", async () => {
  const api = createMockApi();
  await rejects(api.register({ ...USER, password: "short" }), "validation");
  await rejects(api.register({ ...USER, email: "nope" }), "validation");
  await rejects(api.register({ ...USER, name: " " }), "validation");
  await rejects(api.register({ ...USER, role: "Root" }), "validation");
  await api.register(USER);
  await assert.rejects(api.register(USER), (e) => /already has an account/.test(e.fields.email));
});

test("FR-2 failed login never reveals whether the email exists", async () => {
  const api = createMockApi();
  await api.register(USER);
  const a = await api.login({ email: USER.email, password: "wrong" }).catch((e) => e);
  const b = await api.login({ email: "ghost@example.com", password: "wrong" }).catch((e) => e);
  assert.equal(a.message, b.message);
  assert.equal(a.code, "invalid_credentials");
});

test("FR-2 account locks after 5 failures for 15 minutes", async () => {
  let t = new Date("2026-10-25T10:00:00Z");
  const api = createMockApi({ now: () => t });
  await api.register(USER);
  for (let i = 0; i < 5; i++) await api.login({ email: USER.email, password: "bad" }).catch(() => {});
  await rejects(api.login(USER), "locked"); // even the right password
  t = new Date(t.getTime() + 16 * 60000);
  assert.ok((await api.login(USER)).user);
});

test("JWT-style session expires after 30 minutes", async () => {
  let t = new Date("2026-10-25T10:00:00Z");
  const api = createMockApi({ now: () => t });
  await api.register(USER);
  await api.login(USER);
  await api.createList();
  t = new Date(t.getTime() + 31 * 60000);
  await rejects(api.createList(), "session_expired");
  assert.equal(await api.currentUser(), null);
});

test("endpoints need login (401) and other users' lists are forbidden (403, SEC-05)", async () => {
  const api = createMockApi();
  await rejects(api.createList(), "unauthorized");
  await api.register(USER);
  await api.login(USER);
  const list = await api.createList();
  await api.logout();
  await api.register({ ...USER, email: "other@example.com" });
  await api.login({ email: "other@example.com", password: USER.password });
  await rejects(api.getList(list.id), "forbidden");
  await rejects(api.runAnalysis(list.id), "forbidden");
});

test("FR-3 name length and 30-medicine limit", async () => {
  const api = await loggedIn();
  const { id } = await api.createList();
  await rejects(api.addNames(id, ["a"]), "validation");
  await rejects(api.addNames(id, ["x".repeat(101)]), "validation");
  await api.addNames(id, Array.from({ length: 30 }, (_, i) => `Drug${i}x`));
  await rejects(api.addNames(id, ["Panadol"]), "limit");
});

test("FR-6 matching sets confidence and default decisions (SAF-04)", async () => {
  const api = await loggedIn();
  const { id } = await api.createList();
  const list = await api.addNames(id, ["Panadol 500mg", "Metform", "Zxqvlin"]);
  const [high, low, none] = list.items;
  assert.equal(high.label, "High");
  assert.equal(high.decision.status, "accepted");
  assert.equal(low.label, "Low");
  assert.equal(low.decision.status, "unresolved"); // needs an explicit action
  assert.equal(none.label, "unrecognised");
  assert.equal(none.candidates.length, 0);
});

test("FR-7 cannot confirm until every item is resolved; needs 1 medicine", async () => {
  const api = await loggedIn();
  const { id } = await api.createList();
  const list = await api.addNames(id, ["Panadol", "Metform"]);
  await rejects(api.confirmList(id), "validation");
  await api.decideItem(id, list.items[1].id, { status: "accepted", medicationId: "metformin" });
  assert.equal((await api.confirmList(id)).status, "confirmed");

  const l2 = await api.addNames((await api.createList()).id, ["Zxqvlin"]);
  await api.decideItem(l2.id, l2.items[0].id, { status: "kept-unrecognised" });
  await rejects(api.confirmList(l2.id), "validation"); // no confirmed medicine
});

test("an accepted choice must be one of the suggestions", async () => {
  const api = await loggedIn();
  const { id } = await api.createList();
  const list = await api.addNames(id, ["Metform"]);
  await rejects(api.decideItem(id, list.items[0].id, { status: "accepted", medicationId: "warfarin" }), "validation");
});

test("SAF-01 / BR-01: analysis is refused on an unconfirmed list", async () => {
  const api = await loggedIn();
  const { id } = await api.createList();
  await api.addNames(id, ["Warfarin", "Aspirin"]);
  await rejects(api.runAnalysis(id), "not_confirmed");
});

async function confirmed(names) {
  const api = await loggedIn();
  const { id } = await api.createList();
  await api.addNames(id, names);
  await api.confirmList(id);
  return { api, id };
}

test("FR-8 interaction + FR-11 score + FR-13 explanation", async () => {
  const { api, id } = await confirmed(["Warfarin", "Disprin"]);
  const a = await api.runAnalysis(id);
  assert.equal(a.warnings.length, 1);
  const w = a.warnings[0];
  assert.equal(w.rule_id, "DDI-0012");
  assert.equal(w.score, 50);
  assert.equal(w.band, "High");
  assert.ok(w.explanation.includes("DDI-0012"));
  assert.deepEqual(a.band_counts, { Low: 0, Moderate: 0, High: 1, Critical: 0 });
});

test("FR-9 duplicates by brand name and therapeutic duplication", async () => {
  const { api, id } = await confirmed(["Panadol", "Calpol", "Brufen", "Aleve"]);
  const a = await api.runAnalysis(id);
  const cats = a.warnings.map((w) => `${w.category}:${w.score}`).sort();
  assert.deepEqual(cats, ["duplicate:15", "duplicate:30"]);
});

test("FR-10 contraindications use factors; missing factors list as not assessed", async () => {
  const { api, id } = await confirmed(["Metformin"]);
  let a = await api.runAnalysis(id);
  assert.equal(a.warnings.length, 0);
  assert.equal(a.not_assessed.length, 1);
  assert.match(a.not_assessed[0].message, /kidney function/);

  await api.saveFactors(id, { age_range: "unknown", kidney_function: "impaired", liver_function: "unknown" });
  a = await api.runAnalysis(id);
  assert.equal(a.warnings[0].category, "contraindication");
  assert.equal(a.warnings[0].score, 75); // 70 + 5 for impaired kidney function
  assert.equal(a.warnings[0].band, "Critical");
  assert.equal(a.not_assessed.length, 0);
});

test("FR-12 cascade is found and worded as possible", async () => {
  const { api, id } = await confirmed(["Amlodipine", "Lasix"]);
  const a = await api.runAnalysis(id);
  const c = a.warnings.find((w) => w.category === "cascade");
  assert.equal(c.score, 25);
  assert.match(c.explanation, /possible prescribing cascade/);
  assert.match(c.explanation, /not a diagnosis/);
});

test("FR-15 empty result is never called safe; not-analysed items listed (SAF-03)", async () => {
  const api = await loggedIn();
  const { id } = await api.createList();
  const list = await api.addNames(id, ["Panadol", "Zxqvlin"]);
  await api.decideItem(id, list.items[1].id, { status: "kept-unrecognised" });
  await api.confirmList(id);
  const a = await api.runAnalysis(id);
  assert.equal(a.warnings.length, 0);
  assert.equal(a.not_analysed.length, 1);
  assert.equal(a.not_analysed[0].text, "Zxqvlin");
});

test("SAF-08 editing the list or the factors marks the result outdated", async () => {
  const { api, id } = await confirmed(["Warfarin", "Aspirin"]);
  const a = await api.runAnalysis(id);
  assert.equal((await api.getAnalysis(a.id)).freshness, "current");
  await api.saveFactors(id, { age_range: "65_plus", kidney_function: "unknown", liver_function: "unknown" });
  assert.equal((await api.getAnalysis(a.id)).freshness, "outdated");
  assert.equal((await api.getList(id)).status, "confirmed"); // factors do not unconfirm

  await api.confirmList(id);
  const b = await api.runAnalysis(id);
  assert.equal((await api.getAnalysis(b.id)).freshness, "current");
  await api.addNames(id, ["Lasix"]); // FR-7: edit returns to draft
  assert.equal((await api.getList(id)).status, "draft");
  assert.equal((await api.getAnalysis(b.id)).freshness, "outdated");
  await rejects(api.runAnalysis(id), "not_confirmed");
});

test("FR-4 image upload adds OCR items and enforces 5 images per list", async () => {
  const api = await loggedIn();
  const { id } = await api.createList();
  const { list, added } = await api.uploadImage(id, { name: "label.jpg" });
  assert.equal(added, 4); // the instruction line is dropped, not analysed
  assert.ok(list.items.every((i) => i.source === "ocr"));
  assert.ok(list.items.some((i) => i.label === "Low"));
  assert.ok(list.items.some((i) => i.label === "unrecognised"));
  for (let i = 0; i < 4; i++) await api.uploadImage(id, { name: `p${i}.png` });
  await rejects(api.uploadImage(id, { name: "extra.png" }), "limit");
});

test("editing an item re-runs matching; removing drops it", async () => {
  const api = await loggedIn();
  const { id } = await api.createList();
  const list = await api.addNames(id, ["Zxqvlin"]);
  const edited = await api.editItem(id, list.items[0].id, "Lipitor");
  assert.equal(edited.items[0].candidates[0].medicationId, "atorvastatin");
  await rejects(api.editItem(id, list.items[0].id, "x"), "validation");
  const after = await api.removeItem(id, list.items[0].id);
  assert.equal(after.items.length, 0);
});

test("history lists only the user's non-empty lists, newest first", async () => {
  const api = await loggedIn();
  await api.createList(); // empty: not listed
  const l = await api.createList();
  await api.addNames(l.id, ["Panadol"]);
  const lists = await api.listLists();
  assert.equal(lists.length, 1);
  assert.equal(lists[0].id, l.id);
});
