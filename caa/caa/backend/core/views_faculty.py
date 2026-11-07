"""Faculty login, activation and the faculty-only API (/api/faculty/...).

Every permission is checked HERE on the server: a faculty member can only reach their own events, the syllabus of
the subjects the admin assigned to them, and nothing belonging to another faculty member."""
import re

from django.contrib.auth import get_user_model
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.http import Http404
from rest_framework import exceptions, permissions, serializers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from . import faculty_codes, notify, sections as sec
from .models import Event, FacultyActivity, FacultyProfile, Group, SyllabusEntry
from .views import EmailOrUsernameTokenSerializer

User = get_user_model()


# ---------------------------------------------------------------- login
class FacultyTokenSerializer(EmailOrUsernameTokenSerializer):
    """Same password check as the student login, but ONLY faculty accounts get in. Anyone else sees the
    same message as a wrong password, so this form can't be used to learn who is faculty."""
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.role != User.FACULTY:
            raise exceptions.AuthenticationFailed(self.error_messages["no_active_account"], "no_active_account")
        return data


class FacultyLoginView(TokenObtainPairView):
    serializer_class = FacultyTokenSerializer
    throttle_scope = "auth"


class FacultyActivateView(APIView):
    """First login (or after the admin issued a new code): individual access code + a password of the faculty member's own."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "activate"

    def post(self, request):
        d = request.data
        pw, pw2 = d.get("password"), d.get("password2")
        if pw2 is not None and pw != pw2:
            return Response({"detail": "The two passwords don't match.", "code": "mismatch"}, status=400)
        try:
            user = faculty_codes.activate(d.get("identifier"), d.get("code"), pw if isinstance(pw, str) else "")
        except faculty_codes.ActivationError as e:
            return Response({"detail": e.message, "code": e.code}, status=400)
        log(user, "Activated account")
        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


# ---------------------------------------------------------------- permissions
class IsFaculty(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.role == User.FACULTY)


def _profile(user):
    return getattr(user, "faculty_profile", None) if user.is_authenticated else None


class CanManageEvents(IsFaculty):
    message = "You have not been given permission to manage events. Ask the admin."

    def has_permission(self, request, view):
        p = _profile(request.user) if super().has_permission(request, view) else None
        return bool(p and p.can_manage_events)


class CanManageSyllabus(IsFaculty):
    message = "You have not been given permission to manage the syllabus. Ask the admin."

    def has_permission(self, request, view):
        p = _profile(request.user) if super().has_permission(request, view) else None
        return bool(p and p.can_manage_syllabus)


def log(user, text):
    FacultyActivity.objects.create(user=user, text=text[:200])
    stale = FacultyActivity.objects.filter(user=user).order_by("-created_at", "-id").values_list("id", flat=True)[50:]
    if stale:
        FacultyActivity.objects.filter(id__in=list(stale)).delete()


# ---------------------------------------------------------------- scope (which groups/sections an event may target)
def scope_of(profile):
    """None = unrestricted. Otherwise (allowed group ids, allowed section codes)."""
    if profile is None:
        return None
    groups = list(profile.groups.all())
    extra = notify.parse_sections(profile.sections) if profile.sections else []
    if not groups and not extra:
        return None
    allowed = set(extra)
    for g in groups:
        allowed.update(sec.allowed_sections(g.name) or [])
    return {g.id for g in groups}, allowed


# ---------------------------------------------------------------- profile / dashboard
def _profile_json(user):
    p = _profile(user)
    scope = scope_of(p)
    own = Event.objects.filter(created_by=user)
    return {
        "id": user.id, "username": user.username, "first_name": user.first_name, "last_name": user.last_name, "email": user.email, "role": user.role,
        "has_profile": bool(p),
        "designation": p.designation if p else "", "department": p.department if p else "",
        "can_manage_events": bool(p and p.can_manage_events), "can_manage_syllabus": bool(p and p.can_manage_syllabus),
        "subjects": [{"id": s.id, "code": s.code, "name": s.name} for s in (p.subjects.all() if p else [])],
        "scope": {"restricted": scope is not None,
                  "groups": [{"id": g.id, "name": g.name} for g in (p.groups.all() if p else [])],
                  "sections": sorted(scope[1]) if scope else []},
        "stats": {"events_total": own.count(), "events_published": own.filter(is_published=True).count(),
                  "events_draft": own.filter(is_published=False).count(), "subjects": p.subjects.count() if p else 0},
    }


class FacultyMeView(APIView):
    permission_classes = [IsFaculty]

    def get(self, request):
        return Response(_profile_json(request.user))


class FacultyActivityView(APIView):
    permission_classes = [IsFaculty]

    def get(self, request):
        rows = FacultyActivity.objects.filter(user=request.user)[:15]
        return Response([{"id": a.id, "text": a.text, "created_at": a.created_at} for a in rows])


class FacultyGroupsView(APIView):
    """Group / section overview (student COUNTS only, never names or other personal data)."""
    permission_classes = [IsFaculty]

    def get(self, request):
        p = _profile(request.user)
        scope = scope_of(p)
        groups = Group.objects.all() if scope is None else Group.objects.filter(id__in=scope[0])
        counts = dict(User.objects.filter(role=User.STUDENT, is_active=True).exclude(section="").values_list("section").annotate(n=Count("id")))
        out = []
        for g in groups.order_by("name"):
            secs = sec.allowed_sections(g.name) or []
            out.append({"id": g.id, "name": g.name, "students": User.objects.filter(role=User.STUDENT, is_active=True, group=g).count(),
                        "sections": [{"code": c, "students": counts.get(c, 0)} for c in secs]})
        extra = []
        if scope:
            shown = {s["code"] for g in out for s in g["sections"]}
            extra = [{"code": c, "students": counts.get(c, 0)} for c in sorted(scope[1] - shown)]
        return Response({"restricted": scope is not None, "groups": out, "extra_sections": extra})


# ---------------------------------------------------------------- events (own events only)
class FacultyEventSerializer(serializers.ModelSerializer):
    target_group_name = serializers.CharField(source="target_group.name", read_only=True, default=None)

    class Meta:
        model = Event
        fields = ["id", "name", "start", "venue", "organizer", "description", "registration_info", "eligibility",
                  "is_published", "target_group", "target_group_name", "target_sections"]

    def validate_target_sections(self, value):
        try:
            return ", ".join(notify.parse_sections(value))
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, data):
        scope = scope_of(_profile(self.context["request"].user))
        if scope is None:
            return data
        gids, allowed = scope
        inst = self.instance
        secs = notify.parse_sections(data["target_sections"] if "target_sections" in data else (inst.target_sections if inst else ""))
        group = data["target_group"] if "target_group" in data else (inst.target_group if inst else None)
        if secs:
            if not set(secs) <= allowed:
                raise serializers.ValidationError({"target_sections": "You can only target your own sections: " + ", ".join(sorted(allowed)) + "."})
        elif group is not None:
            if group.id not in gids:
                raise serializers.ValidationError({"target_group": "You can only target your own groups."})
        else:
            raise serializers.ValidationError({"target_group": "Choose one of your groups or sections. You can't send an event to everyone."})
        return data


class FacultyEventViewSet(viewsets.ModelViewSet):
    """A faculty member sees and changes ONLY the events they created. Another faculty member's event is simply 'not found'."""
    permission_classes = [CanManageEvents]
    serializer_class = FacultyEventSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Event.objects.filter(created_by=self.request.user).select_related("target_group").order_by("-start")

    def perform_create(self, serializer):
        ev = serializer.save(created_by=self.request.user)
        log(self.request.user, f"{'Published' if ev.is_published else 'Saved draft of'} event: {ev.name}")

    def perform_update(self, serializer):
        was = serializer.instance.is_published
        ev = serializer.save()
        if ev.is_published and not was:
            log(self.request.user, f"Published event: {ev.name}")
        elif was and not ev.is_published:
            log(self.request.user, f"Unpublished event: {ev.name}")
        else:
            log(self.request.user, f"Edited event: {ev.name}")

    def perform_destroy(self, instance):
        name = instance.name
        instance.delete()
        log(self.request.user, f"Deleted event: {name}")


