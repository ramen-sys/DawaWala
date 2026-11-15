import { useState } from "react";
import { api } from "../api/index.js";
import { Layout } from "../components/Layout.jsx";
import { Button, Notice, PageTitle, Spinner, TextField } from "../components/ui.jsx";
import { useErrorMessage } from "../context.jsx";
import { LIMITS } from "../lib/limits.js";
import { plural } from "../lib/format.js";
import { useLoad } from "../lib/useLoad.js";
import { navigate, paths } from "../router.js";

function statusOf(item) {
  const d = item.decision.status;
  if (d === "accepted") return { text: "Confirmed", tone: "ok" };
  if (d === "kept-unrecognised") return { text: "Will not be analysed", tone: "muted" };
  return { text: "Needs a decision", tone: "alert" };
}

function ItemCard({ item, listId, onChange, onError, onPick }) {
  const [editing, setEditing] = useState(null);
  const status = statusOf(item);
  const alert = status.tone === "alert";
  const run = async (fn) => { try { onChange(await fn()); } catch (e) { onError(e); } };
  // Show the choice at once; the server answer replaces it (or rolls it back).
  const decide = (decision) => {
    onPick(item.id, decision);
    run(() => api.decideItem(listId, item.id, decision));
  };

  return (
    <fieldset
      className={`border-b border-line px-4 py-4 sm:px-5 ${alert ? "border-l-[6px] border-l-moderate bg-moderate-tint" : "border-l-[6px] border-l-transparent bg-surface"}`}
    >
      <legend className="float-left mb-2 w-full">
        <span className="block text-sm text-ink-soft">{item.source === "ocr" ? "Read from a photo" : "You typed"}</span>
        <span className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-lg font-bold">“{item.raw}”</span>
          <span className={`rounded-md border px-2 py-0.5 text-sm font-semibold ${alert ? "border-moderate bg-surface text-moderate" : "border-ink-soft bg-surface text-ink"}`}>
            {alert && <span aria-hidden="true">▲ </span>}{status.text}
          </span>
        </span>
      </legend>

      <div className="clear-both">
        {item.candidates.length > 0 ? (
          <div role="radiogroup" aria-label={`Which medicine is “${item.raw}”?`} className="space-y-1">
            {item.candidates.map((c) => (
              <label key={c.medicationId} className="flex min-h-11 cursor-pointer items-start gap-3 rounded-md px-2 py-2 has-checked:bg-brand-tint hover:bg-brand-tint/60">
                <input
                  type="radio" className="mt-1.5 size-5 accent-brand"
                  name={`item-${item.id}`}
                  checked={item.decision.status === "accepted" && item.decision.medicationId === c.medicationId}
                  onChange={() => decide({ status: "accepted", medicationId: c.medicationId })}
                />
                <span>
                  <span className="font-semibold">{c.name}</span>
                  <span className="block text-sm text-ink-soft">
                    Match {c.score} out of 100, {c.label} confidence
                    {c.label === "Low" ? ". Check that this is the right medicine." : "."}
                  </span>
                </span>
              </label>
            ))}
          </div>
        ) : (
          <p className="text-ink">We could not match this name to a medicine in the knowledge base. Edit the text, remove it, or keep it as not analysed.</p>
        )}

        {editing !== null ? (
          <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => { const l = await api.editItem(listId, item.id, editing); setEditing(null); return l; }); }}>
            <TextField className="min-w-48 flex-1" label="Edit the text" value={editing} onChange={(e) => setEditing(e.target.value)} />
            <Button type="submit">Check again</Button>
            <Button variant="quiet" onClick={() => setEditing(null)}>Cancel</Button>
          </form>
        ) : (
          <div className="mt-2 flex flex-wrap gap-1">
            <Button variant="quiet" onClick={() => setEditing(item.raw)}>Edit text</Button>
            {item.decision.status !== "kept-unrecognised" && (
              <Button variant="quiet" onClick={() => decide({ status: "kept-unrecognised" })}>Keep as not analysed</Button>
            )}
            <Button variant="danger" onClick={() => run(() => api.removeItem(listId, item.id))} aria-label={`Remove ${item.raw}`}>Remove</Button>
          </div>
        )}
      </div>
    </fieldset>
  );
}

export function OcrConfirm({ listId }) {
  const toMessage = useErrorMessage();
  const { data: list, loading, error, setData, reload } = useLoad(() => api.getList(listId), listId);
  const [problem, setProblem] = useState("");
  const [extra, setExtra] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) return <Layout><Spinner label="Loading your list" /></Layout>;
  if (error) return <Layout><Notice tone="error" title="We could not open this list">{error}</Notice></Layout>;

  const items = list.items;
  const open = items.filter((i) => i.decision.status === "unresolved").length;
  const accepted = items.filter((i) => i.decision.status === "accepted").length;
  const canConfirm = open === 0 && accepted > 0;
  const reason = open > 0
    ? `Resolve ${plural(open, "more item")} to continue.`
    : accepted === 0 ? "Confirm at least one medicine to continue." : "";

  const update = (l) => { setProblem(""); setData(l); };
  const fail = (e) => { setProblem(toMessage(e)); reload(); };
  const pick = (itemId, decision) =>
    setData({ ...list, items: list.items.map((i) => (i.id === itemId ? { ...i, decision } : i)) });

  async function addExtra(e) {
    e.preventDefault();
    if (!extra.trim()) return;
    try { update(await api.addNames(listId, [extra])); setExtra(""); } catch (err) { fail(err); }
  }

  async function confirm() {
    setBusy(true);
    try { await api.confirmList(listId); navigate(paths.factors(listId)); }
    catch (err) { fail(err); }
    finally { setBusy(false); }
  }

  return (
    <Layout step="confirm" listId={listId}>
      <PageTitle sub="Check each name before we look for problems. A wrong name gives a wrong result, so take a moment to review every item.">
        Confirm your medicine names
      </PageTitle>

      {problem && <Notice tone="error" className="mb-4">{problem}</Notice>}

      <p className="mb-2 font-semibold" role="status">
        {items.length - open} of {items.length} resolved
        {open > 0 && <span className="font-normal text-ink-soft">. Items marked “Needs a decision” are highlighted.</span>}
      </p>

      {items.length === 0 ? (
        <Notice tone="warning">
          Your list is empty. <a className="font-semibold underline" href={`#${paths.medicines(listId)}`}>Add medicines</a> first.
        </Notice>
      ) : (
        <div className="border-t-2 border-ink">
          {items.map((item) => (
            <ItemCard key={item.id} item={item} listId={listId} onChange={update} onError={fail} onPick={pick} />
          ))}
        </div>
      )}

      <form onSubmit={addExtra} className="mt-6 flex flex-wrap items-end gap-3">
        <TextField className="min-w-56 flex-1" label="Add another medicine" value={extra} onChange={(e) => setExtra(e.target.value)} maxLength={LIMITS.NAME_MAX} autoComplete="off" />
        <Button type="submit" variant="secondary">Add</Button>
      </form>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <Button variant="secondary" onClick={() => navigate(paths.medicines(listId))}>Back</Button>
        <div className="text-right">
          <Button onClick={confirm} disabled={!canConfirm || busy} aria-describedby="confirm-reason">Confirm list</Button>
          <p id="confirm-reason" className="mt-1 text-sm text-ink-soft">{reason}</p>
        </div>
      </div>
    </Layout>
  );
}
