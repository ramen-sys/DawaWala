// The screens import `api` from here only. To connect the real backend,
// replace this with a client that calls the REST endpoints and returns the
// same shapes (see README, "Connecting the real backend").
import { browserStorage, createMockApi } from "./mockApi.js";

export const api = createMockApi({ storage: browserStorage(), delayMs: 120 });
export { ApiError } from "./errors.js";
