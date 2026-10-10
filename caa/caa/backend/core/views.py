import hmac
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import serializers as s
from .models import (Assignment, AssignmentProgress, ClassRecord, Comment, Event, Experiment,
                     FormGuide, Group, Lab, Notification, Post, Report, Subject)
from .permissions import IsModerator, ReadAllEditorsWrite

User = get_user_model()


class ThrottledTokenView(TokenObtainPairView):
    throttle_scope = "auth"


class RegisterView(generics.CreateAPIView):
    serializer_class = s.RegisterSerializer
    permission_classes = [AllowAny]
    throttle_scope = "auth"


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
