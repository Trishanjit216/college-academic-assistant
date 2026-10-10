import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, tokens } from "./api.js";
import Auth from "./pages/Auth.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import { Assignments, Events, Forms, Labs, Notifications, Records } from "./pages/Lists.jsx";
import Discussion from "./pages/Discussion.jsx";
import Moderation from "./pages/Moderation.jsx";

const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const nav = useNavigate();

  const load = () => api("/auth/me/").then(setUser).catch(() => setUser(null)).finally(() => setReady(true));
  useEffect(() => {
    tokens.access() ? load() : setReady(true);
    const out = () => { setUser(null); nav("/login"); };
    window.addEventListener("caa-logout", out);
    return () => window.removeEventListener("caa-logout", out);
  }, []);

  if (!ready) return <p className="center">Loading…</p>;
  if (!user) return (
    <Routes>
      <Route path="/login" element={<Auth onDone={() => { load().then(() => nav("/")); }} />} />
      <Route path="*" element={<Navigate to="/login" />} />
    </Routes>
  );

  const canModerate = ["admin", "moderator"].includes(user.role);
  const isStaff = ["admin", "faculty"].includes(user.role);
  return (
    <div className="shell">
      <header>
        <strong>📚 College Academic Assistant</strong>
        <span className="who">{user.first_name || user.username} · {user.role}</span>
        <button className="link" onClick={() => { tokens.clear(); setUser(null); nav("/login"); }}>Log out</button>
      </header>
      <nav>
        <NavLink to="/" end>Dashboard</NavLink>
        <NavLink to="/records">Classes</NavLink>
        <NavLink to="/labs">Labs</NavLink>
        <NavLink to="/assignments">Assignments</NavLink>
        <NavLink to="/events">Events</NavLink>
        <NavLink to="/forms">Forms</NavLink>
        <NavLink to="/discussion">Discussion</NavLink>
        <NavLink to="/notifications">Notifications</NavLink>
        {canModerate && <NavLink to="/moderation">Moderation</NavLink>}
        {isStaff && <a href={`${API}/admin/`} target="_blank" rel="noreferrer">Admin panel ↗</a>}
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/records" element={<Records />} />
          <Route path="/labs" element={<Labs />} />
          <Route path="/assignments" element={<Assignments />} />
          <Route path="/events" element={<Events />} />
          <Route path="/forms" element={<Forms />} />
          <Route path="/discussion" element={<Discussion />} />
          <Route path="/notifications" element={<Notifications />} />
          {canModerate && <Route path="/moderation" element={<Moderation />} />}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
