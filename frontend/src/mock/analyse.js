// Mock rule engine (FR-8, FR-9, FR-10, FR-12): turns a confirmed list into
// warnings, then scores and explains them with the engine port.
import {
  CASCADES, CONTRAINDICATIONS, INTERACTIONS, KB_UPDATED, KB_VERSION, medById,
} from "./kb.js";
import { analysePayload, kbNotice } from "./engine.js";

const FIELD_LABEL = {
  age_range: "age range", kidney_function: "kidney function", liver_function: "liver function",
};

/**
 * @param meds     [{ medicationId, enteredAs }] confirmed medicines
 * @param notAnalysed [{ text, reason }] items kept as unrecognised
 * @param factors  { age_range, kidney_function, liver_function }
 */
export function analyseList({ meds, notAnalysed, factors, today = new Date() }) {
  const warnings = [];
  const ids = meds.map((m) => m.medicationId);
  const unique = [...new Set(ids)];
  const name = (id) => medById(id).name;

  // FR-9 exact duplicates (also when entered under different brand names)
  for (const id of unique) {
    const entries = meds.filter((m) => m.medicationId === id);
    if (entries.length > 1) {
      warnings.push({
        category: "duplicate", medicines: [name(id)], rule_id: `DUP-${id.slice(0, 3).toUpperCase()}`,
        kb_version: KB_VERSION, duplicate_kind: "exact",
        description: `Entered as ${entries.map((e) => e.enteredAs).join(" and ")}.`,
      });
    }
  }
  // FR-9 therapeutic duplication (same duplication-relevant class)
  const byClass = new Map();
  for (const id of unique) {
    const med = medById(id);
    if (med.dupClass) byClass.set(med.cls, [...(byClass.get(med.cls) ?? []), id]);
  }
  for (const [cls, group] of byClass) {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        warnings.push({
          category: "duplicate", medicines: [name(group[i]), name(group[j])],
          rule_id: `TD-${cls.replace(/[^A-Z]/gi, "").slice(0, 4).toUpperCase()}`,
          kb_version: KB_VERSION, duplicate_kind: "therapeutic",
        });
      }
    }
  }
  // FR-8 interactions: every unordered pair with a record
  for (const rule of INTERACTIONS) {
    if (unique.includes(rule.a) && unique.includes(rule.b)) {
      warnings.push({
        category: "interaction", medicines: [name(rule.a), name(rule.b)],
        rule_id: rule.rule, kb_version: KB_VERSION, severity: rule.severity,
        relevant_factors: rule.factors, description: rule.description,
      });
    }
  }
  // FR-10 contraindications, plus the "not assessed" list
  const notAssessed = [];
  for (const rule of CONTRAINDICATIONS) {
    if (!unique.includes(rule.med)) continue;
    const supplied = factors[rule.field];
    if (supplied === "unknown") {
      if (!notAssessed.some((n) => n.medicationId === rule.med && n.need === rule.need)) {
        notAssessed.push({
          medicationId: rule.med, medicine: name(rule.med), need: rule.need,
          field: rule.field,
          message: `${name(rule.med)} has a check that depends on ${FIELD_LABEL[rule.field]}. Add it under patient factors to include this check.`,
        });
      }
    } else if (supplied === rule.value) {
      warnings.push({
        category: "contraindication", medicines: [name(rule.med)],
        rule_id: rule.rule, kb_version: KB_VERSION, severity: rule.severity,
        relevant_factors: [rule.factor], condition: rule.condition,
      });
    }
  }
  // FR-12 prescribing cascades
  for (const rule of CASCADES) {
    const triggers = rule.triggers.filter((t) => unique.includes(t));
    if (triggers.length && unique.includes(rule.downstream)) {
      for (const t of triggers) {
        warnings.push({
          category: "cascade", medicines: [name(t), name(rule.downstream)],
          rule_id: rule.rule, kb_version: KB_VERSION, relevant_factors: rule.factors,
          trigger: name(t), symptom_pattern: rule.symptom, downstream: name(rule.downstream),
        });
      }
    }
  }

  const scored = analysePayload({ warnings, patient_factors: factors });
  return {
    ...scored,
    kb_version: KB_VERSION,
    kb_updated: KB_UPDATED,
    kb_notice: kbNotice(KB_UPDATED, today),
    medicines: unique.map(name),
    not_analysed: notAnalysed,
    not_assessed: notAssessed,
  };
}
