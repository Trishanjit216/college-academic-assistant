import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import Icon from "./icons.jsx";
import { useTheme } from "./theme.js";
import { safeUrl } from "./pages/ui.jsx";

export const FACULTY_URL = safeUrl(import.meta.env.VITE_FACULTY_URL);
const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

function groupsFor(user) {
  const canModerate = ["admin", "moderator"].includes(user.role);
  const isStaff = ["admin", "faculty"].includes(user.role);
  const groups = [
    { label: "Overview", items: [{ to: "/", label: "Dashboard", icon: "dashboard", end: true }] },
    { label: "Academics", items: [
      { to: "/records", label: "Classes", icon: "classes" },
      { to: "/labs", label: "Labs", icon: "labs" },
      { to: "/assignments", label: "Assignments", icon: "assignments" },
      { to: "/syllabus", label: "Syllabus", icon: "syllabus" },
      { to: "/seats", label: "Exam seats", icon: "seat" },
    ] },
    { label: "Campus", items: [
      { to: "/events", label: "Events", icon: "events" },
      { to: "/forms", label: "Forms", icon: "forms" },
      ...(FACULTY_URL ? [{ href: FACULTY_URL, label: "Know Your Faculty", icon: "user" }] : []),
    ] },
    { label: "Community", items: [
      { to: "/discussion", label: "Discussion", icon: "discussion" },
      { to: "/notifications", label: "Notifications", icon: "bell" },
    ] },
  ];
  const admin = [];
  if (canModerate) admin.push({ to: "/moderation", label: "Moderation", icon: "shield" });
  if (isStaff) admin.push({ href: `${API}/admin/`, label: "Admin panel", icon: "external" });
  if (admin.length) groups.push({ label: "Administration", items: admin });
  return groups;
}

const initials = (u) =>
  ((u.first_name?.[0] || u.username[0] || "?") + (u.last_name?.[0] || "")).toUpperCase();

export default function Shell({ user, onLogout, children }) {
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
    if (open) closeBtn.current?.focus();
    else if (wasOpen.current) menuBtn.current?.focus();
    wasOpen.current = open;
    return () => { document.body.style.overflow = ""; document.removeEventListener("keydown", onKey); };
  }, [open]);

  const themeLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <div className="app">
      <a className="skip-link" href="#main">Skip to main content</a>

      <header className="topbar">
        <button ref={menuBtn} className="icon-btn" aria-label="Open navigation menu" aria-expanded={open} aria-controls="sidebar" onClick={() => setOpen(true)}>
          <Icon name="menu" />
        </button>
        <div className="brand brand-sm"><span className="brand-mark"><Icon name="logo" size={18} /></span><span>Academic Assistant</span></div>
        <button className="icon-btn" aria-label={themeLabel} onClick={toggleTheme}>
          <Icon name={theme === "dark" ? "sun" : "moon"} />
        </button>
      </header>

      {open && <div className="scrim" onClick={() => setOpen(false)} />}

      <aside id="sidebar" className={`sidebar ${open ? "is-open" : ""}`} aria-label="Main navigation">
        <div className="sidebar-top">
          <div className="brand">
            <span className="brand-mark"><Icon name="logo" size={20} /></span>
            <span className="brand-text">College Academic<br />Assistant</span>
          </div>
          <button ref={closeBtn} className="icon-btn only-mobile" aria-label="Close navigation menu" onClick={() => setOpen(false)}>
            <Icon name="close" />
          </button>
        </div>

        <nav className="nav">
          {groupsFor(user).map((g) => (
            <div className="nav-group" key={g.label}>
              <div className="nav-label">{g.label}</div>
              {g.items.map((it) => it.href ? (
                <a key={it.label} className="nav-link" href={it.href} target="_blank" rel="noopener noreferrer">
                  <Icon name={it.icon} size={18} /><span>{it.label}</span>
                </a>
              ) : (
                <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `nav-link ${isActive ? "is-active" : ""}`}>
                  <Icon name={it.icon} size={18} /><span>{it.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="user">
            <NavLink to="/profile" className="user-link" aria-label="Your profile">
              <span className="avatar" aria-hidden="true">{initials(user)}</span>
              <span className="user-text">
                <strong>{user.first_name || user.username}</strong>
                <span className="muted">{user.role}{user.section ? ` · ${user.section}` : ""}</span>
              </span>
            </NavLink>
          </div>
          <div className="foot-actions">
            <button className="icon-btn only-desktop" aria-label={themeLabel} onClick={toggleTheme}>
              <Icon name={theme === "dark" ? "sun" : "moon"} />
            </button>
            <button className="btn btn-ghost btn-sm" onClick={onLogout}><Icon name="logout" size={16} />Log out</button>
          </div>
        </div>
      </aside>

      <main id="main" className="main" tabIndex={-1}>
        <div className="container">{children}</div>
      </main>
    </div>
  );
}
