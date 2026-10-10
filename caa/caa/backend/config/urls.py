from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

admin.site.site_header = "College Academic Assistant — Admin"
admin.site.site_title = "CAA Admin"

urlpatterns = [
    path("", lambda r: JsonResponse({"service": "CAA API", "status": "ok"})),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]
