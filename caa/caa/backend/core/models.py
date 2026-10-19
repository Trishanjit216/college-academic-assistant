from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Group(models.Model):
    """Lab batch/group that experiments are allotted to (e.g. 'Group A')."""
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    STUDENT, FACULTY, ADMIN, MODERATOR = "student", "faculty", "admin", "moderator"
    ROLES = [(STUDENT, "Student"), (FACULTY, "Faculty / Academic Editor"),
             (ADMIN, "Admin"), (MODERATOR, "Moderator")]
    role = models.CharField(max_length=10, choices=ROLES, default=STUDENT)
    roll_no = models.CharField(max_length=30, blank=True)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL, related_name="students")
    section = models.CharField(max_length=3, blank=True, default="")   # A1..A12 / B1..B12 (see core/sections.py)

    def clean(self):
        super().clean()
        roll = "".join((self.roll_no or "").split())
        if roll and self.section:
            dup = User.objects.filter(section=self.section, roll_no__iexact=roll).exclude(pk=self.pk)
            if dup.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError(f"Roll number {roll} is already registered in section {self.section}.")

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_editor(self):  # may create/edit official academic data
        return self.is_superuser or self.role in (self.FACULTY, self.ADMIN)

    @property
    def is_moderator(self):
        return self.is_superuser or self.role in (self.ADMIN, self.MODERATOR)


class Subject(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} – {self.name}"


class ClassRecord(models.Model):
    """One row of the period-wise teaching record."""
    PLANNED, ONGOING, COMPLETED = "planned", "ongoing", "completed"
    STATUS = [(PLANNED, "Planned"), (ONGOING, "Ongoing"), (COMPLETED, "Completed")]
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="records")
    date = models.DateField()
    period = models.PositiveSmallIntegerField()
    faculty = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="taught")
    topic = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    section = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default=COMPLETED)

    class Meta:
        ordering = ["-date", "period"]


class Lab(models.Model):
    name = models.CharField(max_length=120)
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL)
    instructions = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Experiment(models.Model):
    PLANNED, ONGOING, COMPLETED = "planned", "ongoing", "completed"
    STATUS = [(PLANNED, "Upcoming"), (ONGOING, "Ongoing"), (COMPLETED, "Completed")]
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name="experiments")
    number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    aim = models.TextField(blank=True)
    apparatus = models.TextField(blank=True, help_text="Apparatus / software required")
    procedure = models.TextField(blank=True)
    submission_requirements = models.TextField(blank=True)
    planned_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default=PLANNED)
    groups = models.ManyToManyField(Group, blank=True, related_name="experiments",
                                    help_text="Groups this experiment is allotted to")

    class Meta:
        ordering = ["lab", "number"]


