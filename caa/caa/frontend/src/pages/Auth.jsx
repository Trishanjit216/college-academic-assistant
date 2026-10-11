import { useEffect, useRef, useState } from "react";
import { api, tokens } from "../api.js";
import Icon from "../icons.jsx";
import { Button, Field } from "./ui.jsx";

const NETWORK_MSG = "Can't reach the server. Check your connection and try again.";
const friendly = (ex) => (ex instanceof TypeError ? NETWORK_MSG : ex.message);

export default function Auth({ onDone }) {
  const [mode, setMode] = useState("login"); // login | register | verify
  const [f, setF] = useState({ identifier: "", password: "", name: "", email: "", roll_no: "", group: "" });
  const [groups, setGroups] = useState([]);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");
  const [pending, setPending] = useState({ email: "", masked: "", expiresIn: 600 });
  const [cooldown, setCooldown] = useState(0);
  const [resending, setResending] = useState(false);
  const codeRef = useRef(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const register = mode === "register";
  const verify = mode === "verify";

  useEffect(() => { document.title = "Sign in · College Academic Assistant"; }, []);
  useEffect(() => { api("/groups/", { auth: false }).then(setGroups).catch(() => {}); }, []);
  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const id = setTimeout(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);
  useEffect(() => { if (verify) codeRef.current?.focus(); }, [verify]);

  function switchMode(next) { setErr(""); setInfo(""); setMode(next); }

  async function login(identifier, password) {
    const t = await api("/auth/token/", { method: "POST", body: { username: identifier, password }, auth: false });
    tokens.save(t.access, t.refresh);
    onDone();
  }

  function enterVerify(res, message) {
    setPending({ email: res.email, masked: res.masked_email, expiresIn: res.expires_in || 600 });
    setCooldown(res.resend_in ?? 60);
    setCode(""); setErr(""); setInfo(message || "");
    setMode("verify");
  }

  async function submit(e) {
    e.preventDefault(); setErr(""); setInfo(""); setBusy(true);
    try {
      if (register) {
        const body = { name: f.name, email: f.email, password: f.password, roll_no: f.roll_no, group: f.group || null };
        const res = await api("/auth/register/", { method: "POST", body, auth: false });
        enterVerify(res);
      } else {
        await login(f.identifier, f.password);
      }
    } catch (ex) {
      if (ex.code === "cooldown" && ex.retryAfter) setCooldown(ex.retryAfter);
      setErr(friendly(ex));
    } finally { setBusy(false); }
  }

  async function submitCode(e) {
    e.preventDefault(); setErr(""); setInfo("");
    if (!/^\d{6}$/.test(code)) { setErr("Enter the 6-digit code from your email."); return; }
    setBusy(true);
    try {
      await api("/auth/verify-otp/", { method: "POST", body: { email: pending.email, otp: code }, auth: false });
      setInfo("Email verified. Logging you in…");
      try { await login(pending.email, f.password); }
      catch { switchMode("login"); setF((s) => ({ ...s, identifier: pending.email, password: "" })); setInfo("Email verified. Please log in."); }
    } catch (ex) {
      if (ex.code === "email_taken") { setF((s) => ({ ...s, identifier: pending.email, password: "" })); setMode("login"); }
      if (ex.code === "expired" || ex.code === "too_many_attempts" || ex.code === "not_found") setCode("");
      if (ex.code === "too_many_attempts" && ex.retryAfter) setCooldown(ex.retryAfter);
      setErr(friendly(ex));
    } finally { setBusy(false); }
  }

  async function resend() {
    setErr(""); setInfo(""); setResending(true);
    try {
      const res = await api("/auth/resend-otp/", { method: "POST", body: { email: pending.email }, auth: false });
      enterVerify(res, "A new code has been sent. Earlier codes no longer work.");
    } catch (ex) {
      if (ex.retryAfter) setCooldown(ex.retryAfter);
      setErr(friendly(ex));
    } finally { setResending(false); }
  }

  const brand = (
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
  );
  const mobileBrand = <div className="brand auth-mobile-brand"><span className="brand-mark"><Icon name="logo" size={20} /></span><span className="brand-text">College Academic Assistant</span></div>;
  const errBox = err && <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{err}</span></div>;
  const infoBox = info && <div className="form-info" role="status"><span>{info}</span></div>;

  if (verify) {
    return (
      <div className="auth-wrap">
        {brand}
        <main className="auth-form">
          <form className="auth-card" onSubmit={submitCode}>
            {mobileBrand}
            <h2>Verify your email</h2>
            <span className="muted">We sent a 6-digit code to <strong>{pending.masked}</strong>. It expires in {Math.round(pending.expiresIn / 60)} minutes. Check your spam folder if you can't find it.</span>
            <Field label="Verification code" htmlFor="otp">
              <input id="otp" ref={codeRef} className="otp-input" inputMode="numeric" pattern="[0-9]*" maxLength={6}
                autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="000000" />
            </Field>
            {infoBox}{errBox}
            <Button loading={busy}>Verify and continue</Button>
            <div className="auth-switch otp-actions">
              <button type="button" className="link-btn" onClick={resend} disabled={cooldown > 0 || resending}>
                {resending ? "Sending…" : cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
              </button>
              <button type="button" className="link-btn" onClick={() => switchMode("register")}>Use a different email</button>
            </div>
          </form>
        </main>
      </div>
    );
  }

  return (
    <div className="auth-wrap">
      {brand}
      <main className="auth-form">
        <form className="auth-card" onSubmit={submit}>
          {mobileBrand}
          <h2>{register ? "Create your student account" : "Log in"}</h2>
          <span className="muted">{register ? "We'll email you a code to confirm your address." : "Welcome back. Enter your details to continue."}</span>

          {register ? (<>
            <Field label="Full name" htmlFor="name"><input id="name" autoComplete="name" value={f.name} onChange={set("name")} required /></Field>
            <Field label="Email" htmlFor="email"><input id="email" type="email" autoComplete="email" value={f.email} onChange={set("email")} required /></Field>
          </>) : (
            <Field label="Email or username" htmlFor="identifier">
              <input id="identifier" autoComplete="username" value={f.identifier} onChange={set("identifier")} required />
            </Field>
          )}
          <Field label="Password" htmlFor="password" hint={register ? "At least 8 characters. Avoid common passwords." : undefined}>
            <input id="password" type="password" autoComplete={register ? "new-password" : "current-password"} value={f.password} onChange={set("password")} required />
          </Field>

          {register && (<>
            <Field label="Roll number (optional)" htmlFor="roll_no"><input id="roll_no" value={f.roll_no} onChange={set("roll_no")} /></Field>
            <Field label="Lab group (optional)" htmlFor="group">
              <select id="group" value={f.group} onChange={set("group")}>
                <option value="">Not sure yet</option>
                {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
            </Field>
          </>)}

          {infoBox}{errBox}
          <Button loading={busy}>{register ? "Send verification code" : "Log in"}</Button>
          <div className="auth-switch">
            <button type="button" className="link-btn" onClick={() => switchMode(register ? "login" : "register")}>
              {register ? "Already have an account? Log in" : "New student? Create an account"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
