from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse


class LodgingStudentScopeMiddleware:
    """An automatic student identity cannot become a teacher/operator through a URL."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False) or not user.is_lodging_student:
            return None
        allowed = {
            "bookings:role_home", "bookings:lodging_index", "bookings:lodging_portal",
            "bookings:lodging_book_bed", "bookings:lodging_pass", "bookings:lodging_start",
            "bookings:lodging_about", "bookings:lodging_reservation_manage",
            "bookings:lodging_room_detail",
            "bookings:lodging_reservation_cancel", "accounts:login", "logout", "webmanifest",
            "google_login", "google_callback", "socialaccount_login_error", "favicon",
        }
        match = request.resolver_match
        if match and (match.view_name in allowed or match.namespace == "notifications"):
            return None
        if request.path.startswith(("/static/", "/media/")):
            return None
        raise PermissionDenied("บัญชีนักเรียนใช้จองเตียงของหลักสูตรตนเองเท่านั้น")


class MustChangePasswordMiddleware:
    """กันผู้ใช้รหัสเริ่มต้นออกจากทุกหน้าจนกว่าจะตั้งรหัสใหม่ที่ S17"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False) and user.must_change_password:
            allowed = {
                reverse("accounts:first_password_change"),
                reverse("accounts:password_reset"),
                reverse("accounts:password_reset_done"),
                reverse("accounts:password_reset_complete"),
                reverse("logout"),
                reverse("webmanifest"),
            }
            allowed_prefixes = (
                "/static/",
                "/accounts/password-reset/",
                "/accounts/password_reset/",
                "/accounts/reset/",
            )
            if request.path not in allowed and not request.path.startswith(allowed_prefixes):
                if request.headers.get("HX-Request") == "true":
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = reverse("accounts:first_password_change")
                    return response
                return redirect("accounts:first_password_change")
        return self.get_response(request)
