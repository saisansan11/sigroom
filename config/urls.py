from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

admin.site.site_header = "SIGROOM — ผู้ดูแลระบบ"
admin.site.site_title = "SIGROOM"
admin.site.index_title = "ทะเบียนและการตั้งค่า"

urlpatterns = [
    path(
        "manifest.webmanifest",
        TemplateView.as_view(template_name="manifest.webmanifest", content_type="application/manifest+json"),
        name="webmanifest",
    ),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("approvals/", include("approvals.urls")),
    path("notifications/", include("notifications.urls")),
    path("resources/", include("resources.urls")),
    path("usage/", include("usage.urls")),
    path("reports/", include("reports.urls")),
    path("", include("bookings.urls")),
]

# เสิร์ฟไฟล์ media (รูปห้อง) เฉพาะ dev ในเครื่อง (FileSystemStorage) — production ใช้ GCS โดยตรง ไม่ผ่าน Django
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
