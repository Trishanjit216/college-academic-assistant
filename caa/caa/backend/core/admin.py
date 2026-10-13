from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (AllotmentRow, Exam, ExamManager, Assignment, AssignmentProgress, ClassRecord, Comment, Event, Experiment,
                     FormGuide, Group, Lab, Notification, Post, ReminderLog, Report, Subject, SyllabusEntry, User)


@admin.register(User)
class CAAUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("College", {"fields": ("role", "roll_no", "group", "section")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("College", {"fields": ("role", "roll_no", "group", "section")}),)
    list_display = ("username", "first_name", "last_name", "role", "roll_no", "group", "section", "is_active")
    list_filter = ("role", "group", "section", "is_active")
    search_fields = ("username", "first_name", "last_name", "roll_no", "email")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(ClassRecord)
class ClassRecordAdmin(admin.ModelAdmin):
    list_display = ("date", "period", "subject", "topic", "faculty", "status")
    list_filter = ("subject", "status", "date")
    search_fields = ("topic", "notes")
    date_hierarchy = "date"


class ExperimentInline(admin.TabularInline):
    model = Experiment
    extra = 0
    show_change_link = True


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ("name", "subject")
    inlines = [ExperimentInline]


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ("lab", "number", "title", "status", "planned_date")
    list_filter = ("lab", "status")
    filter_horizontal = ("groups",)
    search_fields = ("title", "aim")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "deadline")
    list_filter = ("subject",)
    search_fields = ("title",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "start", "venue", "organizer")
    search_fields = ("name", "venue")


@admin.register(FormGuide)
class FormGuideAdmin(admin.ModelAdmin):
    list_display = ("name", "deadline", "accepted_formats")
    search_fields = ("name",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    # Authors are visible ONLY here (backend accountability); the API never exposes them.
    list_display = ("title", "author", "created_at", "hidden")
    list_filter = ("hidden",)
    search_fields = ("title", "body")
    actions = ["hide_selected", "unhide_selected"]

    @admin.action(description="Hide selected posts")
    def hide_selected(self, request, qs):
        qs.update(hidden=True)

    @admin.action(description="Unhide selected posts")
    def unhide_selected(self, request, qs):
        qs.update(hidden=False)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "created_at", "hidden")
    list_filter = ("hidden",)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "post", "comment", "reporter", "reason", "resolved")
    list_filter = ("resolved",)


@admin.register(SyllabusEntry)
class SyllabusEntryAdmin(admin.ModelAdmin):
    list_display = ("subject", "exam", "semester", "verified", "updated_at")
    list_filter = ("semester", "exam", "verified", "subject")
    search_fields = ("subject__name", "subject__code", "content")


class ExamManagerInline(admin.TabularInline):
    model = ExamManager
    extra = 0
    autocomplete_fields = ["user"]
    verbose_name = "faculty allowed to manage this exam"


class AllotmentRowInline(admin.TabularInline):
    model = AllotmentRow
    extra = 0


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    """Admins assign faculty here. Day-to-day editing (PDF upload, CSV import, preview, publish) is in the CAA app."""
    list_display = ("name", "semester", "academic_year", "batch", "exam_date", "status")
    list_filter = ("status", "academic_year")
    search_fields = ("name", "batch")
    inlines = [ExamManagerInline, AllotmentRowInline]


admin.site.register([Group, Notification, ReminderLog, AssignmentProgress])
