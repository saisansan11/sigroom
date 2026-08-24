from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import FirstPasswordChangeForm
from .services import complete_initial_password_change


@login_required
def first_password_change(request):
    if not request.user.must_change_password:
        return redirect("bookings:calendar")
    form = FirstPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = complete_initial_password_change(request.user, form.cleaned_data["new_password1"])
        update_session_auth_hash(request, user)
        messages.success(request, "ตั้งรหัสผ่านใหม่แล้ว ต่อไปให้ใช้รหัสนี้เข้าสู่ระบบ")
        return redirect("bookings:calendar")
    return render(request, "accounts/first_password_change.html", {"form": form})
