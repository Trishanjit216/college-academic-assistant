from datetime import timedelta
from unittest import mock

from django.core.cache import caches
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .management.commands.send_reminders import send_due_reminders
from .models import Assignment, Notification, Post, Subject, User


class AuthAndPermissionTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user("stu", password="pw-12345-x", role="student")
        self.faculty = User.objects.create_user("fac", password="pw-12345-x", role="faculty")
        self.subject = Subject.objects.create(code="X1", name="Maths")

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


LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
          "otp": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "otp-test"}}


@override_settings(CACHES=LOCMEM, BREVO_API_KEY="k", EMAIL_FROM="a@b.c")
class SignupOtpTests(APITestCase):
    """Email-OTP sign-up. Email sending is mocked; real delivery needs a Brevo key."""
    def setUp(self):
        caches["otp"].clear()
        self.sent = []
        p = mock.patch("core.views.send_via_brevo", side_effect=lambda *a, **k: self.sent.append(a[4:6]))
        p.start(); self.addCleanup(p.stop)

    def signup(self, email="new@x.com", **kw):
        d = {"name": "Asha Rao", "email": email, "password": "Str0ng-pass-99"}; d.update(kw)
        return self.client.post("/api/auth/register/", d)

    def code(self):
        return self.sent[-1][1]

    def test_signup_creates_no_user_until_verified(self):
        r = self.signup()
        self.assertEqual(r.status_code, 202)
        self.assertFalse(User.objects.filter(email="new@x.com").exists())
        self.assertNotIn("otp", r.data)
        self.assertNotIn(self.code(), str(r.data))
        login = self.client.post("/api/auth/token/", {"username": "new@x.com", "password": "Str0ng-pass-99"})
        self.assertEqual(login.status_code, 401)

    def test_verify_creates_active_student_and_login_works(self):
        self.signup(role="admin")
        r = self.client.post("/api/auth/verify-otp/", {"email": "new@x.com", "otp": self.code()})
        self.assertEqual(r.status_code, 201)
        u = User.objects.get(email="new@x.com")
        self.assertEqual(u.role, "student"); self.assertEqual(u.first_name, "Asha")
        self.assertEqual(self.client.post("/api/auth/token/", {"username": "new@x.com", "password": "Str0ng-pass-99"}).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/token/", {"username": "NEW@x.com", "password": "Str0ng-pass-99"}).status_code, 200)

    def test_wrong_code_then_lockout(self):
        self.signup()
        good = self.code(); bad = "000000" if good != "000000" else "111111"
        for _ in range(4):
            self.assertEqual(self.client.post("/api/auth/verify-otp/", {"email": "new@x.com", "otp": bad}).data["code"], "invalid")
        self.assertEqual(self.client.post("/api/auth/verify-otp/", {"email": "new@x.com", "otp": bad}).status_code, 429)
        self.assertFalse(User.objects.filter(email="new@x.com").exists())

    def test_expired_code(self):
        self.signup()
        with mock.patch("core.views.time.time", return_value=__import__("time").time() + 700):
            r = self.client.post("/api/auth/verify-otp/", {"email": "new@x.com", "otp": self.code()})
        self.assertEqual(r.data["code"], "expired")

    def test_resend_cooldown_then_new_code(self):
        self.signup()
        r = self.client.post("/api/auth/resend-otp/", {"email": "new@x.com"})
        self.assertEqual(r.status_code, 429); self.assertEqual(r.data["code"], "cooldown"); self.assertGreater(r.data["retry_after"], 0)
        with mock.patch("core.views.time.time", return_value=__import__("time").time() + 61):
            self.assertEqual(self.client.post("/api/auth/resend-otp/", {"email": "new@x.com"}).status_code, 200)
        self.assertEqual(len(self.sent), 2)

    def test_duplicate_email_blocked(self):
        User.objects.create_user("old", email="Taken@x.com", password="pw-12345-x")
        r = self.signup("taken@x.com")
        self.assertEqual(r.status_code, 409); self.assertEqual(self.sent, [])

    def test_email_failure_returns_503_and_no_state(self):
        from .emailer import EmailDeliveryError
        with mock.patch("core.views.send_via_brevo", side_effect=EmailDeliveryError("down")):
            self.assertEqual(self.signup().status_code, 503)
        self.assertEqual(self.client.post("/api/auth/resend-otp/", {"email": "new@x.com"}).data["code"], "not_found")

    def test_weak_password_and_missing_name_rejected(self):
        self.assertEqual(self.signup(password="12345678").status_code, 400)
        self.assertEqual(self.signup(name="").status_code, 400)

    def test_protected_api_needs_login(self):
        self.signup()
        self.assertEqual(self.client.get("/api/records/").status_code, 401)

    def test_legacy_username_login_still_works(self):
        User.objects.create_user("legacy", password="pw-12345-x")
        self.assertEqual(self.client.post("/api/auth/token/", {"username": "legacy", "password": "pw-12345-x"}).status_code, 200)
