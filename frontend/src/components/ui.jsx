import { useId } from "react";

const BTN_BASE =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 py-2 " +
  "text-base font-semibold transition-colors disabled:cursor-not-allowed";

const BTN_VARIANT = {
  primary:
    "bg-brand text-white hover:bg-brand-dark disabled:bg-line disabled:text-ink-soft",
  secondary:
    "border border-ink-soft bg-surface text-ink hover:bg-brand-tint disabled:border-line disabled:text-ink-soft",
  quiet: "px-2 text-brand-dark underline underline-offset-4 hover:bg-brand-tint disabled:text-ink-soft",
  danger: "px-2 text-critical underline underline-offset-4 hover:bg-critical-tint disabled:text-ink-soft",
};

export function Button({ variant = "primary", className = "", type = "button", ...props }) {
  return <button type={type} className={`${BTN_BASE} ${BTN_VARIANT[variant]} ${className}`} {...props} />;
}

export function LinkButton({ variant = "secondary", className = "", ...props }) {
  return <a className={`${BTN_BASE} ${BTN_VARIANT[variant]} no-underline ${className}`} {...props} />;
}

/** Label + input + inline error + hint, wired with aria-describedby. */
export function TextField({ label, error, hint, className = "", inputRef, ...props }) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errId = `${id}-err`;
  const describedBy = [hint && hintId, error && errId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block font-semibold">{label}</label>
      <input
        id={id}
        ref={inputRef}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        className={`min-h-11 w-full rounded-md border bg-surface px-3 py-2 text-base ${
          error ? "border-critical border-2" : "border-ink-soft"
        }`}
        {...props}
      />
      {hint && <p id={hintId} className="mt-1 text-sm text-ink-soft">{hint}</p>}
      {error && (
        <p id={errId} className="mt-1 flex items-start gap-1 text-sm font-semibold text-critical">
          <span aria-hidden="true">!</span>
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}

const NOTICE_STYLE = {
  info: "border-brand bg-brand-tint text-ink",
  error: "border-critical bg-critical-tint text-ink",
  warning: "border-moderate bg-moderate-tint text-ink",
  success: "border-brand bg-brand-tint text-ink",
};

const NOTICE_ICON = { info: "i", error: "!", warning: "!", success: "✓" };

/** Message box. Errors use role=alert so screen readers announce them. */
export function Notice({ tone = "info", title, children, className = "" }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex gap-3 rounded-md border-l-4 border-y border-r p-3 ${NOTICE_STYLE[tone]} ${className}`}
    >
      <span aria-hidden="true" className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-ink text-sm font-bold text-white">
        {NOTICE_ICON[tone]}
      </span>
      <div>
        {title && <p className="font-semibold">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  );
}

export function PageTitle({ children, sub }) {
  return (
    <div className="mb-6">
      <h1 className="text-3xl font-bold leading-tight tracking-tight" tabIndex={-1} id="page-title">
        {children}
      </h1>
      {sub && <p className="mt-2 max-w-prose text-ink-soft">{sub}</p>}
    </div>
  );
}

export function Spinner({ label = "Loading" }) {
  return (
    <p role="status" className="py-10 text-ink-soft">
      <span className="mr-2 inline-block size-4 animate-spin rounded-full border-2 border-brand border-t-transparent align-[-2px] motion-reduce:animate-none" aria-hidden="true" />
      {label}…
    </p>
  );
}
