import { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmtDT, Section } from "./ui.jsx";

export default function Dashboard() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/dashboard/").then(setD).catch((e) => setErr(e.message)); }, []);
  if (err) return <p className="error">{err}</p>;
  if (!d) return <p>Loading…</p>;
  return (
    <div className="grid">
      <Section title="Today's classes">
        {d.today_classes.length === 0 ? <p className="muted">No classes recorded today.</p> :
          d.today_classes.map((c) => <p key={c.id}><b>Period {c.period}</b> · {c.subject_name} — {c.topic}</p>)}
      </Section>
      <Section title="Next lab experiments">
        {d.next_experiments.length === 0 ? <p className="muted">Nothing scheduled.</p> :
          d.next_experiments.map((e) => <p key={e.id}><b>{e.lab_name} #{e.number}</b> — {e.title} <span className="tag">{e.status}</span></p>)}
      </Section>
      <Section title="Assignments due (next 14 days)">
        {d.upcoming_assignments.length === 0 ? <p className="muted">Nothing due 🎉</p> :
          d.upcoming_assignments.map((a) => <p key={a.id} className={a.done ? "done" : ""}><b>{a.title}</b> ({a.subject_name}) — {fmtDT(a.deadline)}</p>)}
      </Section>
      <Section title="Upcoming events">
        {d.upcoming_events.length === 0 ? <p className="muted">No upcoming events.</p> :
          d.upcoming_events.map((e) => <p key={e.id}><b>{e.name}</b> — {fmtDT(e.start)} {e.venue && `@ ${e.venue}`}</p>)}
      </Section>
      <p className="muted">🔔 {d.unread_notifications} unread notification(s)</p>
    </div>
  );
}
