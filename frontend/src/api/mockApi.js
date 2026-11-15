// In-browser stand-in for the Dawawala REST API. It follows the SRS
// (FR-1 to FR-15, SAF-01, SAF-08) so the screens can be built and tested
// before the backend exists. Swap it for the real API in src/api/index.js.
import { ApiError } from "./errors.js";
import { EMAIL_PATTERN, LIMITS, passwordProblems } from "../lib/limits.js";
import { matchCandidates } from "../mock/match.js";
import { analyseList } from "../mock/analyse.js";

const DB_KEY = "dawawala-mock-db-v1";
const CANNED_LABELS = [
  ["Tab. Brufen 400 mg", "Amlo 5mg", "Take one daily after meals", "Metform 500",
   "Zxqvlin 10 mg"],
  ["Warfarin 5 mg", "Disprin 75mg", "Lasix 40 mg", "Take as directed"],
  ["Atorvastatin 20mg", "Lisinopril 10mg", "Spironolactone 25 mg"],
];

export function memoryStorage() {
  const data = new Map();
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => void data.set(k, String(v)),
    removeItem: (k) => void data.delete(k),
  };
}

export function browserStorage() {
  try {
    const s = globalThis.localStorage;
    s.setItem("__t", "1");
    s.removeItem("__t");
    return s;
  } catch {
    return memoryStorage(); // private window, blocked storage, tests
  }
}

const emptyDb = () => ({ users: [], lists: [], analyses: [], seq: 1, lockouts: {}, session: null });

