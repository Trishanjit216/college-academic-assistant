import { useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";
import { useToast } from "../toast.jsx";
import { Button, Dialog, ErrorState, Field, PageHeader, SkeletonList, EmptyState, fmtDT, useList } from "./ui.jsx";

export default function Discussion() {
  const toast = useToast();
  const { items, err, reload } = useList("/posts/", "");
  const [t, setT] = useState("");
  const [b, setB] = useState("");
  const [posting, setPosting] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [reporting, setReporting] = useState(null); // post id
  const [reason, setReason] = useState("");
  const [deleting, setDeleting] = useState(null);   // post
  const [busy, setBusy] = useState(false);

  async function post(e) {
    e.preventDefault(); setFormErr(""); setPosting(true);
    try {
      await api("/posts/", { method: "POST", body: { title: t, body: b } });
      setT(""); setB(""); toast("Posted anonymously"); reload();
    } catch (ex) { setFormErr(ex.message); } finally { setPosting(false); }
  }
  async function sendReport() {
    setBusy(true);
    try {
      await api(`/posts/${reporting}/report/`, { method: "POST", body: { reason } });
      toast("Report sent to the moderators"); setReporting(null); setReason("");
    } catch (ex) { toast(ex.message, "danger"); } finally { setBusy(false); }
  }
  async function removePost() {
    setBusy(true);
    try { await api(`/posts/${deleting.id}/`, { method: "DELETE" }); toast("Post deleted"); setDeleting(null); reload(); }
    catch (ex) { toast(ex.message, "danger"); } finally { setBusy(false); }
  }
  async function comment(id, body, clear) {
    if (!body.trim()) return;
    try { await api(`/posts/${id}/comment/`, { method: "POST", body: { body } }); clear(); toast("Reply posted"); reload(); }
    catch (ex) { toast(ex.message, "danger"); }
  }

  return (
    <div>
      <PageHeader title="Anonymous discussion" description="Your name is never shown to other students. Posts can be reported, and moderators can remove abusive or illegal content." />

      <form className="card composer" onSubmit={post}>
        <h2 style={{ marginBottom: 12 }}>Start a conversation</h2>
        <Field label="Title" htmlFor="post-title"><input id="post-title" value={t} onChange={(e) => setT(e.target.value)} required maxLength={200} /></Field>
        <Field label="Your message" htmlFor="post-body" hint="Share a concern, suggestion or question. Be respectful.">
          <textarea id="post-body" value={b} onChange={(e) => setB(e.target.value)} required maxLength={3000} rows={4} />
        </Field>
        {formErr && <div className="form-error" role="alert"><Icon name="alert" size={18} /><span>{formErr}</span></div>}
        <Button loading={posting}>Post anonymously</Button>
      </form>

      {err && !items ? <ErrorState message={err} onRetry={reload} /> :
        !items ? <SkeletonList /> :
        items.length === 0 ? <EmptyState icon="discussion" title="No posts yet">Be the first to start a conversation.</EmptyState> : (
          <div className="stack">
            {items.map((p) => (
              <PostCard key={p.id} p={p} onComment={comment} onReport={() => { setReason(""); setReporting(p.id); }} onDelete={() => setDeleting(p)} />
            ))}
          </div>
        )}

      <Dialog open={reporting !== null} title="Report this post" onClose={() => setReporting(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setReporting(null)}>Cancel</Button>
          <Button variant="danger" loading={busy} disabled={!reason.trim()} onClick={sendReport}>Send report</Button>
        </>}>
        <p>Tell the moderators what's wrong. Your report is anonymous.</p>
        <Field label="Reason" htmlFor="report-reason">
          <textarea id="report-reason" rows={3} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
      </Dialog>

      <Dialog open={deleting !== null} title="Delete your post?" onClose={() => setDeleting(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setDeleting(null)}>Keep post</Button>
          <Button variant="danger" loading={busy} onClick={removePost}>Delete post</Button>
        </>}>
        <p>This removes "{deleting?.title}" from the discussion.</p>
      </Dialog>
    </div>
  );
}

function PostCard({ p, onReport, onComment, onDelete }) {
  const [c, setC] = useState("");
  return (
    <article className="card">
      <h2 className="card-title">{p.title}</h2>
      <div className="card-meta">
        <span className="anon"><Icon name="user" size={16} />Anonymous{p.mine ? " (you)" : ""}</span>
        <span><Icon name="clock" size={16} />{fmtDT(p.created_at)}</span>
      </div>
      <p className="post-body">{p.body}</p>

      {p.comments.length > 0 && (
        <div aria-label="Replies">
          {p.comments.map((x) => (
            <div key={x.id} className="comment">
              <span>{x.body}</span>
              <span className="muted">Anonymous{x.mine ? " (you)" : ""}</span>
            </div>
          ))}
        </div>
      )}

      <form className="reply" onSubmit={(e) => { e.preventDefault(); onComment(p.id, c, () => setC("")); }}>
        <label className="sr-only" htmlFor={`reply-${p.id}`}>Reply to {p.title}</label>
        <input id={`reply-${p.id}`} placeholder="Write a reply" value={c} onChange={(e) => setC(e.target.value)} maxLength={1500} />
        <Button variant="secondary" disabled={!c.trim()}>Reply</Button>
      </form>

      <div className="card-actions">
        <button className="link-btn" onClick={onReport}><Icon name="flag" size={16} />Report</button>
        {p.mine && <button className="link-btn danger" onClick={onDelete}><Icon name="trash" size={16} />Delete my post</button>}
      </div>
    </article>
  );
}
