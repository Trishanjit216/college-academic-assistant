from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from . import allotment, sections
from .models import (AllotmentRow, AttendanceRecord, Exam, ExamDocument, Assignment, ClassRecord, Comment, Event, Experiment, FormGuide, Group, Lab, SyllabusEntry,
                     Notification, Post, Report, Subject)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "roll_no", "group", "group_name", "section"]
        read_only_fields = ["role"]


class SignupSerializer(serializers.Serializer):
    """Validates the sign-up form. Nothing is saved here: the account is only created after the
    emailed code is verified (see views.VerifyOtpView)."""
    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    roll_no = serializers.CharField(max_length=30, required=False, allow_blank=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=False, allow_null=True)
    section = serializers.CharField(max_length=3, required=False, allow_blank=True)

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, data):
        full = (data.get("name") or "").strip() or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        if not full:
            raise serializers.ValidationError({"name": "Enter your name."})
        first, _, last = full.partition(" ")
        data["first_name"], data["last_name"] = first[:100], last.strip()[:100]
        roll = "".join((data.get("roll_no") or "").split()).upper()
        data["roll_no"] = roll
        data["section"] = (data.get("section") or "").strip().upper()
        gname = data["group"].name if data.get("group") else None
        missing = sections.missing_fields(gname, data["section"], roll)
        if missing:
            raise serializers.ValidationError({"profile": sections.missing_message(missing)})
        err = sections.check(gname, data["section"])
        if err:
            raise serializers.ValidationError({"section": err})
        if User.objects.filter(section=data["section"], roll_no__iexact=roll).exists():
            where = f"section {data['section']}" if data["section"] else "this group"
            raise serializers.ValidationError({"roll_no": f"Roll number {roll} is already registered in {where}."})
        probe = User(username=data["email"], email=data["email"], first_name=first, last_name=last)
        try:
            validate_password(data["password"], user=probe)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return data


class ProfileSerializer(serializers.ModelSerializer):
    """What a logged-in user may change about themselves: group, section, and (once) roll number."""
    class Meta:
        model = User
        fields = ["roll_no", "group", "section"]
        extra_kwargs = {"roll_no": {"required": False}, "group": {"required": False, "allow_null": True},
                        "section": {"required": False, "allow_blank": True}}

    def validate_roll_no(self, value):
        value = "".join((value or "").split()).upper()
        current = "".join((self.instance.roll_no or "").split()).upper()
        if current and value != current:
            raise serializers.ValidationError("Your roll number is already set. Ask an administrator to change it.")
        return value

    def validate(self, data):
        inst = self.instance
        group = data["group"] if "group" in data else inst.group
        if "group" in data and "section" not in data and (data["group"] or None) != (inst.group or None):
            data["section"] = ""                      # changing the group clears an old section
        section = (data["section"] if "section" in data else inst.section or "").strip().upper()
        roll = data.get("roll_no") or "".join((inst.roll_no or "").split()).upper()
        gname = group.name if group else None
        missing = sections.missing_fields(gname, section, roll)
        if missing:
            raise serializers.ValidationError({"profile": sections.missing_message(missing)})
        err = sections.check(gname, section)
        if err:
            raise serializers.ValidationError({"section": err})
        if User.objects.filter(section=section, roll_no__iexact=roll).exclude(pk=inst.pk).exists():
            raise serializers.ValidationError({"roll_no": f"Roll number {roll} is already registered in section {section}."})
        if "section" in data:
            data["section"] = section
        return data


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "code", "name"]


class ClassRecordSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    faculty_name = serializers.SerializerMethodField()

    class Meta:
        model = ClassRecord
        fields = ["id", "subject", "subject_name", "date", "period", "faculty", "faculty_name",
                  "topic", "notes", "section", "status"]

    def get_faculty_name(self, obj):
        return (obj.faculty.get_full_name() or obj.faculty.username) if obj.faculty else ""


class LabSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lab
        fields = ["id", "name", "subject", "instructions"]


class ExperimentSerializer(serializers.ModelSerializer):
    lab_name = serializers.CharField(source="lab.name", read_only=True)
    group_names = serializers.SerializerMethodField()

    class Meta:
        model = Experiment
        fields = ["id", "lab", "lab_name", "number", "title", "aim", "apparatus", "procedure",
                  "submission_requirements", "planned_date", "status", "groups", "group_names"]

    def get_group_names(self, obj):
        return [g.name for g in obj.groups.all()]


class AssignmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    done = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = ["id", "subject", "subject_name", "title", "description", "issue_date",
                  "deadline", "submission_method", "done"]
        read_only_fields = ["issue_date"]

    def get_done(self, obj):
        return obj.id in self.context.get("done_ids", set())


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"

    def validate_target_sections(self, value):
        from . import notify
        try:
            return ", ".join(notify.parse_sections(value))
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class FormGuideSerializer(serializers.ModelSerializer):
    documents_list = serializers.SerializerMethodField()

    class Meta:
        model = FormGuide
        fields = "__all__"

    def get_documents_list(self, obj):
        return [l.strip() for l in obj.required_documents.splitlines() if l.strip()]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "created_at", "read", "kind", "link"]


