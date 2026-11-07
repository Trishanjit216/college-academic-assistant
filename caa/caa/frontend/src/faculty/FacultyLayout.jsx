import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import Icon from "../icons.jsx";
import { useTheme } from "../theme.js";
import { BellButton, NotificationDrawer, useNotifications } from "../notifications.jsx";

const initials = (u) => ((u.first_name?.[0] || u.username[0] || "?") + (u.last_name?.[0] || "")).toUpperCase();

export function navFor(me) {
  const items = [{ to: "/faculty", label: "Dashboard", icon: "dashboard", end: true }];
  if (me?.can_manage_events) items.push({ to: "/faculty/events", label: "My events", icon: "events" });
  if (me?.can_manage_syllabus) items.push({ to: "/faculty/syllabus", label: "Syllabus", icon: "syllabus" });
  items.push({ to: "/faculty/groups", label: "Groups & sections", icon: "classes" });
  items.push({ to: "/faculty/seats", label: "Exam seats", icon: "seat" });
  return items;
}

/** Faculty-only shell: its own dark sidebar, mobile drawer, bell and logout. Nothing from the student shell is reused. */
export default function FacultyShell({ user, me, onLogout, notif, children }) {
  const [open, setOpen] = useState(false);
  const [theme, toggleTheme] = useTheme();
  const { pathname } = useLocation();
  const menuBtn = useRef(null);
  const closeBtn = useRef(null);
  const wasOpen = useRef(false);

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    if (open) closeBtn.current?.focus(); else if (wasOpen.current) menuBtn.current?.focus();
    wasOpen.current = open;
    return () => { document.body.style.overflow = ""; document.removeEventListener("keydown", onKey); };
  }, [open]);

  const themeLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username;

  return (
    <div className="fac-app">
      <a className="skip-link" href="#fac-main">Skip to main content</a>
      <header className="fac-topbar">
        <button ref={menuBtn} className="icon-btn" aria-label="Open faculty menu" aria-expanded={open} aria-controls="fac-side" onClick={() => setOpen(true)}><Icon name="menu" /></button>
        <div className="fac-top-title"><Icon name="logo" size={18} /><span>Faculty portal</span></div>
        <div className="fac-top-actions">
          <BellButton unread={notif.unread} onClick={() => notif.setOpen(true)} />
          <button className="icon-btn" aria-label={themeLabel} onClick={toggleTheme}><Icon name={theme === "dark" ? "sun" : "moon"} /></button>
        </div>
      </header>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}

      <aside id="fac-side" className={`fac-side ${open ? "is-open" : ""}`} aria-label="Faculty navigation">
        <div className="fac-side-top">
          <div className="fac-brand"><span className="fac-brand-mark"><Icon name="logo" size={20} /></span><span><strong>Faculty portal</strong><small>College Academic Assistant</small></span></div>
          <button ref={closeBtn} className="icon-btn only-mobile fac-close" aria-label="Close faculty menu" onClick={() => setOpen(false)}><Icon name="close" /></button>
        </div>
        <nav className="fac-nav">
          {navFor(me).map((it) => (
            <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `fac-link ${isActive ? "is-active" : ""}`}>
              <Icon name={it.icon} size={18} /><span>{it.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="fac-side-foot">
          <div className="fac-who">
            <span className="fac-avatar" aria-hidden="true">{initials(user)}</span>
            <span className="fac-who-text"><strong>{name}</strong><small>{me?.designation || "Faculty"}</small></span>
          </div>
          <div className="fac-foot-actions">
            <BellButton className="only-desktop" unread={notif.unread} onClick={() => notif.setOpen(true)} />
            <button className="icon-btn only-desktop" aria-label={themeLabel} onClick={toggleTheme}><Icon name={theme === "dark" ? "sun" : "moon"} /></button>
            <button className="fac-logout" onClick={onLogout}><Icon name="logout" size={16} />Log out</button>
          </div>
        </div>
      </aside>

      <main id="fac-main" className="fac-main" tabIndex={-1}><div className="fac-container">{children}</div></main>
      <NotificationDrawer n={notif} />
    </div>
  );
}
