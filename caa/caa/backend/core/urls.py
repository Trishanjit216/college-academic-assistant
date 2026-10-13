from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views as v

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
router.register("manage/rows", v.AllotmentRowViewSet, basename="manage-row")

urlpatterns = [
    path("auth/token/", v.ThrottledTokenView.as_view()),
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
