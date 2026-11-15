// Tiny hash router, so the app needs no server-side routing and no extra
// dependency. Example URL: index.html#/lists/list3/confirm
const ROUTES = [
  { name: "login", pattern: /^\/login$/ },
  { name: "new", pattern: /^\/new$/ },
  { name: "history", pattern: /^\/history$/ },
  { name: "medicines", pattern: /^\/lists\/([^/]+)\/medicines$/, keys: ["listId"] },
  { name: "confirm", pattern: /^\/lists\/([^/]+)\/confirm$/, keys: ["listId"] },
  { name: "factors", pattern: /^\/lists\/([^/]+)\/factors$/, keys: ["listId"] },
  { name: "results", pattern: /^\/analyses\/([^/]+)$/, keys: ["analysisId"] },
];

export function parseHash(hash) {
  const path = (hash || "").replace(/^#/, "") || "/history";
  for (const route of ROUTES) {
    const m = path.match(route.pattern);
    if (m) {
      const params = {};
      (route.keys || []).forEach((k, i) => { params[k] = decodeURIComponent(m[i + 1]); });
      return { name: route.name, params, path };
    }
  }
  return { name: "notfound", params: {}, path };
}

export const paths = {
  login: () => "/login",
  newList: () => "/new",
  history: () => "/history",
  medicines: (id) => `/lists/${id}/medicines`,
  confirm: (id) => `/lists/${id}/confirm`,
  factors: (id) => `/lists/${id}/factors`,
  results: (id) => `/analyses/${id}`,
};

export const href = (path) => `#${path}`;
export const navigate = (path) => { window.location.hash = path; };