class CommentSerializer(serializers.ModelSerializer):
    mine = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "body", "created_at", "mine"]   # NO author field: anonymous

    def get_mine(self, obj):
        return obj.author_id == self.context["request"].user.id


class PostSerializer(serializers.ModelSerializer):
    mine = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "title", "body", "created_at", "mine", "comments"]  # NO author field

    def get_mine(self, obj):
        return obj.author_id == self.context["request"].user.id

    def get_comments(self, obj):
        qs = [c for c in obj.comments.all() if not c.hidden]
        return CommentSerializer(qs, many=True, context=self.context).data


class ReportSerializer(serializers.ModelSerializer):
    post_title = serializers.CharField(source="post.title", read_only=True, default=None)
    post_body = serializers.CharField(source="post.body", read_only=True, default=None)
    comment_body = serializers.CharField(source="comment.body", read_only=True, default=None)

    class Meta:
        model = Report
        fields = ["id", "post", "comment", "post_title", "post_body", "comment_body",
                  "reason", "created_at", "resolved"]   # reporter & author identities not exposed


class SyllabusEntrySerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = SyllabusEntry
        fields = ["id", "subject", "subject_code", "subject_name", "semester", "exam", "content",
                  "pdf_url", "verified", "updated_at"]
        read_only_fields = ["updated_at"]


class ExamPublicSerializer(serializers.ModelSerializer):
    """What a student may see about a PUBLISHED exam (never the allotment rows)."""
    has_document = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = ["id", "name", "semester", "academic_year", "batch", "exam_date", "instructions", "published_at", "has_document"]

    def get_has_document(self, obj):
        return ExamDocument.objects.filter(exam_id=obj.id).exists()


class ExamManageSerializer(serializers.ModelSerializer):
    has_document = serializers.SerializerMethodField()
    document_name = serializers.SerializerMethodField()
    row_count = serializers.SerializerMethodField()
    managers = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = ["id", "name", "semester", "academic_year", "batch", "exam_date", "instructions", "status", "published_at",
                  "updated_at", "has_document", "document_name", "row_count", "managers"]
        read_only_fields = ["status", "published_at", "updated_at"]

    def _doc(self, obj):
        return ExamDocument.objects.filter(exam_id=obj.id).values("filename", "size", "uploaded_at").first()

    def get_has_document(self, obj):
        return self._doc(obj) is not None

    def get_document_name(self, obj):
        d = self._doc(obj)
        return d["filename"] if d else ""

    def get_row_count(self, obj):
        return obj.rows.count()

    def get_managers(self, obj):
        return [m.user.get_full_name() or m.user.username for m in obj.managers.select_related("user")]


class AllotmentRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllotmentRow
        fields = ["id", "section", "roll_from", "roll_to", "room", "seat", "note"]

    def validate(self, data):
        merged = {k: data.get(k, getattr(self.instance, k, "")) for k in ("section", "roll_from", "roll_to", "room", "seat", "note")}
        merged["roll_from"], merged["roll_to"] = allotment.norm(merged["roll_from"]), allotment.norm(merged["roll_to"])
        merged["section"] = allotment.norm(merged["section"])
        merged["room"], merged["seat"], merged["note"] = (str(merged[k] or "").strip() for k in ("room", "seat", "note"))
        errs = allotment.validate_row(merged)
        if errs:
            raise serializers.ValidationError({"detail": "; ".join(errs)})
        return merged


class AttendanceSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)

    class Meta:
        model = AttendanceRecord
        fields = ["id", "date", "subject", "subject_name", "period", "status", "reason", "note"]

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("You can't record attendance for a future date.")
        return value

    def validate_note(self, value):
        return (value or "").strip()

    def validate(self, data):
        g = lambda k: data[k] if k in data else getattr(self.instance, k, None)
        status, reason = g("status"), g("reason") or ""
        if status == AttendanceRecord.ABSENT:
            if reason and reason not in dict(AttendanceRecord.REASONS):
                raise serializers.ValidationError({"reason": "Choose one of the listed reasons."})
        else:
            data["reason"] = ""                       # a reason only makes sense for an absence
        user = self.context["request"].user
        dup = AttendanceRecord.objects.filter(user=user, date=g("date"), subject=g("subject"), period=g("period"))
        if self.instance:
            dup = dup.exclude(pk=self.instance.pk)
        if dup.exists():
            raise serializers.ValidationError({"detail": "You already recorded this date, subject and session. Edit that entry instead."})
        return data
