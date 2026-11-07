import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { useToast } from "../toast.jsx";
import { Badge, Button, Dialog, EmptyState, ErrorState, Field, PageHeader, SkeletonList, fmtDT } from "../pages/ui.jsx";

const netMsg = (e) => (e instanceof TypeError ? "Can't reach the server. Check your connection and try again." : e.message);
const fullName = (u) => [u.first_name, u.last_name].filter(Boolean).join(" ") || u.username;
const Err = ({ msg }) => (msg ? <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{msg}</span></div> : null);

/** Loads one URL with loading / error / retry. */
function useGet(path, enabled = true) {
  const [s, setS] = useState({ data: null, err: "" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!enabled) return undefined;
    let dead = false;
    setS((x) => ({ ...x, err: "" }));
    api(path).then((d) => !dead && setS({ data: d, err: "" })).catch((e) => !dead && setS({ data: null, err: netMsg(e) }));
    return () => { dead = true; };
  }, [path, enabled, tick]);
  return { ...s, reload: useCallback(() => setTick((t) => t + 1), []) };
}

function NoAccess({ what }) {
  return <EmptyState icon="shield" title="You don't have access to this">Your administrator has not given you permission to manage {what}. Ask the administrator if you need it.</EmptyState>;
}

/* ================= Dashboard ================= */
export function FacultyDashboard({ user, me, notif }) {
  const act = useGet("/faculty/activity/");
  const name = fullName(user);
  const items = (notif.items || []).slice(0, 4);
  return (
    <div>
      <PageHeader title="Dashboard" />
      <section className="fac-hero">
        <div>
          <h2>Welcome, {name}</h2>
          <p>{[me.designation, me.department].filter(Boolean).join(" · ") || "Faculty member"}</p>
        </div>
        <div className="fac-perms" aria-label="What you can manage">
          <Badge tone={me.can_manage_events ? "success" : "neutral"}>Events: {me.can_manage_events ? "allowed" : "not allowed"}</Badge>
          <Badge tone={me.can_manage_syllabus ? "success" : "neutral"}>Syllabus: {me.can_manage_syllabus ? "allowed" : "not allowed"}</Badge>
        </div>
      </section>

      <div className="fac-stats">
        <div className="fac-stat"><strong>{me.stats.events_published}</strong><span>Published events</span></div>
        <div className="fac-stat"><strong>{me.stats.events_draft}</strong><span>Draft events</span></div>
        <div className="fac-stat"><strong>{me.stats.subjects}</strong><span>Assigned subjects</span></div>
        <div className="fac-stat"><strong>{me.scope.restricted ? (me.scope.groups.length || me.scope.sections.length) : "All"}</strong><span>{me.scope.restricted ? "Groups / sections" : "Groups (no limit)"}</span></div>
      </div>

      <div className="fac-grid">
        <section className="fac-card" aria-labelledby="fp-h">
          <h3 id="fp-h">Profile</h3>
          <dl className="fac-dl">
            <dt>Name</dt><dd>{name}</dd>
            <dt>Email</dt><dd>{me.email || "—"}</dd>
            <dt>Designation</dt><dd>{me.designation || "—"}</dd>
            <dt>Department</dt><dd>{me.department || "—"}</dd>
          </dl>
        </section>

        <section className="fac-card" aria-labelledby="fs-h">
          <h3 id="fs-h">Assigned subjects</h3>
          {me.subjects.length === 0 ? <p className="muted">No subjects assigned yet. Your administrator assigns them.</p> : (
            <ul className="fac-list">{me.subjects.map((s) => <li key={s.id}><Badge tone="primary">{s.code}</Badge> {s.name}</li>)}</ul>
          )}
        </section>

        <section className="fac-card" aria-labelledby="fg-h">
          <h3 id="fg-h">Your groups and sections</h3>
          {!me.scope.restricted ? <p className="muted">You can send events to any group or section.</p> : (
            <>
              {me.scope.groups.length > 0 && <p>{me.scope.groups.map((g) => <Badge key={g.id} tone="primary">{g.name}</Badge>)}</p>}
              {me.scope.sections.length > 0 && <p className="fac-chips">{me.scope.sections.map((c) => <Badge key={c}>{c}</Badge>)}</p>}
            </>
          )}
          <Link to="/faculty/groups" className="link-btn">See group and section details</Link>
        </section>

        <section className="fac-card" aria-labelledby="fn-h">
          <h3 id="fn-h">Notifications</h3>
          {items.length === 0 ? <p className="muted">No notifications.</p> : (
            <ul className="fac-feed">{items.map((n) => <li key={n.id}><strong>{n.title}</strong><small>{fmtDT(n.created_at)}</small></li>)}</ul>
          )}
          <button className="link-btn" onClick={() => notif.setOpen(true)}>Open notifications{notif.unread ? ` (${notif.unread} new)` : ""}</button>
        </section>

        <section className="fac-card fac-wide" aria-labelledby="fa-h">
          <h3 id="fa-h">Recent activity</h3>
          {act.err ? <ErrorState message={act.err} onRetry={act.reload} /> : !act.data ? <SkeletonList count={2} /> : act.data.length === 0 ? (
            <p className="muted">Nothing yet. Events and syllabus updates you publish are listed here.</p>
          ) : <ul className="fac-feed">{act.data.map((a) => <li key={a.id}><span>{a.text}</span><small>{fmtDT(a.created_at)}</small></li>)}</ul>}
        </section>
      </div>
    </div>
  );
}

