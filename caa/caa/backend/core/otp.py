"""Email-OTP sign-up rules. Pure Python (no Django imports) so they can be unit-tested anywhere.

A sign-up is *pending* (stored in a cache-like `store`) until the emailed code is verified.
No User row exists before that, so an unverified sign-up can never log in or reach any API.
"""
import hashlib
import hmac
import re
import secrets

OTP_TTL = 10 * 60          # code valid for 10 minutes
COOLDOWN = 60              # seconds between "send/resend" requests for one email
MAX_SENDS = 5              # codes per email per window
SEND_WINDOW = 60 * 60      # 1 hour
MAX_ATTEMPTS = 5           # wrong guesses per code
STATE_TTL = 24 * 60 * 60   # pending sign-up is forgotten after 24h

_CODE_RE = re.compile(r"^\d{6}$")


class OtpError(Exception):
    def __init__(self, code, message, status=400, retry_after=None):
        super().__init__(message)
        self.code, self.message, self.status, self.retry_after = code, message, status, retry_after


def key_for(email):
    return "signup:" + email


def new_code():
    return f"{secrets.randbelow(10 ** 6):06d}"


def hash_code(secret, email, code):
    """Codes are never stored in plain text: HMAC-SHA256 keyed with the server secret."""
    return hmac.new(secret.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def mask_email(email):
    local, _, domain = email.partition("@")
    return (local[:1] + "***" if len(local) > 1 else local[:1] + "*") + "@" + domain


def _check_send_limits(state, now):
    """Raises OtpError if this email must wait before another code is sent."""
    if not state:
        return
    wait = COOLDOWN - (now - state["last_sent"])
    if wait > 0:
        secs = int(wait) + (1 if wait % 1 else 0)
        raise OtpError("cooldown", f"Please wait {secs} seconds before requesting another code.", 429, secs)
    in_window = now - state["window_start"] < SEND_WINDOW
    if in_window and state["send_count"] >= MAX_SENDS:
        mins = max(1, int((SEND_WINDOW - (now - state["window_start"])) // 60) + 1)
        raise OtpError("rate_limited", f"Too many codes requested. Try again in about {mins} minutes.", 429, mins * 60)


def _issue(store, email, state, send, secret, now):
    code = new_code()
    send(email, code)                      # may raise: then nothing is saved and no cooldown starts
    fresh_window = now - state["window_start"] >= SEND_WINDOW
    state.update(
        otp_hash=hash_code(secret, email, code),
        expires_at=now + OTP_TTL,
        attempts=0,
        last_sent=now,
        window_start=now if fresh_window else state["window_start"],
        send_count=1 if fresh_window else state["send_count"] + 1,
    )
    store.set(key_for(email), state, STATE_TTL)
    return {"resend_in": COOLDOWN, "expires_in": OTP_TTL}


def begin_signup(store, email, profile, password_hash, send, secret, now):
    """Start (or restart) a sign-up: validates limits, emails a code, saves the pending state."""
    state = store.get(key_for(email))
    _check_send_limits(state, now)
    base = state or {"window_start": now, "send_count": 0, "last_sent": 0}
    base = dict(base, profile=profile, password_hash=password_hash)
    return _issue(store, email, base, send, secret, now)


def resend(store, email, send, secret, now):
    state = store.get(key_for(email))
    if not state:
        raise OtpError("not_found", "We couldn't find a sign-up for this email. Please start again.", 400)
    _check_send_limits(state, now)
    return _issue(store, email, state, send, secret, now)


def verify(store, email, code, secret, now):
    """Returns the pending state on success (caller creates the user and deletes the state)."""
    state = store.get(key_for(email))
    if not state:
        raise OtpError("not_found", "We couldn't find a sign-up for this email. Please start again.", 400)
    code = (code or "").strip()
    if not _CODE_RE.match(code):
        raise OtpError("invalid", "Enter the 6-digit code from your email.", 400)
    if not state["otp_hash"]:
        raise OtpError("too_many_attempts", "Too many incorrect attempts. Request a new code.", 429)
    if now > state["expires_at"]:
        raise OtpError("expired", "This code has expired. Request a new one.", 400)
    if hmac.compare_digest(state["otp_hash"], hash_code(secret, email, code)):
        return state
    state["attempts"] += 1
    left = MAX_ATTEMPTS - state["attempts"]
    if left <= 0:
        state["otp_hash"] = ""             # burn the code; a fresh one must be requested
        store.set(key_for(email), state, STATE_TTL)
        raise OtpError("too_many_attempts", "Too many incorrect attempts. Request a new code.", 429)
    store.set(key_for(email), state, STATE_TTL)
    raise OtpError("invalid", f"That code isn't right. {left} {'attempt' if left == 1 else 'attempts'} left.", 400)
