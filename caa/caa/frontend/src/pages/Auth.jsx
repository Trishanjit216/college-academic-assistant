import { useEffect, useState } from "react";
import { api, tokens } from "../api.js";
import Icon from "../icons.jsx";
import { Button, Field } from "./ui.jsx";

export default function Auth({ onDone }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ username: "", password: "", first_name: "", last_name: "", email: "", roll_no: "", group: "" });
  const [groups, setGroups] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const register = mode === "register";

  useEffect(() => { document.title = "Sign in · College Academic Assistant"; }, []);
  useEffect(() => { api("/groups/", { auth: false }).then(setGroups).catch(() => {}); }, []);

  async function submit(e) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      if (register) {
        const body = { ...f, group: f.group || null };
        await api("/auth/register/", { method: "POST", body, auth: false });
      }
      const t = await api("/auth/token/", { method: "POST", body: { username: f.username, password: f.password }, auth: false });
      tokens.save(t.access, t.refresh);
      onDone();
    } catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  }

  return (
    <div className="auth-wrap">
      <section className="auth-brand" aria-label="About College Academic Assistant">
        <div className="brand"><span className="brand-mark"><Icon name="logo" size={20} /></span><span className="brand-text">College Academic<br />Assistant</span></div>
        <h1>Everything you need for college, in one place.</h1>
        <p>Check what was taught, what's due and what's coming up, without scrolling through chat groups.</p>
        <ul className="auth-points">
          <li><Icon name="classes" size={18} />Period-wise class records</li>
          <li><Icon name="labs" size={18} />Lab experiments for your group</li>
          <li><Icon name="assignments" size={18} />Assignment deadlines and reminders</li>
          <li><Icon name="forms" size={18} />Document checklists for college forms</li>
        </ul>
      </section>

      <main className="auth-form">
        <form className="auth-card" onSubmit={submit} noValidate={false}>
          <div className="brand auth-mobile-brand"><span className="brand-mark"><Icon name="logo" size={20} /></span><span className="brand-text">College Academic Assistant</span></div>
          <h2>{register ? "Create your student account" : "Log in"}</h2>
          <span className="muted">{register ? "Use your roll number so classmates and faculty can recognise you." : "Welcome back. Enter your details to continue."}</span>

          <Field label="Username" htmlFor="username">
            <input id="username" autoComplete="username" value={f.username} onChange={set("username")} required />
          </Field>
          <Field label="Password" htmlFor="password" hint={register ? "At least 8 characters. Avoid common passwords." : undefined}>
            <input id="password" type="password" autoComplete={register ? "new-password" : "current-password"} value={f.password} onChange={set("password")} required />
          </Field>

          {register && (<>
            <Field label="First name" htmlFor="first_name"><input id="first_name" autoComplete="given-name" value={f.first_name} onChange={set("first_name")} /></Field>
            <Field label="Last name" htmlFor="last_name"><input id="last_name" autoComplete="family-name" value={f.last_name} onChange={set("last_name")} /></Field>
            <Field label="Email" htmlFor="email"><input id="email" type="email" autoComplete="email" value={f.email} onChange={set("email")} /></Field>
            <Field label="Roll number" htmlFor="roll_no"><input id="roll_no" value={f.roll_no} onChange={set("roll_no")} /></Field>
            <Field label="Lab group (optional)" htmlFor="group">
              <select id="group" value={f.group} onChange={set("group")}>
                <option value="">Not sure yet</option>
                {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
            </Field>
          </>)}

          {err && <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{err}</span></div>}
          <Button loading={busy}>{register ? "Create account" : "Log in"}</Button>
          <div className="auth-switch">
            <button type="button" className="link-btn" onClick={() => { setErr(""); setMode(register ? "login" : "register"); }}>
              {register ? "Already have an account? Log in" : "New student? Create an account"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
