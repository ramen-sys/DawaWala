import { ScoreLedger } from "./ScoreLedger.jsx";
import { SeverityBadge } from "./SeverityBadge.jsx";
import { BAND_STYLE, categoryLabel } from "../lib/severity.js";

export function WarningItem({ warning, position }) {
  const s = BAND_STYLE[warning.band];
  const title = warning.medicines.join(" + ");
  return (
    <article
      aria-labelledby={`w-${position}`}
      className={`border-l-[6px] ${s.edge} border-b border-line bg-surface px-4 py-5 sm:px-6`}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <SeverityBadge band={warning.band} />
            <span className="text-ink-soft">{categoryLabel(warning)}</span>
          </div>
          <h3 id={`w-${position}`} className="text-xl font-bold leading-snug">{title}</h3>
        </div>
        <p className="text-right leading-none" aria-label={`Score ${warning.score} out of 100`}>
          <span className={`block text-5xl font-bold ${s.text}`}>{warning.score}</span>
          <span className="text-sm text-ink-soft">out of 100</span>
        </p>
      </div>

      <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <ScoreLedger warning={warning} />
        <div>
          <h4 className="mb-1 font-semibold">What this means</h4>
          <p className="max-w-prose">{warning.explanation}</p>
        </div>
      </div>
    </article>
  );
}
