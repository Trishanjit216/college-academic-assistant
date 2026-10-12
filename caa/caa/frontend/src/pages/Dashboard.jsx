import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { FACULTY_URL } from "../Layout.jsx";
import { Badge, EmptyState, ErrorState, Section, Skeleton, dueInfo, fmtDT } from "./ui.jsx";

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};

const EXPLORE = [
  { title: "Academics", items: [
    { to: "/records", icon: "classes", name: "Class records", text: "See what was taught in each period." },
    { to: "/labs", icon: "labs", name: "Lab tracker", text: "Experiments allotted to your group." },
    { to: "/assignments", icon: "assignments", name: "Assignments", text: "Deadlines and submission details." },
    { to: "/syllabus", icon: "syllabus", name: "Academic syllabus", text: "Mid-term and end-semester syllabus by subject." },
    { to: "/seats", icon: "seat", name: "Exam seat allotment", text: "Find your room and seat for each exam." },
  ] },
  { title: "Campus", items: [
    { to: "/events", icon: "events", name: "Events calendar", text: "Dates, venues and registration." },
    { to: "/forms", icon: "forms", name: "Form and document guide", text: "Documents, formats and sizes for each form." },
    ...(FACULTY_URL ? [{ href: FACULTY_URL, icon: "user", name: "Know Your Faculty", text: "Meet your faculty. Opens in a new tab." }] : []),
  ] },
  { title: "Community", items: [
    { to: "/discussion", icon: "discussion", name: "Anonymous discussion", text: "Raise concerns without sharing your name." },
    { to: "/notifications", icon: "bell", name: "Notifications", text: "Deadline reminders in one list." },
  ] },
];

function ViewAll({ to, label }) {
  return <Link className="link-btn" to={to}>{label}<Icon name="arrow" size={16} /></Link>;
}

export default function Dashboard({ user }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const load = () => { setErr(""); api("/dashboard/").then(setD).catch((e) => setErr(e.message)); };
  useEffect(load, []);
  useEffect(() => { document.title = "Dashboard · College Academic Assistant"; }, []);

  const name = user.first_name || user.username;
  const today = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div>
      <section className="hero" aria-label="Welcome">
        <div>
          <h1>{greeting()}, {name}</h1>
          <p>{today}. Here's what needs your attention in your classes, labs and assignments.</p>
        </div>
        <Link className="btn" to="/assignments"><Icon name="assignments" size={18} />View assignments</Link>
      </section>

      {err && !d ? <div style={{ marginTop: 24 }}><ErrorState message={err} onRetry={load} /></div> :
        !d ? <div style={{ marginTop: 24 }}><Skeleton /><Skeleton /></div> : (() => {
          const pending = d.upcoming_assignments.filter((a) => !a.done);
          return (<>
            <div className="stats">
              <Link to="/records" className="card card-hover stat">
                <span className="stat-icon"><Icon name="classes" /></span>
                <span><span className="stat-num">{d.today_classes.length}</span><span className="stat-label">{d.today_classes.length === 1 ? "Class today" : "Classes today"}</span></span>
              </Link>
              <Link to="/assignments" className="card card-hover stat">
                <span className="stat-icon"><Icon name="assignments" /></span>
                <span><span className="stat-num">{pending.length}</span><span className="stat-label">Pending in the next 14 days</span></span>
              </Link>
              <Link to="/events" className="card card-hover stat">
                <span className="stat-icon"><Icon name="events" /></span>
                <span><span className="stat-num">{d.upcoming_events.length}</span><span className="stat-label">Upcoming events</span></span>
              </Link>
              <Link to="/notifications" className="card card-hover stat">
                <span className="stat-icon"><Icon name="bell" /></span>
                <span><span className="stat-num">{d.unread_notifications}</span><span className="stat-label">Unread notifications</span></span>
              </Link>
            </div>

            <div className="cols">
              <Section title="Assignments due soon" action={<ViewAll to="/assignments" label="View all" />}>
                {d.upcoming_assignments.length === 0 ? (
                  <EmptyState className="empty-sm" icon="check" title="Nothing due in the next 14 days">New assignments will show up here.</EmptyState>
                ) : (
                  <ul className="rows">
                    {d.upcoming_assignments.map((a) => {
                      const due = dueInfo(a.deadline, a.done);
                      return (
                        <li key={a.id} className={`row-item ${a.done ? "is-done" : ""}`}>
                          <div className="row-main"><strong>{a.title}</strong><span className="muted">{a.subject_name}, {fmtDT(a.deadline)}</span></div>
                          <Badge tone={due.tone}>{due.label}</Badge>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Section>

              <Section title="Today's classes" action={<ViewAll to="/records" label="All records" />}>
                {d.today_classes.length === 0 ? (
                  <EmptyState className="empty-sm" icon="classes" title="No classes recorded today">Topics appear here after faculty add them.</EmptyState>
                ) : (
                  <ul className="rows">
                    {d.today_classes.map((c) => (
                      <li key={c.id} className="row-item">
                        <div className="row-main"><strong>{c.topic}</strong><span className="muted">{c.subject_name}, period {c.period}</span></div>
                        <Badge tone={c.status === "completed" ? "success" : "neutral"}>{c.status}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              <Section title="Next lab experiments" action={<ViewAll to="/labs" label="Lab tracker" />}>
                {d.next_experiments.length === 0 ? (
                  <EmptyState className="empty-sm" icon="labs" title="No experiments scheduled">Your group's next experiment will appear here.</EmptyState>
                ) : (
                  <ul className="rows">
                    {d.next_experiments.map((e) => (
                      <li key={e.id} className="row-item">
                        <div className="row-main"><strong>Experiment {e.number}: {e.title}</strong><span className="muted">{e.lab_name}</span></div>
                        <Badge tone={e.status === "ongoing" ? "primary" : "neutral"}>{e.status === "planned" ? "upcoming" : e.status}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              <Section title="Upcoming events" action={<ViewAll to="/events" label="All events" />}>
                {d.upcoming_events.length === 0 ? (
                  <EmptyState className="empty-sm" icon="events" title="No upcoming events">Check back when the college announces new ones.</EmptyState>
                ) : (
                  <ul className="rows">
                    {d.upcoming_events.map((e) => (
                      <li key={e.id} className="row-item">
                        <div className="row-main"><strong>{e.name}</strong><span className="muted">{fmtDT(e.start)}{e.venue ? `, ${e.venue}` : ""}</span></div>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
            </div>
          </>);
        })()}

      <section className="explore" aria-labelledby="explore-h">
        <h2 id="explore-h">Explore</h2>
        {EXPLORE.map((g) => (
          <div className="explore-group" key={g.title}>
            <h3>{g.title}</h3>
            <div className="feature-grid">
              {g.items.map((it) => it.href ? (
                <a key={it.name} href={it.href} target="_blank" rel="noopener noreferrer" className="card card-hover feature">
                  <span className="stat-icon"><Icon name={it.icon} size={20} /></span>
                  <div><h3>{it.name}</h3><p>{it.text}</p></div>
                </a>
              ) : (
                <Link key={it.to} to={it.to} className="card card-hover feature">
                  <span className="stat-icon"><Icon name={it.icon} size={20} /></span>
                  <div><h3>{it.name}</h3><p>{it.text}</p></div>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
