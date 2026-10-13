const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "") + "/api";

const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
  del: (k) => { try { localStorage.removeItem(k); } catch {} },
};

export const tokens = {
  access: () => store.get("caa_access"),
  save: (a, r) => { store.set("caa_access", a); if (r) store.set("caa_refresh", r); },
  clear: () => { store.del("caa_access"); store.del("caa_refresh"); },
};

async function refresh() {
  const r = store.get("caa_refresh");
  if (!r) return false;
  const res = await fetch(`${BASE}/auth/refresh/`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh: r }),
  });
  if (!res.ok) return false;
  tokens.save((await res.json()).access);
  return true;
}

export async function api(path, { method = "GET", body, auth = true, blob = false } = {}, retry = true) {
  const form = typeof FormData !== "undefined" && body instanceof FormData;   // file uploads: let the browser set the boundary
  const headers = form ? {} : { "Content-Type": "application/json" };
  if (auth && tokens.access()) headers.Authorization = `Bearer ${tokens.access()}`;
  const res = await fetch(`${BASE}${path}`, { method, headers, body: body ? (form ? body : JSON.stringify(body)) : undefined });
  if (res.status === 401 && auth && retry && (await refresh())) return api(path, { method, body, auth, blob }, false);
  if (res.status === 401 && auth) { tokens.clear(); window.dispatchEvent(new Event("caa-logout")); }
  if (res.status === 204) return null;
  if (blob && res.ok) return res.blob();
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = data?.detail || (data && Object.entries(data).map(([k, v]) => `${k}: ${[].concat(v).join(" ")}`).join("; ")) || `Error ${res.status}`;
    const err = new Error(msg);
    err.status = res.status; err.code = data?.code; err.retryAfter = data?.retry_after;
    throw err;
  }
  return data;
}

export const list = async (path) => {
  const d = await api(path);
  return Array.isArray(d) ? d : d.results;
};
