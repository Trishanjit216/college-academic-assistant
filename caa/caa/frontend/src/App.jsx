import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, tokens } from "./api.js";
import Shell from "./Layout.jsx";
import Auth from "./pages/Auth.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import { Assignments, Events, Forms, Labs, Notifications, Records } from "./pages/Lists.jsx";
import Discussion from "./pages/Discussion.jsx";
import Moderation from "./pages/Moderation.jsx";

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

  if (!ready) return <div className="boot" role="status">Loading…</div>;
  if (!user) return (
    <Routes>
      <Route path="/login" element={<Auth onDone={() => { load().then(() => nav("/")); }} />} />
      <Route path="*" element={<Navigate to="/login" />} />
    </Routes>
  );

  const canModerate = ["admin", "moderator"].includes(user.role);
  return (
    <Shell user={user} onLogout={() => { tokens.clear(); setUser(null); nav("/login"); }}>
      <Routes>
        <Route path="/" element={<Dashboard user={user} />} />
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
    </Shell>
  );
}
