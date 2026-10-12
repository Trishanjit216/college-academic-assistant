import { useEffect, useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { checkSection } from "../sections.js";
import { useToast } from "../toast.jsx";
import { Button, Field, PageHeader } from "./ui.jsx";
import GroupSection from "./GroupSection.jsx";

export default function Profile({ user, onSaved }) {
  const toast = useToast();
  const [groups, setGroups] = useState([]);
  const [f, setF] = useState({ group: user.group || "", section: user.section || "", roll_no: user.roll_no || "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const rollLocked = !!user.roll_no;

  useEffect(() => { document.title = "Your profile · College Academic Assistant"; }, []);
  useEffect(() => { api("/groups/", { auth: false }).then(setGroups).catch(() => {}); }, []);

  async function save(e) {
    e.preventDefault(); setErr("");
    const gname = groups.find((g) => String(g.id) === String(f.group))?.name;
    const bad = checkSection(gname, f.section);
    if (bad) { setErr(bad); return; }
    setBusy(true);
    try {
      const body = { group: f.group || null, section: f.section };
      if (!rollLocked && f.roll_no.trim()) body.roll_no = f.roll_no.trim();
      await api("/auth/me/", { method: "PATCH", body });
      toast("Profile saved");
      onSaved?.();
    } catch (ex) { setErr(ex instanceof TypeError ? "Can't reach the server. Try again." : ex.message); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <PageHeader title="Your profile" description="Your group, section and roll number help us show the right labs and exam seat." />
      <form className="card profile-card" onSubmit={save}>
        <p className="muted">{user.first_name} {user.last_name} · {user.email || user.username}</p>
        <Field label="Roll number" htmlFor="p-roll" hint={rollLocked ? "Set. Ask an administrator if it needs changing." : "You can set this once."}>
          <input id="p-roll" value={f.roll_no} disabled={rollLocked} onChange={(e) => setF({ ...f, roll_no: e.target.value })} />
        </Field>
        <GroupSection idPrefix="p-" groups={groups} group={f.group} section={f.section} onChange={(v) => setF((s) => ({ ...s, ...v }))} />
        {err && <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{err}</span></div>}
        <Button loading={busy}>Save changes</Button>
      </form>
    </div>
  );
}
