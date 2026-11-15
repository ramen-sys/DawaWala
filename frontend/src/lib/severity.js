// Severity must be conveyed by text AND icon as well as colour (SAF-05).
export const BANDS = ["Critical", "High", "Moderate", "Low"]; // display order

export const BAND_STYLE = {
  Critical: { text: "text-critical", tint: "bg-critical-tint", border: "border-critical", edge: "border-l-critical", range: "75 to 100" },
  High: { text: "text-high", tint: "bg-high-tint", border: "border-high", edge: "border-l-high", range: "50 to 74" },
  Moderate: { text: "text-moderate", tint: "bg-moderate-tint", border: "border-moderate", edge: "border-l-moderate", range: "25 to 49" },
  Low: { text: "text-low", tint: "bg-low-tint", border: "border-low", edge: "border-l-low", range: "0 to 24" },
};

export const CATEGORY_LABEL = {
  contraindication: "Contraindication",
  interaction: "Drug interaction",
  cascade: "Possible prescribing cascade",
  duplicate: "Duplicate medicine",
};

export function categoryLabel(warning) {
  if (warning.category === "duplicate" && warning.medicines.length > 1) {
    return "Possible duplication in the same drug class";
  }
  return CATEGORY_LABEL[warning.category] ?? warning.category;
}