/* ================= Events ================= */
const toLocalInput = (iso) => { const d = new Date(iso); const p = (n) => String(n).padStart(2, "0"); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; };
const BLANK = { name: "", start: "", venue: "", organizer: "", description: "", registration_info: "", eligibility: "", target_group: "", target_sections: "", is_published: true };

function EventForm({ initial, groups, restricted, onSaved, onCancel }) {
  const [f, setF] = useState(initial ? { ...BLANK, ...Object.fromEntries(Object.entries(initial).map(([k, v]) => [k, v ?? ""])), start: toLocalInput(initial.start) } : BLANK);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault(); setErr(""); setBusy(true);
    const body = { name: f.name.trim(), start: f.start ? new Date(f.start).toISOString() : null, venue: f.venue.trim(), organizer: f.organizer.trim(),
      description: f.description.trim(), registration_info: f.registration_info.trim(), eligibility: f.eligibility.trim(),
      target_group: f.target_group === "" ? null : Number(f.target_group), target_sections: f.target_sections, is_published: !!f.is_published };
    try {
      onSaved(initial ? await api(`/faculty/events/${initial.id}/`, { method: "PATCH", body }) : await api("/faculty/events/", { method: "POST", body }), !initial);
    } catch (x) { setErr(netMsg(x)); } finally { setBusy(false); }
  }
  return (
    <form className="stack" onSubmit={save}>
      <Field label="Event name" htmlFor="ev-name"><input id="ev-name" required maxLength={200} value={f.name} onChange={set("name")} /></Field>
      <div className="grid-2">
        <Field label="Date and time" htmlFor="ev-start"><input id="ev-start" type="datetime-local" required value={f.start} onChange={set("start")} /></Field>
        <Field label="Venue" htmlFor="ev-venue"><input id="ev-venue" maxLength={200} value={f.venue} onChange={set("venue")} /></Field>
      </div>
      <Field label="Organizer" htmlFor="ev-org"><input id="ev-org" maxLength={200} value={f.organizer} onChange={set("organizer")} /></Field>
      <Field label="Description" htmlFor="ev-desc"><textarea id="ev-desc" value={f.description} onChange={set("description")} /></Field>
      <div className="grid-2">
        <Field label="Who can register / how" htmlFor="ev-reg"><input id="ev-reg" value={f.registration_info} onChange={set("registration_info")} /></Field>
        <Field label="Eligibility" htmlFor="ev-el"><input id="ev-el" value={f.eligibility} onChange={set("eligibility")} /></Field>
      </div>
      <div className="grid-2">
        <Field label="Send to group" htmlFor="ev-group" hint={restricted ? "Choose your group, or type sections below." : "Leave as everyone to notify all students."}>
          <select id="ev-group" value={f.target_group} onChange={set("target_group")}>
            {!restricted && <option value="">Everyone</option>}
            {restricted && <option value="">— none (use sections) —</option>}
            {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </Field>
        <Field label="Or only these sections" htmlFor="ev-sec" hint="Comma separated, e.g. A1, A2. Overrides the group.">
          <input id="ev-sec" value={f.target_sections} onChange={set("target_sections")} placeholder="A1, A2" />
        </Field>
      </div>
      <label className="fac-check"><input type="checkbox" checked={!!f.is_published} onChange={(e) => setF({ ...f, is_published: e.target.checked })} />
        <span><strong>Publish now</strong><small>Students in the audience are notified when you publish. Untick to keep it as a private draft.</small></span></label>
      <Err msg={err} />
      <div className="dialog-actions"><Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button><Button loading={busy}>{initial ? "Save changes" : "Save event"}</Button></div>
    </form>
  );
}

