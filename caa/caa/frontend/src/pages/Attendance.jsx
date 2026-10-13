import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { useToast } from "../toast.jsx";
import { Badge, Button, Dialog, EmptyState, ErrorState, Field, PageHeader, SkeletonList, fmtD } from "./ui.jsx";

const REASONS = [["illness", "Illness"], ["personal", "Personal reason"], ["family", "Family reason"],
  ["transport", "Transport or travel issue"], ["college", "College event or approved activity"], ["other", "Other"]];
const STATUSES = [["present", "Present"], ["absent", "Absent"], ["holiday", "Holiday"]];
const TONE = { present: "success", absent: "danger", holiday: "neutral" };
const LABEL = Object.fromEntries(STATUSES);
const REASON_LABEL = Object.fromEntries(REASONS);
const PAGE = 15;

const netMsg = (e) => (e instanceof TypeError ? "Can't reach the server. Check your connection and try again." : e.message);
const isoToday = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const monthLabel = (m) => new Date(`${m}-01T00:00:00`).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
const pct = (v) => (v === null || v === undefined ? "Not enough data" : `${v}%`);
const readTarget = () => { try { return localStorage.getItem("caa_att_target") || ""; } catch { return ""; } };
const saveTarget = (v) => { try { localStorage.setItem("caa_att_target", v); } catch { /* optional convenience */ } };

function Err({ msg }) {
  return msg ? <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{msg}</span></div> : null;
}

