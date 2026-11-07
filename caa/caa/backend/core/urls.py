from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views as v
from . import views_faculty as vf

router = DefaultRouter()
router.register("subjects", v.SubjectViewSet)
router.register("records", v.ClassRecordViewSet)
router.register("labs", v.LabViewSet)
router.register("experiments", v.ExperimentViewSet)
router.register("assignments", v.AssignmentViewSet)
router.register("events", v.EventViewSet)
router.register("forms", v.FormGuideViewSet)
router.register("notifications", v.NotificationViewSet, basename="notification")
router.register("posts", v.PostViewSet, basename="post")
router.register("reports", v.ReportViewSet)
router.register("syllabus", v.SyllabusViewSet)
router.register("exams", v.ExamStudentViewSet, basename="exam")
router.register("manage/exams", v.ExamManageViewSet, basename="manage-exam")
router.register("attendance", v.AttendanceViewSet, basename="attendance")
router.register("manage/rows", v.AllotmentRowViewSet, basename="manage-row")
router.register("faculty/events", vf.FacultyEventViewSet, basename="faculty-event")

urlpatterns = [
    path("push/status/", v.PushStatusView.as_view()),
    path("push/register/", v.PushRegisterView.as_view()),
    path("push/unregister/", v.PushUnregisterView.as_view()),
    path("push/preferences/", v.PushPreferencesView.as_view()),
    path("push/test/", v.PushTestView.as_view()),
    path("auth/token/", v.ThrottledTokenView.as_view()),
    path("auth/faculty/token/", vf.FacultyLoginView.as_view()),
    path("auth/faculty/activate/", vf.FacultyActivateView.as_view()),
    path("faculty/me/", vf.FacultyMeView.as_view()),
    path("faculty/activity/", vf.FacultyActivityView.as_view()),
    path("faculty/groups/", vf.FacultyGroupsView.as_view()),
    path("faculty/syllabus/", vf.FacultySyllabusView.as_view()),
    path("faculty/syllabus/<int:subject_id>/<str:exam>/", vf.FacultySyllabusEntryView.as_view()),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/register/", v.SignupView.as_view()),
    path("auth/verify-otp/", v.VerifyOtpView.as_view()),
    path("auth/resend-otp/", v.ResendOtpView.as_view()),
    path("auth/me/", v.MeView.as_view()),
    path("groups/", v.GroupList.as_view()),
    path("dashboard/", v.DashboardView.as_view()),
    path("cron/send-reminders/", v.CronReminderView.as_view()),
    path("", include(router.urls)),
]
