import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api/index.js";
import { AppContext } from "./context.jsx";
import { Layout } from "./components/Layout.jsx";
import { Notice, Spinner } from "./components/ui.jsx";
import { navigate, paths } from "./router.js";
import { useRoute } from "./useRoute.js";
import { AuthScreen } from "./screens/AuthScreen.jsx";
import { History } from "./screens/History.jsx";
import { MedicationEntry } from "./screens/MedicationEntry.jsx";
import { OcrConfirm } from "./screens/OcrConfirm.jsx";
import { PatientFactors } from "./screens/PatientFactors.jsx";
import { Results } from "./screens/Results.jsx";

const SESSION_CHECK_MS = 30_000;

function NewList() {
  useEffect(() => {
    let alive = true;
    api.createList().then((l) => alive && navigate(paths.medicines(l.id))).catch(() => alive && navigate(paths.history()));
    return () => { alive = false; };
  }, []);
  return <Layout><Spinner label="Starting a new check" /></Layout>;
}

export default function App() {
  const route = useRoute();
  const [user, setUser] = useState(undefined); // undefined = still checking
  const [sessionMessage, setSessionMessage] = useState("");

  useEffect(() => {
    let alive = true;
    api.currentUser().then((u) => alive && setUser(u));
    return () => { alive = false; };
  }, []);

  const endSession = useCallback((message = "") => {
    setSessionMessage(message);
    setUser(null);
    navigate(paths.login());
  }, []);

  // Tokens last 30 minutes (SEC-02): notice an expired session without a click.
  useEffect(() => {
    if (!user) return undefined;
    const t = setInterval(async () => {
      if (!(await api.currentUser())) endSession("Your session ended. Log in again.");
    }, SESSION_CHECK_MS);
    return () => clearInterval(t);
  }, [user, endSession]);

  // Move focus to the page title after each screen change (keyboard users).
  useEffect(() => { document.getElementById("page-title")?.focus({ preventScroll: false }); }, [route.path, user]);

  const ctx = useMemo(() => ({
    user, setUser: (u) => { setSessionMessage(""); setUser(u); },
    endSession, sessionMessage, demo: api.mode === "mock",
    logout: async () => { await api.logout(); endSession(""); },
  }), [user, endSession, sessionMessage]);

  if (user === undefined) return <AppContext.Provider value={ctx}><Layout><Spinner /></Layout></AppContext.Provider>;

  let screen;
  if (!user) {
    if (route.path !== paths.login()) queueMicrotask(() => navigate(paths.login()));
    screen = <AuthScreen />;
  } else {
    switch (route.name) {
      case "login": queueMicrotask(() => navigate(paths.history())); screen = null; break;
      case "new": screen = <NewList />; break;
      case "history": screen = <History />; break;
      case "medicines": screen = <MedicationEntry key={route.params.listId} listId={route.params.listId} />; break;
      case "confirm": screen = <OcrConfirm key={route.params.listId} listId={route.params.listId} />; break;
      case "factors": screen = <PatientFactors key={route.params.listId} listId={route.params.listId} />; break;
      case "results": screen = <Results key={route.params.analysisId} analysisId={route.params.analysisId} />; break;
      default:
        screen = (
          <Layout>
            <Notice tone="warning" title="We could not find that page">
              Go to your <a className="font-semibold underline" href={`#${paths.history()}`}>history</a> or start a <a className="font-semibold underline" href={`#${paths.newList()}`}>new check</a>.
            </Notice>
          </Layout>
        );
    }
  }
  return <AppContext.Provider value={ctx}>{screen}</AppContext.Provider>;
}