/* ---------- add / edit dialog ---------- */
function EntryDialog({ open, entry, subjects, onClose, onSaved }) {
  const blank = { date: isoToday(), status: "present", subject: "", period: "", reason: "", note: "" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setErr("");
    setF(entry ? { date: entry.date, status: entry.status, subject: entry.subject ? String(entry.subject) : "", period: entry.period ?? "", reason: entry.reason || "", note: entry.note || "" } : blank);
  }, [open, entry]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function save(e) {
    e.preventDefault(); setBusy(true); setErr("");
    const body = { date: f.date, status: f.status, subject: f.subject ? Number(f.subject) : null,
      period: f.period === "" ? null : Number(f.period), reason: f.status === "absent" ? f.reason : "", note: f.note.trim() };
    try {
      const saved = entry ? await api(`/attendance/${entry.id}/`, { method: "PATCH", body }) : await api("/attendance/", { method: "POST", body });
      onSaved(saved, !!entry);
    } catch (x) { setErr(netMsg(x)); } finally { setBusy(false); }
  }
  return (
    <Dialog open={open} title={entry ? "Edit entry" : "Add attendance entry"} onClose={onClose}>
      <form className="stack" onSubmit={save}>
        <Field label="Date" htmlFor="att-date"><input id="att-date" type="date" required max={isoToday()} value={f.date} onChange={set("date")} /></Field>
        <fieldset className="seg" aria-label="Status">
          {STATUSES.map(([k, l]) => (
            <label key={k} className={`seg-item ${f.status === k ? "is-on" : ""}`}>
              <input type="radio" name="att-status" value={k} checked={f.status === k} onChange={set("status")} />{l}
            </label>
          ))}
        </fieldset>
        <div className="grid-2">
          <Field label="Subject / class (optional)" htmlFor="att-sub">
            <select id="att-sub" value={f.subject} onChange={set("subject")}>
              <option value="">No subject (whole day)</option>
              {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <Field label="Session / period (optional)" htmlFor="att-per" hint="Only needed if you attend a subject more than once a day.">
            <input id="att-per" type="number" min="1" max="12" value={f.period} onChange={set("period")} />
          </Field>
        </div>
        {f.status === "absent" && (
          <Field label="Reason (optional)" htmlFor="att-reason" hint="Just a category. A reason here does not mean the absence was approved, and you don't need to share medical details.">
            <select id="att-reason" value={f.reason} onChange={set("reason")}>
              <option value="">Not specified</option>
              {REASONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </Field>
        )}
        <Field label="Note (optional)" htmlFor="att-note"><input id="att-note" maxLength={200} value={f.note} onChange={set("note")} /></Field>
        <Err msg={err} />
        <div className="dialog-actions">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={busy}>{entry ? "Save changes" : "Add entry"}</Button>
        </div>
      </form>
    </Dialog>
  );
}

/* ---------- small chart-free bars ---------- */
function Bars({ rows, valueKey, labelKey, max, suffix = "" }) {
  return (
    <ul className="bars">
      {rows.map((r, i) => (
        <li key={i}>
          <span className="bar-label">{r[labelKey]}</span>
          <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: `${max ? Math.max(3, (r[valueKey] / max) * 100) : 0}%` }} /></span>
          <span className="bar-val">{r[valueKey]}{suffix}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Attendance() {
  const toast = useToast();
  const [subjects, setSubjects] = useState([]);
  const [filters, setFilters] = useState({ month: "", from: "", to: "", subject: "", status: "" });
  const [target, setTarget] = useState(readTarget());
  const [records, setRecords] = useState(null);
  const [summary, setSummary] = useState(null);
  const [err, setErr] = useState("");
  const [shown, setShown] = useState(PAGE);
  const [dialog, setDialog] = useState({ open: false, entry: null });
  const [del, setDel] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => { api("/subjects/").then((l) => setSubjects(Array.isArray(l) ? l : l.results || [])).catch(() => {}); }, []);

  const query = useMemo(() => {
    const q = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) q.set(k, v); });
    return q;
  }, [filters]);
  const tnum = Number(target);
  const tvalid = target !== "" && tnum > 0 && tnum <= 100;

  const load = useCallback(async () => {
    setErr("");
    const sq = new URLSearchParams(query);
    if (tvalid) sq.set("target", String(tnum));
    try {
      const [r, s] = await Promise.all([api(`/attendance/?${query}`), api(`/attendance/summary/?${sq}`)]);
      setRecords(r); setSummary(s); setShown(PAGE);
    } catch (e) { setErr(netMsg(e)); }
  }, [query, tvalid, tnum]);
  useEffect(() => { load(); }, [load]);

  const set = (k) => (e) => {
    const v = e.target.value;
    // a month and an explicit date range would fight each other, so choosing one clears the other
    setFilters((f) => ({ ...f, [k]: v, ...(k === "month" && v ? { from: "", to: "" } : {}), ...((k === "from" || k === "to") && v ? { month: "" } : {}) }));
  };
  const hasFilter = Object.values(filters).some(Boolean);

  async function remove() {
    const e = del; setDel(null); setBusy("del");
    try { await api(`/attendance/${e.id}/`, { method: "DELETE" }); toast("Entry deleted."); await load(); }
    catch (x) { toast(netMsg(x), "danger"); } finally { setBusy(""); }
  }
  async function exportCsv() {
    setBusy("csv");
    try {
      const blob = await api(`/attendance/export/?${query}`, { blob: true });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "my-attendance.csv"; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (x) { toast(netMsg(x), "danger"); } finally { setBusy(""); }
  }

  const subjectName = (id) => subjects.find((s) => s.id === id)?.name;
  const maxMonth = summary ? Math.max(1, ...summary.months.map((m) => m.present + m.absent + m.holiday)) : 1;
  const maxReason = summary ? Math.max(1, ...summary.reasons.map((r) => r.count)) : 1;
  const period = summary?.period;
  const basis = summary && summary.total
    ? `Based on ${summary.total} record${summary.total === 1 ? "" : "s"} you entered (${summary.counted} counted: present + absent), ${fmtD(period.first)} to ${fmtD(period.last)}${hasFilter ? ", with your filters applied" : ""}.`
    : "";

  return (
    <div>
      <PageHeader title="My attendance" description="Your own record of the days you attended, missed or had off."
        actions={<Button size="sm" onClick={() => setDialog({ open: true, entry: null })}>Add entry</Button>} />

      <div className="form-info" role="note">
        <strong>Self-reported.</strong> This tracker is only your personal record. It is not your official college attendance and is not shared with faculty.
        A reason you choose does not mean an absence was approved.
      </div>

      <section className="card att-filters" aria-label="Filters">
        <div className="att-filter-grid">
          <Field label="Month" htmlFor="f-month"><input id="f-month" type="month" value={filters.month} onChange={set("month")} /></Field>
          <Field label="From" htmlFor="f-from"><input id="f-from" type="date" value={filters.from} onChange={set("from")} /></Field>
          <Field label="To" htmlFor="f-to"><input id="f-to" type="date" value={filters.to} onChange={set("to")} /></Field>
          <Field label="Subject" htmlFor="f-sub">
            <select id="f-sub" value={filters.subject} onChange={set("subject")}>
              <option value="">All</option><option value="none">No subject (whole day)</option>
              {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <Field label="Status" htmlFor="f-status">
            <select id="f-status" value={filters.status} onChange={set("status")}>
              <option value="">All</option>{STATUSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </Field>
          <Field label="My own target % (optional)" htmlFor="f-target" hint="Only used for estimates. It isn't an official requirement.">
            <input id="f-target" type="number" min="1" max="100" inputMode="numeric" value={target} onChange={(e) => { setTarget(e.target.value); saveTarget(e.target.value); }} />
          </Field>
        </div>
        <div className="card-actions">
          {hasFilter && <Button size="sm" variant="ghost" onClick={() => setFilters({ month: "", from: "", to: "", subject: "", status: "" })}>Clear filters</Button>}
          <Button size="sm" variant="secondary" loading={busy === "csv"} disabled={!records?.length} onClick={exportCsv}>Export CSV</Button>
        </div>
      </section>

      {err && <ErrorState message={err} onRetry={load} />}
      {!err && !summary && <SkeletonList count={2} />}

      {summary && summary.total === 0 && (
        <EmptyState icon="clock" title={hasFilter ? "No entries match these filters" : "No entries yet"}
          action={!hasFilter && <Button onClick={() => setDialog({ open: true, entry: null })}>Add your first entry</Button>}>
          {hasFilter ? "Try clearing the filters." : "Add the days you attended or missed to see your summary here."}
        </EmptyState>
      )}

      {summary && summary.total > 0 && (
        <div className="stack">
          <section className="att-stats" aria-label="Summary">
            <div className="card att-stat att-main">
              <span className="muted">Attendance</span>
              <strong className={summary.percentage === null ? "att-na" : ""}>{pct(summary.percentage)}</strong>
              <span className="muted">Present ÷ (present + absent) × 100. Holidays and days with no entry are not counted.</span>
            </div>
            <div className="card att-stat"><span className="muted">Present</span><strong>{summary.present}</strong></div>
            <div className="card att-stat"><span className="muted">Absent</span><strong>{summary.absent}</strong></div>
            <div className="card att-stat"><span className="muted">Holiday</span><strong>{summary.holiday}</strong></div>
          </section>
          <p className="muted">{basis}</p>

          {summary.target && summary.percentage !== null && (
            <div className="form-info" role="status">
              {summary.target.attend_needed === 0
                ? `You're at or above your ${tnum}% target. You could miss about ${summary.target.can_miss ?? 0} more session(s) and stay there.`
                : summary.target.attend_needed
                  ? `To reach your ${tnum}% target you'd need to attend about ${summary.target.attend_needed} more session(s) in a row.`
                  : `Your ${tnum}% target can't be reached from these records.`}
              {" "}{summary.target.note}
            </div>
          )}

          <section className="card">
            <h2>Suggestions</h2>
            <ul className="tips">{summary.insights.map((t, i) => <li key={i}>{t}</li>)}</ul>
          </section>

          <div className="att-two">
            <section className="card">
              <h2>By month</h2>
              <ul className="month-list">
                {summary.months.map((m) => (
                  <li key={m.month}>
                    <strong>{monthLabel(m.month)}</strong>
                    <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: `${((m.present + m.absent + m.holiday) / maxMonth) * 100}%` }} /></span>
                    <span className="muted">{m.present}P · {m.absent}A · {m.holiday}H · {pct(m.percentage)}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="card">
              <h2>Absence reasons</h2>
              {summary.reasons.length === 0 ? <p className="muted">No absences recorded.</p>
                : <Bars rows={summary.reasons} labelKey="label" valueKey="count" max={maxReason} />}
              {summary.reasons.length > 0 && <p className="muted">Counts how often you chose each category. Not proof of approved leave.</p>}
            </section>
          </div>

          {summary.subjects.some((s) => s.subject !== null) && (
            <section className="card">
              <h2>By subject</h2>
              <div className="table-wrap">
                <table className="data-table">
                  <thead><tr><th>Subject</th><th>Present</th><th>Absent</th><th>Holiday</th><th>Attendance</th></tr></thead>
                  <tbody>{summary.subjects.map((s, i) => (
                    <tr key={i}>
                      <td data-label="Subject">{s.subject === null ? "No subject (whole day)" : s.name || subjectName(s.subject) || "Subject"}</td>
                      <td data-label="Present">{s.present}</td><td data-label="Absent">{s.absent}</td><td data-label="Holiday">{s.holiday}</td>
                      <td data-label="Attendance">{pct(s.percentage)}</td>
                    </tr>))}</tbody>
                </table>
              </div>
              <p className="muted">Each subject is calculated separately from its own entries.</p>
            </section>
          )}

          <section className="card">
            <h2>History</h2>
            <ul className="history">
              {records.slice(0, shown).map((r) => (
                <li key={r.id}>
                  <div className="hist-main">
                    <strong>{fmtD(r.date)}</strong>
                    <Badge tone={TONE[r.status]}>{LABEL[r.status]}</Badge>
                    <span className="muted">{r.subject_name || "Whole day"}{r.period ? ` · session ${r.period}` : ""}</span>
                    {r.reason && <span className="muted">· {REASON_LABEL[r.reason]}</span>}
                  </div>
                  {r.note && <p className="muted hist-note">{r.note}</p>}
                  <div className="row-actions">
                    <Button size="sm" variant="ghost" aria-label={`Edit entry for ${fmtD(r.date)}`} onClick={() => setDialog({ open: true, entry: r })}>Edit</Button>
                    <Button size="sm" variant="ghost" aria-label={`Delete entry for ${fmtD(r.date)}`} onClick={() => setDel(r)}>Delete</Button>
                  </div>
                </li>
              ))}
            </ul>
            {records.length > shown && <Button variant="secondary" size="sm" onClick={() => setShown(shown + PAGE)}>Show more ({records.length - shown} older)</Button>}
          </section>
        </div>
      )}

      <EntryDialog open={dialog.open} entry={dialog.entry} subjects={subjects} onClose={() => setDialog({ open: false, entry: null })}
        onSaved={(_, edited) => { setDialog({ open: false, entry: null }); toast(edited ? "Entry updated." : "Entry added."); load(); }} />
      <Dialog open={!!del} title="Delete this entry?" onClose={() => setDel(null)}
        footer={<><Button variant="ghost" onClick={() => setDel(null)}>Cancel</Button><Button onClick={remove}>Yes, delete</Button></>}>
        <p>{del && `${fmtD(del.date)} · ${LABEL[del.status]}. This also changes your totals and can't be undone.`}</p>
      </Dialog>
    </div>
  );
}
