import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { useToast } from "../toast.jsx";
import { Badge, Button, Dialog, EmptyState, ErrorState, Field, PageHeader, SkeletonList, fmtD } from "./ui.jsx";
import { ExamFacts, PdfButtons } from "./Seats.jsx";

const netMsg = (e) => (e instanceof TypeError ? "Can't reach the server. Check your connection and try again." : e.message);
const BLANK = { name: "", semester: "", academic_year: "", batch: "", exam_date: "", instructions: "" };
const CSV_HELP = "roll_no,roll_to,room,seat,section,note";

function Err({ msg }) {
  return msg ? <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{msg}</span></div> : null;
}

/* ---------- create / edit details ---------- */
function ExamForm({ initial, onSaved, onCancel, isNew }) {
  const [f, setF] = useState({ ...BLANK, ...Object.fromEntries(Object.entries(initial || {}).map(([k, v]) => [k, v ?? ""])) });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault(); setBusy(true); setErr("");
    const body = { name: f.name.trim(), semester: f.semester === "" ? null : Number(f.semester), academic_year: f.academic_year.trim(),
      batch: f.batch.trim(), exam_date: f.exam_date || null, instructions: f.instructions.trim() };
    try {
      onSaved(isNew ? await api("/manage/exams/", { method: "POST", body }) : await api(`/manage/exams/${initial.id}/`, { method: "PATCH", body }));
    } catch (x) { setErr(netMsg(x)); } finally { setBusy(false); }
  }
  return (
    <form className="stack" onSubmit={save}>
      <Field label="Examination name" htmlFor="ex-name"><input id="ex-name" required maxLength={150} value={f.name} onChange={set("name")} placeholder="e.g. Term-I Examination" /></Field>
      <div className="grid-2">
        <Field label="Exam date" htmlFor="ex-date"><input id="ex-date" type="date" value={f.exam_date} onChange={set("exam_date")} /></Field>
        <Field label="Semester" htmlFor="ex-sem"><input id="ex-sem" type="number" min="1" max="12" value={f.semester} onChange={set("semester")} /></Field>
        <Field label="Academic year" htmlFor="ex-ay"><input id="ex-ay" maxLength={20} value={f.academic_year} onChange={set("academic_year")} placeholder="2026-27" /></Field>
        <Field label="Batch" htmlFor="ex-batch"><input id="ex-batch" maxLength={60} value={f.batch} onChange={set("batch")} placeholder="B.Tech 2026 batch" /></Field>
      </div>
      <Field label="Instructions for students (optional)" htmlFor="ex-ins"><textarea id="ex-ins" value={f.instructions} onChange={set("instructions")} /></Field>
      <Err msg={err} />
      <div className="card-actions">
        <Button loading={busy} disabled={!f.name.trim()}>{isNew ? "Create draft" : "Save details"}</Button>
        {onCancel && <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}

/* ---------- one allotment row (view / edit) ---------- */
function RowLine({ r, base, onChanged, onDelete }) {
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState(r);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save() {
    setBusy(true); setErr("");
    try { await api(`/manage/rows/${r.id}/`, { method: "PATCH", body: { section: f.section, roll_from: f.roll_from, roll_to: f.roll_to, room: f.room, seat: f.seat, note: f.note } }); setEdit(false); onChanged(); }
    catch (e) { setErr(netMsg(e)); } finally { setBusy(false); }
  }
  if (!edit) return (
    <tr>
      <td data-label="Roll">{r.roll_from}{r.roll_to ? ` → ${r.roll_to}` : ""}</td>
      <td data-label="Section">{r.section || "All"}</td>
      <td data-label="Room">{r.room}</td>
      <td data-label="Seat">{r.seat || "—"}</td>
      <td data-label="Note">{r.note || "—"}</td>
      <td className="row-actions">
        <Button size="sm" variant="ghost" onClick={() => setEdit(true)} aria-label={`Edit ${r.roll_from}`}>Edit</Button>
        <Button size="sm" variant="ghost" onClick={() => onDelete(r)} aria-label={`Delete ${r.roll_from}`}>Delete</Button>
      </td>
    </tr>
  );
  return (
    <tr className="row-edit">
      <td colSpan={6}>
        <div className="row-form">
          <input aria-label="Roll from" value={f.roll_from} onChange={set("roll_from")} />
          <input aria-label="Roll to (optional)" placeholder="to (optional)" value={f.roll_to} onChange={set("roll_to")} />
          <input aria-label="Section (optional)" placeholder="Section" value={f.section} onChange={set("section")} />
          <input aria-label="Room" value={f.room} onChange={set("room")} />
          <input aria-label="Seat (optional)" placeholder="Seat" value={f.seat} onChange={set("seat")} />
          <input aria-label="Note (optional)" placeholder="Note" value={f.note} onChange={set("note")} />
        </div>
        <Err msg={err} />
        <div className="card-actions"><Button size="sm" loading={busy} onClick={save}>Save row</Button><Button size="sm" variant="ghost" onClick={() => { setEdit(false); setF(r); setErr(""); }}>Cancel</Button></div>
      </td>
    </tr>
  );
}

const EMPTY_ROW = { roll_from: "", roll_to: "", section: "", room: "", seat: "", note: "" };

/* ---------- the detail workspace for one exam ---------- */
function ExamWorkspace({ id, isAdmin, onChanged, onDeleted }) {
  const toast = useToast();
  const [exam, setExam] = useState(null);
  const [rows, setRows] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [err, setErr] = useState("");
  const [loadErr, setLoadErr] = useState("");
  const [busy, setBusy] = useState("");
  const [editing, setEditing] = useState(false);
  const [newRow, setNewRow] = useState(EMPTY_ROW);
  const [rowErr, setRowErr] = useState("");
  const [csv, setCsv] = useState({ text: "", name: "", res: null, replace: false, err: "" });
  const [sugg, setSugg] = useState(null);
  const [pick, setPick] = useState({});
  const [prev, setPrev] = useState({ roll: "", res: null, err: "" });
  const [confirm, setConfirm] = useState(null);
  const pdfInput = useRef(null);

  async function load() {
    setLoadErr("");
    try {
      const [e, r] = await Promise.all([api(`/manage/exams/${id}/`), api(`/manage/exams/${id}/rows/`)]);
      setExam(e); setRows(r.rows); setConflicts(r.conflicts);
    } catch (x) { setLoadErr(netMsg(x)); }
  }
  useEffect(() => { setExam(null); setSugg(null); setCsv({ text: "", name: "", res: null, replace: false, err: "" }); setPrev({ roll: "", res: null, err: "" }); setEditing(false); setErr(""); load(); }, [id]);

  const run = async (key, fn, okMsg) => {
    setBusy(key); setErr("");
    try { await fn(); if (okMsg) toast(okMsg); } catch (x) { setErr(netMsg(x)); } finally { setBusy(""); }
  };
  const refreshAll = async () => { await load(); onChanged(); };

  const publish = () => run("pub", async () => {
    try { setExam(await api(`/manage/exams/${id}/publish/`, { method: "POST" })); onChanged(); }
    catch (x) { if (x.status === 400) { await load(); } throw x; }
  }, "Published. Students can now see their seats.");
  const unpublish = () => run("unpub", async () => { setExam(await api(`/manage/exams/${id}/unpublish/`, { method: "POST" })); onChanged(); }, "Unpublished. Students can no longer see it.");

  function uploadPdf(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) { setErr("That PDF is too large (limit 8 MB)."); return; }
    const fd = new FormData(); fd.append("file", file);
    run("pdf", async () => { setExam(await api(`/manage/exams/${id}/document/`, { method: "POST", body: fd })); setSugg(null); onChanged(); }, "PDF saved.");
  }

  async function addRow(e) {
    e.preventDefault(); setRowErr("");
    try { const r = await api(`/manage/exams/${id}/rows/`, { method: "POST", body: newRow }); setRows(r.rows); setConflicts(r.conflicts); setNewRow(EMPTY_ROW); onChanged(); }
    catch (x) { setRowErr(netMsg(x)); }
  }

  function pickCsv(e) {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    if (f.size > 1_000_000) { setCsv({ ...csv, err: "The file is too large (limit 1 MB)." }); return; }
    const rd = new FileReader();
    rd.onload = () => setCsv({ text: String(rd.result || ""), name: f.name, res: null, replace: csv.replace, err: "" });
    rd.onerror = () => setCsv({ ...csv, err: "Couldn't read that file." });
    rd.readAsText(f);
  }
  async function csvRun(dry) {
    setBusy("csv"); setCsv((c) => ({ ...c, err: "" }));
    try {
      const res = await api(`/manage/exams/${id}/import-csv/`, { method: "POST", body: { csv: csv.text, dry_run: dry, replace: csv.replace } });
      setCsv((c) => ({ ...c, res: { ...res, committed: !dry } }));
      if (!dry) { await refreshAll(); toast(`${res.valid_rows} row(s) imported.`); }
    } catch (x) { setCsv((c) => ({ ...c, err: netMsg(x), res: null })); } finally { setBusy(""); }
  }

  async function extract() {
    setBusy("ext"); setErr(""); setSugg(null);
    try {
      const out = await api(`/manage/exams/${id}/extract/`, { method: "POST" });
      setSugg(out); setPick(Object.fromEntries(out.rows.map((_, i) => [i, true])));
    } catch (x) { setErr(netMsg(x)); } finally { setBusy(""); }
  }
  const sset = (i, k) => (e) => setSugg({ ...sugg, rows: sugg.rows.map((r, j) => (j === i ? { ...r, [k]: e.target.value } : r)) });
  async function saveSuggestions() {
    const chosen = sugg.rows.filter((_, i) => pick[i]).map(({ source, ...r }) => r);
    if (!chosen.length) return;
    setBusy("addsug"); setErr("");
    try {
      const out = await api(`/manage/exams/${id}/add-rows/`, { method: "POST", body: { rows: chosen } });
      setRows(out.rows); setConflicts(out.conflicts); onChanged();
      toast(`${out.added} reviewed row(s) saved as draft.${out.error_count ? ` ${out.error_count} skipped.` : ""}`);
      if (out.error_count) setErr(out.errors.map((x) => `Row ${x.row}: ${x.error}`).join("; ")); else setSugg(null);
    } catch (x) { setErr(netMsg(x)); } finally { setBusy(""); }
  }

  async function preview(e) {
    e.preventDefault(); setPrev((p) => ({ ...p, err: "", res: null }));
    const q = `roll_no=${encodeURIComponent(prev.roll.trim())}${prev.section?.trim() ? `&section=${encodeURIComponent(prev.section.trim())}` : ""}`;
    try { const res = await api(`/manage/exams/${id}/preview/?${q}`); setPrev((p) => ({ ...p, res })); }
    catch (x) { setPrev((p) => ({ ...p, err: netMsg(x) })); }
  }

  async function doConfirm() {
    const c = confirm; setConfirm(null);
    if (c.kind === "row") await run("del", async () => { await api(`/manage/rows/${c.row.id}/`, { method: "DELETE" }); await refreshAll(); }, "Row deleted.");
    if (c.kind === "pdf") await run("del", async () => { await api(`/manage/exams/${id}/document/`, { method: "DELETE" }); await refreshAll(); }, "PDF removed.");
    if (c.kind === "exam") await run("del", async () => { await api(`/manage/exams/${id}/`, { method: "DELETE" }); onDeleted(); }, "Examination deleted.");
  }

  if (loadErr) return <ErrorState message={loadErr} onRetry={load} />;
  if (!exam) return <SkeletonList count={2} />;
  const published = exam.status === "published";

  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <div>
            <h2 className="card-title">{exam.name}</h2>
            <ExamFacts exam={exam} />
          </div>
          <Badge tone={published ? "success" : "warning"}>{published ? "Published" : "Draft — hidden from students"}</Badge>
        </div>
        {exam.managers?.length > 0 && <p className="muted">Faculty assigned: {exam.managers.join(", ")}</p>}
        <Err msg={err} />
        <div className="card-actions">
          {published
            ? <Button variant="secondary" loading={busy === "unpub"} onClick={unpublish}>Unpublish</Button>
            : <Button loading={busy === "pub"} onClick={publish} disabled={rows.length === 0 || conflicts.length > 0}>Publish to students</Button>}
          <Button variant="ghost" onClick={() => setEditing(!editing)}>{editing ? "Close details" : "Edit details"}</Button>
          {isAdmin && <Button variant="ghost" onClick={() => setConfirm({ kind: "exam" })}>Delete examination</Button>}
        </div>
        {!published && rows.length === 0 && <p className="muted">Add the allotment rows below before publishing.</p>}
        {!published && conflicts.length > 0 && <p className="muted">Fix the problems listed under “Checks” before publishing.</p>}
        {editing && <div style={{ marginTop: 12 }}><ExamForm initial={exam} onSaved={(e) => { setExam(e); setEditing(false); onChanged(); toast("Details saved."); }} onCancel={() => setEditing(false)} /></div>}
      </section>

      <section className="card">
        <h2>Official PDF</h2>
        {exam.has_document ? (
          <>
            <p className="muted">{exam.document_name}</p>
            <PdfButtons path={`/manage/exams/${id}/document/`} filename={exam.document_name} />
          </>
        ) : <p className="muted">No PDF uploaded yet. Students see the PDF only after you publish.</p>}
        <input ref={pdfInput} type="file" accept="application/pdf,.pdf" hidden onChange={uploadPdf} aria-label="Choose PDF file" />
        <div className="card-actions">
          <Button size="sm" variant="secondary" loading={busy === "pdf"} onClick={() => pdfInput.current?.click()}>{exam.has_document ? "Replace PDF" : "Upload PDF"}</Button>
          {exam.has_document && <Button size="sm" variant="ghost" onClick={() => setConfirm({ kind: "pdf" })}>Remove PDF</Button>}
        </div>
      </section>

      <section className="card">
        <h2>Allotment rows <span className="muted">({rows.length})</span></h2>
        <p className="muted">A row can be a range of roll numbers (from → to) or a single roll number. A single-roll row overrides a range. Only enter what the official notice says.</p>
        {rows.length === 0 ? <p className="muted">No rows yet.</p> : (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Roll</th><th>Section</th><th>Room</th><th>Seat</th><th>Note</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>{rows.map((r) => <RowLine key={r.id} r={r} onChanged={refreshAll} onDelete={(row) => setConfirm({ kind: "row", row })} />)}</tbody>
            </table>
          </div>
        )}
        <form className="row-add" onSubmit={addRow}>
          <h3>Add a row</h3>
          <div className="row-form">
            <input aria-label="New row: roll from" required placeholder="Roll (from)" value={newRow.roll_from} onChange={(e) => setNewRow({ ...newRow, roll_from: e.target.value })} />
            <input aria-label="New row: roll to" placeholder="to (optional)" value={newRow.roll_to} onChange={(e) => setNewRow({ ...newRow, roll_to: e.target.value })} />
            <input aria-label="New row: section" placeholder="Section (optional)" value={newRow.section} onChange={(e) => setNewRow({ ...newRow, section: e.target.value })} />
            <input aria-label="New row: room" required placeholder="Room" value={newRow.room} onChange={(e) => setNewRow({ ...newRow, room: e.target.value })} />
            <input aria-label="New row: seat" placeholder="Seat (optional)" value={newRow.seat} onChange={(e) => setNewRow({ ...newRow, seat: e.target.value })} />
            <input aria-label="New row: note" placeholder="Note (optional)" value={newRow.note} onChange={(e) => setNewRow({ ...newRow, note: e.target.value })} />
          </div>
          <Err msg={rowErr} />
          <Button size="sm" disabled={!newRow.roll_from.trim() || !newRow.room.trim()}>Add row</Button>
        </form>
      </section>

      <section className="card">
        <h2>Import from CSV</h2>
        <p className="muted">Header line: <code>{CSV_HELP}</code> (roll_no and room are required). Check the file first; nothing is saved until you import.</p>
        <Field label="CSV file" htmlFor="csv-file"><input id="csv-file" type="file" accept=".csv,text/csv" onChange={pickCsv} /></Field>
        <label className="check"><input type="checkbox" checked={csv.replace} onChange={(e) => setCsv({ ...csv, replace: e.target.checked, res: null })} /> Replace all existing rows with this file</label>
        <Err msg={csv.err} />
        <div className="card-actions">
          <Button size="sm" variant="secondary" loading={busy === "csv"} disabled={!csv.text} onClick={() => csvRun(true)}>Check file</Button>
          <Button size="sm" loading={busy === "csv"} disabled={!csv.text || !csv.res || csv.res.committed || csv.res.valid_rows === 0 || csv.res.conflicts?.length > 0} onClick={() => csvRun(false)}>Import valid rows</Button>
        </div>
        {csv.res && (
          <div className="form-info" role="status">
            {csv.res.committed ? `Imported ${csv.res.valid_rows} row(s); ${csv.res.error_count} skipped.` : `${csv.name || "File"}: ${csv.res.valid_rows} valid row(s), ${csv.res.error_count} with problems. Nothing saved yet.`}
            {csv.res.errors.length > 0 && <ul className="import-errors">{csv.res.errors.map((e, i) => <li key={i}>Row {e.row}: {e.error}</li>)}</ul>}
            {!csv.res.committed && csv.res.conflicts?.length > 0 && <><strong> Conflicts (fix the file first):</strong><ul className="import-errors">{csv.res.conflicts.map((c, i) => <li key={i}>{c}</li>)}</ul></>}
          </div>
        )}
      </section>

      <section className="card">
        <h2>Suggest rows from the PDF</h2>
        <p className="muted">Reads the text inside the uploaded PDF and proposes rows. These are only suggestions and may be wrong: check each against the PDF, fix them, and tick the ones to keep. Scanned (image-only) PDFs cannot be read.</p>
        <div className="card-actions"><Button size="sm" variant="secondary" loading={busy === "ext"} disabled={!exam.has_document} onClick={extract}>Read PDF</Button></div>
        {sugg && sugg.rows.length === 0 && <p className="muted">Text was found but no rows could be recognised. Use CSV import or add rows by hand.</p>}
        {sugg && sugg.rows.length > 0 && (
          <>
            <div className="sugg-list">
              {sugg.rows.map((r, i) => (
                <div key={i} className="sugg">
                  <label className="check"><input type="checkbox" checked={!!pick[i]} onChange={(e) => setPick({ ...pick, [i]: e.target.checked })} /> Keep</label>
                  <div className="row-form">
                    <input aria-label={`Suggestion ${i + 1} roll from`} value={r.roll_from} onChange={sset(i, "roll_from")} />
                    <input aria-label={`Suggestion ${i + 1} roll to`} value={r.roll_to} onChange={sset(i, "roll_to")} />
                    <input aria-label={`Suggestion ${i + 1} section`} value={r.section} onChange={sset(i, "section")} />
                    <input aria-label={`Suggestion ${i + 1} room`} value={r.room} onChange={sset(i, "room")} />
                    <input aria-label={`Suggestion ${i + 1} seat`} value={r.seat} onChange={sset(i, "seat")} />
                  </div>
                  <p className="muted">From the PDF: “{r.source}”</p>
                </div>
              ))}
            </div>
            <Button size="sm" loading={busy === "addsug"} onClick={saveSuggestions}>Save ticked rows as draft</Button>
          </>
        )}
      </section>

      <section className="card">
        <h2>Checks</h2>
        {conflicts.length === 0 ? <p className="muted">{rows.length ? "No duplicate or overlapping assignments found." : "Nothing to check yet."}</p>
          : <ul className="import-errors">{conflicts.map((c, i) => <li key={i}>{c}</li>)}</ul>}
        <form className="seat-search" onSubmit={preview} style={{ marginTop: 12, marginBottom: 0 }}>
          <Field label="Preview a roll number as a student would see it" htmlFor="prev-roll"><input id="prev-roll" value={prev.roll} onChange={(e) => setPrev({ ...prev, roll: e.target.value })} /></Field>
          <Field label="Section (if rows are section-specific)" htmlFor="prev-sec"><input id="prev-sec" value={prev.section || ""} onChange={(e) => setPrev({ ...prev, section: e.target.value })} /></Field>
          <Button variant="secondary" disabled={!prev.roll.trim()}>Preview</Button>
        </form>
        <Err msg={prev.err} />
        {prev.res && (
          <div className="form-info" role="status">
            {prev.res.found ? `${prev.res.roll_no}: ${prev.res.result.room}${prev.res.result.seat ? `, seat ${prev.res.result.seat}` : ""}${prev.res.result.note ? ` — ${prev.res.result.note}` : ""}` : `No allotment found for ${prev.res.roll_no}.`}
          </div>
        )}
      </section>

      <Dialog open={!!confirm} title="Are you sure?" onClose={() => setConfirm(null)}
        footer={<><Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button><Button onClick={doConfirm}>Yes, continue</Button></>}>
        <p>{confirm?.kind === "exam" ? "This permanently deletes the examination, its PDF and all its rows." : confirm?.kind === "pdf" ? "This removes the uploaded PDF." : "This deletes this allotment row."}</p>
      </Dialog>
    </div>
  );
}

