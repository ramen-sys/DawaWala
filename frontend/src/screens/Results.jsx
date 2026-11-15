import { api } from "../api/index.js";
import { Layout } from "../components/Layout.jsx";
import { SeverityBadge } from "../components/SeverityBadge.jsx";
import { SeverityIcon } from "../components/Icons.jsx";
import { WarningItem } from "../components/WarningItem.jsx";
import { Button, LinkButton, Notice, PageTitle, Spinner } from "../components/ui.jsx";
import { DISCLAIMER } from "../lib/limits.js";
import { describeFactors, formatDate, formatDateTime, plural } from "../lib/format.js";
import { BANDS, BAND_STYLE } from "../lib/severity.js";
import { useLoad } from "../lib/useLoad.js";
import { href, paths } from "../router.js";

export function Results({ analysisId }) {
  const { data: a, loading, error } = useLoad(() => api.getAnalysis(analysisId), analysisId);

  if (loading) return <Layout><Spinner label="Loading your results" /></Layout>;
  if (error) return <Layout><Notice tone="error" title="We could not open these results">{error}</Notice></Layout>;

  const outdated = a.freshness === "outdated";
  const total = a.warnings.length;

  return (
    <Layout step="results" listId={a.listId} analysisId={a.id} wide>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <PageTitle sub={`${plural(a.medicines.length, "medicine")} checked: ${a.medicines.join(", ")}.`}>
          Your results
        </PageTitle>
        <Button variant="secondary" onClick={() => window.print()} className="print:hidden">Print or save as PDF</Button>
      </div>

      {/* SAF-02: shown on every results view and in print. */}
      <p className="mb-4 rounded-md border-2 border-ink bg-surface p-3 font-semibold" role="note">{DISCLAIMER}</p>

      {outdated && (
        <Notice tone="error" title="These results are out of date" className="mb-4">
          You changed your medicine list or patient factors after this check. Do not rely on it.{" "}
          <a className="font-semibold underline" href={href(paths.factors(a.listId))}>Run the check again</a>
        </Notice>
      )}
      {a.kb_notice && <Notice tone="warning" className="mb-4">{a.kb_notice}</Notice>}

      <section aria-labelledby="summary-h" className="mb-8">
        <h2 id="summary-h" className="mb-2 text-xl font-bold">
          {total === 0 ? "Summary" : `${plural(total, "warning")} found`}
        </h2>
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {BANDS.map((band) => (
            <li key={band} className={`rounded-md border p-3 ${BAND_STYLE[band].border} ${BAND_STYLE[band].tint}`}>
              <p className={`flex items-center gap-1.5 font-semibold ${BAND_STYLE[band].text}`}>
                <SeverityIcon band={band} />{band}
              </p>
              <p className="text-3xl font-bold leading-tight">{a.band_counts[band]}</p>
              <p className="text-sm text-ink-soft">score {BAND_STYLE[band].range}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="warnings-h" className={outdated ? "opacity-60" : ""}>
        <h2 id="warnings-h" className="border-b-2 border-ink pb-1 text-xl font-bold">
          Warnings, highest priority first
        </h2>
        {total === 0 ? (
          <div className="border-b border-line bg-surface p-5">
            <p className="text-lg font-semibold">No interactions were found in the knowledge base for the medicines analysed.</p>
            <p className="mt-1 max-w-prose text-ink-soft">
              That only means no rule matched. The knowledge base does not cover every medicine or every risk, so
              keep asking your doctor or pharmacist.
            </p>
          </div>
        ) : (
          a.warnings.map((w, i) => <WarningItem key={`${w.rule_id}-${i}`} warning={w} position={i} />)
        )}
      </section>

      <div className="mt-10 grid gap-8 md:grid-cols-2">
        <section aria-labelledby="na-h">
          <h2 id="na-h" className="border-b-2 border-ink pb-1 text-xl font-bold">Not analysed</h2>
          {a.not_analysed.length === 0 ? (
            <p className="py-3 text-ink-soft">Every medicine on your list was recognised and analysed.</p>
          ) : (
            <>
              <p className="py-2 text-ink-soft">We could not check these, so they are not covered by the results above.</p>
              <ul>
                {a.not_analysed.map((n) => (
                  <li key={n.text} className="border-b border-line py-2"><span className="font-semibold">{n.text}</span><br /><span className="text-sm text-ink-soft">{n.reason}</span></li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section aria-labelledby="nas-h">
          <h2 id="nas-h" className="border-b-2 border-ink pb-1 text-xl font-bold">Not assessed</h2>
          {a.not_assessed.length === 0 ? (
            <p className="py-3 text-ink-soft">No checks were skipped for missing patient information.</p>
          ) : (
            <>
              <p className="py-2 text-ink-soft">These checks need patient information you did not give.</p>
              <ul>
                {a.not_assessed.map((n) => (
                  <li key={n.medicationId + n.field} className="border-b border-line py-2">
                    {n.message}{" "}
                    <a className="font-semibold text-brand-dark underline" href={href(paths.factors(a.listId))}>Add {n.need}</a>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>

      <section aria-labelledby="about-h" className="mt-10 border-t border-line pt-4 text-ink-soft">
        <h2 id="about-h" className="mb-1 font-bold text-ink">About this result</h2>
        <p>
          Knowledge base {a.kb_version}, last updated {formatDate(a.kb_updated)}. Check run {formatDateTime(a.createdAt)}.
        </p>
        <p>
          Patient factors used:{" "}
          {describeFactors(a.factors).map((f) => `${f.title.toLowerCase()} ${f.value.toLowerCase()}`).join(", ")}.
        </p>
        <p>The knowledge base covers a limited set of medicines. Its rules need review by a pharmacist or doctor before any real-world use.</p>
      </section>

      <div className="mt-8 flex flex-wrap gap-3 print:hidden">
        <LinkButton href={href(paths.newList())}>Check another list</LinkButton>
        <LinkButton href={href(paths.history())}>View history</LinkButton>
      </div>
    </Layout>
  );
}
