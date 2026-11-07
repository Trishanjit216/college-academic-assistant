import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import Logo from "../Logo.jsx";
import { Button, Field } from "./ui.jsx";

const netMsg = (e) => (e instanceof TypeError ? "Can't reach the server. Check your connection and try again." : e.message);
const post = (step, body) => api(`/auth/password-reset/${step}/`, { method: "POST", auth: false, body });

/** Forgot password for one portal ("student" or "faculty"): email -> 6-digit code -> new password -> done. */
export default function ForgotPassword({ portal }) {
  const faculty = portal === "faculty";
  const loginPath = faculty ? "/faculty/login" : "/login";
  const nav = useNavigate();
  const [stage, setStage] = useState("email");                 // email | otp | password | done
  const [email, setEmail] = useState("");
  const [masked, setMasked] = useState("");
  const [code, setCode] = useState("");
  const [token, setToken] = useState("");
  const [pw, setPw] = useState({ password: "", password2: "" });
  const [cooldown, setCooldown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const codeRef = useRef(null);

  useEffect(() => { document.title = "Forgot password · College Academic Assistant"; }, []);
  useEffect(() => { if (cooldown <= 0) return undefined; const t = setTimeout(() => setCooldown((c) => c - 1), 1000); return () => clearTimeout(t); }, [cooldown]);
  useEffect(() => { if (stage === "otp") codeRef.current?.focus(); }, [stage]);
  useEffect(() => { if (stage !== "done") return undefined; const t = setTimeout(() => nav(loginPath), 6000); return () => clearTimeout(t); }, [stage, nav, loginPath]);

  const startOver = (msg = "") => { setStage("email"); setCode(""); setToken(""); setPw({ password: "", password2: "" }); setInfo(""); setErr(msg); };

  async function sendCode(e, isResend = false) {
    e?.preventDefault(); setErr(""); setInfo("");
    const addr = email.trim().toLowerCase();
    if (!addr.includes("@") || addr.includes(" ")) { setErr("Enter the email address registered with your account."); return; }
    isResend ? setResending(true) : setBusy(true);
    try {
      const r = await post("request", { portal, email: addr });
      setEmail(addr); setMasked(r.masked_email); setCooldown(r.resend_in ?? 60); setCode(""); setStage("otp");
      setInfo(isResend ? "A new code was requested. The previous code no longer works." : "");
    } catch (ex) {
      if (ex.status === 429 && ex.retryAfter) setCooldown(Math.min(ex.retryAfter, 3600));
      setErr(netMsg(ex));
      if (ex.status === 429 && stage === "email" && ex.code === "cooldown") { setMasked(addr.replace(/^(.).*(@.*)$/, "$1***$2")); setStage("otp"); }
    } finally { setBusy(false); setResending(false); }
  }

  async function verify(e) {
    e.preventDefault(); setErr(""); setInfo("");
    if (!/^\d{6}$/.test(code)) { setErr("Enter the 6-digit code from your email."); return; }
    setBusy(true);
    try { const r = await post("verify", { portal, email, otp: code }); setToken(r.reset_token); setStage("password"); }
    catch (ex) { setErr(netMsg(ex)); if (ex.code === "too_many_attempts") setCode(""); } finally { setBusy(false); }
  }

  async function save(e) {
    e.preventDefault(); setErr("");
    if (pw.password.length < 8) { setErr("Your password must be at least 8 characters."); return; }
    if (pw.password !== pw.password2) { setErr("The two passwords do not match."); return; }
    setBusy(true);
    try { await post("confirm", { portal, email, reset_token: token, password: pw.password, password2: pw.password2 }); setStage("done"); }
    catch (ex) {
      if (ex.code === "invalid_token") startOver(ex.message);
      else setErr(netMsg(ex));
    } finally { setBusy(false); }
  }

  const errBox = err && <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{err}</span></div>;
  const infoBox = info && <div className="form-info" role="status"><span>{info}</span></div>;
  const steps = ["email", "otp", "password"];
  const at = steps.indexOf(stage);

  return (
    <div className="fp-wrap">
      <div className="fp-brand"><span className="brand-mark"><Logo size={26} /></span><span>College Academic Assistant</span></div>
      <div className="auth-card fp-card">
        {stage !== "done" && (
          <ol className="fp-steps" aria-label="Progress">
            {["Your email", "Verify code", "New password"].map((l, i) => (
              <li key={l} className={i < at ? "is-done" : i === at ? "is-now" : ""} aria-current={i === at ? "step" : undefined}><span>{i < at ? "✓" : i + 1}</span>{l}</li>
            ))}
          </ol>
        )}

        {stage === "email" && (
          <form onSubmit={(e) => sendCode(e)} noValidate>
            <h2>Forgot your {faculty ? "faculty " : ""}password?</h2>
            <span className="muted">Enter the email address registered with your {faculty ? "faculty" : "student"} account. We'll email you a 6-digit code.</span>
            <Field label="Registered email" htmlFor="fp-email" hint="Mobile numbers can't be used for password recovery.">
              <input id="fp-email" type="email" inputMode="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Field>
            {errBox}
            <Button loading={busy}>Send code</Button>
          </form>
        )}

        {stage === "otp" && (
          <form onSubmit={verify}>
            <h2>Enter the code</h2>
            <span className="muted">If <strong>{masked}</strong> belongs to a {faculty ? "faculty" : "student"} account, we sent a 6-digit code to it. It expires in 5 minutes. Check your spam folder too.</span>
            <Field label="6-digit code" htmlFor="fp-otp">
              <input id="fp-otp" ref={codeRef} className="otp-input" inputMode="numeric" pattern="[0-9]*" maxLength={6} autoComplete="one-time-code"
                value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" />
            </Field>
            {infoBox}{errBox}
            <Button loading={busy}>Verify code</Button>
            <div className="auth-switch otp-actions">
              <button type="button" className="link-btn" disabled={cooldown > 0 || resending} onClick={() => sendCode(null, true)}>
                {resending ? "Sending…" : cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
              </button>
              <button type="button" className="link-btn" onClick={() => startOver()}>Use a different email</button>
            </div>
          </form>
        )}

        {stage === "password" && (
          <form onSubmit={save}>
            <h2>Create a new password</h2>
            <span className="muted">Code verified. Choose a new password. You'll be signed out of any other devices.</span>
            <Field label="New password" htmlFor="fp-pw" hint="At least 8 characters. Avoid common passwords.">
              <input id="fp-pw" type="password" autoComplete="new-password" autoFocus value={pw.password} onChange={(e) => setPw({ ...pw, password: e.target.value })} required />
            </Field>
            <Field label="Confirm new password" htmlFor="fp-pw2">
              <input id="fp-pw2" type="password" autoComplete="new-password" value={pw.password2} onChange={(e) => setPw({ ...pw, password2: e.target.value })} required />
            </Field>
            {errBox}
            <Button loading={busy}>Change password</Button>
          </form>
        )}

        {stage === "done" && (
          <div className="fp-done" role="status">
            <span className="fp-tick"><Icon name="check" size={28} /></span>
            <h2>Password changed</h2>
            <p className="muted">Your password was changed successfully. Log in with your new password.</p>
            <Button type="button" onClick={() => nav(loginPath)}>Go to {faculty ? "faculty " : ""}login</Button>
          </div>
        )}

        {stage !== "done" && (
          <div className="auth-switch"><Link to={loginPath} className="link-btn">← Back to {faculty ? "faculty " : ""}login</Link></div>
        )}
      </div>
    </div>
  );
}
