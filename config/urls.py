from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.templatetags.static import static as static_url
from django.urls import include, path
from django.views.generic import TemplateView

from audit.views import client_ip_diagnostics
from notifications.push_views import service_worker

admin.site.site_header = "SIGROOM — ผู้ดูแลระบบ"
admin.site.site_title = "SIGROOM"
admin.site.index_title = "ทะเบียนและการตั้งค่า"


def favicon_redirect(request):
    # คำนวณตอนรับคำขอ (ไม่ใช่ตอน import urls) เพราะ Manifest storage ต้องมี collectstatic ก่อนจึงหา URL แบบ hash ได้
    # ไม่เช่นนั้น migrate/check ก่อน collectstatic จะล้มบนเครื่องที่ DEBUG=0
    return HttpResponseRedirect(static_url("img/brand/favicon.ico"))


urlpatterns = [
    path("favicon.ico", favicon_redirect, name="favicon"),
    path(
        "manifest.webmanifest",
        TemplateView.as_view(template_name="manifest.webmanifest", content_type="application/manifest+json"),
        name="webmanifest",
    ),
    path("sw.js", service_worker, name="push_service_worker"),
    path("ops/client-ip/", client_ip_diagnostics, name="client_ip_diagnostics"),
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
