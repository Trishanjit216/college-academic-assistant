import { useEffect, useState } from "react";
import { api, tokens } from "../api.js";

export default function Auth({ onDone }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ username: "", password: "", first_name: "", last_name: "", email: "", roll_no: "", group: "" });
  const [groups, setGroups] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => { api("/groups/", { auth: false }).then(setGroups).catch(() => {}); }, []);

  async function submit(e) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      if (mode === "register") {
        const body = { ...f, group: f.group || null };
        await api("/auth/register/", { method: "POST", body, auth: false });
      }
      const t = await api("/auth/token/", { method: "POST", body: { username: f.username, password: f.password }, auth: false });
      tokens.save(t.access, t.refresh);
      onDone();
    } catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  }

  return (
    <form className="card auth" onSubmit={submit}>
      <h1>College Academic Assistant</h1>
      <p className="muted">Everything you need for college, in one place.</p>
      <input placeholder="Username" value={f.username} onChange={set("username")} required />
      <input placeholder="Password" type="password" value={f.password} onChange={set("password")} required />
      {mode === "register" && (<>
        <input placeholder="First name" value={f.first_name} onChange={set("first_name")} />
        <input placeholder="Last name" value={f.last_name} onChange={set("last_name")} />
        <input placeholder="Email" type="email" value={f.email} onChange={set("email")} />
        <input placeholder="Roll number" value={f.roll_no} onChange={set("roll_no")} />
        <select value={f.group} onChange={set("group")}>
          <option value="">Lab group (optional)</option>
          {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select>
      </>)}
      {err && <p className="error">{err}</p>}
      <button disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Log in" : "Create student account"}</button>
      <button type="button" className="link" onClick={() => { setErr(""); setMode(mode === "login" ? "register" : "login"); }}>
        {mode === "login" ? "New student? Sign up" : "Have an account? Log in"}
      </button>
    </form>
  );
}
