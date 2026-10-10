from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (Assignment, ClassRecord, Comment, Event, Experiment, FormGuide, Group, Lab,
                     Notification, Post, Report, Subject)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "roll_no", "group", "group_name"]
        read_only_fields = ["role"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "password", "first_name", "last_name", "email", "roll_no", "group"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, data):
        # Public sign-up can only ever create students.
        return User.objects.create_user(role=User.STUDENT, **data)


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
