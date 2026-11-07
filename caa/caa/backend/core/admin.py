from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from . import faculty_codes

from .models import (AllotmentRow, Exam, ExamManager, Assignment, AssignmentProgress, ClassRecord, Comment, Event, Experiment,
                     FacultyProfile, FormGuide, Group, Lab, Notification, Post, PushDevice, ReminderLog, Report, Subject, SyllabusEntry, User)


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
    list_display = ("name", "start", "venue", "organizer", "is_published", "target_group", "target_sections")
    list_filter = ("is_published", "target_group")
    search_fields = ("name", "venue")
    fieldsets = (
        (None, {"fields": ("name", "start", "venue", "organizer", "description", "registration_info", "eligibility")}),
        ("Publishing and notifications", {"fields": ("is_published", "target_group", "target_sections"),
                                          "description": "Students get a notification when an event is published. Drafts (unticked) notify nobody."}),
    )


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


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    """Who has phone alerts switched on. The secret device token is deliberately not shown."""
    list_display = ("user", "user_agent", "created_at", "last_seen")
    search_fields = ("user__username", "user__email")
    fields = ("user", "user_agent", "created_at", "last_seen")
    readonly_fields = ("user", "user_agent", "created_at", "last_seen")

    def has_add_permission(self, request):
        return False


# =====================================================================
#  Faculty accounts: create, assign permissions, issue / regenerate / revoke individual access codes
# =====================================================================
def _is_admin(request):
    u = request.user
    return bool(u.is_authenticated and u.is_active and (u.is_superuser or u.role == User.ADMIN))


class FacultyAddForm(forms.ModelForm):
    """Create a brand-new faculty account here, or attach a profile to an existing faculty account."""
    username = forms.CharField(max_length=150, required=False, help_text="New account: the login name.")
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    email = forms.EmailField(required=False, help_text="New account: the faculty member's email (also works as a login name).")
    existing_user = forms.ModelChoiceField(queryset=User.objects.filter(role=User.FACULTY, faculty_profile__isnull=True), required=False,
                                           label="OR choose an existing faculty account",
                                           help_text="Their current password stops working until they activate with the new code.")

    class Meta:
        model = FacultyProfile
        exclude = ("user",)

    def clean(self):
        data = super().clean()
        if data.get("existing_user"):
            return data
        for f in ("username", "first_name", "email"):
            if not data.get(f):
                self.add_error(f, "Required for a new account (or choose an existing faculty account).")
        un, em = data.get("username"), (data.get("email") or "").strip()
        if un and User.objects.filter(username__iexact=un).exists():
            self.add_error("username", "That login name is already taken.")
        if em and User.objects.filter(email__iexact=em).exists():
            self.add_error("email", "That email is already used by another account.")
        return data


@admin.register(FacultyProfile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "access_status", "can_manage_events", "can_manage_syllabus", "subject_list")
    list_filter = ("can_manage_events", "can_manage_syllabus", "department")
    search_fields = ("user__username", "user__first_name", "user__last_name", "user__email")
    filter_horizontal = ("subjects", "groups")
    actions = ["generate_new_code", "revoke_access"]

    # only real admins may touch faculty accounts
    def has_module_permission(self, request): return _is_admin(request)
    def has_view_permission(self, request, obj=None): return _is_admin(request)
    def has_add_permission(self, request): return _is_admin(request)
    def has_change_permission(self, request, obj=None): return _is_admin(request)
    def has_delete_permission(self, request, obj=None): return _is_admin(request)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = FacultyAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        perms = ("Permissions", {"fields": ("can_manage_events", "can_manage_syllabus", "subjects", "groups", "sections")})
        about = ("Profile", {"fields": ("designation", "department")})
        if obj is None:
            return (("New faculty account", {"fields": ("username", "first_name", "last_name", "email", "existing_user"),
                                              "description": "An activation code is generated when you save. It is shown ONCE at the top of the next page."}),
                    about, perms)
        return (("Account", {"fields": ("user", "access_status")}), about, perms)

    def get_readonly_fields(self, request, obj=None):
        return ("user", "access_status") if obj else ()

    @admin.display(description="Name")
    def name(self, obj):
        return obj.user.get_full_name() or obj.user.get_username()

    @admin.display(description="Subjects")
    def subject_list(self, obj):
        return ", ".join(s.code for s in obj.subjects.all()) or "—"

    @admin.display(description="Access status")
    def access_status(self, obj):
        rec = getattr(obj.user, "access_code", None)
        if rec is None:
            return "Active (no code issued yet)" if obj.user.is_active else "Disabled"
        if rec.status == rec.PENDING:
            late = " – EXPIRED" if rec.expires_at and rec.expires_at < timezone.now() else ""
            return f"Waiting for activation (code valid until {timezone.localtime(rec.expires_at):%d %b %Y}){late}" if rec.expires_at else "Waiting for activation"
        if rec.status == rec.ACTIVATED:
            return "Active" if obj.user.is_active else "Activated, but account disabled"
        return dict(rec.STATUS)[rec.status]

    def save_model(self, request, obj, form, change):
        if change:
            return super().save_model(request, obj, form, change)
        user = form.cleaned_data.get("existing_user")
        if user is None:
            user = User(username=form.cleaned_data["username"], first_name=form.cleaned_data["first_name"],
                        last_name=form.cleaned_data.get("last_name", ""), email=form.cleaned_data["email"].strip(), role=User.FACULTY)
            user.set_unusable_password()
            user.is_active = False
            user.save()
        obj.user = user
        super().save_model(request, obj, form, change)
        self._announce(request, user, faculty_codes.issue_code(user, issued_by=request.user))

    @staticmethod
    def _announce(request, user, code):
        who = user.get_full_name() or user.get_username()
        messages.warning(request, f"ACCESS CODE for {who} ({user.get_username()}): {code}   – shown only once, valid {faculty_codes.DEFAULT_TTL_DAYS} days. "
                                  f"Give it to them privately. They activate it on the Faculty Login page and choose their own password.")

    @admin.action(description="Generate a NEW access code (old code and password stop working)")
    def generate_new_code(self, request, queryset):
        for p in queryset.select_related("user"):
            self._announce(request, p.user, faculty_codes.issue_code(p.user, issued_by=request.user))

    @admin.action(description="REVOKE access (disable login and destroy any code)")
    def revoke_access(self, request, queryset):
        n = 0
        for p in queryset.select_related("user"):
            faculty_codes.revoke(p.user)
            n += 1
        self.message_user(request, f"Access revoked for {n} faculty member(s). To let one back in, generate a new access code.", messages.SUCCESS)
