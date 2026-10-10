import { api } from "../api.js";
import { fmtDT, Page } from "./ui.jsx";

export default function Moderation() {
  return (
    <Page title="Moderation queue" searchable={false} path="/reports/" render={(r, reload) => (
      <div className={`card ${r.resolved ? "done" : ""}`} key={r.id}>
        <span className="muted">{fmtDT(r.created_at)}</span> <span className="tag">{r.resolved ? "resolved" : "open"}</span>
        <p><b>Reason:</b> {r.reason}</p>
        {r.post_title && <p><b>{r.post_title}</b><br />{r.post_body}</p>}
        {r.comment_body && <p>💬 {r.comment_body}</p>}
        {!r.resolved && (<>
          <button onClick={() => api(`/reports/${r.id}/hide_content/`, { method: "POST" }).then(reload)}>Hide content</button>{" "}
          <button className="link" onClick={() => api(`/reports/${r.id}/dismiss/`, { method: "POST" }).then(reload)}>Dismiss</button>
        </>)}
      </div>
    )} />
  );
}
