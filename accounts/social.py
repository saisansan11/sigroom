"""Google identity rules; school domain and a QR never grant course membership."""
from urllib.parse import urlsplit
from uuid import uuid4

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from audit.services import audit
from .models import User


def safe_login_next(value):
    """Accept relative paths or the configured public origin, never request headers."""
    origin = urlsplit(settings.PUBLIC_BASE_URL)
    value = value or ""
    if not url_has_allowed_host_and_scheme(
        value, allowed_hosts={origin.netloc} if origin.netloc else set(),
        require_https=origin.scheme == "https",
    ):
        return ""
    return value


class NoSignupAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False

    def is_safe_url(self, url):
        return bool(safe_login_next(url))

    def get_login_redirect_url(self, request):
        return reverse("bookings:role_home")


class GoogleLoginDenied(Exception):
    def __init__(self, reason):
        self.reason = reason


def _masked(value):
    value = str(value or "")
    return value[:2] + "***" + ("@" + value.rsplit("@", 1)[1] if "@" in value else "")


@transaction.atomic
def _match_school_identity(request, sociallogin):
    from bookings.lodging_models import CourseStudentEnrollment
    data = sociallogin.account.extra_data
    domain = settings.ALLOWED_EMAIL_DOMAIN.lower()
    if sociallogin.account.provider != "google" or not isinstance(data, dict):
        raise GoogleLoginDenied("provider")
    if data.get("email_verified") is not True:
        raise GoogleLoginDenied("unverified")
    email = data.get("email", "")
    if not isinstance(email, str):
        raise GoogleLoginDenied("domain")
    email = email.strip().lower()
    if not email.endswith("@" + domain) or email.count("@") != 1:
        raise GoogleLoginDenied("domain")
    if data.get("hd") != domain:
        raise GoogleLoginDenied("hd")
    uid = sociallogin.account.uid
    if not uid or str(data.get("sub", "")) != str(uid):
        raise GoogleLoginDenied("uid_mismatch")
    users = list(User.objects.select_for_update().filter(email__iexact=email)[:2])
    if len(users) > 1:
        raise GoogleLoginDenied("ambiguous_email")
    user = users[0] if users else None
    linked = SocialAccount.objects.select_for_update().filter(provider="google", uid=uid).first()
    if linked and (user is None or linked.user_id != user.pk):
        raise GoogleLoginDenied("uid_mismatch")
    if user and not user.is_active:
        raise GoogleLoginDenied("inactive")
    if user and SocialAccount.objects.filter(provider="google", user=user).exclude(uid=uid).exists():
        raise GoogleLoginDenied("uid_mismatch")
    cohort_id = (sociallogin.state.get("data") or {}).get("cohort_id")
    enrollment = None
    if cohort_id:
        enrollment = CourseStudentEnrollment.objects.select_for_update().filter(
            cohort_id=cohort_id, email=email, is_active=True,
            cohort__is_active=True,
            cohort__allocation_status="allocated",
        ).first()
    if user is None:
        if enrollment is None or enrollment.user_id:
            raise GoogleLoginDenied("not_registered")
        name = data.get("name", "")
        if not isinstance(name, str) or not name.strip():
            raise GoogleLoginDenied("missing_name")
        user = User(
            username="student-" + uuid4().hex, email=email,
            first_name=name.strip()[:150], is_lodging_student=True,
            is_staff=False, is_superuser=False, rank=enrollment.rank,
            phone=enrollment.phone,
        )
        user.set_unusable_password()
        user.full_clean()
        user.save()
        audit(user, "accounts.user", user.pk, "google_student_created",
              after={"email": _masked(email), "cohort": str(cohort_id)})
    if enrollment:
        if enrollment.user_id and enrollment.user_id != user.pk:
            raise GoogleLoginDenied("membership_mismatch")
        enrollment.user = user
        enrollment.save(update_fields=["user"])
    if user.is_lodging_student and enrollment is None:
        # A returning student can log in normally; scoped services still require a roster.
        if cohort_id or not user.student_enrollments.filter(is_active=True).exists():
            raise GoogleLoginDenied("membership")
    if linked:
        sociallogin.account = linked
        sociallogin.user = user
    else:
        sociallogin.connect(request, user)
    sociallogin.state["next"] = safe_login_next(sociallogin.state.get("next"))
    return user, email


class SchoolGoogleAdapter(DefaultSocialAccountAdapter):
    def list_apps(self, request, provider=None, client_id=None):
        # Secrets have one authority: environment configuration, never SocialApp rows.
        return [app for app in super().list_apps(request, provider, client_id) if app.pk is None]

    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        try:
            user, email = _match_school_identity(request, sociallogin)
        except (GoogleLoginDenied, IntegrityError) as exc:
            data = sociallogin.account.extra_data
            reason = exc.reason if isinstance(exc, GoogleLoginDenied) else "identity_conflict"
            audit(None, "accounts.user", "google", "login_google_rejected",
                  after={"reason": reason, "email": _masked(data.get("email") if isinstance(data, dict) else ""),
                         "uid": _masked(sociallogin.account.uid)})
            messages.error(request, "บัญชี Google นี้ใช้เข้า SIGROOM ไม่ได้ ใช้บัญชีโรงเรียนที่ลงทะเบียนแล้ว หรือติดต่อผู้จัดหลักสูตร")
            raise ImmediateHttpResponse(redirect("accounts:login"))
        audit(user, "accounts.user", user.pk, "login_google",
              after={"email": _masked(email), "uid": _masked(sociallogin.account.uid)})

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        audit(None, "accounts.user", "google", "login_google_rejected", after={"reason": "oauth_error"})
        messages.error(request, "เข้าสู่ระบบด้วย Google ไม่สำเร็จ กรุณาลองใหม่จากหน้าเข้าสู่ระบบ")
        raise ImmediateHttpResponse(redirect("accounts:login"))