export function FacultyEvents({ me }) {
  const allowed = me.can_manage_events;
  const ev = useGet("/faculty/events/", allowed);
  const gr = useGet("/faculty/groups/", allowed);
  const toast = useToast();
  const [dlg, setDlg] = useState(null);       // null | {event?}
  const [del, setDel] = useState(null);
  const [busyId, setBusyId] = useState(null);

  if (!allowed) return <div><PageHeader title="My events" /><NoAccess what="events" /></div>;

  async function toggle(e) {
    setBusyId(e.id);
    try { await api(`/faculty/events/${e.id}/`, { method: "PATCH", body: { is_published: !e.is_published } }); toast(e.is_published ? "Event moved back to draft." : "Event published. Students were notified."); ev.reload(); }
    catch (x) { toast(netMsg(x), "danger"); } finally { setBusyId(null); }
  }
  async function remove() {
    const e = del; setBusyId(e.id);
    try { await api(`/faculty/events/${e.id}/`, { method: "DELETE" }); toast("Event deleted."); setDel(null); ev.reload(); }
    catch (x) { toast(netMsg(x), "danger"); } finally { setBusyId(null); }
  }

  return (
    <div>
      <PageHeader title="My events" description="Events you created. Publishing an event notifies the students in its audience."
        actions={<Button icon="events" onClick={() => setDlg({})}>New event</Button>} />
      {ev.err ? <ErrorState message={ev.err} onRetry={ev.reload} /> : !ev.data ? <SkeletonList /> : ev.data.length === 0 ? (
        <EmptyState icon="events" title="No events yet" action={<Button onClick={() => setDlg({})}>Create your first event</Button>}>Events you create will be listed here.</EmptyState>
      ) : (
        <div className="stack">
          {ev.data.map((e) => (
            <article key={e.id} className="fac-card fac-row">
              <div className="fac-row-main">
                <h3>{e.name}</h3>
                <p className="muted">{fmtDT(e.start)}{e.venue ? ` · ${e.venue}` : ""}</p>
                <p><Badge tone={e.is_published ? "success" : "warning"}>{e.is_published ? "Published" : "Draft"}</Badge>{" "}
                  <Badge>{e.target_sections ? `Sections: ${e.target_sections}` : e.target_group_name || "Everyone"}</Badge></p>
              </div>
              <div className="fac-row-actions">
                <Button size="sm" variant="secondary" loading={busyId === e.id} onClick={() => toggle(e)}>{e.is_published ? "Unpublish" : "Publish"}</Button>
                <Button size="sm" variant="secondary" onClick={() => setDlg({ event: e })}>Edit</Button>
                <Button size="sm" variant="ghost" aria-label={`Delete ${e.name}`} onClick={() => setDel(e)}><Icon name="trash" size={16} />Delete</Button>
              </div>
            </article>
          ))}
        </div>
      )}
      <Dialog open={!!dlg} title={dlg?.event ? "Edit event" : "New event"} onClose={() => setDlg(null)}>
        {dlg && <EventForm initial={dlg.event} groups={gr.data?.groups || []} restricted={!!gr.data?.restricted}
          onCancel={() => setDlg(null)} onSaved={(saved, isNew) => { setDlg(null); toast(saved.is_published ? (isNew ? "Event published. Students were notified." : "Event saved.") : "Draft saved."); ev.reload(); }} />}
      </Dialog>
      <Dialog open={!!del} title="Delete this event?" onClose={() => setDel(null)}
        footer={<><Button variant="ghost" onClick={() => setDel(null)}>Cancel</Button><Button variant="danger" loading={busyId === del?.id} onClick={remove}>Delete</Button></>}>
        <p>"{del?.name}" will be removed for everyone. This can't be undone.</p>
      </Dialog>
    </div>
  );
}

/* ================= Syllabus ================= */
const EXAM_LABEL = { mid1: "Mid-Term 1", mid2: "Mid-Term 2", end: "End-Semester" };

