import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, tokens } from "../api.js";
import Logo from "../Logo.jsx";
import Icon from "../icons.jsx";
import { Button, Field } from "../pages/ui.jsx";

const friendly = (ex) => (ex instanceof TypeError ? "Can't reach the server. Check your connection and try again." : ex.message);

/** Faculty sign-in (email/username + password) and first-time activation (access code + new password). */
export default function FacultyAuth({ onDone }) {
  const [mode, setMode] = useState("login");           // login | activate
  const [f, setF] = useState({ identifier: "", password: "", code: "", password2: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const activate = mode === "activate";

  useEffect(() => { document.title = "Faculty sign in · College Academic Assistant"; }, []);
  const switchMode = (m) => { setErr(""); setMode(m); setF((s) => ({ ...s, password: "", password2: "", code: "" })); };

  async function submit(e) {
    e.preventDefault(); setErr("");
    if (activate && f.password !== f.password2) { setErr("The two passwords do not match."); return; }
    setBusy(true);
    try {
      const t = activate
        ? await api("/auth/faculty/activate/", { method: "POST", auth: false, body: { identifier: f.identifier.trim(), code: f.code, password: f.password, password2: f.password2 } })
        : await api("/auth/faculty/token/", { method: "POST", auth: false, body: { username: f.identifier.trim(), password: f.password } });
      tokens.save(t.access, t.refresh);
      onDone();
    } catch (ex) { setErr(friendly(ex)); } finally { setBusy(false); }
  }

  return (
    <div className="fac-auth">
      <section className="fac-auth-side" aria-label="Faculty portal">
        <div className="brand"><span className="brand-mark"><Logo size={20} /></span><span className="brand-text">College Academic<br />Assistant</span></div>
        <h1>Faculty portal</h1>
        <p>Publish events and syllabus updates for your students. Students are notified automatically.</p>
        <ul className="fac-points">
          <li><Icon name="shield" size={18} />Your own access code. Never shared.</li>
          <li><Icon name="events" size={18} />Events for your groups and sections</li>
          <li><Icon name="syllabus" size={18} />Syllabus for your subjects</li>
        </ul>
      </section>
      <main className="fac-auth-main">
        <form className="auth-card" onSubmit={submit}>
          <div className="fac-switch" role="group" aria-label="Choose login type">
            <Link to="/login" className="fac-switch-btn">Student Login</Link>
            <span className="fac-switch-btn is-active" aria-current="page">Faculty Login</span>
          </div>
          <h2>{activate ? "Activate your faculty account" : "Faculty log in"}</h2>
          <span className="muted">
            {activate ? "Enter the access code your administrator gave you, then choose your own password. The code works once." : "Enter your email or username and your password."}
          </span>

          <Field label="Email or username" htmlFor="fid"><input id="fid" autoComplete="username" value={f.identifier} onChange={set("identifier")} required /></Field>
          {activate && (
            <Field label="Access code" htmlFor="fcode" hint="Looks like ABCD-EFGH-JKLM.">
              <input id="fcode" className="fac-code-input" autoComplete="off" autoCapitalize="characters" spellCheck={false} value={f.code} onChange={set("code")} placeholder="XXXX-XXXX-XXXX" required />
            </Field>
          )}
          <Field label={activate ? "Choose a password" : "Password"} htmlFor="fpw" hint={activate ? "At least 8 characters. Avoid common passwords." : undefined}>
            <input id="fpw" type="password" autoComplete={activate ? "new-password" : "current-password"} value={f.password} onChange={set("password")} required />
          </Field>
          {activate && (
            <Field label="Confirm password" htmlFor="fpw2"><input id="fpw2" type="password" autoComplete="new-password" value={f.password2} onChange={set("password2")} required /></Field>
          )}

          {err && <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{err}</span></div>}
          <Button loading={busy}>{activate ? "Activate and log in" : "Log in"}</Button>
          <div className="auth-switch">
            <button type="button" className="link-btn" onClick={() => switchMode(activate ? "login" : "activate")}>
              {activate ? "Already activated? Log in" : "First time, or got a new code? Activate your account"}
            </button>
          </div>
          <p className="muted fac-note">Faculty accounts are created by the administrator. There is no self sign-up.</p>
        </form>
      </main>
    </div>
  );
}
