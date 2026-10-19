from datetime import timedelta
from unittest import mock

from django.core.cache import caches
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .management.commands.send_reminders import send_due_reminders
from .models import AllotmentRow, Assignment, AttendanceRecord, Event, Exam, ExamManager, Group, Notification, Post, Subject, SyllabusEntry, User


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
        self.ga = Group.objects.create(name="Group A")
        self.sent = []
        p = mock.patch("core.views.send_via_brevo", side_effect=lambda *a, **k: self.sent.append(a[4:6]))
        p.start(); self.addCleanup(p.stop)

    def signup(self, email="new@x.com", **kw):
        d = {"name": "Asha Rao", "email": email, "password": "Str0ng-pass-99", "group": self.ga.id,
             "section": "A1", "roll_no": "R" + email.split("@")[0].upper()}; d.update(kw)
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


@override_settings(CACHES=LOCMEM, BREVO_API_KEY="k", EMAIL_FROM="a@b.c")
class SectionTests(APITestCase):
    def setUp(self):
        caches["otp"].clear()
        self.ga = Group.objects.create(name="Group A")
        self.gb = Group.objects.create(name="Group B")
        self.sent = []
        p = mock.patch("core.views.send_via_brevo", side_effect=lambda *a, **k: self.sent.append(a[4:6]))
        p.start(); self.addCleanup(p.stop)

    def signup(self, **kw):
        d = {"name": "Asha Rao", "email": "s@x.com", "password": "Str0ng-pass-99", "roll_no": "21CS001"}; d.update(kw)
        return self.client.post("/api/auth/register/", d)

    def test_valid_section_saved_through_otp_flow(self):
        self.assertEqual(self.signup(group=self.ga.id, section="A7").status_code, 202)
        self.client.post("/api/auth/verify-otp/", {"email": "s@x.com", "otp": self.sent[-1][1]})
        u = User.objects.get(email="s@x.com")
        self.assertEqual((u.group_id, u.section), (self.ga.id, "A7"))

    def test_mismatched_or_groupless_section_rejected(self):
        self.assertEqual(self.signup(group=self.ga.id, section="B2").status_code, 400)
        self.assertEqual(self.signup(group=self.gb.id, section="B13").status_code, 400)
        self.assertEqual(self.signup(section="A1").status_code, 400)
        self.assertEqual(self.sent, [])

    def test_profile_update_and_group_change_clears_section(self):
        u = User.objects.create_user("p", password="pw-12345-x", group=self.ga, section="A1", roll_no="21CS001")
        self.client.force_authenticate(u)
        # changing group clears the old section, and a section is then required again
        self.assertEqual(self.client.patch("/api/auth/me/", {"group": self.gb.id}).status_code, 400)
        self.assertEqual(self.client.patch("/api/auth/me/", {"group": self.gb.id, "section": "A4"}).status_code, 400)
        self.assertEqual(self.client.patch("/api/auth/me/", {"group": self.gb.id, "section": "B4"}).status_code, 200)
        u.refresh_from_db(); self.assertEqual((u.group_id, u.section), (self.gb.id, "B4"))

    def test_role_cannot_be_changed_via_profile(self):
        u = User.objects.create_user("p", password="pw-12345-x", group=self.ga, section="A1", roll_no="21CS001")
        self.client.force_authenticate(u)
        self.client.patch("/api/auth/me/", {"role": "admin", "section": "A2"})
        u.refresh_from_db(); self.assertEqual(u.role, "student")

    def test_all_profile_fields_are_mandatory(self):
        self.assertEqual(self.signup(roll_no="").status_code, 400)
        self.assertEqual(self.signup(group=None).status_code, 400)
        self.assertEqual(self.signup(section="").status_code, 400)
        self.assertEqual(self.sent, [])
        old = User.objects.create_user("old", password="pw-12345-x")       # legacy user, incomplete profile
        self.client.force_authenticate(old)
        self.assertEqual(self.client.patch("/api/auth/me/", {"group": self.ga.id, "section": "A1"}).status_code, 400)
        self.assertEqual(self.client.patch("/api/auth/me/", {"group": self.ga.id, "section": "A1", "roll_no": "7"}).status_code, 200)

    def test_roll_unique_within_section_only(self):
        User.objects.create_user("x", password="pw-12345-x", group=self.ga, section="A1", roll_no="21CS009")
        self.assertEqual(self.signup(roll_no="21cs009", section="A1", email="a@x.com").status_code, 400)   # same section
        self.assertEqual(self.signup(roll_no="21 CS 009", section="A1", email="b@x.com").status_code, 400)  # spaces/case
        self.assertEqual(self.signup(roll_no="21CS009", section="A2", email="c@x.com").status_code, 202)   # other section ok

    def test_roll_clash_blocked_on_profile_and_at_verify(self):
        User.objects.create_user("x", password="pw-12345-x", group=self.ga, section="A1", roll_no="5")
        u = User.objects.create_user("p", password="pw-12345-x", group=self.ga, section="A2", roll_no="5")
        self.client.force_authenticate(u)
        self.assertEqual(self.client.patch("/api/auth/me/", {"section": "A1"}).status_code, 400)
        self.client.force_authenticate(None)
        self.assertEqual(self.signup(roll_no="9", section="A3", email="n@x.com").status_code, 202)
        User.objects.create_user("y", password="pw-12345-x", group=self.ga, section="A3", roll_no="9")   # taken meanwhile
        r = self.client.post("/api/auth/verify-otp/", {"email": "n@x.com", "otp": self.sent[-1][1]})
        self.assertEqual((r.status_code, r.data["code"]), (409, "roll_taken"))

    def test_admin_form_validation_blocks_duplicate_roll(self):
        from django.core.exceptions import ValidationError
        User.objects.create_user("x", password="pw-12345-x", group=self.ga, section="A1", roll_no="5")
        dup = User(username="z", group=self.ga, section="A1", roll_no="5")
        with self.assertRaises(ValidationError):
            dup.clean()


