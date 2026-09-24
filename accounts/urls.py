from django.urls import path

from . import views

app_name = "accounts"

reset_view = views.UnitPasswordResetView.as_view()
reset_done_view = views.UnitPasswordResetDoneView.as_view()
reset_confirm_view = views.UnitPasswordResetConfirmView.as_view()
reset_complete_view = views.UnitPasswordResetCompleteView.as_view()

urlpatterns = [
    path("change-initial-password/", views.first_password_change, name="first_password_change"),
    # เส้นทางหลักที่แสดงต่อผู้ใช้
    path("password-reset/", reset_view, name="password_reset"),
    path("password-reset/done/", reset_done_view, name="password_reset_done"),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        reset_confirm_view,
        name="password_reset_confirm",
    ),
    path("password-reset/complete/", reset_complete_view, name="password_reset_complete"),
    # Shadow เส้นทางมาตรฐานของ django.contrib.auth.urls ที่ include ต่อจาก accounts.urls
    # เพื่อไม่ให้มี bypass ที่ข้าม domain guard / audited SetPasswordForm.
    path("password_reset/", reset_view),
    path("password_reset/done/", reset_done_view),
    path("reset/<uidb64>/<token>/", reset_confirm_view),
    path("reset/done/", reset_complete_view),
]
