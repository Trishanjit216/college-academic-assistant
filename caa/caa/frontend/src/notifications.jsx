import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "./api.js";
import Icon from "./icons.jsx";
import { Badge, Button, fmtDT } from "./pages/ui.jsx";

export const CHANGED = "caa-notifications-changed";     // other pages fire this after marking something read
const POLL_MS = 60_000;
const netMsg = (e) => (e instanceof TypeError ? "Can't reach the server. Check your connection." : e.message);
const safeLink = (l) => (typeof l === "string" && l.startsWith("/") && !l.startsWith("//") ? l : "");

/** One shared state for the bell buttons and the drawer. Everything is read from / written to the server. */
export function useNotifications() {
  const [state, setState] = useState({ unread: 0, items: null, error: "" });
  const [open, setOpen] = useState(false);
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const d = await api("/notifications/latest/");
      if (alive.current) setState({ unread: d.unread, items: d.items, error: "" });
    } catch (e) {
      if (alive.current) setState((s) => ({ ...s, error: netMsg(e) }));
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    refresh();
    const tick = () => { if (document.visibilityState === "visible") refresh(); };
    const t = setInterval(tick, POLL_MS);
    window.addEventListener("focus", tick);
    window.addEventListener(CHANGED, refresh);
    return () => { alive.current = false; clearInterval(t); window.removeEventListener("focus", tick); window.removeEventListener(CHANGED, refresh); };
  }, [refresh]);

  useEffect(() => { if (open) refresh(); }, [open, refresh]);

  const markRead = useCallback(async (id) => {
    setState((s) => ({ ...s, items: s.items?.map((n) => (n.id === id ? { ...n, read: true } : n)), unread: Math.max(0, s.unread - (s.items?.find((n) => n.id === id && !n.read) ? 1 : 0)) }));
    try { await api(`/notifications/${id}/read/`, { method: "POST" }); }
    catch (e) { setState((s) => ({ ...s, error: netMsg(e) })); refresh(); }
  }, [refresh]);

  const markAll = useCallback(async () => {
    setState((s) => ({ ...s, unread: 0, items: s.items?.map((n) => ({ ...n, read: true })) }));
    try { await api("/notifications/read_all/", { method: "POST" }); }
    catch (e) { setState((s) => ({ ...s, error: netMsg(e) })); refresh(); }
  }, [refresh]);

  return { ...state, open, setOpen, refresh, markRead, markAll };
}

export function BellButton({ unread, onClick, className = "" }) {
  const label = unread > 0 ? `Notifications, ${unread} unread` : "Notifications";
  return (
    <button className={`icon-btn bell-btn ${className}`} aria-label={label} aria-haspopup="dialog" onClick={onClick}>
      <Icon name="bell" />
      {unread > 0 && <span className="bell-count" aria-hidden="true">{unread > 9 ? "9+" : unread}</span>}
    </button>
  );
}

export function NotificationDrawer({ n }) {
  const nav = useNavigate();
  const ref = useRef(null);
  const closeRef = useRef(null);
  const { open, setOpen, items, unread, error } = n;

  useEffect(() => {
    if (!open) return undefined;
    const prev = document.activeElement;
    closeRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") { setOpen(false); return; }
      if (e.key !== "Tab" || !ref.current) return;
      const f = ref.current.querySelectorAll("button:not([disabled]), a[href]");
      if (!f.length) return;
      const a = f[0], z = f[f.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, [open, setOpen]);

  if (!open) return null;

  function openItem(item) {
    if (!item.read) n.markRead(item.id);
    const link = safeLink(item.link);
    setOpen(false);
    if (link) nav(link);
  }

  return (
    <div className="drawer-wrap">
      <div className="scrim" onClick={() => setOpen(false)} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="notif-title" ref={ref}>
        <div className="drawer-head">
          <h2 id="notif-title">Notifications</h2>
          <button ref={closeRef} className="icon-btn" aria-label="Close notifications" onClick={() => setOpen(false)}><Icon name="close" /></button>
        </div>
        <div className="drawer-tools">
          <span className="muted" role="status">{unread > 0 ? `${unread} unread` : "All caught up"}</span>
          <Button size="sm" variant="secondary" disabled={unread === 0} onClick={n.markAll}>Mark all as read</Button>
        </div>

        {error && (
          <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{error}</span>
            <button className="link-btn" onClick={n.refresh}>Retry</button></div>
        )}

        <div className="drawer-body">
          {items === null && !error && <p className="muted" role="status">Loading…</p>}
          {items && items.length === 0 && (
            <div className="empty empty-sm"><div className="empty-icon"><Icon name="bell" size={24} /></div>
              <h3>No notifications yet</h3><p className="muted">New events, syllabus updates and deadline reminders will appear here.</p></div>
          )}
          <ul className="notif-list">
            {(items || []).map((it) => {
              const link = safeLink(it.link);
              return (
                <li key={it.id} className={`notif ${it.read ? "is-read" : "is-unread"}`}>
                  <button className="notif-main" onClick={() => openItem(it)} aria-label={`${it.read ? "" : "Unread: "}${it.title}`}>
                    <span className="notif-title">{!it.read && <span className="unread-dot" aria-hidden="true" />}{it.title}</span>
                    {it.message && <span className="notif-msg">{it.message}</span>}
                    <span className="notif-meta muted">{fmtDT(it.created_at)}{link ? " · Tap to open" : ""}</span>
                  </button>
                  <div className="notif-actions">
                    {it.read ? <Badge>Read</Badge> : <button className="link-btn" onClick={() => n.markRead(it.id)}>Mark as read</button>}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="drawer-foot">
          <button className="link-btn" onClick={() => { setOpen(false); nav("/notifications"); }}>See all notifications</button>
        </div>
      </aside>
    </div>
  );
}
