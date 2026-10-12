from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from . import sections
from .models import (Assignment, ClassRecord, Comment, Event, Experiment, FormGuide, Group, Lab, SeatAllotment, SyllabusEntry,
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
        if roll and User.objects.filter(roll_no__iexact=roll).exists():
            raise serializers.ValidationError({"roll_no": "This roll number is already linked to another account."})
        data["section"] = (data.get("section") or "").strip().upper()
        err = sections.check(data["group"].name if data.get("group") else None, data["section"])
        if err:
            raise serializers.ValidationError({"section": err})
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
        current = (self.instance.roll_no or "").strip()
        if current and value != "".join(current.split()).upper():
            raise serializers.ValidationError("Your roll number is already set. Ask an administrator to change it.")
        if value and User.objects.filter(roll_no__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("This roll number is already linked to another account.")
        return value

    def validate(self, data):
        inst = self.instance
        group = data["group"] if "group" in data else inst.group
        if "group" in data and "section" not in data and (data["group"] or None) != (inst.group or None):
            data["section"] = ""                      # changing the group clears an old section
        section = (data["section"] if "section" in data else inst.section or "").strip().upper()
        err = sections.check(group.name if group else None, section)
        if err:
            raise serializers.ValidationError({"section": err})
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
        fields = ["id", "title", "message", "created_at", "read"]


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


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeatAllotment
        fields = ["roll_no", "student_name", "exam_name", "exam_date", "room", "seat", "instructions"]
