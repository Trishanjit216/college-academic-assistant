import hmac
import math
import os
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.cache import caches
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from . import serializers as s
from .models import (Assignment, AssignmentProgress, ClassRecord, Comment, Event, Experiment,
                     FormGuide, Group, Lab, Notification, Post, Report, Subject)
from . import otp
from .emailer import EmailDeliveryError, send_via_brevo
from .permissions import IsModerator, ReadAllEditorsWrite

User = get_user_model()


class EmailOrUsernameTokenSerializer(TokenObtainPairSerializer):
    """New accounts log in with their email; older accounts can keep using their username."""
    def validate(self, attrs):
        ident = (attrs.get("username") or "").strip()
        if "@" in ident:
            match = User.objects.filter(email__iexact=ident).order_by("id").first()
            if match:
                attrs["username"] = match.get_username()
        return super().validate(attrs)


class ThrottledTokenView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenSerializer
    throttle_scope = "auth"


# ---------- email-OTP sign-up ----------
def _otp_store():
    return caches["otp"]


def _send_code(email, code):
    send_via_brevo(settings.BREVO_API_KEY, settings.EMAIL_FROM, settings.EMAIL_FROM_NAME, email, code,
                   ttl_minutes=otp.OTP_TTL // 60)


def _otp_error(e):
    body = {"detail": e.message, "code": e.code}
    resp = Response(body, status=e.status)
    if e.retry_after:
        body["retry_after"] = e.retry_after
        resp["Retry-After"] = str(e.retry_after)
    return resp


def _email_unavailable(e):
    return Response({"detail": str(e), "code": "email_unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


def _clean_email(raw):
    return (raw or "").strip().lower()[:150]


def _email_taken(email):
    return User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists()


class _OtpView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []        # ignore any stale Authorization header on these public endpoints
    throttle_scope = "otp"


class SignupView(_OtpView):
    """POST /api/auth/register/  — validates the form and emails a code. Creates NO account yet."""
    def post(self, request):
        ser = s.SignupSerializer(data=request.data)
        if not ser.is_valid():
            msgs = []
            for field, errs in ser.errors.items():
                for m in ([errs] if isinstance(errs, str) else errs):
                    msgs.append(str(m))
            return Response({"detail": " ".join(msgs) or "Please check the form.", "code": "invalid_input",
                             "errors": ser.errors}, status=status.HTTP_400_BAD_REQUEST)
        d = ser.validated_data
        email = d["email"]
        if _email_taken(email):
            return Response({"detail": "An account with this email already exists. Log in instead.",
                             "code": "email_taken"}, status=status.HTTP_409_CONFLICT)
        profile = {"first_name": d["first_name"], "last_name": d["last_name"],
                   "roll_no": d.get("roll_no", ""), "group": d["group"].id if d.get("group") else None}
        try:
            info = otp.begin_signup(_otp_store(), email, profile, make_password(d["password"]),
                                    _send_code, settings.SECRET_KEY, time.time())
        except otp.OtpError as e:
            return _otp_error(e)
        except EmailDeliveryError as e:
            return _email_unavailable(e)
        return Response({"email": email, "masked_email": otp.mask_email(email), **info},
                        status=status.HTTP_202_ACCEPTED)


class ResendOtpView(_OtpView):
    """POST /api/auth/resend-otp/  {email}"""
    def post(self, request):
        email = _clean_email(request.data.get("email"))
        try:
            info = otp.resend(_otp_store(), email, _send_code, settings.SECRET_KEY, time.time())
        except otp.OtpError as e:
            return _otp_error(e)
        except EmailDeliveryError as e:
            return _email_unavailable(e)
        return Response({"email": email, "masked_email": otp.mask_email(email), **info})


class VerifyOtpView(_OtpView):
    """POST /api/auth/verify-otp/  {email, otp}  — creates the (student) account if the code is right."""
    def post(self, request):
        email = _clean_email(request.data.get("email"))
        store = _otp_store()
        try:
            state = otp.verify(store, email, request.data.get("otp"), settings.SECRET_KEY, time.time())
        except otp.OtpError as e:
            return _otp_error(e)
        taken = Response({"detail": "An account with this email already exists. Log in instead.",
                          "code": "email_taken"}, status=status.HTTP_409_CONFLICT)
        profile = state["profile"]
        group_id = profile.get("group")
        if group_id and not Group.objects.filter(pk=group_id).exists():
            group_id = None
        try:
            with transaction.atomic():
                if _email_taken(email):
                    store.delete(otp.key_for(email))
                    return taken
                user = User(username=email, email=email, first_name=profile["first_name"],
                            last_name=profile["last_name"], roll_no=profile.get("roll_no", ""),
                            group_id=group_id, role=User.STUDENT)
                user.password = state["password_hash"]       # already hashed at sign-up
                user.save()
        except IntegrityError:
            store.delete(otp.key_for(email))
            return taken
        store.delete(otp.key_for(email))
        return Response({"detail": "Email verified. Your account is ready.", "code": "verified"},
                        status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveAPIView):
    serializer_class = s.UserSerializer

    def get_object(self):
        return self.request.user


class GroupList(generics.ListAPIView):
    """Public so the sign-up form can list groups."""
    queryset = Group.objects.all()
    serializer_class = s.GroupSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadAllEditorsWrite]
    filter_backends = [filters.SearchFilter]


class SubjectViewSet(BaseViewSet):
    queryset = Subject.objects.all()
    serializer_class = s.SubjectSerializer
    search_fields = ["name", "code"]
    pagination_class = None


class ClassRecordViewSet(BaseViewSet):
    queryset = ClassRecord.objects.select_related("subject", "faculty")
    serializer_class = s.ClassRecordSerializer
    search_fields = ["topic", "notes", "subject__name"]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("subject"):
            qs = qs.filter(subject_id=p["subject"])
        if p.get("date"):
            qs = qs.filter(date=p["date"])
        return qs


class LabViewSet(BaseViewSet):
    queryset = Lab.objects.all()
    serializer_class = s.LabSerializer
    search_fields = ["name"]
    pagination_class = None


class ExperimentViewSet(BaseViewSet):
    queryset = Experiment.objects.select_related("lab").prefetch_related("groups")
    serializer_class = s.ExperimentSerializer
    search_fields = ["title", "aim", "lab__name"]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("lab"):
            qs = qs.filter(lab_id=p["lab"])
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("mine") == "1" and self.request.user.group_id:
            qs = qs.filter(groups=self.request.user.group_id)
        return qs


class AssignmentViewSet(BaseViewSet):
    queryset = Assignment.objects.select_related("subject")
    serializer_class = s.AssignmentSerializer
    search_fields = ["title", "description", "subject__name"]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        u = self.request.user
        ctx["done_ids"] = set(AssignmentProgress.objects.filter(user=u, done=True)
                              .values_list("assignment_id", flat=True)) if u.is_authenticated else set()
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("upcoming") == "1":
            qs = qs.filter(deadline__gte=timezone.now())
        return qs

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def toggle_done(self, request, pk=None):
        a = self.get_object()
        prog, _ = AssignmentProgress.objects.get_or_create(user=request.user, assignment=a)
        prog.done = not prog.done
        prog.save()
        return Response({"done": prog.done})


class EventViewSet(BaseViewSet):
    queryset = Event.objects.all()
    serializer_class = s.EventSerializer
    search_fields = ["name", "description", "venue", "organizer"]


class FormGuideViewSet(BaseViewSet):
    queryset = FormGuide.objects.all()
    serializer_class = s.FormGuideSerializer
    search_fields = ["name", "purpose", "required_documents"]


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        n = self.get_object()
        n.read = True
        n.save(update_fields=["read"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def read_all(self, request):
        self.get_queryset().update(read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostViewSet(viewsets.ModelViewSet):
    """Anonymous discussion. Author is recorded server-side but never serialized."""
    serializer_class = s.PostSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]
    throttle_scope = None

    def get_throttles(self):
        if self.action in ("create", "comment", "report"):
            self.throttle_scope = "posts"
        return super().get_throttles()

    def get_queryset(self):
        return Post.objects.filter(hidden=False).prefetch_related("comments")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def destroy(self, request, *args, **kwargs):
        post = self.get_object()
        if post.author_id != request.user.id and not request.user.is_moderator:
            return Response(status=status.HTTP_403_FORBIDDEN)
        post.hidden = True       # soft-delete keeps an audit trail
        post.save(update_fields=["hidden"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        post = self.get_object()
        body = (request.data.get("body") or "").strip()
        if not body or len(body) > 1500:
            return Response({"body": "Required, max 1500 characters."}, status=400)
        c = Comment.objects.create(post=post, author=request.user, body=body)
        return Response(s.CommentSerializer(c, context={"request": request}).data, status=201)

    @action(detail=True, methods=["post"])
    def report(self, request, pk=None):
        post = self.get_object()
        reason = (request.data.get("reason") or "").strip()[:300]
        if not reason:
            return Response({"reason": "Please give a reason."}, status=400)
        Report.objects.create(post=post, reporter=request.user, reason=reason)
        return Response(status=status.HTTP_201_CREATED)


class ReportViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsModerator]
    serializer_class = s.ReportSerializer
    queryset = Report.objects.select_related("post", "comment")

    @action(detail=True, methods=["post"])
    def hide_content(self, request, pk=None):
        r = self.get_object()
        if r.post:
            r.post.hidden = True
            r.post.save(update_fields=["hidden"])
        if r.comment:
            r.comment.hidden = True
            r.comment.save(update_fields=["hidden"])
        r.resolved = True
        r.save(update_fields=["resolved"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def dismiss(self, request, pk=None):
        r = self.get_object()
        r.resolved = True
        r.save(update_fields=["resolved"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardView(APIView):
    def get(self, request):
        now = timezone.now()
        today = timezone.localdate()
        u = request.user
        ctx = {"request": request}
        done_ids = set(AssignmentProgress.objects.filter(user=u, done=True)
                       .values_list("assignment_id", flat=True))
        assignments = Assignment.objects.select_related("subject").filter(
            deadline__gte=now, deadline__lte=now + timedelta(days=14))[:10]
        exp_qs = Experiment.objects.select_related("lab").prefetch_related("groups").filter(
            status__in=[Experiment.ONGOING, Experiment.PLANNED])
        if u.group_id:
            exp_qs = exp_qs.filter(Q(groups=u.group_id) | Q(groups=None))
        return Response({
            "today_classes": s.ClassRecordSerializer(
                ClassRecord.objects.select_related("subject", "faculty").filter(date=today),
                many=True, context=ctx).data,
            "next_experiments": s.ExperimentSerializer(exp_qs.distinct()[:3], many=True, context=ctx).data,
            "upcoming_assignments": s.AssignmentSerializer(
                assignments, many=True, context={**ctx, "done_ids": done_ids}).data,
            "upcoming_events": s.EventSerializer(
                Event.objects.filter(start__gte=now)[:5], many=True, context=ctx).data,
            "unread_notifications": Notification.objects.filter(user=u, read=False).count(),
        })


class CronReminderView(APIView):
    """POST /api/cron/send-reminders/  with header  X-Cron-Secret: <CRON_SECRET>.
    Lets a free external scheduler (GitHub Actions / cron-job.org) trigger reminders hourly."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from .management.commands.send_reminders import send_due_reminders
        secret = os.environ.get("CRON_SECRET", "")
        given = request.headers.get("X-Cron-Secret", "")
        if not secret or not hmac.compare_digest(secret, given):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response({"notifications_created": send_due_reminders()})
