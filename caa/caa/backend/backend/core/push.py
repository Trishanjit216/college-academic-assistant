"""Phone (web) push notifications through Firebase Cloud Messaging, HTTP v1 API.

The server-side credential (a Firebase service-account JSON) lives ONLY in the FCM_SERVICE_ACCOUNT_JSON
environment variable. Nothing here ever logs it, returns it, or sends it to the browser.

Top half: pure helpers (no Django) so they can be unit-tested.  Bottom half: database side.
"""
import base64
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_:.\-]{20,512}$")      # FCM registration tokens look like this


# ---------------------------------------------------------------- pure helpers
def load_service_account(raw):
    """Parse the FCM_SERVICE_ACCOUNT_JSON value (plain JSON, or the same JSON base64-encoded). None if unusable."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.startswith("{"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except Exception:
            return None
    try:
        info = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(info, dict) or not all(isinstance(info.get(k), str) and info.get(k) for k in ("client_email", "private_key", "project_id")):
        return None
    return info


def safe_link(link):
    """Only in-app paths may be opened from a notification."""
    if isinstance(link, str) and link.startswith("/") and not link.startswith("//") and "\\" not in link and len(link) <= 200:
        return link
    return "/notifications"


def clean_token(token):
    token = token.strip() if isinstance(token, str) else ""
    return token if TOKEN_RE.match(token) else None


def push_body(message, limit=160):
    """One short line from the stored notification message."""
    flat = " ".join((message or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def build_message(token, title, body, link, tag="", kind=""):
    """A data-only message: our service worker builds the visible notification itself, so a message is never shown twice."""
    return {"message": {
        "token": token,
        "data": {"title": (title or "CAA")[:100], "body": (body or "")[:200], "link": safe_link(link), "tag": (tag or "")[:80], "kind": (kind or "")[:12]},
        "webpush": {"headers": {"TTL": "86400", "Urgency": "high"}},
    }}


def classify(status, text):
    """'ok' | 'dead' (token is no longer valid: delete it) | 'retry' (try once more) | 'fail' (log, keep the token)."""
    if 200 <= status < 300:
        return "ok"
    low = (text or "").lower()
    if status == 404 or "unregistered" in low or "sender_id_mismatch" in low or (status == 400 and "registration token" in low):
        return "dead"
    if status == 429 or status >= 500:
        return "retry"
    return "fail"


class Sender:
    """Sends FCM v1 messages with a service account. `post` and `token_fn` can be replaced in tests."""

    def __init__(self, info, post=None, token_fn=None):
        self.info = info
        self.project = info["project_id"]
        self._post = post or self._http_post
        self._token_fn = token_fn or self._google_token
        self._tok, self._exp, self._lock = None, 0, threading.Lock()

    @property
    def url(self):
        return f"https://fcm.googleapis.com/v1/projects/{self.project}/messages:send"

    def _google_token(self):
        from google.auth.transport.requests import Request          # imported lazily so the rest works without the library
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(self.info, scopes=[SCOPE])
        creds.refresh(Request())
        return creds.token, 3000                                      # Google tokens last 3600 s; renew a bit early

    def access_token(self):
        with self._lock:
            if not self._tok or time.time() >= self._exp:
                self._tok, ttl = self._token_fn()
                self._exp = time.time() + ttl
            return self._tok

    @staticmethod
    def _http_post(url, headers, body):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:                                          # network trouble: worth one retry
            return 599, str(e)

    def send(self, message):
        try:
            headers = {"Authorization": f"Bearer {self.access_token()}", "Content-Type": "application/json; charset=UTF-8"}
        except Exception:
            log.exception("could not get an FCM access token (check FCM_SERVICE_ACCOUNT_JSON)")
            return "fail"
        body = json.dumps(message).encode()
        for attempt in (1, 2):
            status, text = self._post(self.url, headers, body)
            result = classify(status, text)
            if result != "retry" or attempt == 2:
                if result == "fail":
                    log.warning("FCM rejected a message: HTTP %s %s", status, (text or "")[:300])
                return result
            time.sleep(1)


def send_many(sender, tokens, title, body, link, tag="", kind="", workers=8):
    """Send the same notification to many device tokens. Returns {"sent": n, "failed": n, "dead": [tokens to delete]}."""
    tokens = list(dict.fromkeys(t for t in tokens if t))          # each token once, even if listed twice
    out = {"sent": 0, "failed": 0, "dead": []}
    if not tokens:
        return out

    def one(t):
        return t, sender.send(build_message(t, title, body, link, tag, kind))

    with ThreadPoolExecutor(max_workers=min(workers, len(tokens))) as pool:
        for t, res in pool.map(one, tokens):
            if res == "ok":
                out["sent"] += 1
            elif res == "dead":
                out["dead"].append(t)
            else:
                out["failed"] += 1
    return out


# ---------------------------------------------------------------- database side
_sender_cache = {"raw": None, "sender": None}


def get_sender():
    """The shared Sender, or None when the server has no usable FCM credential."""
    from django.conf import settings
    raw = getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", "")
    if _sender_cache["raw"] != raw:
        info = load_service_account(raw)
        _sender_cache.update(raw=raw, sender=Sender(info) if info else None)
    return _sender_cache["sender"]


def configured():
    return get_sender() is not None


def device_tokens(user_ids, kind):
    """Tokens of the given users who have not switched this kind of alert off."""
    from .models import PushDevice, PushPreference
    field = {"event": "events", "syllabus": "syllabus"}.get(kind)
    qs = PushDevice.objects.filter(user_id__in=list(user_ids))
    if field:
        off = PushPreference.objects.filter(**{field: False}).values_list("user_id", flat=True)
        qs = qs.exclude(user_id__in=off)
    return list(qs.values_list("token", flat=True))


def forget(tokens):
    from .models import PushDevice
    if tokens:
        PushDevice.objects.filter(token__in=tokens).delete()


def _deliver(sender, tokens, title, body, link, tag, kind):
    """Runs in a background thread, after the database transaction has committed."""
    try:
        res = send_many(sender, tokens, title, body, link, tag, kind)
        forget(res["dead"])
        log.info("push %s: sent=%s failed=%s removed=%s", tag, res["sent"], res["failed"], len(res["dead"]))
    except Exception:
        log.exception("push delivery crashed")


def _start(fn):
    def run():
        from django.db import connection
        try:
            fn()
        finally:
            connection.close()                                  # the thread has its own database connection
    threading.Thread(target=run, daemon=True).start()


def dispatch(user_ids, kind, title, message, link, tag):
    """Queue a push for these users once the current transaction commits. Never raises, never blocks the request."""
    try:
        sender = get_sender()
        if not sender:
            return 0
        tokens = device_tokens(user_ids, kind)
        if not tokens:
            return 0
        body = push_body(message)
        from django.db import transaction
        transaction.on_commit(lambda: _start(lambda: _deliver(sender, tokens, title, body, link, tag, kind)))
        return len(tokens)
    except Exception:
        log.exception("could not queue push notifications")
        return 0
