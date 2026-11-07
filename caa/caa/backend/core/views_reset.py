"""Forgot password for students and faculty (email OTP). Reuses the existing User table, password hashing and Brevo email."""
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import caches
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import reset_otp as ro
from .emailer import EmailDeliveryError, send_via_brevo

User = get_user_model()


def _store():
    return caches["otp"]


def eligible_user(portal, email):
    """The ONE account a recovery for this portal may change, or None. Admins and moderators can never be reset here,
    a student can never reach a faculty account (and vice versa), and a deactivated / revoked / not-yet-activated
    faculty account can't be brought back this way."""
    if portal not in ro.PORTALS or not email:
        return None
    role = User.STUDENT if portal == "student" else User.FACULTY
    users = list(User.objects.filter(email__iexact=email, role=role, is_active=True, is_superuser=False, is_staff=False)[:2])
    if len(users) != 1:
        return None
    user = users[0]
    if portal == "faculty":
        rec = getattr(user, "access_code", None)
        if rec is None or rec.status != rec.ACTIVATED or not user.has_usable_password():
            return None
    return user


def _send(email, code):
    send_via_brevo(settings.BREVO_API_KEY, settings.EMAIL_FROM, settings.EMAIL_FROM_NAME, email, code,
                   ttl_minutes=ro.OTP_TTL // 60, purpose="reset")


def _err(e):
    body = {"detail": e.message, "code": e.code}
    resp = Response(body, status=e.status)
    if e.retry_after:
        body["retry_after"] = e.retry_after
        resp["Retry-After"] = str(e.retry_after)
    return resp


def _bad(msg, code="invalid_input", st=400):
    return Response({"detail": msg, "code": code}, status=st)


class _Base(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []          # public: a stale Authorization header must not matter
    throttle_scope = "pwreset"

    def read(self, request):
        portal = request.data.get("portal")
        email = (request.data.get("email") or "").strip().lower()[:150] if isinstance(request.data.get("email"), str) else ""
        if portal not in ro.PORTALS:
            return None, None, _bad("Choose student or faculty.")
        if "@" not in email or " " in email:
            return None, None, _bad("Enter the email address registered with your account.")
        return portal, email, None


class ResetRequestView(_Base):
    """POST {portal, email}. Sends a code to the account's email. The reply is identical whether or not the account exists.
    Also used for 'Resend code' (the 60-second cooldown and the hourly limit are enforced per email)."""
    def post(self, request):
        portal, email, bad = self.read(request)
        if bad:
            return bad
        if not (settings.BREVO_API_KEY and settings.EMAIL_FROM):      # same answer for everyone: nothing was sent
            return _bad("Email delivery isn't set up on the server yet. Please contact the administrator.", "email_unavailable", 503)
        real = eligible_user(portal, email) is not None
        try:
            info = ro.begin(_store(), portal, email, real, _send, settings.SECRET_KEY, time.time())
        except ro.ResetError as e:
            return _err(e)
        except EmailDeliveryError as e:
            return _bad(str(e), "email_unavailable", 503)         # honest: no code went out, so no cooldown was started
        return Response({"masked_email": ro.mask_email(email), **info,
                         "detail": "If this email belongs to an account, a code has been sent."}, status=status.HTTP_202_ACCEPTED)


class ResetVerifyView(_Base):
    """POST {portal, email, otp}. Right code -> a one-time reset_token for the next step."""
    def post(self, request):
        portal, email, bad = self.read(request)
        if bad:
            return bad
        try:
            token = ro.verify(_store(), portal, email, request.data.get("otp"), settings.SECRET_KEY, time.time())
        except ro.ResetError as e:
            return _err(e)
        return Response({"reset_token": token, "expires_in": ro.RESET_TTL})


class ResetConfirmView(_Base):
    """POST {portal, email, reset_token, password, password2}. Saves the new password and ends every old session."""
    def post(self, request):
        portal, email, bad = self.read(request)
        if bad:
            return bad
        pw, pw2 = request.data.get("password"), request.data.get("password2")
        if not isinstance(pw, str) or not pw:
            return _bad("Enter a new password.")
        if pw != pw2:
            return _bad("The two passwords don't match.", "mismatch")
        store = _store()
        gone = _bad("This reset session has expired. Please start again.", "invalid_token")
        if not ro.check_token(store, portal, email, request.data.get("reset_token"), settings.SECRET_KEY, time.time()):
            return gone
        with transaction.atomic():
            user = eligible_user(portal, email)
            if user is None:
                return gone
            try:
                validate_password(pw, user)                      # strength problems don't burn the token: the user can retry
            except ValidationError as e:
                return _bad(" ".join(e.messages), "weak_password")
            user.set_password(pw)                                # existing hasher; changing it also ends all old sessions
            user.save(update_fields=["password"])
        ro.finish(store, portal, email)
        return Response({"detail": "Your password has been changed. Log in with your new password.", "code": "reset_done"})
