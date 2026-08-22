from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ระบบจองห้อง รร.ส.สส. — ผู้ดูแลระบบ"
admin.site.site_title = "ระบบจองห้อง"
admin.site.index_title = "ทะเบียนและการตั้งค่า"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
]
