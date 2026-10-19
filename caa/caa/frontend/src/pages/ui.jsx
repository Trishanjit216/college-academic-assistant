import { useEffect, useRef, useState } from "react";
import { list } from "../api.js";
import Icon from "../icons.jsx";

/* ---------- formatting helpers ---------- */
export const fmtDT = (s) => new Date(s).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
export const fmtD = (s) => (s ? new Date(s).toLocaleDateString("en-IN", { dateStyle: "medium" }) : "—");

/** Human deadline status. Text always carries the meaning; colour is secondary. */
export function dueInfo(deadline, done) {
  if (done) return { label: "Completed", tone: "success" };
  const ms = new Date(deadline) - Date.now();
  if (ms < 0) return { label: "Overdue", tone: "danger" };
  const h = Math.floor(ms / 36e5);
  if (h < 1) return { label: "Due within the hour", tone: "danger" };
  if (h < 24) return { label: `Due in ${h}h`, tone: "danger" };
  const d = Math.floor(h / 24);
  return { label: `Due in ${d} ${d === 1 ? "day" : "days"}`, tone: d <= 3 ? "warning" : "neutral" };
}

/* ---------- small building blocks ---------- */
export function Badge({ tone = "neutral", children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Button({ variant = "primary", size, loading = false, icon, children, className = "", disabled, ...rest }) {
  return (
    <button className={`btn btn-${variant} ${size === "sm" ? "btn-sm" : ""} ${className}`} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {icon && <Icon name={icon} size={18} />}
      {loading ? "Please wait…" : children}
    </button>
  );
}

export const Section = ({ title, action, children }) => (
  <section className="card section-card">
    <div className="section-head">
      <h2>{title}</h2>
      {action}
    </div>
    {children}
  </section>
);

export function PageHeader({ title, description, actions }) {
  useEffect(() => { document.title = `${title} · College Academic Assistant`; }, [title]);
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Skeleton({ lines = 3 }) {
  return (
    <div className="card skeleton-card" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton" style={{ width: i === 0 ? "45%" : i === lines - 1 ? "70%" : "100%" }} />
      ))}
    </div>
  );
}

export function SkeletonList({ count = 3 }) {
  return <div role="status" aria-label="Loading">{Array.from({ length: count }).map((_, i) => <Skeleton key={i} />)}</div>;
}

export function EmptyState({ icon = "inbox", title, children, action, className = "" }) {
  return (
    <div className={`empty ${className}`}>
      <div className="empty-icon"><Icon name={icon} size={24} /></div>
      <h3>{title}</h3>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="empty empty-error" role="alert">
      <div className="empty-icon"><Icon name="alert" size={24} /></div>
      <h3>Couldn't load this page</h3>
      <p className="muted">{message || "Check your internet connection and try again."}</p>
      {onRetry && <Button variant="secondary" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Field({ label, htmlFor, hint, children }) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

/** Accessible modal dialog: focus moves in, Tab is trapped, Esc closes, focus returns. */
export function Dialog({ open, title, onClose, children, footer }) {
  const ref = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const el = ref.current;
    const first = el && el.querySelector("input, textarea, select");
    (first || el)?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") { closeRef.current(); return; }
      if (e.key !== "Tab" || !el) return;
      const f = el.querySelectorAll('button:not([disabled]), [href], input, textarea, select, [tabindex]:not([tabindex="-1"])');
      if (!f.length) return;
      const a = f[0];
      const z = f[f.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); previous?.focus?.(); };
  }, [open]);

  if (!open) return null;
  return (
    <div className="overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-title" tabIndex={-1} ref={ref}>
        <h2 id="dlg-title">{title}</h2>
        {children}
        {footer && <div className="dialog-actions">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------- data loading ---------- */
export function useList(path, search) {
  const [items, setItems] = useState(null);
  const [err, setErr] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let cancelled = false;
    const sep = path.includes("?") ? "&" : "?";
    setErr("");
    const t = setTimeout(() => {
      list(`${path}${search ? `${sep}search=${encodeURIComponent(search)}` : ""}`)
        .then((d) => { if (!cancelled) setItems(d); })
        .catch((e) => { if (!cancelled) setErr(e.message); });
    }, search ? 250 : 0);
    return () => { cancelled = true; clearTimeout(t); };
  }, [path, search, tick]);
  return { items, err, reload: () => setTick((t) => t + 1) };
}

/** Standard list page: header, search, optional filter tabs, loading / empty / error states. */
export function ListPage({ title, description, path, searchable = true, filters, empty, actions, render, notice }) {
  const [q, setQ] = useState("");
  const [f, setF] = useState(filters ? filters[0].key : null);
  const { items, err, reload } = useList(path, q);
  const active = filters ? filters.find((x) => x.key === f) : null;
  const shown = items && active ? items.filter(active.test) : items;

  return (
    <div>
      <PageHeader title={title} description={description} actions={actions ? actions(reload, items) : null} />
      <div className="toolbar">
        {filters && (
          <div className="tabs" role="tablist" aria-label={`Filter ${title}`}>
            {filters.map((x) => (
              <button key={x.key} role="tab" aria-selected={f === x.key} className={`tab ${f === x.key ? "is-active" : ""}`} onClick={() => setF(x.key)}>
                {x.label}
              </button>
            ))}
          </div>
        )}
        {searchable && (
          <div className="search">
            <Icon name="search" size={18} />
            <input type="search" aria-label={`Search ${title}`} placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        )}
      </div>
      {notice && items ? notice(items) : null}
      {err && !items ? <ErrorState message={err} onRetry={reload} /> :
        !shown ? <SkeletonList /> :
        shown.length === 0 ? (
          <EmptyState title={q ? "No results found" : empty?.title || "Nothing here yet"}>
            {q ? "Try a different search term." : empty?.text || "Items will appear here once they are added."}
          </EmptyState>
        ) : <div className="stack">{shown.map((i) => render(i, reload))}</div>}
    </div>
  );
}


/* ---------- links ---------- */
/** Returns the URL if it is a real http(s) link, otherwise "". Blocks javascript:, data: and the like. */
export function safeUrl(value) {
  try {
    const u = new URL(String(value || "").trim());
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : "";
  } catch { return ""; }
}

const URL_RE = /((?:https?:\/\/|www\.)[^\s<>"']+)/gi;

/** Plain text in which every web address becomes a real, safe link (opens in a new tab). */
export function Linkify({ text }) {
  if (!text) return null;
  return String(text).split(URL_RE).map((part, i) => {
    if (i % 2 === 0) return part;
    const trail = (part.match(/[.,;:!?)\]]+$/) || [""])[0];
    const raw = trail ? part.slice(0, -trail.length) : part;
    const href = safeUrl(/^www\./i.test(raw) ? `https://${raw}` : raw);
    if (!href) return part;
    return <span key={i}><a className="text-link" href={href} target="_blank" rel="noopener noreferrer">{raw}</a>{trail}</span>;
  });
}

/** A link-styled button for an external address; renders nothing for a missing or invalid URL. */
export function ExternalButton({ href, children, variant = "secondary", size = "sm" }) {
  const url = safeUrl(href);
  if (!url) return null;
  return (
    <a className={`btn btn-${variant} btn-${size}`} href={url} target="_blank" rel="noopener noreferrer">
      {children}<Icon name="external" size={16} />
    </a>
  );
}
