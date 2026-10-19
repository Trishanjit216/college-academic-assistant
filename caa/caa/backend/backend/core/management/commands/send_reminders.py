"""Create assignment reminders (72h, 24h, 3h before the deadline).

Run every hour (cron):  python manage.py send_reminders
Safe to run repeatedly: ReminderLog guarantees each (assignment, offset) fires once.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.timezone import localtime

from core.models import Assignment, AssignmentProgress, Notification, ReminderLog, User

OFFSETS = [72, 24, 3]


def send_due_reminders(now=None):
    """Returns number of notifications created.

    For each assignment, only the tightest window it currently falls in produces a
    notification (so a late-created assignment doesn't spam 72h+24h+3h at once);
    the wider windows are marked as sent silently.
    """
    now = now or timezone.now()
    students = list(User.objects.filter(role=User.STUDENT, is_active=True))
    created = 0
    for a in Assignment.objects.select_related("subject").filter(
            deadline__gt=now, deadline__lte=now + timedelta(hours=max(OFFSETS))):
        remaining = a.deadline - now
        windows = [h for h in sorted(OFFSETS) if remaining <= timedelta(hours=h)]
        tightest = windows[0]
        notify = False
        for h in windows:
            try:
                with transaction.atomic():
                    ReminderLog.objects.create(assignment=a, hours_before=h)
                if h == tightest:
                    notify = True
            except IntegrityError:
                pass  # already sent
        if not notify:
            continue
        done = set(AssignmentProgress.objects.filter(assignment=a, done=True)
                   .values_list("user_id", flat=True))
        when = localtime(a.deadline).strftime("%d %b, %I:%M %p")
        rows = [Notification(user=u, title=f"Due soon: {a.title}",
                             message=f"{a.subject.name} assignment is due {when} (within {tightest} hours).",
                             kind="assignment", link="/assignments")
                for u in students if u.id not in done]
        Notification.objects.bulk_create(rows)
        created += len(rows)
    return created


class Command(BaseCommand):
    help = "Send due assignment reminders"

    def handle(self, *args, **opts):
        n = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(f"{n} notifications created"))
