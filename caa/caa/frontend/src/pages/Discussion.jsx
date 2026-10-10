import { useState } from "react";
import { api } from "../api.js";
import { fmtDT, useList } from "./ui.jsx";

export default function Discussion() {
  const { items, err, reload } = useList("/posts/", "");
  const [t, setT] = useState("");
  const [b, setB] = useState("");
  const [msg, setMsg] = useState("");

  async function post(e) {
    e.preventDefault(); setMsg("");
    try { await api("/posts/", { method: "POST", body: { title: t, body: b } }); setT(""); setB(""); reload(); }
    catch (ex) { setMsg(ex.message); }
  }
  async function report(id) {
    const reason = prompt("Why are you reporting this?");
    if (reason) { try { await api(`/posts/${id}/report/`, { method: "POST", body: { reason } }); alert("Reported. Thank you."); } catch (e) { alert(e.message); } }
  }
  async function comment(id, body, clear) {
    if (!body.trim()) return;
    try { await api(`/posts/${id}/comment/`, { method: "POST", body: { body } }); clear(); reload(); } catch (e) { alert(e.message); }
  }

  return (
    <div>
      <h1>Anonymous discussion</h1>
      <p className="muted">Your name is never shown to other students. Posts can be reported, and moderators can remove abusive or illegal content. Be respectful.</p>
      <form className="card" onSubmit={post}>
        <input placeholder="Title" value={t} onChange={(e) => setT(e.target.value)} required maxLength={200} />
        <textarea placeholder="Share a concern, suggestion or question…" value={b} onChange={(e) => setB(e.target.value)} required maxLength={3000} rows={4} />
        {msg && <p className="error">{msg}</p>}
        <button>Post anonymously</button>
      </form>
      {err && <p className="error">{err}</p>}
      {(items || []).map((p) => <PostCard key={p.id} p={p} onReport={report} onComment={comment}
        onDelete={async () => { if (confirm("Delete your post?")) { await api(`/posts/${p.id}/`, { method: "DELETE" }); reload(); } }} />)}
    </div>
  );
}

function PostCard({ p, onReport, onComment, onDelete }) {
  const [c, setC] = useState("");
  return (
    <div className="card">
      <b>{p.title}</b> <span className="muted">Anonymous · {fmtDT(p.created_at)}</span>
      <p style={{ whiteSpace: "pre-wrap" }}>{p.body}</p>
      {p.comments.map((x) => (
        <p key={x.id} className="comment">💬 {x.body} <span className="muted">· Anonymous {x.mine && "(you)"}</span></p>
      ))}
      <div className="row">
        <input placeholder="Add a comment…" value={c} onChange={(e) => setC(e.target.value)} maxLength={1500} />
        <button onClick={() => onComment(p.id, c, () => setC(""))}>Reply</button>
      </div>
      <button className="link" onClick={() => onReport(p.id)}>🚩 Report</button>
      {p.mine && <button className="link" onClick={onDelete}>Delete my post</button>}
    </div>
  );
}
