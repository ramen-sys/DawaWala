import { SeverityIcon } from "./Icons.jsx";
import { BAND_STYLE } from "../lib/severity.js";

/** Band name in words plus an icon, so colour is never the only signal. */
export function SeverityBadge({ band, count, className = "" }) {
  const s = BAND_STYLE[band];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-semibold ${s.text} ${s.tint} ${s.border} ${className}`}>
      <SeverityIcon band={band} />
      <span>{band}</span>
      {count !== undefined && <span className="ml-1 font-bold">{count}</span>}
    </span>
  );
}
