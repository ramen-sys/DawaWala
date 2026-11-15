import { api } from "../api/index.js";
import { Layout } from "../components/Layout.jsx";
import { LinkButton, Notice, PageTitle, Spinner } from "../components/ui.jsx";
import { formatDateTime, plural } from "../lib/format.js";
import { useLoad } from "../lib/useLoad.js";
import { href, paths } from "../router.js";

export function statusOfList(list) {
  if (list.status === "draft") return { text: "Draft", detail: "Not confirmed yet" };
  if (list.analysisStatus === "current") return { text: "Analysed", detail: "Results are up to date" };
  if (list.analysisStatus === "outdated") return { text: "Results out of date", detail: "Run the check again" };
  return { text: "Confirmed", detail: "Ready to check" };
}

export function History() {
  const { data: lists, loading, error } = useLoad(() => api.listLists(), "history");

  return (
    <Layout wide>
      <PageTitle sub="Your earlier medicine lists and checks, newest first.">History</PageTitle>
      {loading && <Spinner label="Loading your history" />}
      {error && <Notice tone="error" title="We could not load your history">{error}</Notice>}
      {lists && lists.length === 0 && (
        <div className="border-t-2 border-ink py-8">
          <p className="text-lg font-semibold">No checks yet.</p>
          <p className="mb-4 text-ink-soft">Add the medicines you take, and we will look for possible problems.</p>
          <LinkButton variant="primary" href={href(paths.newList())}>Start a check</LinkButton>
        </div>
      )}
      {lists && lists.length > 0 && (
        <ul className="border-t-2 border-ink">
          {lists.map((l) => {
            const st = statusOfList(l);
            const names = l.items.map((i) => i.raw);
            const latest = l.analyses[l.analyses.length - 1];
            const continueTo = l.status === "draft" ? paths.confirm(l.id) : paths.factors(l.id);
            return (
              <li key={l.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-4 py-4">
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{plural(l.items.length, "medicine")}: {names.slice(0, 4).join(", ")}{names.length > 4 ? ` and ${names.length - 4} more` : ""}</p>
                  <p className="text-ink-soft">{formatDateTime(l.updatedAt)}</p>
                  <p className="mt-1">
                    <span className="rounded-md border border-ink-soft px-2 py-0.5 text-sm font-semibold">{st.text}</span>
                    <span className="ml-2 text-sm text-ink-soft">{st.detail}</span>
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {latest && <LinkButton href={href(paths.results(latest.id))} aria-label={`Open results for list from ${formatDateTime(l.updatedAt)}`}>Open results</LinkButton>}
                  <LinkButton href={href(continueTo)} aria-label={`${l.status === "draft" ? "Continue" : "Re-run check"} for list from ${formatDateTime(l.updatedAt)}`}>{l.status === "draft" ? "Continue" : "Re-run check"}</LinkButton>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Layout>
  );
}