/* ---------- page: list + workspace ---------- */
export default function ManageExams({ user }) {
  const isAdmin = user.role === "admin";
  const allowed = ["admin", "faculty"].includes(user.role);
  const [exams, setExams] = useState(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState(null);
  const [creating, setCreating] = useState(false);

  const load = () => api("/manage/exams/").then((l) => { setErr(""); setExams(l); }).catch((e) => setErr(netMsg(e)));
  useEffect(() => { if (allowed) load(); }, []);

  if (!allowed) return <EmptyState icon="shield" title="Not available">Only administrators and assigned faculty can manage seat allotments.</EmptyState>;

  return (
    <div>
      <PageHeader title="Manage seat allotments" description={isAdmin ? "Create examinations, upload the official PDF, add rows and publish." : "You can manage the examinations assigned to you."}
        actions={<><Link className="btn btn-ghost btn-sm" to="/seats">Student view</Link>{isAdmin && <Button size="sm" onClick={() => setCreating(true)}>New examination</Button>}</>} />
      {err && <ErrorState message={err} onRetry={load} />}
      {!err && exams === null && <SkeletonList count={2} />}
      {exams && exams.length === 0 && (
        <EmptyState icon="seat" title="No examinations yet">
          {isAdmin ? "Create an examination to get started." : "No examination has been assigned to you. An administrator can assign you one in the admin panel (Exams → Managers)."}
        </EmptyState>
      )}
      {exams && exams.length > 0 && (
        <div className="manage-grid">
          <ul className="exam-list" aria-label="Examinations">
            {exams.map((x) => (
              <li key={x.id}>
                <button className={`exam-item ${sel === x.id ? "is-active" : ""}`} onClick={() => setSel(x.id)} aria-pressed={sel === x.id}>
                  <strong>{x.name}</strong>
                  <span className="muted">{x.exam_date ? fmtD(x.exam_date) : "No date"} · {x.row_count} rows</span>
                  <Badge tone={x.status === "published" ? "success" : "warning"}>{x.status === "published" ? "Published" : "Draft"}</Badge>
                </button>
              </li>
            ))}
          </ul>
          <div>{sel ? <ExamWorkspace key={sel} id={sel} isAdmin={isAdmin} onChanged={load} onDeleted={() => { setSel(null); load(); }} /> : <EmptyState icon="seat" title="Select an examination">Choose one on the left to manage it.</EmptyState>}</div>
        </div>
      )}
      <Dialog open={creating} title="New examination" onClose={() => setCreating(false)}>
        <ExamForm isNew onCancel={() => setCreating(false)} onSaved={(e) => { setCreating(false); load(); setSel(e.id); }} />
      </Dialog>
    </div>
  );
}