export function createMockApi({ storage = memoryStorage(), now = () => new Date(), delayMs = 0 } = {}) {
  const load = () => {
    try {
      return JSON.parse(storage.getItem(DB_KEY)) ?? emptyDb();
    } catch {
      return emptyDb();
    }
  };
  const db = load();
  const save = () => storage.setItem(DB_KEY, JSON.stringify(db));
  const nextId = (p) => `${p}${db.seq++}`;
  const wait = () => (delayMs ? new Promise((r) => setTimeout(r, delayMs)) : Promise.resolve());
  const iso = () => now().toISOString();

  // ---- helpers ----------------------------------------------------------
  const sessionUser = () => {
    const s = db.session;
    if (!s) throw new ApiError("unauthorized", "Log in to continue.");
    if (new Date(s.expiresAt) <= now()) {
      db.session = null;
      save();
      throw new ApiError("session_expired", "Your session ended. Log in again.");
    }
    return db.users.find((u) => u.id === s.userId);
  };
  const ownList = (id) => {
    const user = sessionUser();
    const list = db.lists.find((l) => l.id === id);
    if (!list) throw new ApiError("not_found", "We could not find that medication list.");
    if (list.userId !== user.id) {
      throw new ApiError("forbidden", "You can only open your own medication lists.");
    }
    return list;
  };
  const markOutdated = (list) => {
    list.status = "draft"; // FR-7: editing returns a confirmed list to draft
    db.analyses.filter((a) => a.listId === list.id).forEach((a) => { a.freshness = "outdated"; });
  };
  const makeItem = (raw, source) => {
    const { term, candidates } = matchCandidates(raw);
    const top = candidates[0];
    const label = top ? top.label : "unrecognised";
    return {
      id: nextId("item"), raw: String(raw).trim(), term, source, candidates, label,
      // High-confidence matches start accepted; Low and unrecognised items
      // must be resolved by the user (FR-7, SAF-04).
      decision: label === "High"
        ? { status: "accepted", medicationId: top.medicationId }
        : { status: "unresolved" },
    };
  };
  const publicList = (list) => ({
    ...structuredClone(list),
    analysisStatus: (() => {
      const mine = db.analyses.filter((a) => a.listId === list.id);
      if (!mine.length) return "none";
      return mine[mine.length - 1].freshness === "current" ? "current" : "outdated";
    })(),
  });
  const unresolved = (list) => list.items.filter((i) => i.decision.status === "unresolved");

  const api = {
    mode: "mock",

    // ---- accounts (FR-1, FR-2) ------------------------------------------
    async register({ name, email, password, role }) {
      await wait();
      const fields = {};
      if (!String(name ?? "").trim()) fields.name = "Enter your name.";
      if (!EMAIL_PATTERN.test(String(email ?? "").trim())) fields.email = "Enter an email address like name@example.com.";
      const problems = passwordProblems(String(password ?? ""));
      if (problems.length) fields.password = problems.join(" ");
      if (!["User", "Admin"].includes(role)) fields.role = "Choose a role.";
      if (Object.keys(fields).length) throw new ApiError("validation", "Check the highlighted fields.", fields);
      const mail = email.trim().toLowerCase();
      if (db.users.some((u) => u.email === mail)) {
        throw new ApiError("validation", "Check the highlighted fields.", { email: "This email already has an account. Log in instead." });
      }
      db.users.push({ id: nextId("user"), name: name.trim(), email: mail, password, role, createdAt: iso() });
      save();
      return { message: "Account created. You can log in now." };
    },

    async login({ email, password }) {
      await wait();
      const mail = String(email ?? "").trim().toLowerCase();
      const lock = db.lockouts[mail];
      if (lock?.until && new Date(lock.until) > now()) {
        throw new ApiError("locked", `Too many attempts. Try again in ${LIMITS.LOCKOUT_MIN} minutes.`);
      }
      const user = db.users.find((u) => u.email === mail);
      if (!user || user.password !== password) {
        // Same message whether or not the email exists (FR-2).
        const entry = (db.lockouts[mail] ??= { count: 0 });
        entry.count += 1;
        if (entry.count >= LIMITS.MAX_FAILED_LOGINS) {
          entry.until = new Date(now().getTime() + LIMITS.LOCKOUT_MIN * 60000).toISOString();
          entry.count = 0;
        }
        save();
        throw new ApiError("invalid_credentials", "The email or password is not correct.");
      }
      delete db.lockouts[mail];
      db.session = { userId: user.id, expiresAt: new Date(now().getTime() + LIMITS.TOKEN_TTL_MIN * 60000).toISOString() };
      save();
      return { user: { id: user.id, name: user.name, email: user.email, role: user.role }, expiresAt: db.session.expiresAt };
    },

    async logout() { db.session = null; save(); },

    async currentUser() {
      await wait();
      if (!db.session) return null;
      try {
        const u = sessionUser();
        return { id: u.id, name: u.name, email: u.email, role: u.role, expiresAt: db.session.expiresAt };
      } catch {
        return null;
      }
    },

    // ---- lists and items (FR-3, FR-4, FR-6, FR-7) -------------------------
    async createList() {
      await wait();
      const user = sessionUser();
      const list = {
        id: nextId("list"), userId: user.id, status: "draft", source: "manual",
        items: [], images: [], factors: { age_range: "unknown", kidney_function: "unknown", liver_function: "unknown" },
        createdAt: iso(), updatedAt: iso(),
      };
      db.lists.push(list);
      save();
      return publicList(list);
    },

    async getList(id) { await wait(); return publicList(ownList(id)); },

    async listLists() {
      await wait();
      const user = sessionUser();
      return db.lists.filter((l) => l.userId === user.id && (l.items.length || l.images.length))
        .map((l) => ({
          ...publicList(l),
          analyses: db.analyses.filter((a) => a.listId === l.id).map((a) => ({ id: a.id, createdAt: a.createdAt, freshness: a.freshness })),
        }))
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    },

    async addNames(id, names) {
      await wait();
      const list = ownList(id);
      const cleaned = names.map((n) => String(n).trim()).filter(Boolean);
      for (const n of cleaned) {
        if (n.length < LIMITS.NAME_MIN || n.length > LIMITS.NAME_MAX) {
          throw new ApiError("validation", `Enter a medicine name with ${LIMITS.NAME_MIN} to ${LIMITS.NAME_MAX} characters.`, { name: `"${n.slice(0, 20)}" is not a valid length.` });
        }
      }
      if (list.items.filter((i) => i.decision.status !== "removed").length + cleaned.length > LIMITS.MAX_MEDS_PER_LIST) {
        throw new ApiError("limit", `You can add up to ${LIMITS.MAX_MEDS_PER_LIST} medicines to one list.`);
      }
      for (const n of cleaned) list.items.push(makeItem(n, "manual"));
      list.source = list.images.length ? "mixed" : "manual";
      list.updatedAt = iso();
      markOutdated(list);
      save();
      return publicList(list);
    },

    async uploadImage(id, file) {
      await wait();
      const list = ownList(id);
      if (list.images.length >= LIMITS.MAX_IMAGES_PER_LIST) {
        throw new ApiError("limit", `You can upload up to ${LIMITS.MAX_IMAGES_PER_LIST} photos to one list.`);
      }
      // Simulated OCR: canned label text, one set per upload.
      const lines = CANNED_LABELS[list.images.length % CANNED_LABELS.length];
      const image = { id: nextId("img"), name: file?.name ?? "photo", ocrStatus: "completed", uploadedAt: iso(), lineCount: lines.length };
      list.images.push(image);
      let added = 0;
      for (const line of lines) {
        const item = makeItem(line, "ocr");
        if (!item.term) continue; // instructions only, kept as a note, not analysed
        item.imageId = image.id;
        list.items.push(item);
        added += 1;
      }
      list.source = list.items.some((i) => i.source === "manual") ? "mixed" : "OCR";
      list.updatedAt = iso();
      markOutdated(list);
      save();
      return { list: publicList(list), image, added };
    },

    async editItem(id, itemId, text) {
      await wait();
      const list = ownList(id);
      const idx = list.items.findIndex((i) => i.id === itemId);
      if (idx < 0) throw new ApiError("not_found", "We could not find that item.");
      const t = String(text).trim();
      if (t.length < LIMITS.NAME_MIN || t.length > LIMITS.NAME_MAX) {
        throw new ApiError("validation", `Enter a medicine name with ${LIMITS.NAME_MIN} to ${LIMITS.NAME_MAX} characters.`);
      }
      const fresh = makeItem(t, list.items[idx].source);
      list.items[idx] = { ...fresh, id: itemId, imageId: list.items[idx].imageId };
      list.updatedAt = iso();
      markOutdated(list);
      save();
      return publicList(list);
    },

    async decideItem(id, itemId, decision) {
      await wait();
      const list = ownList(id);
      const item = list.items.find((i) => i.id === itemId);
      if (!item) throw new ApiError("not_found", "We could not find that item.");
      if (decision.status === "accepted") {
        if (!item.candidates.some((c) => c.medicationId === decision.medicationId)) {
          throw new ApiError("validation", "Choose one of the suggested medicines, or edit the text.");
        }
        item.decision = { status: "accepted", medicationId: decision.medicationId };
      } else if (decision.status === "kept-unrecognised") {
        item.decision = { status: "kept-unrecognised" };
      } else if (decision.status === "unresolved") {
        item.decision = { status: "unresolved" };
      } else {
        throw new ApiError("validation", "Unknown decision.");
      }
      list.updatedAt = iso();
      markOutdated(list);
      save();
      return publicList(list);
    },

    async removeItem(id, itemId) {
      await wait();
      const list = ownList(id);
      list.items = list.items.filter((i) => i.id !== itemId);
      list.updatedAt = iso();
      markOutdated(list);
      save();
      return publicList(list);
    },

    async confirmList(id) {
      await wait();
      const list = ownList(id);
      const open = unresolved(list);
      if (open.length) {
        throw new ApiError("validation", `Resolve ${open.length} more ${open.length === 1 ? "item" : "items"} before you confirm the list.`);
      }
      if (!list.items.some((i) => i.decision.status === "accepted")) {
        throw new ApiError("validation", "Confirm at least one medicine before you continue.");
      }
      list.status = "confirmed";
      list.updatedAt = iso();
      save();
      return publicList(list);
    },

    // ---- patient factors (FR-14) ------------------------------------------
    async saveFactors(id, factors) {
      await wait();
      const list = ownList(id);
      const allowed = {
        age_range: ["under_18", "18_64", "65_plus", "unknown"],
        kidney_function: ["normal", "impaired", "unknown"],
        liver_function: ["normal", "impaired", "unknown"],
      };
      for (const [k, values] of Object.entries(allowed)) {
        if (!values.includes(factors[k])) throw new ApiError("validation", "Choose one of the listed options.", { [k]: "Choose one of the listed options." });
      }
      const changed = JSON.stringify(list.factors) !== JSON.stringify(factors);
      list.factors = { age_range: factors.age_range, kidney_function: factors.kidney_function, liver_function: factors.liver_function };
      if (changed) {
        // SAF-08: an earlier result is stale once factors change.
        db.analyses.filter((a) => a.listId === list.id).forEach((a) => { a.freshness = "outdated"; });
      }
      list.updatedAt = iso();
      save();
      return publicList(list);
    },

    // ---- analysis (FR-8 to FR-13, FR-15) ----------------------------------
    async runAnalysis(id) {
      await wait();
      const list = ownList(id);
      if (list.status !== "confirmed") {
        // SAF-01 / BR-01: never analyse an unconfirmed list.
        throw new ApiError("not_confirmed", "Confirm your medicine list before you run the check.");
      }
      const meds = list.items
        .filter((i) => i.decision.status === "accepted")
        .map((i) => ({ medicationId: i.decision.medicationId, enteredAs: i.raw }));
      const notAnalysed = list.items
        .filter((i) => i.decision.status === "kept-unrecognised")
        .map((i) => ({ text: i.raw, reason: "We could not match this to a medicine in the knowledge base." }));
      db.analyses.filter((a) => a.listId === list.id).forEach((a) => { a.freshness = "outdated"; });
      const result = analyseList({ meds, notAnalysed, factors: list.factors, today: now() });
      const analysis = { id: nextId("an"), listId: list.id, createdAt: iso(), freshness: "current", factors: { ...list.factors }, ...result };
      db.analyses.push(analysis);
      list.updatedAt = iso();
      save();
      return structuredClone(analysis);
    },

    async getAnalysis(id) {
      await wait();
      const user = sessionUser();
      const a = db.analyses.find((x) => x.id === id);
      if (!a) throw new ApiError("not_found", "We could not find that analysis.");
      const list = db.lists.find((l) => l.id === a.listId);
      if (list.userId !== user.id) throw new ApiError("forbidden", "You can only open your own results.");
      return structuredClone(a);
    },
  };
  return api;
}
