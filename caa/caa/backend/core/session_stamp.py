"""Ties every login token to the account's current password so a password change/reset signs old sessions out.
The stamp is a short fingerprint of the stored password HASH (never the password)."""
import hashlib

CLAIM = "pw"


def stamp(user):
    return hashlib.sha256(("caa-session:" + (user.password or "")).encode()).hexdigest()[:20]
