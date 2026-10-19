import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { useToast } from "../toast.jsx";
import { CHANGED } from "../notifications.jsx";
import { Badge, Button, Linkify, ListPage, dueInfo, fmtD, fmtDT } from "./ui.jsx";

const STATUS_TONE = { completed: "success", ongoing: "primary", planned: "neutral" };

export const Records = () => (
  <ListPage
    title="Class records"
    description="What was taught in each period, subject by subject."
    path="/records/"
    empty={{ title: "No class records yet", text: "Faculty add topics after each class. They will appear here." }}
    render={(r) => (
      <article className="card" key={r.id}>
        <div className="card-head">
          <div>
            <h2 className="card-title">{r.topic}</h2>
            <div className="card-meta">
              <span><Icon name="classes" size={16} />{r.subject_name}</span>
              <span><Icon name="events" size={16} />{fmtD(r.date)}</span>
              <span><Icon name="clock" size={16} />Period {r.period}</span>
              {r.faculty_name && <span><Icon name="user" size={16} />{r.faculty_name}</span>}
            </div>
          </div>
          <Badge tone={STATUS_TONE[r.status] || "neutral"}>{r.status}</Badge>
        </div>
        {r.notes && <p className="card-body"><Linkify text={r.notes} /></p>}
      </article>
    )}
  />
);

export const Labs = () => (
  <ListPage
    title="Lab tracker"
    description="Experiments, who they're allotted to, and what to prepare."
    path="/experiments/"
    filters={[
      { key: "all", label: "All", test: () => true },
      { key: "ongoing", label: "Ongoing", test: (e) => e.status === "ongoing" },
      { key: "planned", label: "Upcoming", test: (e) => e.status === "planned" },
      { key: "completed", label: "Completed", test: (e) => e.status === "completed" },
    ]}
    empty={{ title: "No experiments found", text: "Experiments appear here once faculty add them to a lab." }}
    render={(e) => (
      <article className="card" key={e.id}>
        <div className="card-head">
          <div>
            <h2 className="card-title">Experiment {e.number}: {e.title}</h2>
            <div className="card-meta">
              <span><Icon name="labs" size={16} />{e.lab_name}</span>
              {e.planned_date && <span><Icon name="events" size={16} />Planned {fmtD(e.planned_date)}</span>}
            </div>
          </div>
          <Badge tone={STATUS_TONE[e.status] || "neutral"}>{e.status === "planned" ? "upcoming" : e.status}</Badge>
        </div>
        {e.group_names.length > 0 && (
          <div className="chips" style={{ marginTop: 12 }} aria-label="Allotted groups">
            {e.group_names.map((g) => <Badge key={g} tone="primary">{g}</Badge>)}
          </div>
        )}
        {e.aim && <p className="card-body"><strong>Aim: </strong><Linkify text={e.aim} /></p>}
        {(e.apparatus || e.procedure || e.submission_requirements) && (
          <details className="more">
            <summary>Apparatus, procedure and submission</summary>
            <dl className="facts">
              {e.apparatus && <div><dt>Apparatus / software</dt><dd><Linkify text={e.apparatus} /></dd></div>}
              {e.procedure && <div><dt>Procedure</dt><dd><Linkify text={e.procedure} /></dd></div>}
              {e.submission_requirements && <div><dt>Submission</dt><dd><Linkify text={e.submission_requirements} /></dd></div>}
            </dl>
          </details>
        )}
      </article>
    )}
  />
);

function AssignmentCard({ a, reload }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const due = dueInfo(a.deadline, a.done);
  async function toggle() {
    setBusy(true);
    try {
      const r = await api(`/assignments/${a.id}/toggle_done/`, { method: "POST" });
      toast(r.done ? "Marked as done" : "Marked as not done");
      reload();
    } catch (e) { toast(e.message, "danger"); } finally { setBusy(false); }
  }
  return (
    <article className={`card ${a.done ? "is-done" : ""}`}>
      <div className="card-head">
        <div>
          <h2 className="card-title">{a.title}</h2>
          <div className="card-meta">
            <span><Icon name="classes" size={16} />{a.subject_name}</span>
            <span><Icon name="clock" size={16} />{fmtDT(a.deadline)}</span>
          </div>
        </div>
        <Badge tone={due.tone}>{due.label}</Badge>
      </div>
      {a.description && <p className="card-body"><Linkify text={a.description} /></p>}
      {a.submission_method && <p className="muted" style={{ marginTop: 8 }}>How to submit: <Linkify text={a.submission_method} /></p>}
      <div className="card-actions">
        <Button variant={a.done ? "secondary" : "primary"} size="sm" loading={busy} icon={a.done ? undefined : "check"} onClick={toggle}>
          {a.done ? "Mark as not done" : "Mark as done"}
        </Button>
      </div>
    </article>
  );
}

export const Assignments = () => (
  <ListPage
    title="Assignments"
    description="Deadlines for every subject. You'll get a reminder 72 hours before each one."
    path="/assignments/"
    filters={[
      { key: "pending", label: "Pending", test: (a) => !a.done },
      { key: "done", label: "Done", test: (a) => a.done },
      { key: "all", label: "All", test: () => true },
    ]}
    empty={{ title: "No assignments here", text: "Assignments added by faculty will appear here." }}
    render={(a, reload) => <AssignmentCard key={a.id} a={a} reload={reload} />}
  />
);

