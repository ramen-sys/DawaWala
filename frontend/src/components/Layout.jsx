import { CapsuleMark } from "./Icons.jsx";
import { Button } from "./ui.jsx";
import { href, paths } from "../router.js";
import { useApp } from "../context.jsx";

const STEPS = [
  { key: "medicines", label: "Add medicines" },
  { key: "confirm", label: "Confirm names" },
  { key: "factors", label: "Patient factors" },
  { key: "results", label: "Results" },
];

function Stepper({ current, listId, analysisId }) {
  const link = {
    medicines: listId && paths.medicines(listId),
    confirm: listId && paths.confirm(listId),
    factors: listId && paths.factors(listId),
    results: analysisId && paths.results(analysisId),
  };
  const idx = STEPS.findIndex((s) => s.key === current);
  return (
    <nav aria-label="Progress" className="mb-6 print:hidden">
      <ol className="flex flex-wrap gap-x-1 gap-y-2">
        {STEPS.map((s, i) => {
          const active = i === idx;
          const content = (
            <>
              <span aria-hidden="true" className={`grid size-6 place-items-center rounded-full text-sm font-bold ${active ? "bg-brand text-white" : "bg-line text-ink"}`}>{i + 1}</span>
              <span className={active ? "font-bold" : ""}>{s.label}</span>
            </>
          );
          return (
            <li key={s.key} className="flex items-center">
              {link[s.key] && !active ? (
                <a href={href(link[s.key])} className="flex items-center gap-2 rounded-md px-2 py-2 text-ink underline-offset-4 hover:bg-brand-tint hover:underline">{content}</a>
              ) : (
                <span aria-current={active ? "step" : undefined} className={`flex items-center gap-2 px-2 py-2 ${active ? "" : "text-ink-soft"}`}>{content}</span>
              )}
              {i < STEPS.length - 1 && <span aria-hidden="true" className="mx-1 hidden h-px w-5 bg-ink-soft sm:block" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function Layout({ children, step, listId, analysisId, wide = false }) {
  const { user, logout, demo } = useApp();
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:font-semibold">
        Skip to main content
      </a>
      <header className="bg-ink text-white print:bg-transparent print:text-ink">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3">
          <a href={href(paths.history())} className="flex items-center gap-2 text-xl font-bold tracking-tight text-white print:text-ink">
            <CapsuleMark />
            Dawawala
          </a>
          {user ? (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 print:hidden">
              <a href={href(paths.newList())} className="rounded-md px-2 py-2 text-white underline-offset-4 hover:underline">New check</a>
              <a href={href(paths.history())} className="rounded-md px-2 py-2 text-white underline-offset-4 hover:underline">History</a>
              <span className="text-white/85">
                <span className="sr-only">Signed in as </span>
                {user.name} ({user.role})
              </span>
              <Button variant="secondary" onClick={logout} className="!min-h-10 !border-white !bg-transparent !text-white hover:!bg-white/15">
                Log out
              </Button>
            </div>
          ) : null}
        </div>
      </header>

      <main id="main" className={`mx-auto w-full flex-1 px-4 py-8 ${wide ? "max-w-5xl" : "max-w-3xl"}`}>
        {step && <Stepper current={step} listId={listId} analysisId={analysisId} />}
        {children}
      </main>

      <footer className="border-t border-line bg-surface print:border-0">
        <div className="mx-auto flex max-w-5xl flex-wrap justify-between gap-2 px-4 py-4 text-sm text-ink-soft">
          <p>Dawawala is decision support only. It does not diagnose or replace a doctor or pharmacist.</p>
          {demo && <p className="font-semibold">Demo mode: sample data, saved only in this browser.</p>}
        </div>
      </footer>
    </div>
  );
}
