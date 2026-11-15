import { useCallback, useEffect, useState } from "react";
import { useErrorMessage } from "../context.jsx";

/** Load something once per key, with loading and error state. */
export function useLoad(loader, key) {
  const toMessage = useErrorMessage();
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const run = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      setState({ data: await loader(), loading: false, error: null });
    } catch (err) {
      setState({ data: null, loading: false, error: toMessage(err) });
    }
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { run(); }, [run]);
  const setData = useCallback((data) => setState({ data, loading: false, error: null }), []);
  return { ...state, reload: run, setData };
}
