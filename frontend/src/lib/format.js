export function formatDateTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  }).format(d);
}

export function formatDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" }).format(d);
}

export const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export const FACTOR_OPTIONS = {
  age_range: [
    ["under_18", "Under 18"], ["18_64", "18 to 64"], ["65_plus", "65 or over"], ["unknown", "Unknown"],
  ],
  kidney_function: [["normal", "Normal"], ["impaired", "Impaired"], ["unknown", "Unknown"]],
  liver_function: [["normal", "Normal"], ["impaired", "Impaired"], ["unknown", "Unknown"]],
};

export const FACTOR_TITLES = {
  age_range: "Age range", kidney_function: "Kidney function", liver_function: "Liver function",
};

export function describeFactors(factors) {
  const label = (key) =>
    FACTOR_OPTIONS[key].find(([v]) => v === factors[key])?.[1] ?? "Unknown";
  return Object.keys(FACTOR_TITLES).map((k) => ({ key: k, title: FACTOR_TITLES[k], value: label(k) }));
}
