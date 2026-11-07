"""Forgot-password OTP rules. Pure Python (no Django) so it can be unit-tested anywhere.

Security notes
- The code is random (secrets), 6 digits, kept only as an HMAC (never in plain text), valid 5 minutes, 5 wrong guesses, then burned.
- A new code replaces (invalidates) the previous one. A successful check burns the code and hands out a one-time reset token.
- Unknown / ineligible accounts get the SAME state, cooldown, attempt counting and replies as real ones; no code is ever
  sent for them and their code can never match, so error messages never reveal whether an account exists.
- Student and faculty recoveries are stored under different keys, so a code for one portal is useless in the other.
"""
import hashlib
import hmac
import re
import secrets

OTP_TTL = 5 * 60          # code valid for 5 minutes
COOLDOWN = 60             # seconds before another code can be requested
MAX_SENDS = 5             # codes per email per hour
SEND_WINDOW = 60 * 60
MAX_ATTEMPTS = 5          # wrong guesses per code
RESET_TTL = 10 * 60       # after the code is verified the user has 10 minutes to choose a password
STATE_TTL = 2 * 60 * 60

PORTALS = ("student", "faculty")
_CODE_RE = re.compile(r"^\d{6}$")
NEVER = "x" * 64          # stored instead of a hash for accounts that don't exist: nothing can ever match it
GENERIC_BAD = "That code isn't right or has expired. Request a new one."


class ResetError(Exception):
    def __init__(self, code, message, status=400, retry_after=None):
        super().__init__(message)
        self.code, self.message, self.status, self.retry_after = code, message, status, retry_after


def key_for(portal, email):
    return f"pwreset:{portal}:{email}"


def new_code():
    return f"{secrets.randbelow(10 ** 6):06d}"


def _h(secret, scope, value):
    return hmac.new(secret.encode(), f"{scope}:{value}".encode(), hashlib.sha256).hexdigest()


def hash_code(secret, portal, email, code):
    return _h(secret, f"otp:{portal}:{email}", code)


def mask_email(email):
    local, _, domain = email.partition("@")
    return (local[:1] + "***" if len(local) > 1 else local[:1] + "*") + "@" + domain


def begin(store, portal, email, real, send, secret, now):
    """Issue a code. `send(email, code)` is called ONLY for a real account; if it raises, nothing is saved and no cooldown starts."""
    k = key_for(portal, email)
    state = store.get(k)
    if state:
        wait = COOLDOWN - (now - state["last_sent"])
        if wait > 0:
            secs = int(wait) + (1 if wait % 1 else 0)
            raise ResetError("cooldown", f"Please wait {secs} seconds before requesting another code.", 429, secs)
        if now - state["window_start"] < SEND_WINDOW and state["send_count"] >= MAX_SENDS:
            mins = max(1, int((SEND_WINDOW - (now - state["window_start"])) // 60) + 1)
            raise ResetError("rate_limited", f"Too many codes requested. Try again in about {mins} minutes.", 429, mins * 60)
    code = new_code()
    if real:
        send(email, code)
    fresh = (not state) or now - state["window_start"] >= SEND_WINDOW
    store.set(k, {
        "otp_hash": hash_code(secret, portal, email, code) if real else NEVER,
        "expires_at": now + OTP_TTL, "attempts": 0, "last_sent": now,
        "window_start": now if fresh else state["window_start"],
        "send_count": 1 if fresh else state["send_count"] + 1,
        "token_hash": "", "token_expires": 0,
    }, STATE_TTL)
    return {"resend_in": COOLDOWN, "expires_in": OTP_TTL}


def verify(store, portal, email, code, secret, now):
    """Check the emailed code. On success the code is burned and a one-time reset token (plain) is returned."""
    k = key_for(portal, email)
    state = store.get(k)
    code = (code or "").strip()
    if not _CODE_RE.match(code):
        raise ResetError("invalid", "Enter the 6-digit code from your email.", 400)
    if not state or not state["otp_hash"]:
        raise ResetError("invalid", GENERIC_BAD, 400)
    if now > state["expires_at"]:
        raise ResetError("expired", "This code has expired. Request a new one.", 400)
    if state["otp_hash"] != NEVER and hmac.compare_digest(state["otp_hash"], hash_code(secret, portal, email, code)):
        token = secrets.token_urlsafe(32)
        state.update(otp_hash="", token_hash=_h(secret, f"tok:{portal}:{email}", token), token_expires=now + RESET_TTL, attempts=0)
        store.set(k, state, STATE_TTL)
        return token
    state["attempts"] += 1
    left = MAX_ATTEMPTS - state["attempts"]
    if left <= 0:
        state["otp_hash"] = ""                 # burn it: a fresh code must be requested
        store.set(k, state, STATE_TTL)
        raise ResetError("too_many_attempts", "Too many incorrect attempts. Request a new code.", 429)
    store.set(k, state, STATE_TTL)
    raise ResetError("invalid", f"That code isn't right. {left} {'attempt' if left == 1 else 'attempts'} left.", 400)


def check_token(store, portal, email, token, secret, now):
    """True only for the live token issued by verify(). Does not consume it (call finish() after the password is saved)."""
    state = store.get(key_for(portal, email))
    if not state or not state.get("token_hash") or now > state.get("token_expires", 0) or not isinstance(token, str):
        return False
    return hmac.compare_digest(state["token_hash"], _h(secret, f"tok:{portal}:{email}", token))


def finish(store, portal, email):
    store.delete(key_for(portal, email))
