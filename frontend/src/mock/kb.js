// Small demo knowledge base. The real one (300+ medicines, 1,000+
// interactions) lives in the backend database. Content here is for demo
// only and has NOT been clinically reviewed (SAF-09).

export const KB_VERSION = "KB-1.0.0";
export const KB_UPDATED = "2026-10-01";

// id, standard name, brand names/aliases, drug class, class duplication relevant
export const MEDICATIONS = [
  { id: "warfarin", name: "Warfarin", aliases: ["Coumadin", "Jantoven"], cls: "Anticoagulant", dupClass: false },
  { id: "aspirin", name: "Aspirin", aliases: ["Disprin", "Ecosprin", "Loprin"], cls: "Antiplatelet", dupClass: false },
  { id: "clopidogrel", name: "Clopidogrel", aliases: ["Plavix"], cls: "Antiplatelet P2Y12", dupClass: false },
  { id: "ibuprofen", name: "Ibuprofen", aliases: ["Brufen", "Advil", "Nurofen", "Motrin"], cls: "NSAID", dupClass: true },
  { id: "naproxen", name: "Naproxen", aliases: ["Aleve", "Naprosyn"], cls: "NSAID", dupClass: true },
  { id: "diclofenac", name: "Diclofenac", aliases: ["Voltaren", "Voltral", "Cataflam"], cls: "NSAID", dupClass: true },
  { id: "paracetamol", name: "Paracetamol", aliases: ["Panadol", "Calpol", "Tylenol", "Acetaminophen"], cls: "Analgesic", dupClass: false },
  { id: "metformin", name: "Metformin", aliases: ["Glucophage", "Glycomet"], cls: "Biguanide", dupClass: false },
  { id: "amlodipine", name: "Amlodipine", aliases: ["Norvasc", "Amlo"], cls: "Calcium-channel blocker", dupClass: false },
  { id: "furosemide", name: "Furosemide", aliases: ["Lasix", "Frusemide"], cls: "Loop diuretic", dupClass: false },
  { id: "spironolactone", name: "Spironolactone", aliases: ["Aldactone"], cls: "Potassium-sparing diuretic", dupClass: false },
  { id: "lisinopril", name: "Lisinopril", aliases: ["Zestril", "Prinivil"], cls: "ACE inhibitor", dupClass: true },
  { id: "enalapril", name: "Enalapril", aliases: ["Renitec", "Vasotec"], cls: "ACE inhibitor", dupClass: true },
  { id: "losartan", name: "Losartan", aliases: ["Cozaar", "Losacar"], cls: "ARB", dupClass: false },
  { id: "simvastatin", name: "Simvastatin", aliases: ["Zocor"], cls: "Statin", dupClass: true },
  { id: "atorvastatin", name: "Atorvastatin", aliases: ["Lipitor", "Atorva"], cls: "Statin", dupClass: true },
  { id: "clarithromycin", name: "Clarithromycin", aliases: ["Klaricid", "Biaxin"], cls: "Macrolide antibiotic", dupClass: false },
  { id: "omeprazole", name: "Omeprazole", aliases: ["Losec", "Risek", "Prilosec"], cls: "Proton-pump inhibitor", dupClass: true },
  { id: "esomeprazole", name: "Esomeprazole", aliases: ["Nexium", "Nexum"], cls: "Proton-pump inhibitor", dupClass: true },
  { id: "digoxin", name: "Digoxin", aliases: ["Lanoxin"], cls: "Cardiac glycoside", dupClass: false },
  { id: "amiodarone", name: "Amiodarone", aliases: ["Cordarone"], cls: "Antiarrhythmic", dupClass: false },
  { id: "sertraline", name: "Sertraline", aliases: ["Zoloft", "Lustral"], cls: "SSRI", dupClass: true },
  { id: "tramadol", name: "Tramadol", aliases: ["Tramal", "Ultram"], cls: "Opioid analgesic", dupClass: false },
  { id: "metoprolol", name: "Metoprolol", aliases: ["Betaloc", "Lopressor"], cls: "Beta blocker", dupClass: true },
];

