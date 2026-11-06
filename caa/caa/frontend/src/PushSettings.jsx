import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { useToast } from "./toast.jsx";
import { Badge, Button } from "./pages/ui.jsx";
import { browserSupport, disablePush, enablePush, firebaseConfigured, listenForeground, permission, savedToken, syncPush } from "./push.js";
import { CHANGED } from "./notifications.jsx";

let synced = false;   // keep the server in step once per page load, not on every visit to a page

/** Keeps this phone registered, and shows an in-app message when an alert arrives while CAA is open (so nothing is shown twice). */
export function usePushBackground() {
  const toast = useToast();
  useEffect(() => {
    let off = null, dead = false;
    (async () => {
      if (!savedToken() || !firebaseConfigured()) return;
      if (!synced) { synced = true; await syncPush(); }
      if (dead || !savedToken()) return;
      try {
        off = await listenForeground((d) => {
          window.dispatchEvent(new Event(CHANGED));                  // the bell updates straight away
          if (d.title && d.kind !== "test") toast(d.title);
          else if (d.kind === "test") toast("Test notification received. Phone notifications are working.");
        });
      } catch { /* firebase unavailable: the bell still polls */ }
    })();
    return () => { dead = true; if (typeof off === "function") off(); };
  }, []);
}

const ERRORS_TO_SHOW = ["denied", "dismissed", "unsupported", "not_configured", "register_failed", "no_token"];

export default function PushSettings() {
  const toast = useToast();
  const support = browserSupport();
  const [server, setServer] = useState(null);          // {configured, devices, events, syllabus}
  const [on, setOn] = useState(!!savedToken() && permission() === "granted");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(() => api("/push/status/").then(setServer).catch(() => setServer({ configured: false })), []);
  useEffect(() => { load(); }, [load]);

  const ready = firebaseConfigured() && server?.configured !== false;
  const blocked = permission() === "denied";

  async function turnOn() {
    setBusy("on"); setMsg("");
    try { await enablePush(); setOn(true); await load(); toast("Phone notifications are on"); }
    catch (e) { setMsg(ERRORS_TO_SHOW.includes(e.code) ? e.message : e.message || "Something went wrong. Please try again."); }
    finally { setBusy(""); }
  }
  async function turnOff() {
    setBusy("off"); setMsg("");
    try { await disablePush(); setOn(false); await load(); toast("Phone notifications are off on this phone"); }
    finally { setBusy(""); }
  }
  async function pref(key, value) {
    const before = server;
    setServer({ ...server, [key]: value });
    try { setServer(await api("/push/preferences/", { method: "POST", body: { [key]: value } }).then((r) => ({ ...before, ...r }))); }
    catch (e) { setServer(before); toast(e.message, "danger"); }
  }
  async function test() {
    setBusy("test"); setMsg("");
    try {
      const r = await api("/push/test/", { method: "POST" });
      if (r.sent) toast("Test sent. It should appear on your phone in a few seconds.");
      else setMsg("The test couldn't be delivered. Try turning notifications off and on again on this phone.");
      if (r.removed) setOn(false);
      load();
    } catch (e) { setMsg(e.message); } finally { setBusy(""); }
  }

  return (
    <section className="card push-card" aria-labelledby="push-title">
      <div className="push-head">
        <h2 id="push-title" className="push-title">Phone notifications</h2>
        {on && <Badge tone="success">On for this phone</Badge>}
      </div>

      {!support.ok ? (
        <p className="muted push-note">{support.reason}</p>
      ) : !ready && server ? (
        <p className="muted push-note">Phone notifications haven't been switched on for CAA yet. Your in-app notifications still work.</p>
      ) : on ? (
        <>
          <p className="muted push-note">You'll get an alert on this phone even when CAA is closed.</p>
          <div className="push-prefs" role="group" aria-label="Which alerts to receive">
            <label className="check"><input type="checkbox" checked={server?.events !== false} onChange={(e) => pref("events", e.target.checked)} /> New events for my group or section</label>
            <label className="check"><input type="checkbox" checked={server?.syllabus !== false} onChange={(e) => pref("syllabus", e.target.checked)} /> Syllabus published or updated</label>
          </div>
          <div className="push-actions">
            <Button variant="secondary" size="sm" loading={busy === "test"} onClick={test}>Send me a test</Button>
            <Button variant="ghost" size="sm" loading={busy === "off"} onClick={turnOff}>Turn off on this phone</Button>
          </div>
        </>
      ) : (
        <>
          <p className="push-note">Get an alert on your phone when:</p>
          <ul className="push-list">
            <li>a new event is published for your group or section</li>
            <li>a syllabus is published or updated</li>
          </ul>
          <p className="muted push-note">No spam, no ads. Your browser will ask for permission only after you tap the button, and you can turn this off any time.</p>
          {blocked && <p className="push-warn" role="alert">Notifications are blocked for this site. Tap the lock icon next to the address, choose Permissions → Notifications → Allow, then reload this page.</p>}
          <div className="push-actions">
            <Button loading={busy === "on"} onClick={turnOn} disabled={blocked || !server}>Enable Phone Notifications</Button>
          </div>
        </>
      )}
      {msg && <p className="push-warn" role="alert">{msg}</p>}
    </section>
  );
}
