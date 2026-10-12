import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { Badge, Button, EmptyState, Field, PageHeader, fmtD } from "./ui.jsx";

const TEMPLATE = "roll_no,student_name,exam_name,exam_date,room,seat,instructions";

function SeatCard({ r }) {
  return (
    <article className="card seat-card">
      <div className="card-head">
        <div>
          <h2 className="card-title">{r.exam_name}</h2>
          <div className="card-meta">
            <span><Icon name="user" size={16} />{r.student_name ? `${r.student_name}, ` : ""}{r.roll_no}</span>
            {r.exam_date && <span><Icon name="events" size={16} />{fmtD(r.exam_date)}</span>}
          </div>
        </div>
      </div>
      <dl className="seat-facts">
        <div><dt>Room / hall</dt><dd>{r.room}</dd></div>
        <div><dt>Seat / bench</dt><dd>{r.seat}</dd></div>
      </dl>
      {r.instructions && <p className="card-body"><strong>Instructions: </strong>{r.instructions}</p>}
    </article>
  );
}

function ImportPanel() {
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const file = useRef(null);

  function pick(e) {
    const f = e.target.files?.[0];
    setRes(null); setErr("");
    if (!f) return;
    if (f.size > 1_000_000) { setErr("The file is too large (limit 1 MB)."); return; }
    setName(f.name);
    const r = new FileReader();
    r.onload = () => setText(String(r.result || ""));
    r.onerror = () => setErr("Couldn't read that file.");
    r.readAsText(f);
  }
  async function run(dry) {
    setBusy(true); setErr("");
    try { setRes(await api("/seats/import/", { method: "POST", body: { csv: text, dry_run: dry } })); }
    catch (e) { setErr(e instanceof TypeError ? "Can't reach the server." : e.message); setRes(null); }
    finally { setBusy(false); }
  }
  return (
    <details className="card more import-panel">
      <summary>Import seat allotment (administrators)</summary>
      <p className="muted" style={{ marginTop: 8 }}>
        Upload a CSV from the examination cell. Required columns: <code>roll_no, exam_name, room, seat</code>.
        Optional: <code>student_name, exam_date (YYYY-MM-DD), instructions</code>. First line must be: <code>{TEMPLATE}</code>.
        Check first, then import. Rows with problems are skipped and listed; nothing is made up.
      </p>
      <Field label="CSV file" htmlFor="seat-file">
        <input id="seat-file" ref={file} type="file" accept=".csv,text/csv" onChange={pick} />
      </Field>
      {err && <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{err}</span></div>}
      <div className="card-actions">
        <Button variant="secondary" size="sm" loading={busy} disabled={!text} onClick={() => run(true)}>Check file</Button>
        <Button size="sm" loading={busy} disabled={!text || !res || !res.dry_run || res.valid_rows === 0} onClick={() => run(false)}>Import valid rows</Button>
      </div>
      {res && (
        <div className="form-info" role="status">
          {res.dry_run
            ? `${name || "File"}: ${res.valid_rows} valid row(s), ${res.error_count} with problems. Nothing saved yet.`
            : `Imported: ${res.created} added, ${res.updated} updated, ${res.error_count} skipped.`}
          {res.errors.length > 0 && (
            <ul className="import-errors">{res.errors.map((e, i) => <li key={i}>Row {e.row}: {e.error}</li>)}</ul>
          )}
        </div>
      )}
    </details>
  );
}

export default function Seats({ user }) {
  const isStaff = ["admin", "faculty"].includes(user.role);
  const isAdmin = user.role === "admin";
  const [roll, setRoll] = useState("");
  const [state, setState] = useState({ loading: false, data: null, err: "", code: "" });

  useEffect(() => { document.title = "Exam seat allotment · College Academic Assistant"; }, []);

  async function find(r) {
    setState({ loading: true, data: null, err: "", code: "" });
    try {
      const q = r ? `?roll_no=${encodeURIComponent(r)}` : "";
      setState({ loading: false, data: await api(`/seats/lookup/${q}`), err: "", code: "" });
    } catch (e) {
      setState({ loading: false, data: null, code: e.code || "", err: e instanceof TypeError ? "Can't reach the server. Check your connection and try again." : e.message });
    }
  }
  useEffect(() => { if (!isStaff && user.roll_no) find(""); }, []);

  const d = state.data;
  return (
    <div>
      <PageHeader title="Exam seat allotment" description="Find your room and seat for each examination." />

      {isStaff && (
        <form className="card seat-search" onSubmit={(e) => { e.preventDefault(); if (roll.trim()) find(roll.trim()); }}>
          <Field label="Roll number" htmlFor="seat-roll" hint="Faculty and administrators can look up any roll number.">
            <input id="seat-roll" value={roll} onChange={(e) => setRoll(e.target.value)} autoComplete="off" />
          </Field>
          <Button loading={state.loading} disabled={!roll.trim()}>Find seat</Button>
        </form>
      )}

      {!isStaff && !user.roll_no && (
        <EmptyState icon="seat" title="Add your roll number first">
          Your seat is looked up using the roll number on your profile. <Link to="/profile">Open your profile</Link> to add it.
        </EmptyState>
      )}

      {!isStaff && user.roll_no && (
        <div className="card seat-search">
          <p>Showing the seat allotment for roll number <strong>{user.roll_no}</strong>.</p>
          <Button variant="secondary" size="sm" loading={state.loading} onClick={() => find("")}>Refresh</Button>
        </div>
      )}

      {state.err && state.code !== "no_roll_no" && (
        <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{state.err}</span></div>
      )}

      {d && !d.published && (
        <EmptyState icon="seat" title="Seat allotment not yet published">The examination cell hasn't published any seating yet. Check back later.</EmptyState>
      )}
      {d && d.published && d.results.length === 0 && (
        <EmptyState icon="seat" title="No seat found">
          No allotment was found for <strong>{d.roll_no}</strong>. Check the roll number, or ask the examination cell if your seating has been published.
        </EmptyState>
      )}
      {d && d.results.length > 0 && <div className="stack">{d.results.map((r, i) => <SeatCard key={i} r={r} />)}</div>}
      {d && d.results.length > 0 && <p className="muted seat-note">Seating comes from data supplied by the examination cell. If something looks wrong, confirm with them before the exam.</p>}

      {isAdmin && <ImportPanel />}
    </div>
  );
}
