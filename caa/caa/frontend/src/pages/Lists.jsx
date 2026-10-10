import { api } from "../api.js";
import { fmtD, fmtDT, Page } from "./ui.jsx";

export const Records = () => (
  <Page title="Class records (topics taught)" path="/records/" render={(r) => (
    <div className="card" key={r.id}>
      <b>{r.subject_name}</b> · {fmtD(r.date)} · Period {r.period} <span className="tag">{r.status}</span>
      <p>{r.topic}</p>
      {r.notes && <p className="muted">{r.notes}</p>}
      {r.faculty_name && <p className="muted">Faculty: {r.faculty_name}</p>}
    </div>
  )} />
);

export const Labs = () => (
  <Page title="Lab tracker" path="/experiments/" render={(e) => (
    <div className="card" key={e.id}>
      <b>{e.lab_name} — Experiment {e.number}: {e.title}</b> <span className="tag">{e.status}</span>
      {e.planned_date && <p className="muted">Planned: {fmtD(e.planned_date)}</p>}
      {e.group_names.length > 0 && <p>Allotted to: {e.group_names.join(", ")}</p>}
      {e.aim && <p><b>Aim:</b> {e.aim}</p>}
      {e.apparatus && <p><b>Apparatus/Software:</b> {e.apparatus}</p>}
      {e.procedure && <p><b>Procedure:</b> {e.procedure}</p>}
      {e.submission_requirements && <p><b>Submission:</b> {e.submission_requirements}</p>}
    </div>
  )} />
);

export const Assignments = () => (
  <Page title="Assignments" path="/assignments/" render={(a, reload) => {
    const overdue = new Date(a.deadline) < new Date();
    return (
      <div className={`card ${a.done ? "done" : ""}`} key={a.id}>
        <b>{a.title}</b> ({a.subject_name})
        <p>Deadline: <b className={overdue && !a.done ? "error" : ""}>{fmtDT(a.deadline)}</b>{overdue && " (passed)"}</p>
        {a.description && <p>{a.description}</p>}
        {a.submission_method && <p className="muted">Submit: {a.submission_method}</p>}
        <button onClick={() => api(`/assignments/${a.id}/toggle_done/`, { method: "POST" }).then(reload)}>
          {a.done ? "✓ Done — undo" : "Mark as done"}
        </button>
      </div>
    );
  }} />
);

export const Events = () => (
  <Page title="Events calendar" path="/events/" render={(e) => (
    <div className="card" key={e.id}>
      <b>{e.name}</b> — {fmtDT(e.start)}
      <p className="muted">{[e.venue, e.organizer && `by ${e.organizer}`, e.eligibility && `Eligibility: ${e.eligibility}`].filter(Boolean).join(" · ")}</p>
      {e.description && <p>{e.description}</p>}
      {e.registration_info && <p><b>Registration:</b> {e.registration_info}</p>}
    </div>
  )} />
);

export const Forms = () => (
  <Page title="Form & document guide" path="/forms/" render={(f) => (
    <div className="card" key={f.id}>
      <b>{f.name}</b> {f.deadline && <span className="tag">Deadline {fmtD(f.deadline)}</span>}
      {f.purpose && <p>{f.purpose}</p>}
      {f.documents_list.length > 0 && (<><b>Required documents</b><ul>{f.documents_list.map((d) => <li key={d}>{d}</li>)}</ul></>)}
      {f.accepted_formats && <p><b>Formats:</b> {f.accepted_formats}</p>}
      {f.file_size_limit && <p><b>File size:</b> {f.file_size_limit}</p>}
      {f.photo_signature_specs && <p><b>Photo/signature:</b> {f.photo_signature_specs}</p>}
      {f.how_to_submit && <p><b>How to submit:</b> {f.how_to_submit}</p>}
      {f.instructions && <p className="muted"><b>Notes / common mistakes:</b> {f.instructions}</p>}
    </div>
  )} />
);

export const Notifications = () => (
  <Page title="Notifications" searchable={false} path="/notifications/" render={(n, reload) => (
    <div className={`card ${n.read ? "done" : ""}`} key={n.id}>
      <b>{n.title}</b> <span className="muted">{fmtDT(n.created_at)}</span>
      <p>{n.message}</p>
      {!n.read && <button onClick={() => api(`/notifications/${n.id}/read/`, { method: "POST" }).then(reload)}>Mark read</button>}
    </div>
  )} />
);
