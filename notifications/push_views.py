import json
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import PushSubscription
from .push import push_enabled, subscribe, unsubscribe


def _configured():
    if not push_enabled():
        raise Http404


def push_configured(view):
    """ปิดผิวโจมตีของ feature ทั้งหมดก่อน auth/method handling เมื่อ VAPID ไม่พร้อม"""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        _configured()
        return view(request, *args, **kwargs)

    return wrapped


def _body(request):
    if request.content_type != "application/json" or len(request.body) > 8192:
        raise ValidationError("ข้อมูลแจ้งเตือนจากเบราว์เซอร์ไม่ถูกต้อง")
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("ข้อมูลแจ้งเตือนจากเบราว์เซอร์ไม่ถูกต้อง") from None
    if not isinstance(data, dict):
        raise ValidationError("ข้อมูลแจ้งเตือนจากเบราว์เซอร์ไม่ถูกต้อง")
    return data


def _error(exc):
    message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
    return JsonResponse({"error": message}, status=409 if isinstance(exc, PermissionError) else 400)


@push_configured
@login_required
@require_GET
def push_status(request):
    response = JsonResponse({"endpoints": list(PushSubscription.objects.filter(user=request.user).values_list("endpoint", flat=True))})
    response["Cache-Control"] = "no-store"
    return response


@push_configured
@login_required
@require_POST
def push_subscribe(request):
    try:
        subscribe(request.user, _body(request), request.META.get("HTTP_USER_AGENT", ""))
    except (ValidationError, PermissionError) as exc:
        return _error(exc)
    return JsonResponse({"enabled": True})


@push_configured
@login_required
@require_POST
def push_unsubscribe(request):
    try:
        data = _body(request)
        unsubscribe(request.user, data.get("endpoint"))
    except (ValidationError, PermissionError) as exc:
        return _error(exc)
    return JsonResponse({"enabled": False})


@push_configured
@require_GET
def service_worker(request):
    source = (settings.BASE_DIR / "static" / "js" / "web_push_sw.js").read_text(encoding="utf-8")
    response = HttpResponse(source, content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response
