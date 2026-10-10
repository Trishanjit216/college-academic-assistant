from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from .management.commands.send_reminders import send_due_reminders
from .models import Assignment, Notification, Post, Subject, User


class AuthAndPermissionTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user("stu", password="pw-12345-x", role="student")
        self.faculty = User.objects.create_user("fac", password="pw-12345-x", role="faculty")
        self.subject = Subject.objects.create(code="X1", name="Maths")

    def test_register_is_always_student(self):
        r = self.client.post("/api/auth/register/", {"username": "n", "password": "Str0ng-pass-99", "role": "admin"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(User.objects.get(username="n").role, "student")

    def test_student_cannot_write_official_data_but_faculty_can(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post("/api/subjects/", {"code": "Z", "name": "Z"}).status_code, 403)
        self.assertEqual(self.client.get("/api/subjects/").status_code, 200)
        self.client.force_authenticate(self.faculty)
        self.assertEqual(self.client.post("/api/subjects/", {"code": "Z", "name": "Z"}).status_code, 201)

    def test_login_required(self):
        self.assertEqual(self.client.get("/api/records/").status_code, 401)


class DiscussionTests(APITestCase):
    def setUp(self):
        self.a = User.objects.create_user("a", password="pw-12345-x")
        self.b = User.objects.create_user("b", password="pw-12345-x")
        self.mod = User.objects.create_user("m", password="pw-12345-x", role="moderator")

    def test_author_never_exposed_and_report_flow(self):
        self.client.force_authenticate(self.a)
        r = self.client.post("/api/posts/", {"title": "Hi", "body": "Concern"})
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("author", r.data)
        self.assertTrue(r.data["mine"])
        pid = r.data["id"]

        self.client.force_authenticate(self.b)
        listing = self.client.get("/api/posts/").data["results"]
        self.assertNotIn("author", listing[0])
        self.assertFalse(listing[0]["mine"])
        self.assertEqual(self.client.post(f"/api/posts/{pid}/report/", {"reason": "abusive"}).status_code, 201)
        self.assertEqual(self.client.get("/api/reports/").status_code, 403)  # students can't moderate

        self.client.force_authenticate(self.mod)
        rep = self.client.get("/api/reports/").data["results"][0]
        self.assertNotIn("reporter", rep)
        self.assertEqual(self.client.post(f"/api/reports/{rep['id']}/hide_content/").status_code, 204)
        self.assertEqual(self.client.get("/api/posts/").data["results"], [])
        self.assertEqual(Post.objects.get(pk=pid).hidden, True)

    def test_cannot_delete_others_post(self):
        self.client.force_authenticate(self.a)
        pid = self.client.post("/api/posts/", {"title": "t", "body": "b"}).data["id"]
        self.client.force_authenticate(self.b)
        self.assertEqual(self.client.delete(f"/api/posts/{pid}/").status_code, 403)


class ReminderTests(APITestCase):
    def test_72h_reminder_sent_once_and_skips_done(self):
        s1 = User.objects.create_user("s1", password="pw-12345-x")
        s2 = User.objects.create_user("s2", password="pw-12345-x")
        subj = Subject.objects.create(code="M", name="Maths")
        a = Assignment.objects.create(subject=subj, title="PS1", deadline=timezone.now() + timedelta(hours=70))
        a.progress.create(user=s2, done=True)
        send_due_reminders()
        self.assertEqual(Notification.objects.filter(user=s1).count(), 1)
        self.assertEqual(Notification.objects.filter(user=s2).count(), 0)
        send_due_reminders()  # second run must not duplicate
        self.assertEqual(Notification.objects.filter(user=s1).count(), 1)

    def test_far_deadline_not_reminded(self):
        User.objects.create_user("s1", password="pw-12345-x")
        subj = Subject.objects.create(code="M", name="Maths")
        Assignment.objects.create(subject=subj, title="Later", deadline=timezone.now() + timedelta(days=10))
        self.assertEqual(send_due_reminders(), 0)


class DashboardTests(APITestCase):
    def test_dashboard_and_seed(self):
        call_command("seed_demo")
        u = User.objects.create_user("s", password="pw-12345-x")
        self.client.force_authenticate(u)
        r = self.client.get("/api/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["upcoming_assignments"]), 1)


class CronEndpointTests(APITestCase):
    def test_requires_secret(self):
        import os
        os.environ["CRON_SECRET"] = "s3cret"
        self.assertEqual(self.client.post("/api/cron/send-reminders/").status_code, 403)
        r = self.client.post("/api/cron/send-reminders/", HTTP_X_CRON_SECRET="s3cret")
        self.assertEqual(r.status_code, 200)