function EventCard({ e, target }) {
  const d = new Date(e.start);
  const me = String(e.id) === target;
  const ref = useRef(null);
  useEffect(() => { if (me) ref.current?.scrollIntoView({ block: "center" }); }, [me]);
  return (
    <article ref={ref} id={`event-${e.id}`} className={`card event ${me ? "is-target" : ""}`} aria-current={me ? "true" : undefined}>
      <div className="date-tile" aria-hidden="true">
        <strong>{d.getDate()}</strong>
        <span>{d.toLocaleDateString("en-IN", { month: "short" })}</span>
      </div>
      <div className="event-body">
        <h2 className="card-title">{e.name}</h2>
        <div className="card-meta">
          <span><Icon name="clock" size={16} />{fmtDT(e.start)}</span>
          {e.venue && <span><Icon name="pin" size={16} />{e.venue}</span>}
          {e.organizer && <span><Icon name="user" size={16} />{e.organizer}</span>}
        </div>
        {e.description && <p className="card-body"><Linkify text={e.description} /></p>}
        {(e.registration_info || e.eligibility) && (
          <dl className="facts">
            {e.registration_info && <div><dt>Registration</dt><dd><Linkify text={e.registration_info} /></dd></div>}
            {e.eligibility && <div><dt>Eligibility</dt><dd><Linkify text={e.eligibility} /></dd></div>}
          </dl>
        )}
      </div>
    </article>
  );
}

export function Events() {
  const target = new URLSearchParams(useLocation().search).get("event") || "";
  return (
    <ListPage
      title="Events calendar"
      description="Upcoming and past college events."
      path="/events/"
      empty={{ title: "No events yet", text: "Events will appear here when the college adds them." }}
      notice={(items) => target && !items.some((x) => String(x.id) === target)
        ? <div className="form-info" role="status">That event is no longer available. It may have been removed or moved back to draft.</div> : null}
      render={(e) => <EventCard key={e.id} e={e} target={target} />}
    />
  );
}

export const Forms = () => (
  <ListPage
    title="Form and document guide"
    description="What to prepare before you fill in a college form."
    path="/forms/"
    empty={{ title: "No forms listed yet", text: "Document checklists will appear here when they are added." }}
    render={(f) => (
      <article className="card" key={f.id}>
        <div className="card-head">
          <h2 className="card-title">{f.name}</h2>
          {f.deadline && <Badge tone="warning">Deadline {fmtD(f.deadline)}</Badge>}
        </div>
        {f.purpose && <p className="card-body"><Linkify text={f.purpose} /></p>}
        {f.documents_list.length > 0 && (
          <>
            <h3 style={{ marginTop: 16 }}>Documents you need</h3>
            <ul className="checklist">
              {f.documents_list.map((x) => <li key={x}><Icon name="check" size={16} /><span><Linkify text={x} /></span></li>)}
            </ul>
          </>
        )}
        {(f.accepted_formats || f.file_size_limit || f.photo_signature_specs || f.how_to_submit) && (
          <dl className="facts">
            {f.accepted_formats && <div><dt>File formats</dt><dd><Linkify text={f.accepted_formats} /></dd></div>}
            {f.file_size_limit && <div><dt>File size</dt><dd>{f.file_size_limit}</dd></div>}
            {f.photo_signature_specs && <div><dt>Photo and signature</dt><dd><Linkify text={f.photo_signature_specs} /></dd></div>}
            {f.how_to_submit && <div><dt>How to submit</dt><dd><Linkify text={f.how_to_submit} /></dd></div>}
          </dl>
        )}
        {f.instructions && <p className="card-body"><strong>Common mistakes: </strong><Linkify text={f.instructions} /></p>}
      </article>
    )}
  />
);

function NotificationCard({ n, reload }) {
  const toast = useToast();
  async function markRead() {
    try { await api(`/notifications/${n.id}/read/`, { method: "POST" }); reload(); window.dispatchEvent(new Event(CHANGED)); }
    catch (e) { toast(e.message, "danger"); }
  }
  return (
    <article className={`card notif-card ${n.read ? "is-done" : "is-unread"}`}>
      <div className="card-head">
        <h2 className="card-title">{!n.read && <span className="unread-dot" aria-hidden="true" />}{n.title}</h2>
        {!n.read && <Badge tone="primary">New</Badge>}
      </div>
      <div className="card-meta"><span><Icon name="clock" size={16} />{fmtDT(n.created_at)}</span></div>
      {n.message && <p className="card-body notif-pre">{n.message}</p>}
      <div className="card-actions">
        {n.link && n.link.startsWith("/") && <Link className="link-btn" to={n.link} onClick={() => { if (!n.read) markRead(); }}>Open</Link>}
        {!n.read && <button className="link-btn" onClick={markRead}>Mark as read</button>}
      </div>
    </article>
  );
}

function MarkAllRead({ reload, items }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  if (!items || !items.some((n) => !n.read)) return null;
  async function run() {
    setBusy(true);
    try { await api("/notifications/read_all/", { method: "POST" }); toast("All notifications marked as read"); reload(); window.dispatchEvent(new Event(CHANGED)); }
    catch (e) { toast(e.message, "danger"); } finally { setBusy(false); }
  }
  return <Button variant="secondary" size="sm" loading={busy} onClick={run}>Mark all as read</Button>;
}

export const Notifications = () => (
  <ListPage
    title="Notifications"
    description="New events, syllabus updates and assignment reminders."
    path="/notifications/"
    searchable={false}
    actions={(reload, items) => <MarkAllRead reload={reload} items={items} />}
    empty={{ title: "You're all caught up", text: "New events, syllabus updates and deadline reminders will show up here." }}
    render={(n, reload) => <NotificationCard key={n.id} n={n} reload={reload} />}
  />
);