class SyllabusTests(APITestCase):
    def setUp(self):
        self.stu = User.objects.create_user("stu", password="pw-12345-x")
        self.fac = User.objects.create_user("fac", password="pw-12345-x", role="faculty")
        self.sub = Subject.objects.create(code="MA101", name="Maths")

    def test_read_for_students_write_for_editors(self):
        SyllabusEntry.objects.create(subject=self.sub, exam="mid1", semester=1, content="Unit 1: Limits")
        self.client.force_authenticate(self.stu)
        self.assertEqual(self.client.get("/api/syllabus/").data[0]["subject_code"], "MA101")
        self.assertEqual(self.client.post("/api/syllabus/", {"subject": self.sub.id, "exam": "end"}).status_code, 403)
        self.client.force_authenticate(self.fac)
        self.assertEqual(self.client.post("/api/syllabus/", {"subject": self.sub.id, "exam": "end"}).status_code, 201)

    def test_requires_login(self):
        self.assertEqual(self.client.get("/api/syllabus/").status_code, 401)

    def test_ensure_schema_is_a_noop_when_up_to_date(self):
        from .schema_sync import ensure_schema
        self.assertEqual(ensure_schema(), [])


class ExamAllotmentTests(APITestCase):
    PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    def setUp(self):
        self.adm = User.objects.create_user("adm", password="pw-12345-x", role="admin")
        self.fac = User.objects.create_user("fac", password="pw-12345-x", role="faculty")
        self.fac2 = User.objects.create_user("fac2", password="pw-12345-x", role="faculty")
        self.stu = User.objects.create_user("stu", password="pw-12345-x", roll_no="21CS017", section="A1")
        self.stu2 = User.objects.create_user("stu2", password="pw-12345-x", roll_no="21CS005", section="A1")
        self.nor = User.objects.create_user("nor", password="pw-12345-x")
        self.exam = Exam.objects.create(name="Term-I", semester=1)
        self.other = Exam.objects.create(name="Term-II")
        ExamManager.objects.create(exam=self.exam, user=self.fac)
        AllotmentRow.objects.create(exam=self.exam, roll_from="21CS001", roll_to="21CS060", room="Room 204")
        AllotmentRow.objects.create(exam=self.exam, roll_from="21CS017", room="Room 301", seat="B4", note="Special")

    def test_draft_is_invisible_to_students_until_published(self):
        self.client.force_authenticate(self.stu)
        self.assertEqual(self.client.get("/api/exams/").data, [])
        self.assertEqual(self.client.get(f"/api/exams/{self.exam.id}/lookup/").status_code, 404)
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.post(f"/api/manage/exams/{self.exam.id}/publish/").status_code, 200)
        self.client.force_authenticate(self.stu)
        self.assertEqual(len(self.client.get("/api/exams/").data), 1)
        r = self.client.get(f"/api/exams/{self.exam.id}/lookup/")
        self.assertEqual((r.data["found"], r.data["result"]["room"], r.data["result"]["seat"]), (True, "Room 301", "B4"))   # exception wins
        self.client.force_authenticate(self.stu2)
        self.assertEqual(self.client.get(f"/api/exams/{self.exam.id}/lookup/").data["result"]["room"], "Room 204")

    def test_student_cannot_look_up_someone_else_or_see_rows(self):
        self.exam.status = "published"; self.exam.save()
        self.client.force_authenticate(self.stu)
        self.assertEqual(self.client.get(f"/api/exams/{self.exam.id}/lookup/?roll_no=21CS005").status_code, 403)
        self.assertEqual(self.client.get(f"/api/exams/{self.exam.id}/lookup/?roll_no=21cs017").status_code, 200)
        self.assertEqual(self.client.get(f"/api/exams/{self.exam.id}/rows/").status_code, 404)
        self.assertEqual(self.client.get("/api/manage/exams/").status_code, 403)
        self.client.force_authenticate(self.nor)
        self.assertEqual(self.client.get(f"/api/exams/{self.exam.id}/lookup/").data["code"], "no_roll_no")

    def test_no_match_is_reported_honestly(self):
        self.exam.status = "published"; self.exam.save()
        u = User.objects.create_user("x", password="pw-12345-x", roll_no="99ZZ999")
        self.client.force_authenticate(u)
        r = self.client.get(f"/api/exams/{self.exam.id}/lookup/")
        self.assertEqual((r.data["found"], r.data["result"]), (False, None))

    def test_faculty_only_manage_assigned_exams(self):
        self.client.force_authenticate(self.fac)
        self.assertEqual([e["id"] for e in self.client.get("/api/manage/exams/").data], [self.exam.id])
        self.assertEqual(self.client.get(f"/api/manage/exams/{self.other.id}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/manage/exams/{self.other.id}/publish/").status_code, 404)
        self.assertEqual(self.client.post("/api/manage/exams/", {"name": "New"}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/manage/exams/{self.exam.id}/").status_code, 403)
        self.assertEqual(self.client.patch(f"/api/manage/exams/{self.exam.id}/", {"batch": "2026"}).status_code, 200)
        self.client.force_authenticate(self.fac2)
        self.assertEqual(self.client.get("/api/manage/exams/").data, [])
        self.assertEqual(self.client.patch(f"/api/manage/exams/{self.exam.id}/", {"batch": "x"}).status_code, 404)

    def test_status_cannot_be_forced_through_edit(self):
        self.client.force_authenticate(self.adm)
        self.client.patch(f"/api/manage/exams/{self.exam.id}/", {"status": "published"})
        self.exam.refresh_from_db(); self.assertEqual(self.exam.status, "draft")

    def test_publish_blocked_when_empty_or_conflicting(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.post(f"/api/manage/exams/{self.other.id}/publish/").status_code, 400)
        self.client.post(f"/api/manage/exams/{self.exam.id}/rows/", {"roll_from": "21CS050", "roll_to": "21CS070", "room": "Room 999"})
        r = self.client.post(f"/api/manage/exams/{self.exam.id}/publish/")
        self.assertEqual(r.status_code, 400); self.assertTrue(r.data["conflicts"])
        self.exam.refresh_from_db(); self.assertEqual(self.exam.status, "draft")

    def test_row_edit_delete_and_validation(self):
        self.client.force_authenticate(self.fac)
        row = self.exam.rows.first()
        self.assertEqual(self.client.patch(f"/api/manage/rows/{row.id}/", {"room": "Room 1"}).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/manage/rows/{row.id}/", {"roll_to": "21CS000"}).status_code, 400)
        foreign = AllotmentRow.objects.create(exam=self.other, roll_from="1", room="R")
        self.assertEqual(self.client.patch(f"/api/manage/rows/{foreign.id}/", {"room": "X"}).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/manage/rows/{foreign.id}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/manage/rows/{row.id}/").status_code, 204)
        self.client.force_authenticate(self.stu)
        self.assertEqual(self.client.delete(f"/api/manage/rows/{self.exam.rows.first().id}/").status_code, 403)

    def test_csv_import_dry_run_then_commit_and_replace(self):
        self.client.force_authenticate(self.fac)
        csv_text = "roll_no,roll_to,room\n21CS061,21CS090,Room 205\n,,Room 9\n"
        r = self.client.post(f"/api/manage/exams/{self.exam.id}/import-csv/", {"csv": csv_text}, format="json")
        self.assertEqual((r.data["valid_rows"], r.data["error_count"], self.exam.rows.count()), (1, 1, 2))
        self.client.post(f"/api/manage/exams/{self.exam.id}/import-csv/", {"csv": csv_text, "dry_run": False}, format="json")
        self.assertEqual(self.exam.rows.count(), 3)
        self.client.post(f"/api/manage/exams/{self.exam.id}/import-csv/", {"csv": csv_text, "dry_run": False, "replace": True}, format="json")
        self.assertEqual(self.exam.rows.count(), 1)
        self.assertEqual(self.client.post(f"/api/manage/exams/{self.exam.id}/import-csv/", {"csv": "x,y\n1,2"}, format="json").status_code, 400)

    def test_pdf_upload_validation_view_and_visibility(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_authenticate(self.fac)
        bad = SimpleUploadedFile("x.pdf", b"not a pdf")
        self.assertEqual(self.client.post(f"/api/manage/exams/{self.exam.id}/document/", {"file": bad}, format="multipart").status_code, 400)
        ok = SimpleUploadedFile("../notice 1.pdf", self.PDF)
        r = self.client.post(f"/api/manage/exams/{self.exam.id}/document/", {"file": ok}, format="multipart")
        self.assertEqual(r.status_code, 200); self.assertTrue(r.data["has_document"]); self.assertNotIn("/", r.data["document_name"])
        self.client.force_authenticate(self.stu)
        self.assertEqual(self.client.get(f"/api/exams/{self.exam.id}/document/").status_code, 404)   # draft
        self.exam.status = "published"; self.exam.save()
        r = self.client.get(f"/api/exams/{self.exam.id}/document/")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(r.content.startswith(b"%PDF-"))
        self.client.force_authenticate(self.fac)
        self.assertEqual(self.client.post(f"/api/manage/exams/{self.exam.id}/extract/").status_code, 422)   # not real text

    def test_manage_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/manage/exams/").status_code, 401)
        self.assertEqual(self.client.get("/api/exams/").status_code, 401)


class AttendanceTests(APITestCase):
    def setUp(self):
        self.a = User.objects.create_user("a", password="pw-12345-x")
        self.b = User.objects.create_user("b", password="pw-12345-x")
        self.sub = Subject.objects.create(code="MA101", name="Maths")
        self.today = timezone.localdate()

    def add(self, user, **kw):
        self.client.force_authenticate(user)
        d = {"date": str(self.today), "status": "present"}; d.update(kw)
        return self.client.post("/api/attendance/", d, format="json")

    def test_create_edit_delete_and_duplicates(self):
        r = self.add(self.a, status="absent", reason="illness", note="fever")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.add(self.a).status_code, 400)                                  # same date/subject/session
        self.assertEqual(self.add(self.a, subject=self.sub.id).status_code, 201)             # different subject ok
        self.assertEqual(self.client.patch(f"/api/attendance/{r.data['id']}/", {"status": "present"}, format="json").data["reason"], "")
        self.assertEqual(self.client.delete(f"/api/attendance/{r.data['id']}/").status_code, 204)

    def test_future_dates_and_bad_values_rejected(self):
        self.assertEqual(self.add(self.a, date=str(self.today + timedelta(days=1))).status_code, 400)
        self.assertEqual(self.add(self.a, status="maybe").status_code, 400)
        self.assertEqual(self.add(self.a, status="absent", reason="nonsense").status_code, 400)

    def test_students_cannot_touch_each_others_records(self):
        mine = self.add(self.a).data["id"]
        self.client.force_authenticate(self.b)
        self.assertEqual(self.client.get(f"/api/attendance/{mine}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/attendance/{mine}/", {"status": "absent"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/attendance/{mine}/").status_code, 404)
        self.assertEqual(self.client.get("/api/attendance/").data, [])
        self.assertEqual(self.client.get("/api/attendance/summary/").data["total"], 0)
        self.assertNotIn("a", self.client.get("/api/attendance/export/").content.decode().lower().split("\n")[0].split(",")[:0])
        r = self.add(self.b, user=self.a.id)                                                  # cannot assign to another user
        self.assertEqual(AttendanceRecord.objects.get(pk=r.data["id"]).user_id, self.b.id)

    def test_summary_formula(self):
        for i, st in enumerate(["present", "present", "absent", "holiday"]):
            self.add(self.a, date=str(self.today - timedelta(days=i + 1)), status=st, **({"reason": "family"} if st == "absent" else {}))
        s = self.client.get("/api/attendance/summary/?target=75").data
        self.assertEqual((s["present"], s["absent"], s["holiday"], s["percentage"]), (2, 1, 1, 66.7))
        self.assertEqual(s["reasons"][0]["count"], 1)
        self.assertIn("not your official", s["target"]["note"])
        self.assertIsNone(self.client.get("/api/attendance/summary/?status=holiday").data["percentage"])

    def test_csv_export_is_own_and_formula_safe(self):
        self.add(self.a, status="absent", reason="other", note="=HYPERLINK(\"x\")")
        self.add(self.b, status="absent", reason="other", note="b-private")
        self.client.force_authenticate(self.a)
        body = self.client.get("/api/attendance/export/").content.decode()
        self.assertIn("'=HYPERLINK", body); self.assertNotIn("b-private", body)
        self.assertEqual(self.client.get("/api/attendance/export/").status_code, 200)

    def test_bad_filter_values_do_not_crash(self):
        self.add(self.a)
        self.assertEqual(len(self.client.get("/api/attendance/?from=abc&to=2020-99-99&month=zz&subject=x&status=nope").data), 1)
        self.assertEqual(self.client.get("/api/attendance/summary/?target=abc").status_code, 200)

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/attendance/").status_code, 401)


@override_settings(CACHES=LOCMEM, AI_API_KEY="SECRET", AI_MODEL="m", AI_PROVIDER="gemini", AI_DAILY_LIMIT_PER_USER=2)
class AIAssistantTests(APITestCase):
    def setUp(self):
        caches["otp"].clear()
        self.u = User.objects.create_user("u", password="pw-12345-x", first_name="Asha", roll_no="21CS001")
        self.client.force_authenticate(self.u)
        self.calls = []
        def fake(cfg, system, msgs):
            self.calls.append((cfg, system, msgs)); return "Answer"
        p = mock.patch("core.views.ai_provider.chat", side_effect=fake); p.start(); self.addCleanup(p.stop)

    def chat(self, text="What is a pointer?"):
        return self.client.post("/api/ai/chat/", {"messages": [{"role": "user", "content": text}]}, format="json")

    def test_reply_and_no_private_data_or_key_sent_back(self):
        r = self.chat()
        self.assertEqual((r.status_code, r.data["reply"]), (200, "Answer"))
        self.assertNotIn("SECRET", str(r.data))
        cfg, system, msgs = self.calls[0]
        blob = system + str(msgs)
        for private in ("Asha", "21CS001", "pw-12345-x", "u@"):
            self.assertNotIn(private, blob)

    def test_followup_history_is_passed(self):
        r = self.client.post("/api/ai/chat/", {"messages": [{"role": "user", "content": "Explain arrays"}, {"role": "assistant", "content": "ok"},
                                                            {"role": "user", "content": "and pointers?"}]}, format="json")
        self.assertEqual(len(self.calls[0][2]), 3)

    def test_verified_syllabus_is_retrieved_unverified_is_not(self):
        sub = Subject.objects.create(code="CS101", name="Programming in C")
        SyllabusEntry.objects.create(subject=sub, exam="mid1", content="Unit 1: pointers and arrays", verified=True)
        SyllabusEntry.objects.create(subject=sub, exam="mid2", content="Unit 9: secretdraft pointers", verified=False)
        self.chat("what pointers are in the C syllabus")
        self.assertIn("Unit 1: pointers", self.calls[0][1]); self.assertNotIn("secretdraft", self.calls[0][1])

    def test_limits_validation_and_status(self):
        self.assertEqual(self.chat().status_code, 200); self.assertEqual(self.chat().status_code, 200)
        r = self.chat(); self.assertEqual((r.status_code, r.data["code"]), (429, "daily_limit"))
        self.assertEqual(self.client.post("/api/ai/chat/", {"messages": []}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/ai/chat/", {"messages": [{"role": "user", "content": "x" * 3000}]}, format="json").status_code, 400)
        st = self.client.get("/api/ai/status/").data
        self.assertTrue(st["enabled"]); self.assertNotIn("SECRET", str(st))

    def test_provider_failure_is_friendly_and_does_not_use_allowance(self):
        from .ai_provider import AIError
        with mock.patch("core.views.ai_provider.chat", side_effect=AIError("quota", "Quota used up", 429)):
            r = self.chat(); self.assertEqual((r.status_code, r.data["code"]), (429, "quota"))
        self.assertEqual(self.chat().status_code, 200); self.assertEqual(self.chat().status_code, 200)

    @override_settings(AI_API_KEY="")
    def test_off_until_configured_and_login_required(self):
        self.assertEqual(self.chat().status_code, 503)
        self.assertFalse(self.client.get("/api/ai/status/").data["enabled"])
        self.client.force_authenticate(None)
        self.assertEqual(self.chat().status_code, 401)


class NotificationTests(APITestCase):
    """Event / syllabus notifications. (Written for Django's test runner; run with: python manage.py test core)"""

    def setUp(self):
        self.ga, self.gb = Group.objects.create(name="Group A"), Group.objects.create(name="Group B")
        mk = lambda name, **kw: User.objects.create_user(name, password="pw-12345-x", **kw)
        self.s1 = mk("s1", group=self.ga, section="A1", roll_no="1")
        self.s2 = mk("s2", group=self.ga, section="A2", roll_no="2")
        self.s3 = mk("s3", group=self.gb, section="B1", roll_no="3")
        self.fac = mk("fac", role="faculty")
        self.adm = mk("adm", role="admin")
        self.sub = Subject.objects.create(code="MA101", name="Maths")
        self.when = timezone.now() + timedelta(days=3)

    def count(self, user, **kw):
        return Notification.objects.filter(user=user, **kw).count()

    # ---- events ----
    def test_published_event_notifies_students_only_with_details(self):
        e = Event.objects.create(name="Hackathon", start=self.when, venue="Hall A", description="Build things")
        for u in (self.s1, self.s2, self.s3):
            n = Notification.objects.get(user=u)
            self.assertEqual((n.kind, n.link, n.read), ("event", f"/events?event={e.pk}", False))
            self.assertIn("Hackathon", n.title); self.assertIn("Build things", n.message)
            self.assertIn("Event date:", n.message); self.assertIn("Published on", n.message)
        self.assertEqual(Notification.objects.filter(user__in=[self.fac, self.adm]).count(), 0)

    def test_draft_notifies_nobody_until_published_and_never_twice(self):
        e = Event.objects.create(name="Draft", start=self.when, is_published=False)
        self.assertEqual(Notification.objects.count(), 0)
        e.description = "edited while draft"; e.save()
        self.assertEqual(Notification.objects.count(), 0)
        e.is_published = True; e.save()
        self.assertEqual(Notification.objects.count(), 3)
        e.save(); e.refresh_from_db(); e.save()                       # repeated saves / double click
        self.assertEqual(Notification.objects.count(), 3)
        e.description = "internal note changed"; e.save()              # unrelated edit
        self.assertEqual(Notification.objects.count(), 3)

    def test_group_and_section_targeting(self):
        Event.objects.create(name="Group A only", start=self.when, target_group=self.ga)
        self.assertEqual((self.count(self.s1), self.count(self.s2), self.count(self.s3)), (1, 1, 0))
        Event.objects.create(name="Sections", start=self.when, target_sections="A1, B1")
        self.assertEqual((self.count(self.s1), self.count(self.s2), self.count(self.s3)), (2, 1, 1))
        Event.objects.create(name="Section beats group", start=self.when, target_group=self.gb, target_sections="A2")
        self.assertEqual((self.count(self.s1), self.count(self.s2), self.count(self.s3)), (2, 2, 1))

    def test_unpublish_and_delete_remove_notifications(self):
        e = Event.objects.create(name="Gone", start=self.when)
        self.assertEqual(Notification.objects.count(), 3)
        e.is_published = False; e.save()
        self.assertEqual(Notification.objects.count(), 0)
        e.is_published = True; e.save()
        self.assertEqual(Notification.objects.count(), 3)
        e.delete()
        self.assertEqual(Notification.objects.count(), 0)

    def test_drafts_hidden_from_students_in_api_and_dashboard(self):
        Event.objects.create(name="Public", start=self.when)
        Event.objects.create(name="Secret draft", start=self.when, is_published=False)
        self.client.force_authenticate(self.s1)
        names = [x["name"] for x in self.client.get("/api/events/").data["results"]]
        self.assertEqual(names, ["Public"])
        self.client.force_authenticate(self.fac)
        self.assertEqual(len(self.client.get("/api/events/").data["results"]), 2)

    def test_api_rejects_invalid_sections_and_students_cannot_create(self):
        self.client.force_authenticate(self.fac)
        body = {"name": "E", "start": self.when.isoformat(), "target_sections": "Z9"}
        self.assertEqual(self.client.post("/api/events/", body, format="json").status_code, 400)
        body["target_sections"] = "a2"
        r = self.client.post("/api/events/", body, format="json")
        self.assertEqual((r.status_code, r.data["target_sections"]), (201, "A2"))
        self.assertEqual((self.count(self.s2), self.count(self.s1)), (1, 0))
        self.client.force_authenticate(self.s1)
        self.assertEqual(self.client.post("/api/events/", body, format="json").status_code, 403)

    # ---- syllabus ----
    def post_syllabus(self, user=None, **kw):
        self.client.force_authenticate(user or self.fac)
        body = {"subject": self.sub.id, "exam": "mid1", "semester": 1, "content": "Unit 1\n- Limits", "verified": True}
        body.update(kw)
        return self.client.post("/api/syllabus/", body, format="json")

    def test_new_verified_syllabus_notifies_with_subject_exam_and_link(self):
        r = self.post_syllabus()
        self.assertEqual(r.status_code, 201)
        n = Notification.objects.get(user=self.s1)
        self.assertEqual(n.kind, "syllabus"); self.assertIn("published", n.title.lower())
        self.assertIn("Maths", n.title); self.assertIn("Mid-Term 1", n.title)
        self.assertEqual(n.link, f"/syllabus?subject={self.sub.id}&exam=mid1")
        self.assertEqual(self.count(self.s3), 1)
        self.assertEqual(Notification.objects.filter(user=self.fac).count(), 0)

    def test_unverified_draft_notifies_nobody_until_verified(self):
        r = self.post_syllabus(verified=False)
        self.assertEqual(Notification.objects.count(), 0)
        self.client.patch(f"/api/syllabus/{r.data['id']}/", {"content": "Unit 1\n- Limits\n- Continuity"}, format="json")
        self.assertEqual(Notification.objects.count(), 0)
        self.client.patch(f"/api/syllabus/{r.data['id']}/", {"verified": True}, format="json")
        self.assertEqual(self.count(self.s1), 1)
        self.assertIn("published", Notification.objects.get(user=self.s1).title.lower())

    def test_update_notifies_once_and_unchanged_save_does_not(self):
        sid = self.post_syllabus().data["id"]
        patch = lambda **kw: self.client.patch(f"/api/syllabus/{sid}/", kw, format="json")
        patch(content="Unit 1\n- Limits")                                  # identical
        patch(content="Unit 1  \r\n- Limits\n")                           # whitespace only
        patch(semester=2)                                                  # unrelated field
        self.assertEqual(self.count(self.s1), 1)
        patch(content="Unit 1\n- Limits\n- Continuity")
        self.assertEqual(self.count(self.s1), 2)
        newest = Notification.objects.filter(user=self.s1).first()
        self.assertIn("updated", newest.title.lower()); self.assertIn("1 line added", newest.message)
        patch(content="Unit 1\n- Limits\n- Continuity")                   # repeated request / double click
        self.assertEqual(self.count(self.s1), 2)
        patch(pdf_url="https://college.example.org/ma101.pdf")
        self.assertEqual(self.count(self.s1), 3)
        self.assertIn("PDF", Notification.objects.filter(user=self.s1).first().message)

    def test_deleting_syllabus_removes_its_notifications(self):
        sid = self.post_syllabus().data["id"]
        self.assertEqual(self.count(self.s1), 1)
        self.client.delete(f"/api/syllabus/{sid}/")
        self.assertEqual(Notification.objects.count(), 0)

    def test_students_cannot_publish_syllabus(self):
        self.assertEqual(self.post_syllabus(user=self.s1).status_code, 403)
        self.assertEqual(Notification.objects.count(), 0)

    # ---- notification API: privacy + read state ----
    def test_students_see_only_their_own_notifications(self):
        Event.objects.create(name="E1", start=self.when, target_sections="A1")
        Event.objects.create(name="E2", start=self.when, target_sections="B1")
        self.client.force_authenticate(self.s1)
        r = self.client.get("/api/notifications/latest/")
        self.assertEqual((r.data["unread"], [i["title"] for i in r.data["items"]]), (1, ["New event: E1"]))
        other = Notification.objects.get(user=self.s3)
        self.assertEqual(self.client.post(f"/api/notifications/{other.id}/read/").status_code, 404)
        other.refresh_from_db(); self.assertFalse(other.read)
        self.assertEqual(self.client.get(f"/api/notifications/{other.id}/").status_code, 404)
        self.assertEqual(self.client.post("/api/notifications/", {"title": "x", "user": self.s3.id}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/notifications/{other.id}/").status_code, 405)
        self.assertEqual(self.client.patch(f"/api/notifications/{other.id}/", {"read": True}, format="json").status_code, 405)

    def test_read_state_persists_and_read_all_only_touches_own(self):
        Event.objects.create(name="E1", start=self.when)
        Event.objects.create(name="E2", start=self.when)
        self.client.force_authenticate(self.s1)
        first = self.client.get("/api/notifications/latest/").data["items"][0]["id"]
        self.assertEqual(self.client.post(f"/api/notifications/{first}/read/").status_code, 204)
        self.client.force_authenticate(None); self.client.force_authenticate(self.s1)          # "log in again"
        self.assertEqual(self.client.get("/api/notifications/latest/").data["unread"], 1)
        self.client.post("/api/notifications/read_all/")
        self.assertEqual(self.client.get("/api/notifications/latest/").data["unread"], 0)
        self.assertEqual(self.count(self.s2, read=False), 2)

    def test_notifications_require_login(self):
        self.assertEqual(self.client.get("/api/notifications/latest/").status_code, 401)

    def test_db_enforces_one_notification_per_publication(self):
        from django.db import IntegrityError, transaction
        Notification.objects.create(user=self.s1, title="a", dedupe_key="k1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(user=self.s1, title="b", dedupe_key="k1")
        Notification.objects.create(user=self.s1, title="c", dedupe_key="")           # blank keys are unlimited
        Notification.objects.create(user=self.s1, title="d", dedupe_key="")

