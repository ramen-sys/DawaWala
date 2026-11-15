import { useRef, useState } from "react";
import { api } from "../api/index.js";
import { Button, Notice, TextField } from "../components/ui.jsx";
import { CapsuleMark } from "../components/Icons.jsx";
import { EMAIL_PATTERN, passwordProblems } from "../lib/limits.js";
import { navigate, paths } from "../router.js";
import { useApp } from "../context.jsx";

export function AuthScreen() {
  const { setUser, sessionMessage, demo } = useApp();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "User" });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(sessionMessage || "");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const heading = useRef(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const switchMode = (m) => {
    setMode(m); setFieldErrors({}); setFormError(""); setSuccess("");
    heading.current?.focus();
  };

  async function submit(e) {
    e.preventDefault();
    setFormError(""); setSuccess("");
    const errors = {};
    if (!EMAIL_PATTERN.test(form.email.trim())) errors.email = "Enter an email address like name@example.com.";
    if (mode === "register") {
      if (!form.name.trim()) errors.name = "Enter your name.";
      const problems = passwordProblems(form.password);
      if (problems.length) errors.password = problems.join(" ");
    } else if (!form.password) {
      errors.password = "Enter your password.";
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;

    setBusy(true);
    try {
      if (mode === "register") {
        const res = await api.register(form);
        setMode("login");
        setForm((f) => ({ ...f, password: "" }));
        setSuccess(res.message);
      } else {
        const { user } = await api.login(form);
        setUser(user);
        navigate(paths.newList());
      }
    } catch (err) {
      if (err.fields && Object.keys(err.fields).length) setFieldErrors(err.fields);
      else setFormError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";
  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center gap-3">
          <span className="grid size-12 place-items-center rounded-md bg-ink"><CapsuleMark className="size-9" /></span>
          <div>
            <p className="text-2xl font-bold leading-none">Dawawala</p>
            <p className="text-ink-soft">Check a medicine list for possible problems</p>
          </div>
        </div>

        <h1 ref={heading} tabIndex={-1} id="page-title" className="mb-4 text-3xl font-bold tracking-tight">
          {isLogin ? "Log in" : "Create an account"}
        </h1>

        {success && <Notice tone="success" className="mb-4">{success}</Notice>}
        {formError && <Notice tone="error" className="mb-4">{formError}</Notice>}

        <form onSubmit={submit} noValidate className="space-y-4">
          {!isLogin && (
            <TextField label="Name" autoComplete="name" value={form.name} onChange={set("name")} error={fieldErrors.name} />
          )}
          <TextField
            label="Email" type="email" autoComplete="email" inputMode="email"
            value={form.email} onChange={set("email")} error={fieldErrors.email}
          />
          <TextField
            label="Password" type="password"
            autoComplete={isLogin ? "current-password" : "new-password"}
            value={form.password} onChange={set("password")} error={fieldErrors.password}
            hint={isLogin ? undefined : "At least 8 characters, with a letter and a number."}
          />
          {!isLogin && (
            <div>
              <label htmlFor="role" className="mb-1 block font-semibold">I am signing up as</label>
              <select id="role" value={form.role} onChange={set("role")} className="min-h-11 w-full rounded-md border border-ink-soft bg-surface px-3 text-base">
                <option value="User">A patient or healthcare professional</option>
                <option value="Admin">A healthcare professional who maintains the medicine data</option>
              </select>
              {fieldErrors.role && <p className="mt-1 text-sm font-semibold text-critical">{fieldErrors.role}</p>}
            </div>
          )}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Please wait…" : isLogin ? "Log in" : "Create account"}
          </Button>
        </form>

        <p className="mt-6">
          {isLogin ? "New to Dawawala? " : "Already have an account? "}
          <button type="button" onClick={() => switchMode(isLogin ? "register" : "login")} className="font-semibold text-brand-dark underline underline-offset-4">
            {isLogin ? "Create an account" : "Log in"}
          </button>
        </p>
        {demo && (
          <p className="mt-8 border-t border-line pt-4 text-sm text-ink-soft">
            Demo mode: create any account to try the app. Nothing leaves this browser.
          </p>
        )}
      </div>
    </div>
  );
}
