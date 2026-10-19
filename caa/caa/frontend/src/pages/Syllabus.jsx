import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { EXAMS, parseSyllabus } from "../syllabusFormat.js";
import { Badge, EmptyState, ErrorState, ExternalButton, PageHeader, SkeletonList, safeUrl } from "./ui.jsx";

const arr = (d) => (Array.isArray(d) ? d : d?.results || []);

function Content({ text }) {
  const { intro, units } = parseSyllabus(text);
  return (
    <div className="syl-content">
      {intro.map((l, i) => <p key={i}>{l}</p>)}
      {units.map((u, i) => (
        <section key={i} className="syl-unit">
          {u.title && <h4>{u.title}</h4>}
          <ul>
            {u.items.map((it, j) => (
              <li key={j}>
                {it.text}
                {it.subs.length > 0 && <ul>{it.subs.map((s, k) => <li key={k}>{s}</li>)}</ul>}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function SubjectCard({ subject, entries, open, onToggle, isStaff, focusExam, focused }) {
  const [exam, setExam] = useState("mid1");
  const cardRef = useRef(null);
  useEffect(() => { if (focused) { if (focusExam) setExam(focusExam); cardRef.current?.scrollIntoView({ block: "start" }); } }, [focused, focusExam]);
  const e = entries[exam];
  const has = (k) => !!(entries[k] && (entries[k].content?.trim() || safeUrl(entries[k].pdf_url)));
  const pdf = e ? safeUrl(e.pdf_url) : "";
  const panelId = `syl-${subject.id}`;
  return (
    <article ref={cardRef} className={`card syl-card ${focused ? "is-target" : ""}`}>
      <button className="syl-head" aria-expanded={open} aria-controls={panelId} onClick={onToggle}>
        <span className="syl-title">
          <span className="syl-code">{subject.code}</span>
          <strong>{subject.name}</strong>
        </span>
        <span className="syl-badges" aria-label="Available syllabus">
          {EXAMS.map((x) => <Badge key={x.key} tone={has(x.key) ? "success" : "neutral"}>{x.label}</Badge>)}
        </span>
        <Icon name="arrow" size={18} className={`syl-chev ${open ? "is-open" : ""}`} />
      </button>
      {open && (
        <div id={panelId} className="syl-panel">
          <div className="tabs syl-tabs" role="tablist" aria-label={`${subject.name} examinations`}>
            {EXAMS.map((x) => (
              <button key={x.key} role="tab" aria-selected={exam === x.key} className={`tab ${exam === x.key ? "is-active" : ""}`} onClick={() => setExam(x.key)}>
                {x.label}
              </button>
            ))}
          </div>
          <div role="tabpanel" aria-label={EXAMS.find((x) => x.key === exam).label}>
            {!has(exam) ? (
              <EmptyState className="empty-sm" icon="syllabus" title="Syllabus not yet uploaded">
                The {EXAMS.find((x) => x.key === exam).label} syllabus for this subject hasn't been added yet.
                {isStaff && " Add it from the Admin panel under Syllabus entries."}
              </EmptyState>
            ) : (
              <>
                <div className="syl-meta">
                  {e.verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Awaiting verification</Badge>}
                  {e.semester && <span className="muted">Semester {e.semester}</span>}
                </div>
                {!e.verified && <p className="muted syl-note">This has not been checked against the official document yet. Confirm with your faculty before relying on it.</p>}
                {e.content?.trim() && <Content text={e.content} />}
                {pdf && <div className="card-actions"><ExternalButton href={pdf}>View official PDF</ExternalButton></div>}
              </>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

export default function Syllabus({ user }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [sem, setSem] = useState("all");
  const [openId, setOpenId] = useState(null);
  const [tick, setTick] = useState(0);
  const isStaff = ["admin", "faculty"].includes(user.role);
  // deep link from a notification: /syllabus?subject=<id>&exam=mid1
  const qs = new URLSearchParams(useLocation().search);
  const focusId = Number(qs.get("subject")) || null;
  const focusExam = EXAMS.some((x) => x.key === qs.get("exam")) ? qs.get("exam") : "";
  useEffect(() => { if (focusId && data?.subjects.some((s) => s.id === focusId)) { setOpenId(focusId); setSem("all"); setQ(""); } }, [data, focusId, focusExam]);

  useEffect(() => { document.title = "Academic syllabus · College Academic Assistant"; }, []);
  useEffect(() => {
    let off = false;
    setErr("");
    Promise.all([api("/subjects/"), api("/syllabus/")])
      .then(([subjects, entries]) => { if (!off) setData({ subjects: arr(subjects), entries: arr(entries) }); })
      .catch((e) => { if (!off) setErr(e.message); });
    return () => { off = true; };
  }, [tick]);

  const rows = useMemo(() => {
    if (!data) return null;
    const by = {};
    data.entries.forEach((e) => { (by[e.subject] = by[e.subject] || {})[e.exam] = e; });
    return data.subjects.map((s) => {
      const ent = by[s.id] || {};
      const semester = Object.values(ent).map((x) => x.semester).find(Boolean) || null;
      return { subject: s, entries: ent, semester };
    });
  }, [data]);

  if (err && !data) return <div><PageHeader title="Academic syllabus" /><ErrorState message={err} onRetry={() => setTick((t) => t + 1)} /></div>;

  const semesters = rows ? [...new Set(rows.map((r) => r.semester).filter(Boolean))].sort((a, b) => a - b) : [];
  const needle = q.trim().toLowerCase();
  const shown = rows ? rows.filter((r) =>
    (sem === "all" || String(r.semester) === sem || (sem === "none" && !r.semester)) &&
    (!needle || r.subject.name.toLowerCase().includes(needle) || r.subject.code.toLowerCase().includes(needle))) : null;
  const groups = {};
  (shown || []).forEach((r) => { (groups[r.semester || 0] = groups[r.semester || 0] || []).push(r); });
  const order = Object.keys(groups).map(Number).sort((a, b) => (a || 99) - (b || 99));

  return (
    <div>
      <PageHeader title="Academic syllabus" description="Pick a subject, then switch between Mid-Term 1, Mid-Term 2 and End-Semester." />
      <div className="toolbar">
        <div className="field syl-filter">
          <label htmlFor="sem" className="sr-only">Semester</label>
          <select id="sem" value={sem} onChange={(e) => setSem(e.target.value)}>
            <option value="all">All semesters</option>
            {semesters.map((s) => <option key={s} value={s}>Semester {s}</option>)}
            {rows?.some((r) => !r.semester) && <option value="none">Semester not set</option>}
          </select>
        </div>
        <div className="search">
          <Icon name="search" size={18} />
          <input type="search" aria-label="Search subjects" placeholder="Search by subject or code" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {focusId && data && !data.subjects.some((s) => s.id === focusId) && (
        <div className="form-info" role="status">That syllabus is no longer available.</div>
      )}
      {!shown ? <SkeletonList /> :
        rows.length === 0 ? (
          <EmptyState icon="syllabus" title="No subjects yet">Subjects and their syllabus will appear here once the college adds them.</EmptyState>
        ) : shown.length === 0 ? (
          <EmptyState title="No subjects match">Try a different search or semester.</EmptyState>
        ) : order.map((k) => (
          <section key={k} className="syl-group" aria-label={k ? `Semester ${k}` : "Semester not set"}>
            <h2 className="syl-sem">{k ? `Semester ${k}` : "Semester not set"}</h2>
            <div className="stack">
              {groups[k].map((r) => (
                <SubjectCard key={r.subject.id} subject={r.subject} entries={r.entries} isStaff={isStaff}
                  focused={focusId === r.subject.id} focusExam={focusExam}
                  open={openId === r.subject.id} onToggle={() => setOpenId(openId === r.subject.id ? null : r.subject.id)} />
              ))}
            </div>
          </section>
        ))}
    </div>
  );
}
