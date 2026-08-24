from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class MustChangePasswordMiddleware:
    """กันผู้ใช้รหัสเริ่มต้นออกจากทุกหน้าจนกว่าจะตั้งรหัสใหม่ที่ S17"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False) and user.must_change_password:
            allowed = {
                reverse("accounts:first_password_change"),
                reverse("logout"),
                reverse("password_reset"),
                reverse("password_reset_done"),
                reverse("password_reset_complete"),
            }
            allowed_prefixes = ("/static/", "/accounts/reset/")
            if request.path not in allowed and not request.path.startswith(allowed_prefixes):
                if request.headers.get("HX-Request") == "true":
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = reverse("accounts:first_password_change")
                    return response
                return redirect("accounts:first_password_change")
        return self.get_response(request)