# ---------------------------------------------------------------- syllabus (assigned subjects only)
EXAMS = [e for e, _ in SyllabusEntry.EXAMS]
MAX_CONTENT = 20000


def _entry_json(e):
    return {"exam": e.exam, "content": e.content, "pdf_url": e.pdf_url, "verified": e.verified, "semester": e.semester, "updated_at": e.updated_at}


class FacultySyllabusView(APIView):
    permission_classes = [CanManageSyllabus]

    def get(self, request):
        subjects = list(_profile(request.user).subjects.all())
        entries = SyllabusEntry.objects.filter(subject__in=subjects)
        by = {(e.subject_id, e.exam): e for e in entries}
        return Response([{"subject": {"id": s.id, "code": s.code, "name": s.name},
                          "entries": {x: (_entry_json(by[(s.id, x)]) if (s.id, x) in by else None) for x in EXAMS}} for s in subjects])


class FacultySyllabusEntryView(APIView):
    """PUT /faculty/syllabus/<subject_id>/<exam>/  -> create or update. Saving goes through the normal model save,
    so the existing notification workflow (published / updated / unchanged) runs exactly as for the admin."""
    permission_classes = [CanManageSyllabus]
    throttle_scope = "posts"

    def put(self, request, subject_id, exam):
        p = _profile(request.user)
        subject = p.subjects.filter(pk=subject_id).first()
        if exam not in EXAMS or subject is None:
            raise Http404()                                   # not yours (or not real): looks identical
        d = request.data
        content = d.get("content", "")
        pdf = (d.get("pdf_url") or "").strip()
        errors = {}
        if not isinstance(content, str) or len(content) > MAX_CONTENT:
            errors["content"] = f"Syllabus text must be at most {MAX_CONTENT} characters."
        if pdf:
            try:
                if not re.match(r"^https?://", pdf, re.I):
                    raise DjangoValidationError("bad scheme")
                URLValidator()(pdf)
            except DjangoValidationError:
                errors["pdf_url"] = "Enter a web link starting with http:// or https://"
            if len(pdf) > 500:
                errors["pdf_url"] = "That link is too long."
        sem = d.get("semester")
        if sem not in (None, ""):
            try:
                sem = int(sem)
                if not 1 <= sem <= 12:
                    raise ValueError
            except (TypeError, ValueError):
                errors["semester"] = "Semester must be a number from 1 to 12."
        else:
            sem = None
        if "verified" in d and not isinstance(d.get("verified"), bool):
            errors["verified"] = "Must be true or false."
        if errors:
            return Response({"detail": " ".join(errors.values()), "errors": errors}, status=400)
        entry = SyllabusEntry.objects.filter(subject=subject, exam=exam).first() or SyllabusEntry(subject=subject, exam=exam)
        was_verified = entry.verified
        entry.content = content
        entry.pdf_url = pdf
        if sem is not None:
            entry.semester = sem
        if "verified" in d:
            entry.verified = d["verified"]
        entry.save()
        label = entry.get_exam_display()
        log(request.user, f"{'Published' if entry.verified and not was_verified else 'Updated'} syllabus: {subject.name} ({label})")
        return Response(_entry_json(entry))
