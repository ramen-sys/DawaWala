import { useEffect, useState } from "react";
import { api } from "../api/index.js";
import { Layout } from "../components/Layout.jsx";
import { Button, Notice, PageTitle, Spinner } from "../components/ui.jsx";
import { useErrorMessage } from "../context.jsx";
import { FACTOR_OPTIONS, FACTOR_TITLES } from "../lib/format.js";
import { useLoad } from "../lib/useLoad.js";
import { navigate, paths } from "../router.js";

const HELP = {
  age_range: "Some medicines carry more risk from age 65.",
  kidney_function: "Some medicines build up when the kidneys work less well.",
  liver_function: "Some medicines are broken down by the liver.",
};

export function PatientFactors({ listId }) {
  const toMessage = useErrorMessage();
  const { data: list, loading, error } = useLoad(() => api.getList(listId), listId);
  const [factors, setFactors] = useState(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  useEffect(() => { if (list) setFactors({ ...list.factors }); }, [list]);

  if (loading || !factors) {
    return <Layout>{error ? <Notice tone="error" title="We could not open this list">{error}</Notice> : <Spinner label="Loading" />}</Layout>;
  }

  const changed = JSON.stringify(factors) !== JSON.stringify(list.factors);
  const hadResult = list.analysisStatus !== "none";
  const allUnknown = Object.values(factors).every((v) => v === "unknown");

  async function run() {
    setBusy(true); setProblem("");
    try {
      await api.saveFactors(listId, factors);
      const analysis = await api.runAnalysis(listId);
      navigate(paths.results(analysis.id));
    } catch (err) {
      setProblem(toMessage(err));
      setBusy(false);
    }
  }

  return (
    <Layout step="factors" listId={listId}>
      <PageTitle sub="This step is optional. Your answers only refine the contraindication checks and the priority score. Leave a question as Unknown if you are not sure.">
        Patient factors
      </PageTitle>

      {hadResult && changed && (
        <Notice tone="warning" title="You changed these answers" className="mb-4">
          Your earlier result is now out of date. Run the check again to update it.
        </Notice>
      )}
      {problem && <Notice tone="error" className="mb-4">{problem}</Notice>}

      <div className="space-y-6">
        {Object.keys(FACTOR_TITLES).map((key) => (
          <fieldset key={key}>
            <legend className="text-lg font-bold">{FACTOR_TITLES[key]}</legend>
            <p className="mb-2 text-ink-soft">{HELP[key]}</p>
            <div className="flex flex-wrap gap-2">
              {FACTOR_OPTIONS[key].map(([value, label]) => (
                <label
                  key={value}
                  className="flex min-h-11 min-w-28 cursor-pointer items-center gap-2 rounded-md border border-ink-soft bg-surface px-3 py-2 has-checked:border-brand-dark has-checked:bg-brand-tint has-checked:font-bold has-checked:ring-2 has-checked:ring-brand-dark has-focus-visible:outline-3 has-focus-visible:outline-offset-2 has-focus-visible:outline-brand-dark"
                >
                  <input
                    type="radio" name={key} value={value} className="size-5 accent-brand"
                    checked={factors[key] === value}
                    onChange={() => setFactors({ ...factors, [key]: value })}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      </div>

      <div className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <Button variant="secondary" onClick={() => navigate(paths.confirm(listId))}>Back</Button>
        <Button onClick={run} disabled={busy}>
          {busy ? "Checking…" : allUnknown ? "Skip and run the check" : "Run the check"}
        </Button>
      </div>
    </Layout>
  );
}
