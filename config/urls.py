from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "SIGROOM — ผู้ดูแลระบบ"
admin.site.site_title = "SIGROOM"
admin.site.index_title = "ทะเบียนและการตั้งค่า"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("approvals/", include("approvals.urls")),
    path("notifications/", include("notifications.urls")),
    path("", include("bookings.urls")),
]
