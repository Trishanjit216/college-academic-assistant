import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { Badge, Button, EmptyState, ErrorState, Field, PageHeader, SkeletonList, fmtD, fmtDT } from "./ui.jsx";

const netMsg = (e) => (e instanceof TypeError ? "Can't reach the server. Check your connection and try again." : e.message);

/** Fetch the PDF with the login token (it is not a public link), then open or save it. */
export async function fetchPdf(path, filename, mode) {
  const blob = await api(path, { blob: true });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  if (mode === "download") a.download = filename || "seat-allotment.pdf";
  else { a.target = "_blank"; a.rel = "noopener noreferrer"; }
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function PdfButtons({ path, filename }) {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  async function go(mode) {
    setBusy(mode); setErr("");
    try { await fetchPdf(path, filename, mode); } catch (e) { setErr(netMsg(e)); } finally { setBusy(""); }
  }
  return (
    <div>
      <div className="card-actions">
        <Button variant="secondary" size="sm" icon="external" loading={busy === "open"} onClick={() => go("open")}>Open official PDF</Button>
        <Button variant="secondary" size="sm" loading={busy === "download"} onClick={() => go("download")}>Download PDF</Button>
      </div>
      {err && <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{err}</span></div>}
    </div>
  );
}

export function ExamFacts({ exam }) {
  return (
    <div className="card-meta">
      {exam.exam_date && <span><Icon name="events" size={16} />{fmtD(exam.exam_date)}</span>}
      {exam.semester && <span>Semester {exam.semester}</span>}
      {exam.batch && <span>{exam.batch}</span>}
      {exam.academic_year && <span>{exam.academic_year}</span>}
    </div>
  );
}

export default function Seats({ user }) {
  const isStaff = ["admin", "faculty"].includes(user.role);
  const [exams, setExams] = useState(null);
  const [loadErr, setLoadErr] = useState("");
  const [examId, setExamId] = useState("");
  const [roll, setRoll] = useState(user.roll_no || "");
  const [state, setState] = useState({ loading: false, data: null, err: "", code: "" });

  const load = () => {
    setLoadErr("");
    api("/exams/").then((l) => {
      setExams(l);
      if (l.length === 1) setExamId(String(l[0].id));
    }).catch((e) => setLoadErr(netMsg(e)));
  };
  useEffect(load, []);

  const exam = (exams || []).find((x) => String(x.id) === examId);

  async function find(id = examId, r = roll) {
    if (!id) return;
    setState({ loading: true, data: null, err: "", code: "" });
    try {
      const q = r.trim() ? `?roll_no=${encodeURIComponent(r.trim())}` : "";
      setState({ loading: false, data: await api(`/exams/${id}/lookup/${q}`), err: "", code: "" });
    } catch (e) {
      setState({ loading: false, data: null, code: e.code || "", err: netMsg(e) });
    }
  }
  // Students with a roll number on their profile get their result as soon as an exam is chosen.
  useEffect(() => { setState({ loading: false, data: null, err: "", code: "" }); if (examId && roll.trim()) find(examId, roll); }, [examId]);

  const d = state.data;
  return (
    <div>
      <PageHeader
        title="Exam seat allotment"
        description="Find your room and seat for a published examination."
        actions={isStaff && <Link className="btn btn-secondary btn-sm" to="/seats/manage">Manage allotments</Link>}
      />

      {loadErr && <ErrorState message={loadErr} onRetry={load} />}
      {!loadErr && exams === null && <SkeletonList count={1} />}
      {exams && exams.length === 0 && (
        <EmptyState icon="seat" title="No seat allotment published yet">
          No seat allotment has been published for any examination yet. Check back after the examination cell releases it.
        </EmptyState>
      )}

      {exams && exams.length > 0 && (
        <form className="card seat-search" onSubmit={(e) => { e.preventDefault(); find(); }}>
          <Field label="Examination" htmlFor="seat-exam">
            <select id="seat-exam" value={examId} onChange={(e) => setExamId(e.target.value)}>
              <option value="">Select an examination…</option>
              {exams.map((x) => <option key={x.id} value={x.id}>{x.name}{x.exam_date ? ` — ${fmtD(x.exam_date)}` : ""}</option>)}
            </select>
          </Field>
          <Field label="Roll number" htmlFor="seat-roll" hint={isStaff ? "Faculty and administrators can look up any roll number they manage." : "Students can only see their own seat."}>
            <input id="seat-roll" value={roll} onChange={(e) => setRoll(e.target.value)} autoComplete="off" />
          </Field>
          <Button loading={state.loading} disabled={!examId || !roll.trim()}>Find my seat</Button>
        </form>
      )}

      {exams && exams.length > 0 && !isStaff && !user.roll_no && (
        <p className="muted seat-note">Tip: add your roll number in <Link to="/profile">your profile</Link> and it will be filled in automatically.</p>
      )}

      {state.err && (
        <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{state.err}</span></div>
      )}

      {exam && (
        <article className="card seat-card">
          <div className="card-head">
            <div>
              <h2 className="card-title">{exam.name}</h2>
              <ExamFacts exam={exam} />
            </div>
            <Badge tone="success">Published{exam.published_at ? ` ${fmtDT(exam.published_at)}` : ""}</Badge>
          </div>

          {d && d.found && (
            <>
              <p className="muted" style={{ marginTop: 12 }}>Roll number <strong>{d.roll_no}</strong></p>
              <dl className="seat-facts">
                <div><dt>Room / hall</dt><dd>{d.result.room}</dd></div>
                {d.result.seat && <div><dt>Seat / bench</dt><dd>{d.result.seat}</dd></div>}
              </dl>
              {d.result.note && <p className="card-body"><strong>Note from the examination cell: </strong>{d.result.note}</p>}
            </>
          )}
          {d && !d.found && (
            <div className="form-info" role="status">
              No seat allotment was found for roll number <strong>{d.roll_no}</strong> in this examination. Please verify your roll number
              and check the official notice{exam.has_document ? " (button below)" : ""} or contact the examination cell.
            </div>
          )}
          {exam.instructions && <p className="card-body"><strong>Instructions: </strong>{exam.instructions}</p>}
          {exam.has_document
            ? <PdfButtons path={`/exams/${exam.id}/document/`} filename={`${exam.name}.pdf`} />
            : <p className="muted">The official PDF has not been attached to this examination.</p>}
        </article>
      )}
      {exam && d && <p className="muted seat-note">Seating comes from data supplied by the examination cell. If something looks wrong, confirm with them before the exam. The official PDF is the authority.</p>}
    </div>
  );
}
