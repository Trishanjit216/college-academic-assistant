import { useEffect, useState } from "react";
import { list } from "../api.js";

export const fmtDT = (s) => new Date(s).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
export const fmtD = (s) => (s ? new Date(s).toLocaleDateString("en-IN", { dateStyle: "medium" }) : "—");

export const Section = ({ title, children }) => (
  <section className="card"><h2>{title}</h2>{children}</section>
);

/** Generic searchable list page. */
export function useList(path, search) {
  const [items, setItems] = useState(null);
  const [err, setErr] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const sep = path.includes("?") ? "&" : "?";
    const t = setTimeout(() => {
      list(`${path}${search ? `${sep}search=${encodeURIComponent(search)}` : ""}`)
        .then(setItems).catch((e) => setErr(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [path, search, tick]);
  return { items, err, reload: () => setTick((t) => t + 1) };
}

export function Page({ title, searchable = true, path, render }) {
  const [q, setQ] = useState("");
  const { items, err, reload } = useList(path, q);
  return (
    <div>
      <div className="bar"><h1>{title}</h1>
        {searchable && <input className="search" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />}
      </div>
      {err && <p className="error">{err}</p>}
      {!items ? <p>Loading…</p> : items.length === 0 ? <p className="muted">Nothing here yet.</p> : items.map((i) => render(i, reload))}
    </div>
  );
}
