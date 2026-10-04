"""สิทธิ์และการส่ง Web Push; ไม่เผย endpoint หรือกุญแจในข้อความผิดพลาด/log"""

import base64
import json
import logging
import re
from urllib.parse import unquote, urlsplit

import requests
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from pywebpush import webpush

from .models import PushSubscription

logger = logging.getLogger(__name__)
MAX_SUBSCRIPTIONS = 10
PUSH_EXACT_HOSTS = frozenset({"fcm.googleapis.com", "updates.push.services.mozilla.com"})
PUSH_HOST_SUFFIXES = (".push.apple.com", ".notify.windows.com")


def push_enabled():
    return all((settings.WEBPUSH_VAPID_PUBLIC_KEY, settings.WEBPUSH_VAPID_PRIVATE_KEY, settings.WEBPUSH_VAPID_SUBJECT))


def validate_endpoint(endpoint):
    if not isinstance(endpoint, str) or not 1 <= len(endpoint) <= 2048 or not endpoint.isascii():
        raise ValidationError("ข้อมูลปลายทางแจ้งเตือนไม่ถูกต้อง")
    if any(character.isspace() or ord(character) < 32 for character in endpoint) or "\\" in endpoint:
        raise ValidationError("ข้อมูลปลายทางแจ้งเตือนไม่ถูกต้อง")
    try:
        parts = urlsplit(endpoint)
        host = parts.hostname or ""
        valid_host = host in PUSH_EXACT_HOSTS or any(host.endswith(suffix) for suffix in PUSH_HOST_SUFFIXES)
        if (
            parts.scheme != "https" or not valid_host or parts.port not in (None, 443)
            or parts.username is not None or parts.password is not None or parts.fragment
        ):
            raise ValueError
    except ValueError:
        raise ValidationError("รองรับเฉพาะปลายทาง HTTPS ของบริการแจ้งเตือนเบราว์เซอร์") from None
    return endpoint


def _validated_key(value, *, size, public=False):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
        raise ValidationError("กุญแจแจ้งเตือนจากเบราว์เซอร์ไม่ถูกต้อง")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        if len(raw) != size:
            raise ValueError
        if public:
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
    except (ValueError, TypeError):
        raise ValidationError("กุญแจแจ้งเตือนจากเบราว์เซอร์ไม่ถูกต้อง") from None
    return value.rstrip("=")


@transaction.atomic
def subscribe(user, data, user_agent=""):
    if not isinstance(data, dict) or not isinstance(data.get("keys"), dict):
        raise ValidationError("ข้อมูลแจ้งเตือนจากเบราว์เซอร์ไม่ครบ")
    endpoint = validate_endpoint(data.get("endpoint"))
    p256dh = _validated_key(data["keys"].get("p256dh"), size=65, public=True)
    auth = _validated_key(data["keys"].get("auth"), size=16)
    get_user_model().objects.select_for_update().get(pk=user.pk)
    existing = PushSubscription.objects.select_for_update().filter(endpoint=endpoint).first()
    if existing:
        if existing.user_id != user.pk:
            raise PermissionError("เครื่องนี้ผูกกับบัญชีอื่น กรุณาปิดแจ้งเตือนด้วยบัญชีเดิมก่อน")
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = str(user_agent)[:500]
        existing.save(update_fields=["p256dh", "auth", "user_agent"])
        return existing
    if PushSubscription.objects.filter(user=user).count() >= MAX_SUBSCRIPTIONS:
        raise ValidationError("เปิดแจ้งเตือนได้ไม่เกิน 10 เครื่อง กรุณาปิดเครื่องที่ไม่ใช้ก่อน")
    try:
        with transaction.atomic():
            return PushSubscription.objects.create(
                user=user, endpoint=endpoint, p256dh=p256dh, auth=auth, user_agent=str(user_agent)[:500],
            )
    except IntegrityError:
        # ผู้ใช้อื่นอาจลงทะเบียน endpoint เดียวกันระหว่างการตรวจและสร้าง
        if PushSubscription.objects.filter(endpoint=endpoint).exists():
            raise PermissionError("เครื่องนี้ผูกกับบัญชีอื่น กรุณาปิดแจ้งเตือนด้วยบัญชีเดิมก่อน") from None
        raise


@transaction.atomic
def unsubscribe(user, endpoint):
    endpoint = validate_endpoint(endpoint)
    get_user_model().objects.select_for_update().get(pk=user.pk)
    item = PushSubscription.objects.select_for_update().filter(endpoint=endpoint).first()
    if item and item.user_id != user.pk:
        raise PermissionError("เครื่องนี้ผูกกับบัญชีอื่น กรุณาปิดแจ้งเตือนด้วยบัญชีเดิมก่อน")
    return PushSubscription.objects.filter(user=user, endpoint=endpoint).delete()[0]


def validate_internal_url(url):
    if not isinstance(url, str) or not url.startswith("/") or len(url) > 500:
        raise ValidationError("ลิงก์แจ้งเตือนต้องอยู่ภายใน SIGROOM")
    decoded = url
    for _ in range(3):
        decoded = unquote(decoded)
    if decoded.startswith("//") or "\\" in decoded or any(ord(character) < 32 for character in decoded):
        raise ValidationError("ลิงก์แจ้งเตือนต้องอยู่ภายใน SIGROOM")
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ValidationError("ลิงก์แจ้งเตือนต้องอยู่ภายใน SIGROOMและไม่มีข้อมูลส่วนตัวใน query")
    return url


class _PushSession(requests.Session):
    def post(self, url, *args, **kwargs):
        validate_endpoint(url)
        kwargs["allow_redirects"] = False
        return super().post(url, *args, **kwargs)


def send_push(user, title, body, url):
    counts = {"sent": 0, "removed": 0, "failed": 0}
    if not push_enabled():
        return counts
    try:
        payload = json.dumps(
            {"title": str(title)[:100], "body": str(body)[:300], "url": validate_internal_url(url)},
            ensure_ascii=False,
        )
    except ValidationError:
        logger.warning("web_push_payload_rejected")
        return counts
    with _PushSession() as session:
        for item in PushSubscription.objects.filter(user=user).iterator():
            try:
                validate_endpoint(item.endpoint)
                webpush(
                    subscription_info={"endpoint": item.endpoint, "keys": {"p256dh": item.p256dh, "auth": item.auth}},
                    data=payload,
                    vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.WEBPUSH_VAPID_SUBJECT},
                    requests_session=session,
                    timeout=5,
                    ttl=600,
                )
            except Exception as exc:
                response = getattr(exc, "response", None)
                status = getattr(response, "status_code", getattr(exc, "status_code", None))
                if status in (404, 410):
                    PushSubscription.objects.filter(pk=item.pk, user=user).delete()
                    counts["removed"] += 1
                else:
                    PushSubscription.objects.filter(pk=item.pk, user=user).update(failed_count=F("failed_count") + 1)
                    counts["failed"] += 1
                    logger.warning("web_push_failed subscription_id=%s error_type=%s", item.pk, type(exc).__name__)
                continue
            PushSubscription.objects.filter(pk=item.pk, user=user).update(last_success_at=timezone.now(), failed_count=0)
            counts["sent"] += 1
    return counts