function SyllabusForm({ subject, exam, entry, onSaved, onCancel }) {
  const [f, setF] = useState({ content: entry?.content || "", pdf_url: entry?.pdf_url || "", semester: entry?.semester ?? "", verified: entry ? !!entry.verified : true });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function save(e) {
    e.preventDefault(); setErr(""); setBusy(true);
    try { onSaved(await api(`/faculty/syllabus/${subject.id}/${exam}/`, { method: "PUT", body: { content: f.content, pdf_url: f.pdf_url.trim(), semester: f.semester === "" ? null : Number(f.semester), verified: f.verified } })); }
    catch (x) { setErr(netMsg(x)); } finally { setBusy(false); }
  }
  return (
    <form className="stack" onSubmit={save}>
      <Field label="Syllabus topics" htmlFor="sy-c" hint="One topic per line. Start a unit with 'Unit 1: Title'."><textarea id="sy-c" rows={9} maxLength={20000} value={f.content} onChange={(e) => setF({ ...f, content: e.target.value })} /></Field>
      <div className="grid-2">
        <Field label="PDF link (optional)" htmlFor="sy-p"><input id="sy-p" type="url" placeholder="https://" value={f.pdf_url} onChange={(e) => setF({ ...f, pdf_url: e.target.value })} /></Field>
        <Field label="Semester" htmlFor="sy-s"><input id="sy-s" type="number" min="1" max="12" value={f.semester} onChange={(e) => setF({ ...f, semester: e.target.value })} /></Field>
      </div>
      <label className="fac-check"><input type="checkbox" checked={f.verified} onChange={(e) => setF({ ...f, verified: e.target.checked })} />
        <span><strong>Publish to students</strong><small>When on, students see this syllabus and are notified of new or changed topics. Untick to keep it hidden.</small></span></label>
      <Err msg={err} />
      <div className="dialog-actions"><Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button><Button loading={busy}>Save syllabus</Button></div>
    </form>
  );
}

export function FacultySyllabus({ me }) {
  const allowed = me.can_manage_syllabus;
  const sy = useGet("/faculty/syllabus/", allowed);
  const toast = useToast();
  const [dlg, setDlg] = useState(null);
  if (!allowed) return <div><PageHeader title="Syllabus" /><NoAccess what="syllabus" /></div>;
  return (
    <div>
      <PageHeader title="Syllabus" description="Add or update the syllabus for your assigned subjects, one examination at a time." />
      {sy.err ? <ErrorState message={sy.err} onRetry={sy.reload} /> : !sy.data ? <SkeletonList /> : sy.data.length === 0 ? (
        <EmptyState icon="syllabus" title="No subjects assigned">Your administrator assigns subjects to you. They will appear here.</EmptyState>
      ) : (
        <div className="stack">
          {sy.data.map((row) => (
            <section key={row.subject.id} className="fac-card">
              <h3><Badge tone="primary">{row.subject.code}</Badge> {row.subject.name}</h3>
              <div className="fac-exams">
                {Object.keys(EXAM_LABEL).map((x) => {
                  const en = row.entries[x];
                  return (
                    <div key={x} className="fac-exam">
                      <strong>{EXAM_LABEL[x]}</strong>
                      <Badge tone={!en ? "neutral" : en.verified ? "success" : "warning"}>{!en ? "Not added" : en.verified ? "Published" : "Draft"}</Badge>
                      {en && <small className="muted">Updated {fmtDT(en.updated_at)}</small>}
                      <Button size="sm" variant="secondary" onClick={() => setDlg({ subject: row.subject, exam: x, entry: en })}>{en ? "Edit" : "Add"}</Button>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
      <Dialog open={!!dlg} title={dlg ? `${dlg.subject.code} · ${EXAM_LABEL[dlg.exam]}` : ""} onClose={() => setDlg(null)}>
        {dlg && <SyllabusForm {...dlg} onCancel={() => setDlg(null)} onSaved={(s) => { setDlg(null); toast(s.verified ? "Syllabus saved and published." : "Syllabus saved as a draft."); sy.reload(); }} />}
      </Dialog>
    </div>
  );
}

/* ================= Groups & sections ================= */
export function FacultyGroups() {
  const g = useGet("/faculty/groups/");
  return (
    <div>
      <PageHeader title="Groups & sections" description="Student counts for the groups and sections you work with. Names are not shown." />
      {g.err ? <ErrorState message={g.err} onRetry={g.reload} /> : !g.data ? <SkeletonList /> : (g.data.groups.length === 0 && g.data.extra_sections.length === 0) ? (
        <EmptyState icon="classes" title="No groups assigned">Your administrator assigns groups or sections to you.</EmptyState>
      ) : (
        <div className="fac-grid">
          {g.data.groups.map((gr) => (
            <section key={gr.id} className="fac-card">
              <h3>{gr.name} <Badge tone="primary">{gr.students} students</Badge></h3>
              {gr.sections.length === 0 ? <p className="muted">No sections.</p> : (
                <ul className="fac-list">{gr.sections.map((s) => <li key={s.code}><strong>{s.code}</strong> <span className="muted">{s.students} {s.students === 1 ? "student" : "students"}</span></li>)}</ul>
              )}
            </section>
          ))}
          {g.data.extra_sections.length > 0 && (
            <section className="fac-card"><h3>Other sections</h3>
              <ul className="fac-list">{g.data.extra_sections.map((s) => <li key={s.code}><strong>{s.code}</strong> <span className="muted">{s.students} {s.students === 1 ? "student" : "students"}</span></li>)}</ul></section>
          )}
        </div>
      )}
    </div>
  );
}
