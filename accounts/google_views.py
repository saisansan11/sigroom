"""Expose only the OAuth code flow, using server configuration for its callback."""
from urllib.parse import urlsplit

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.providers.base import AuthProcess
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter, _verify_and_decode
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from allauth.socialaccount.providers.oauth2.views import OAuth2CallbackView
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.shortcuts import render
from django.urls import Resolver404, resolve, reverse
from django.views.decorators.http import require_POST

from .social import safe_login_next


class CanonicalGoogleOAuth2Adapter(GoogleOAuth2Adapter):
    def get_callback_url(self, request, app):
        base = settings.PUBLIC_BASE_URL.rstrip("/")
        parsed = urlsplit(base)
        if (not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or parsed.scheme not in ("http", "https")
                or (not settings.DEBUG and parsed.scheme != "https")):
            raise ImproperlyConfigured("PUBLIC_BASE_URL ต้องเป็น origin ที่เชื่อถือได้สำหรับ Google login")
        return base + reverse("google_callback")

    def _decode_id_token(self, app, id_token):
        # allauth can omit signature checks for token-endpoint responses; this flow always verifies.
        return _verify_and_decode(app, id_token, verify_signature=True)

    def complete_login(self, request, app, token, **kwargs):
        if not kwargs["response"].get("id_token"):
            raise OAuth2Error("Missing signed identity token")
        return super().complete_login(request, app, token, **kwargs)


def _cohort_for_next(next_url):
    from bookings.lodging_models import CourseLodgingCohort
    try:
        match = resolve(urlsplit(next_url).path)
    except Resolver404:
        return None
    if match.view_name != "bookings:lodging_portal":
        return None
    return CourseLodgingCohort.objects.filter(
        slug=match.kwargs["slug"], is_active=True, allocation_status="allocated",
    ).values_list("pk", flat=True).first()


def google_login(request):
    if not settings.GOOGLE_LOGIN_ENABLED:
        raise Http404
    return _google_start(request)


@require_POST
def _google_start(request):
    next_url = safe_login_next(request.POST.get("next"))
    cohort_id = _cohort_for_next(next_url)
    provider = get_adapter(request).get_provider(request, "google")
    provider.oauth2_adapter_class = CanonicalGoogleOAuth2Adapter
    # Ignore process/scope/auth_params supplied by callers: there is no connect or token flow.
    return provider.redirect(request, process=AuthProcess.LOGIN, next_url=next_url or None,
                             data={"cohort_id": str(cohort_id)} if cohort_id else {})


def google_callback(request):
    if not settings.GOOGLE_LOGIN_ENABLED:
        raise Http404
    return OAuth2CallbackView.adapter_view(CanonicalGoogleOAuth2Adapter)(request)


def google_error(request):
    if not settings.GOOGLE_LOGIN_ENABLED:
        raise Http404
    return render(request, "registration/google_error.html", status=400)
