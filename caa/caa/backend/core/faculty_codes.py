"""Individual faculty activation codes.

* Each faculty member gets their OWN random code (60 bits, e.g. K7QM-4TXD-9WPA). There is no shared code.
* Only a salted PBKDF2 hash is stored; the plain code is shown to the admin once and cannot be read again.
* A code is single-use, expires, and locks after a few wrong guesses.
* The code only ACTIVATES the account: the faculty member then sets their own password and logs in with it.

The first half is plain Python (unit-testable without Django); the second half touches the database.
"""
import base64
import hashlib
import hmac
import re
import secrets

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # no I, O, 0 or 1: nothing to misread
CODE_LEN = 12
ITERATIONS = 200_000
MAX_ATTEMPTS = 5
DEFAULT_TTL_DAYS = 7
_VALID = re.compile(rf"^[{ALPHABET}]{{{CODE_LEN}}}$")


# ---------------------------------------------------------------- pure helpers
def generate_code():
    raw = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))
    return "-".join(raw[i:i + 4] for i in range(0, CODE_LEN, 4))


def normalize(code):
    """What the faculty member typed -> canonical form, or '' if it can't be a valid code."""
    raw = re.sub(r"[\s\-]", "", (code or "")).upper() if isinstance(code, str) else ""
    return raw if _VALID.match(raw) else ""


def hash_code(code, salt=None, iterations=ITERATIONS):
    norm = normalize(code)
    if not norm:
        raise ValueError("not a valid code")
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", norm.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${base64.b64encode(digest).decode()}"


def check_code(code, stored):
    """True only if `code` matches the stored hash. Never raises."""
    try:
        norm = normalize(code)
        algo, iters, salt, _ = stored.split("$", 3)
        if not norm or algo != "pbkdf2_sha256":
            return False
        return hmac.compare_digest(hash_code(norm, salt, int(iters)), stored)
    except Exception:
        return False


DUMMY_HASH = hash_code("AAAA-AAAA-AAAA", salt="0" * 16)


class ActivationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


GENERIC = "That access code is invalid, expired or already used. Ask the admin for a new code."


# ---------------------------------------------------------------- database side
def _models():
    from .models import FacultyAccessCode, User
    return FacultyAccessCode, User


def find_faculty(identifier):
    """Faculty account by email or username. Only role=faculty accounts can ever be found."""
    _, User = _models()
    ident = (identifier or "").strip()
    if not ident or len(ident) > 150:
        return None
    qs = User.objects.filter(role=User.FACULTY)
    if "@" in ident:
        return qs.filter(email__iexact=ident).order_by("id").first()
    return qs.filter(username__iexact=ident).order_by("id").first()


def issue_code(user, issued_by=None, ttl_days=None):
    """New code for a faculty member. Returns the PLAIN code (show it once, never store it).
    The account is locked and its old password disabled until the code is used, so a regenerated code
    also ends every older session and password."""
    from datetime import timedelta
    from django.db import transaction
    from django.utils import timezone
    FacultyAccessCode, User = _models()
    if user.role != User.FACULTY:
        raise ValueError("access codes are only for faculty accounts")
    code = generate_code()
    with transaction.atomic():
        rec, _ = FacultyAccessCode.objects.select_for_update().get_or_create(user=user)
        rec.code_hash = hash_code(code)
        rec.status = FacultyAccessCode.PENDING
        rec.expires_at = timezone.now() + timedelta(days=ttl_days or DEFAULT_TTL_DAYS)
        rec.failed_attempts = 0
        rec.issued_by = issued_by
        rec.issued_at = timezone.now()
        rec.used_at = None
        rec.save()
        user.is_active = False
        user.set_unusable_password()
        user.save(update_fields=["is_active", "password"])
    return code


def revoke(user):
    """Cut off a faculty member: code destroyed, login disabled (existing sessions stop working at once)."""
    from django.db import transaction
    FacultyAccessCode, _ = _models()
    with transaction.atomic():
        rec, _ = FacultyAccessCode.objects.select_for_update().get_or_create(user=user)
        rec.code_hash, rec.status, rec.expires_at = "", FacultyAccessCode.REVOKED, None
        rec.save()
        user.is_active = False
        user.save(update_fields=["is_active"])


def activate(identifier, code, password):
    """Faculty member proves they hold THEIR code and chooses a password. Returns the activated user.
    Every failure about the code gives the same message so nobody can probe which accounts exist."""
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from django.utils import timezone
    FacultyAccessCode, _ = _models()

    user = find_faculty(identifier)
    # password strength first: depends only on what the caller typed, so it can't reveal whether the code was right
    try:
        validate_password(password or "", user)
    except ValidationError as e:
        raise ActivationError("weak_password", " ".join(e.messages))

    norm = normalize(code)
    with transaction.atomic():
        rec = FacultyAccessCode.objects.select_for_update().filter(user=user).first() if user else None
        stored = rec.code_hash if rec and rec.status == FacultyAccessCode.PENDING else ""
        ok = check_code(norm, stored or DUMMY_HASH) and bool(stored) and bool(norm)     # same work whether or not the account exists
        live = bool(rec) and rec.status == FacultyAccessCode.PENDING and rec.expires_at and rec.expires_at > timezone.now()
        if not (ok and live):
            if rec and rec.status == FacultyAccessCode.PENDING:
                rec.failed_attempts += 1
                if rec.failed_attempts >= MAX_ATTEMPTS:
                    rec.status, rec.code_hash = FacultyAccessCode.LOCKED, ""
                rec.save(update_fields=["failed_attempts", "status", "code_hash"])
            raise ActivationError("invalid_code", GENERIC)
        user.set_password(password)
        user.is_active = True
        user.save(update_fields=["password", "is_active"])
        rec.status, rec.code_hash, rec.used_at = FacultyAccessCode.ACTIVATED, "", timezone.now()
        rec.save(update_fields=["status", "code_hash", "used_at"])
    return user
