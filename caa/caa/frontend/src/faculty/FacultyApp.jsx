import Logo from "../Logo.jsx";
import { Navigate, Route, Routes } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useNotifications } from "../notifications.jsx";
import ManageExams from "../pages/ManageExams.jsx";
import { ErrorState } from "../pages/ui.jsx";
import FacultyShell from "./FacultyLayout.jsx";
import { FacultyDashboard, FacultyEvents, FacultyGroups, FacultySyllabus } from "./FacultyPages.jsx";

/** Everything a faculty member sees after login. Only /faculty/* exists here; student routes are not mounted at all. */
export default function FacultyApp({ user, onLogout }) {
  const [me, setMe] = useState(null);
  const [err, setErr] = useState("");
  const notif = useNotifications();
  const load = () => { setErr(""); api("/faculty/me/").then(setMe).catch((e) => setErr(e instanceof TypeError ? "Can't reach the server. Check your connection and try again." : e.message)); };
  useEffect(load, []);

  if (err) return <div className="fac-boot"><ErrorState message={err} onRetry={load} /><button className="link-btn" onClick={onLogout}>Log out</button></div>;
  if (!me) return <div className="boot" role="status"><div className="boot-logo"><span className="brand-mark"><Logo size={72} /></span><span>Loading…</span></div></div>;
  return (
    <FacultyShell user={user} me={me} onLogout={onLogout} notif={notif}>
      <Routes>
        <Route path="/faculty" element={<FacultyDashboard user={user} me={me} notif={notif} />} />
        <Route path="/faculty/events" element={<FacultyEvents me={me} />} />
        <Route path="/faculty/syllabus" element={<FacultySyllabus me={me} />} />
        <Route path="/faculty/groups" element={<FacultyGroups />} />
        <Route path="/faculty/seats" element={<ManageExams user={user} />} />
        <Route path="*" element={<Navigate to="/faculty" />} />
      </Routes>
    </FacultyShell>
  );
}