// Interaction rules (FR-8). `factors` = patient factors the rule lists.
export const INTERACTIONS = [
  { rule: "DDI-0012", a: "warfarin", b: "aspirin", severity: "major", factors: ["age_65_plus", "kidney_impaired"], description: "Both medicines can raise the risk of bleeding." },
  { rule: "DDI-0020", a: "warfarin", b: "ibuprofen", severity: "major", factors: ["age_65_plus"], description: "Together they can raise the risk of bleeding in the stomach and gut." },
  { rule: "DDI-0021", a: "warfarin", b: "diclofenac", severity: "major", factors: ["age_65_plus"], description: "Together they can raise the risk of bleeding in the stomach and gut." },
  { rule: "DDI-0031", a: "simvastatin", b: "clarithromycin", severity: "contraindicated", factors: ["age_65_plus", "liver_impaired"], description: "Clarithromycin can raise simvastatin levels in the blood. This may harm the muscles." },
  { rule: "DDI-0044", a: "lisinopril", b: "spironolactone", severity: "major", factors: ["age_65_plus", "kidney_impaired"], description: "Together they can raise potassium levels in the blood." },
  { rule: "DDI-0045", a: "losartan", b: "spironolactone", severity: "major", factors: ["age_65_plus", "kidney_impaired"], description: "Together they can raise potassium levels in the blood." },
  { rule: "DDI-0050", a: "clopidogrel", b: "omeprazole", severity: "moderate", factors: ["age_65_plus"], description: "Omeprazole may lower how well clopidogrel works." },
  { rule: "DDI-0061", a: "digoxin", b: "amiodarone", severity: "major", factors: ["age_65_plus", "kidney_impaired"], description: "Amiodarone can raise digoxin levels in the blood." },
  { rule: "DDI-0072", a: "sertraline", b: "tramadol", severity: "major", factors: ["age_65_plus"], description: "Together they can raise the risk of a serious reaction in the nervous system." },
  { rule: "DDI-0080", a: "ibuprofen", b: "lisinopril", severity: "moderate", factors: ["age_65_plus", "kidney_impaired"], description: "Together they can strain the kidneys and may weaken the blood-pressure medicine." },
  { rule: "DDI-0081", a: "diclofenac", b: "lisinopril", severity: "moderate", factors: ["age_65_plus", "kidney_impaired"], description: "Together they can strain the kidneys and may weaken the blood-pressure medicine." },
  { rule: "DDI-0090", a: "metformin", b: "furosemide", severity: "minor", factors: ["kidney_impaired"], description: "Furosemide can slightly change metformin levels in the blood." },
  { rule: "DDI-0100", a: "aspirin", b: "ibuprofen", severity: "moderate", factors: ["age_65_plus"], description: "Ibuprofen may reduce the heart-protecting effect of low-dose aspirin." },
];

// Contraindication rules (FR-10): apply when `field` has `value`.
export const CONTRAINDICATIONS = [
  { rule: "CI-0044", med: "metformin", field: "kidney_function", value: "impaired", factor: "kidney_impaired", severity: "contraindicated", condition: "severe kidney problems", need: "kidney function" },
  { rule: "CI-0051", med: "ibuprofen", field: "kidney_function", value: "impaired", factor: "kidney_impaired", severity: "major", condition: "reduced kidney function", need: "kidney function" },
  { rule: "CI-0052", med: "naproxen", field: "kidney_function", value: "impaired", factor: "kidney_impaired", severity: "major", condition: "reduced kidney function", need: "kidney function" },
  { rule: "CI-0053", med: "diclofenac", field: "kidney_function", value: "impaired", factor: "kidney_impaired", severity: "major", condition: "reduced kidney function", need: "kidney function" },
  { rule: "CI-0054", med: "diclofenac", field: "liver_function", value: "impaired", factor: "liver_impaired", severity: "major", condition: "reduced liver function", need: "liver function" },
  { rule: "CI-0060", med: "spironolactone", field: "kidney_function", value: "impaired", factor: "kidney_impaired", severity: "major", condition: "reduced kidney function", need: "kidney function" },
  { rule: "CI-0070", med: "simvastatin", field: "liver_function", value: "impaired", factor: "liver_impaired", severity: "major", condition: "liver disease", need: "liver function" },
  { rule: "CI-0071", med: "atorvastatin", field: "liver_function", value: "impaired", factor: "liver_impaired", severity: "major", condition: "liver disease", need: "liver function" },
  { rule: "CI-0080", med: "paracetamol", field: "liver_function", value: "impaired", factor: "liver_impaired", severity: "moderate", condition: "reduced liver function", need: "liver function" },
  { rule: "CI-0090", med: "tramadol", field: "age_range", value: "65_plus", factor: "age_65_plus", severity: "moderate", condition: "an age of 65 or over", need: "age range" },
];

// Prescribing-cascade rules (FR-12).
export const CASCADES = [
  { rule: "CAS-003", triggers: ["amlodipine"], symptom: "ankle swelling", downstream: "furosemide", factors: ["age_65_plus"] },
  { rule: "CAS-007", triggers: ["ibuprofen", "naproxen", "diclofenac"], symptom: "higher blood pressure", downstream: "amlodipine", factors: ["age_65_plus", "kidney_impaired"] },
  { rule: "CAS-011", triggers: ["lisinopril", "enalapril"], symptom: "low blood pressure and dizziness", downstream: "metoprolol", factors: ["age_65_plus"] },
];

export const medById = (id) => MEDICATIONS.find((m) => m.id === id);
