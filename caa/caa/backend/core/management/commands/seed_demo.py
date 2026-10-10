"""Create the admin user (needs DEMO_ADMIN_PASSWORD) and optional demo content (SEED_DEMO_DATA=0 to skip). Safe to re-run on every deploy.

  python manage.py seed_demo

"""
import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (Assignment, ClassRecord, Event, Experiment, FormGuide, Group, Lab, Subject, User)


class Command(BaseCommand):
    help = "Seed demo data"

    def handle(self, *args, **opts):
        self.make_admin()
        if os.environ.get("SEED_DEMO_DATA", "1") == "1":
            self.make_demo_content()

    def make_admin(self):
        pw = os.environ.get("DEMO_ADMIN_PASSWORD")
        if not pw:
            self.stdout.write("DEMO_ADMIN_PASSWORD not set - admin user not created")
            return
        admin, made = User.objects.get_or_create(username="admin", defaults={
            "role": "admin", "is_staff": True, "is_superuser": True})
        if made:
            admin.set_password(pw)
            admin.save()
        self.stdout.write(self.style.SUCCESS("Admin user 'admin' " + ("created" if made else "already exists")))

    def make_demo_content(self):
        now = timezone.now()
        ga, _ = Group.objects.get_or_create(name="Group A")
        gb, _ = Group.objects.get_or_create(name="Group B")
        math, _ = Subject.objects.get_or_create(code="MA101", defaults={"name": "Engineering Mathematics"})
        prog, _ = Subject.objects.get_or_create(code="CS101", defaults={"name": "Programming in C"})
        ClassRecord.objects.get_or_create(subject=math, date=timezone.localdate(), period=2,
                                          defaults={"topic": "Integral Test", "status": "completed"})
        lab, _ = Lab.objects.get_or_create(name="C Programming Lab", defaults={"subject": prog})
        e, c = Experiment.objects.get_or_create(lab=lab, number=1, defaults={
            "title": "Hello World & I/O", "aim": "Learn basic I/O in C", "apparatus": "GCC / Code::Blocks",
            "status": "ongoing"})
        if c:
            e.groups.set([ga, gb])
        Assignment.objects.get_or_create(subject=math, title="Problem Set 1", defaults={
            "deadline": now + timedelta(days=3), "submission_method": "Hand in during class"})
        Event.objects.get_or_create(name="Freshers' Orientation", defaults={
            "start": now + timedelta(days=5), "venue": "Main Auditorium", "organizer": "Student Council"})
        FormGuide.objects.get_or_create(name="Scholarship Application", defaults={
            "purpose": "Apply for the merit scholarship",
            "required_documents": "Marksheet\nIncome certificate\nPassport photo\nSignature scan",
            "accepted_formats": "PDF, JPG", "file_size_limit": "Each file 50KB–200KB",
            "photo_signature_specs": "Photo 35x45mm, white background; signature on white paper",
            "how_to_submit": "Upload on the college portal"})
