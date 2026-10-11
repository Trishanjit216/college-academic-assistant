import { useState } from "react";
import { api } from "../api.js";
import { useToast } from "../toast.jsx";
import { Badge, Button, ListPage, fmtDT } from "./ui.jsx";

function ReportCard({ r, reload }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  async function act(path, message) {
    setBusy(true);
    try { await api(`/reports/${r.id}/${path}/`, { method: "POST" }); toast(message); reload(); }
    catch (e) { toast(e.message, "danger"); setBusy(false); }
  }
  return (
    <article className={`card ${r.resolved ? "is-done" : ""}`}>
      <div className="card-head">
        <div>
          <h2 className="card-title">{r.post_title || "Reported comment"}</h2>
          <div className="card-meta"><span>Reported {fmtDT(r.created_at)}</span></div>
        </div>
        <Badge tone={r.resolved ? "success" : "warning"}>{r.resolved ? "Resolved" : "Needs review"}</Badge>
      </div>
      <p className="card-body"><strong>Reason: </strong>{r.reason}</p>
      {r.post_body && <p className="post-body">{r.post_body}</p>}
      {r.comment_body && <p className="post-body">{r.comment_body}</p>}
      {!r.resolved && (
        <div className="card-actions">
          <Button variant="danger" size="sm" loading={busy} onClick={() => act("hide_content", "Content hidden")}>Hide content</Button>
          <Button variant="secondary" size="sm" disabled={busy} onClick={() => act("dismiss", "Report dismissed")}>Dismiss report</Button>
        </div>
      )}
    </article>
  );
}

export default function Moderation() {
  return (
    <ListPage
      title="Moderation queue"
      description="Review reported discussion posts. Authors stay anonymous here."
      path="/reports/"
      searchable={false}
      filters={[
        { key: "open", label: "Needs review", test: (r) => !r.resolved },
        { key: "resolved", label: "Resolved", test: (r) => r.resolved },
        { key: "all", label: "All", test: () => true },
      ]}
      empty={{ title: "No reports to review", text: "Reported posts will appear here." }}
      render={(r, reload) => <ReportCard key={r.id} r={r} reload={reload} />}
    />
  );
}
