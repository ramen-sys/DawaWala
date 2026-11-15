// WCAG 2.1 AA contrast check (QA-USA-03: at least 4.5:1 for text).
// Run:  node scripts/check-contrast.mjs
// Keep the palette in sync with src/index.css.
const C = {
  ink: "#14272e", inkSoft: "#3f565d", paper: "#f6f8f7", surface: "#ffffff",
  brand: "#0b6b6f", brandDark: "#084a4d", brandTint: "#e2f0f0",
  low: "#1e5a7d", lowTint: "#e4eff6", moderate: "#6b4800", moderateTint: "#fff1cc",
  high: "#9a3408", highTint: "#ffe6d8", critical: "#9b0f27", criticalTint: "#fde2e7",
  white: "#ffffff",
};

const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const lum = (h) => { const [r, g, b] = rgb(h).map(lin); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const blend = (fg, bg, alpha) => "#" + rgb(fg).map((c, i) => Math.round(c * alpha + rgb(bg)[i] * (1 - alpha)).toString(16).padStart(2, "0")).join("");

const pairs = [
  ["body text", C.ink, C.paper], ["body text on white", C.ink, C.surface],
  ["secondary text on page", C.inkSoft, C.paper], ["secondary text on white", C.inkSoft, C.surface],
  ["secondary text on amber highlight", C.inkSoft, C.moderateTint],
  ["secondary text on teal tint", C.inkSoft, C.brandTint],
  ["primary button label", C.white, C.brand], ["primary button hover", C.white, C.brandDark],
  ["link on page", C.brandDark, C.paper], ["link on teal tint", C.brandDark, C.brandTint],
  ["header user name (85% white)", blend(C.white, C.ink, 0.85), C.ink],
  ["Critical text on tint", C.critical, C.criticalTint], ["Critical text on white", C.critical, C.surface],
  ["High text on tint", C.high, C.highTint], ["High text on white", C.high, C.surface],
  ["Moderate text on tint", C.moderate, C.moderateTint], ["Moderate text on white", C.moderate, C.surface],
  ["Low text on tint", C.low, C.lowTint], ["Low text on white", C.low, C.surface],
  ["error text on page", C.critical, C.paper], ["remove link on tint", C.critical, C.criticalTint],
  ["body text on amber highlight", C.ink, C.moderateTint], ["body text on red tint", C.ink, C.criticalTint],
  ["status chip text on white (amber)", C.moderate, C.surface],
];

let failed = 0;
for (const [name, fg, bg] of pairs) {
  const r = ratio(fg, bg);
  const ok = r >= 4.5;
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${r.toFixed(2).padStart(5)}:1  ${name}`);
}
console.log(failed ? `\n${failed} pair(s) below 4.5:1` : "\nAll text pairs meet WCAG AA (4.5:1).");
process.exit(failed ? 1 : 0);
