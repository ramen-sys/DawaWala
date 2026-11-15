import { createContext, useCallback, useContext } from "react";

export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

const SESSION_CODES = new Set(["unauthorized", "session_expired"]);

/** Turn any thrown error into a message; end the session if it expired. */
export function useErrorMessage() {
  const { endSession } = useApp();
  return useCallback((err) => {
    if (err?.code && SESSION_CODES.has(err.code)) {
      endSession(err.message);
      return err.message;
    }
    return err?.message || "Something went wrong. Try again.";
  }, [endSession]);
}
