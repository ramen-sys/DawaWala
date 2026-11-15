// Mock drug-name normalisation (FR-6): split text into candidate terms and
// fuzzy-match them against standard names and brand names. The real service
// uses lightweight NLP + fuzzy matching on the server; this one is only
// good enough to drive the screens.
import { MEDICATIONS } from "./kb.js";

export const MATCH_HIGH = 90; // SAF-04: High confidence at or above
export const MATCH_LOW = 70;  // below this no candidate is suggested
export const MAX_CANDIDATES = 3;

const NOISE = new Set([
  "tab", "tabs", "tablet", "tablets", "cap", "caps", "capsule", "capsules",
  "syrup", "susp", "suspension", "inj", "injection", "drops", "cream",
  "take", "one", "two", "three", "once", "twice", "daily", "day", "days",
  "after", "before", "with", "without", "meals", "meal", "food", "water",
  "morning", "night", "evening", "bedtime", "for", "times", "every", "hours",
  "as", "needed", "sig", "rx", "qty", "the", "and", "of", "by", "mouth",
  "orally", "oral", "per", "each", "dose", "use", "apply",
]);

/** Remove strengths, dosage forms and instructions; keep the drug words. */
export function extractTerm(line) {
  const cleaned = String(line)
    .toLowerCase()
    .replace(/\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|iu|%|units?)\b/g, " ")
    .replace(/[^a-z\s'-]/g, " ");
  return cleaned
    .split(/\s+/)
    .filter((t) => t.length >= 2 && !NOISE.has(t))
    .join(" ");
}

export function levenshtein(a, b) {
  const row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let prev = row[0];
    row[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const tmp = row[j];
      row[j] = Math.min(
        row[j] + 1,
        row[j - 1] + 1,
        prev + (a[i - 1] === b[j - 1] ? 0 : 1)
      );
      prev = tmp;
    }
  }
  return row[b.length];
}

/** Similarity from 0 to 100. */
export function similarity(a, b) {
  if (!a && !b) return 100;
  const longest = Math.max(a.length, b.length);
  return Math.round(100 * (1 - levenshtein(a, b) / longest));
}

export const confidenceLabel = (score) =>
  score >= MATCH_HIGH ? "High" : score >= MATCH_LOW ? "Low" : "unrecognised";

/** Up to 3 candidate medicines for one piece of text, best first. */
export function matchCandidates(text) {
  const term = extractTerm(text);
  if (!term) return { term, candidates: [] };
  const best = new Map();
  for (const med of MEDICATIONS) {
    for (const name of [med.name, ...med.aliases]) {
      const score = similarity(term, name.toLowerCase());
      if (score >= MATCH_LOW && score > (best.get(med.id)?.score ?? -1)) {
        best.set(med.id, { medicationId: med.id, name: med.name, matchedOn: name, score });
      }
    }
  }
  const candidates = [...best.values()]
    .sort((x, y) => y.score - x.score || x.name.localeCompare(y.name))
    .slice(0, MAX_CANDIDATES)
    .map((c) => ({ ...c, label: confidenceLabel(c.score) }));
  return { term, candidates };
}