class Assignment(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    issue_date = models.DateField(auto_now_add=True)
    deadline = models.DateTimeField()
    submission_method = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["deadline"]

    def __str__(self):
        return self.title


class AssignmentProgress(models.Model):
    """A student's personal done/not-done flag for an assignment."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="progress")
    done = models.BooleanField(default=False)

    class Meta:
        unique_together = [("user", "assignment")]


class ReminderLog(models.Model):
    """Guarantees each reminder (assignment x offset) is sent only once."""
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="reminder_logs")
    hours_before = models.PositiveSmallIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("assignment", "hours_before")]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    kind = models.CharField(max_length=12, blank=True, default="")                 # "event", "syllabus", "assignment" ...
    link = models.CharField(max_length=200, blank=True, default="")                # in-app path, e.g. /events?event=3
    ref = models.CharField(max_length=60, blank=True, default="", db_index=True)  # what it is about, e.g. "event:3"
    dedupe_key = models.CharField(max_length=80, blank=True, default="")         # one notification per (user, key)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "dedupe_key"], condition=~models.Q(dedupe_key=""),
                                               name="core_notif_user_dedupe_uniq")]


class Event(models.Model):
    name = models.CharField(max_length=200)
    start = models.DateTimeField()
    venue = models.CharField(max_length=200, blank=True)
    organizer = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    registration_info = models.TextField(blank=True)
    eligibility = models.CharField(max_length=200, blank=True)
    is_published = models.BooleanField(default=True, help_text="Untick to keep this event as a draft: hidden from students, and nobody is notified. "
                                                                 "Students are notified when it is published.")
    target_group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                     help_text="Leave empty to notify everyone. Or choose a group.")
    target_sections = models.CharField(max_length=120, blank=True, default="",
                                       help_text="Optional. Notify only these sections, e.g. A1, A2, B3 (overrides the group).")

    class Meta:
        ordering = ["start"]

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        from . import notify
        try:
            secs = notify.parse_sections(self.target_sections)
        except ValueError as e:
            raise ValidationError({"target_sections": str(e)})
        self.target_sections = ", ".join(secs)


class FormGuide(models.Model):
    name = models.CharField(max_length=200)
    purpose = models.TextField(blank=True)
    required_documents = models.TextField(blank=True, help_text="One per line")
    accepted_formats = models.CharField(max_length=100, blank=True, help_text="e.g. PDF, JPG")
    file_size_limit = models.CharField(max_length=100, blank=True, help_text="e.g. 50KB–200KB")
    photo_signature_specs = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    how_to_submit = models.TextField(blank=True)
    instructions = models.TextField(blank=True, help_text="Important instructions / common mistakes")

    class Meta:
        ordering = ["name"]


class Post(models.Model):
    """Anonymous discussion post. `author` is stored for accountability but never exposed by the API."""
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="posts")
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    hidden = models.BooleanField(default=False, help_text="Hidden by a moderator")

    class Meta:
        ordering = ["-created_at"]


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comments")
    body = models.TextField(max_length=1500)
    created_at = models.DateTimeField(auto_now_add=True)
    hidden = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]


class Report(models.Model):
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name="reports")
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["resolved", "-created_at"]


class SyllabusEntry(models.Model):
    """Syllabus of one subject for one examination. Content is entered by an administrator / faculty member
    from official documents; nothing is pre-filled. Format of `content`: a line starting with 'Unit' or a
    number starts a unit; lines starting with '-' are topics; lines starting with '--' are subtopics."""
    MID1, MID2, END = "mid1", "mid2", "end"
    EXAMS = [(MID1, "Mid-Term 1"), (MID2, "Mid-Term 2"), (END, "End-Semester")]
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="syllabus_entries")
    semester = models.PositiveSmallIntegerField(null=True, blank=True)
    exam = models.CharField(max_length=5, choices=EXAMS)
    content = models.TextField(blank=True)
    pdf_url = models.URLField(blank=True, max_length=500, help_text="Link to the official syllabus PDF, if any")
    verified = models.BooleanField(default=False, help_text="Tick once checked against the official document. Students are notified when a verified syllabus is published or changed.")
    updated_at = models.DateTimeField(auto_now=True)
    revision = models.PositiveIntegerField(default=0, editable=False)   # bumped each time students are notified

    class Meta:
        unique_together = [("subject", "exam")]
        ordering = ["semester", "subject__name", "exam"]
        verbose_name_plural = "syllabus entries"

    def __str__(self):
        return f"{self.subject.code} {self.get_exam_display()}"


class Exam(models.Model):
    """One examination whose official seat allotment CAA publishes. Never filled automatically."""
    DRAFT, PUBLISHED = "draft", "published"
    STATUS = [(DRAFT, "Draft (hidden from students)"), (PUBLISHED, "Published")]
    name = models.CharField(max_length=150)
    semester = models.PositiveSmallIntegerField(null=True, blank=True)
    academic_year = models.CharField(max_length=20, blank=True, help_text="e.g. 2026-27")
    batch = models.CharField(max_length=60, blank=True, help_text="e.g. B.Tech 2026 batch")
    exam_date = models.DateField(null=True, blank=True)
    instructions = models.TextField(blank=True, help_text="Shown to students with their result")
    status = models.CharField(max_length=10, choices=STATUS, default=DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-exam_date", "-created_at"]

    def __str__(self):
        return self.name


class ExamDocument(models.Model):
    """The official PDF, stored in the database so it survives redeploys (free hosting has no permanent disk)."""
    exam = models.OneToOneField(Exam, on_delete=models.CASCADE, related_name="document")
    filename = models.CharField(max_length=200)
    size = models.PositiveIntegerField(default=0)
    data = models.BinaryField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    uploaded_at = models.DateTimeField(auto_now=True)


class ExamManager(models.Model):
    """A faculty member explicitly permitted to manage one exam (admins manage all exams)."""
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="managers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="managed_exams")

    class Meta:
        unique_together = [("exam", "user")]


class AllotmentRow(models.Model):
    """roll_to empty = one roll number (an exception wins over ranges); roll_to filled = a range. See core/allotment.py."""
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="rows")
    section = models.CharField(max_length=10, blank=True)
    roll_from = models.CharField(max_length=30)
    roll_to = models.CharField(max_length=30, blank=True)
    room = models.CharField(max_length=60)
    seat = models.CharField(max_length=30, blank=True)
    note = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section", "roll_from"]


class AttendanceRecord(models.Model):
    """A student's PERSONAL self-tracked attendance. Private to the owner; not official college attendance."""
    PRESENT, ABSENT, HOLIDAY = "present", "absent", "holiday"
    STATUS = [(PRESENT, "Present"), (ABSENT, "Absent"), (HOLIDAY, "Holiday")]
    REASONS = [("illness", "Illness"), ("personal", "Personal reason"), ("family", "Family reason"),
               ("transport", "Transport or travel issue"), ("college", "College event or approved activity"), ("other", "Other")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    period = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=STATUS)
    reason = models.CharField(max_length=12, choices=REASONS, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["user", "date"])]
