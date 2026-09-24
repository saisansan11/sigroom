from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import AuditedSetPasswordForm, FirstPasswordChangeForm, UnitPasswordResetForm
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


class UnitPasswordResetView(auth_views.PasswordResetView):
    form_class = UnitPasswordResetForm
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class UnitPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class UnitPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    form_class = AuditedSetPasswordForm
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class UnitPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"
