import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.exceptions import ValidationError
from django.test import Client, override_settings
from django.urls import reverse

from accounts.models import User
from notifications.models import PushSubscription
from notifications.push import MAX_SUBSCRIPTIONS, send_push, subscribe, validate_endpoint, validate_internal_url

pytestmark = pytest.mark.django_db

VAPID_SETTINGS = {
    "WEBPUSH_VAPID_PUBLIC_KEY": "public-test-key",
    "WEBPUSH_VAPID_PRIVATE_KEY": "private-test-key",
    "WEBPUSH_VAPID_SUBJECT": "mailto:push-admin@example.test",
}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _browser_keys():
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return {"p256dh": _b64(public), "auth": _b64(b"0123456789abcdef")}


def _subscription(number=1, host="fcm.googleapis.com"):
    return {
        "endpoint": f"https://{host}/fcm/send/push-test-{number}",
        "keys": _browser_keys(),
    }


@pytest.fixture
def push_user():
    return User.objects.create_user(username="push-user", email="push-user@example.test", password="test-password-1234")


@pytest.mark.parametrize("path_name", ["notifications:push_status", "push_service_worker"])
@override_settings(WEBPUSH_VAPID_PUBLIC_KEY="", WEBPUSH_VAPID_PRIVATE_KEY="", WEBPUSH_VAPID_SUBJECT="")
def test_push_surface_is_404_when_vapid_disabled(client, path_name):
    assert client.get(reverse(path_name)).status_code == 404


@override_settings(**VAPID_SETTINGS)
def test_status_requires_login_and_never_caches(client):
    url = reverse("notifications:push_status")
    assert client.get(url).status_code == 302
    user = User.objects.create_user(username="push-status-user", email="push-status@example.test")
    PushSubscription.objects.create(user=user, endpoint=_subscription(1)["endpoint"], **_browser_keys())
    client.force_login(user)
    response = client.get(url)
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert response.json()["endpoints"] == [_subscription(1)["endpoint"]]


@override_settings(**VAPID_SETTINGS)
def test_subscribe_requires_csrf_for_authenticated_user(push_user):
    client = Client(enforce_csrf_checks=True)
    client.force_login(push_user)
    response = client.post(
        reverse("notifications:push_subscribe"),
        data=json.dumps(_subscription(1)),
        content_type="application/json",
    )
    assert response.status_code == 403
    assert not PushSubscription.objects.exists()


@override_settings(**VAPID_SETTINGS)
def test_subscribe_refreshes_same_owner_but_never_transfers_endpoint(client, push_user):
    payload = _subscription(2)
    client.force_login(push_user)
    response = client.post(reverse("notifications:push_subscribe"), data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    item = PushSubscription.objects.get()
    assert item.user == push_user
    assert item.endpoint == payload["endpoint"]

    refreshed = _subscription(2)
    response = client.post(reverse("notifications:push_subscribe"), data=json.dumps(refreshed), content_type="application/json")
    assert response.status_code == 200
    assert PushSubscription.objects.count() == 1

    outsider = User.objects.create_user(username="push-outsider", email="push-outsider@example.test")
    client.force_login(outsider)
    response = client.post(reverse("notifications:push_subscribe"), data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 409
    response = client.post(
        reverse("notifications:push_unsubscribe"),
        data=json.dumps({"endpoint": payload["endpoint"]}),
        content_type="application/json",
    )
    assert response.status_code == 409
    item.refresh_from_db()
    assert item.user == push_user


@override_settings(**VAPID_SETTINGS)
def test_subscription_limit_is_per_user(push_user):
    for number in range(MAX_SUBSCRIPTIONS):
        subscribe(push_user, _subscription(number), "browser")
    with pytest.raises(ValidationError, match="ไม่เกิน 10 เครื่อง"):
        subscribe(push_user, _subscription(MAX_SUBSCRIPTIONS), "browser")
    assert PushSubscription.objects.filter(user=push_user).count() == MAX_SUBSCRIPTIONS


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/a",
        "https://evil.example/push",
        "https://user@fcm.googleapis.com/fcm/send/a",
        "https://fcm.googleapis.com:444/fcm/send/a",
        "https://fcm.googleapis.com/fcm/send/a#fragment",
        "https://fcm.googleapis.com\\@evil.example/a",
    ],
)
def test_endpoint_validation_rejects_ssrf_shapes(endpoint):
    with pytest.raises(ValidationError):
        validate_endpoint(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/a",
        "https://updates.push.services.mozilla.com/wpush/v2/a",
        "https://web.push.apple.com/QPush/a",
        "https://wns2-bl2p.notify.windows.com/w/?token=a",
    ],
)
def test_endpoint_validation_accepts_known_browser_push_hosts(endpoint):
    assert validate_endpoint(endpoint) == endpoint


def test_invalid_browser_keys_are_rejected_before_database_write(push_user):
    payload = _subscription(3)
    payload["keys"]["p256dh"] = "not-a-real-key"
    with pytest.raises(ValidationError):
        subscribe(push_user, payload)
    assert not PushSubscription.objects.exists()


@pytest.mark.parametrize("url", ["https://evil.example/a", "//evil.example/a", "/bookings/1/?token=secret", "/x#fragment", "/%2f%2fevil.example/a"])
def test_push_payload_url_must_be_clean_internal_path(url):
    with pytest.raises(ValidationError):
        validate_internal_url(url)


@override_settings(**VAPID_SETTINGS)
def test_send_push_success_updates_subscription_and_uses_safe_payload(push_user, monkeypatch):
    payload = _subscription(4)
    item = PushSubscription.objects.create(user=push_user, endpoint=payload["endpoint"], **payload["keys"])
    calls = []

    def fake_webpush(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("notifications.push.webpush", fake_webpush)
    counts = send_push(push_user, "SIGROOM", "ถึงเวลาสอนแล้ว", "/bookings/example/pass/")
    assert counts == {"sent": 1, "removed": 0, "failed": 0}
    item.refresh_from_db()
    assert item.last_success_at is not None
    assert item.failed_count == 0
    sent = json.loads(calls[0]["data"])
    assert sent == {"title": "SIGROOM", "body": "ถึงเวลาสอนแล้ว", "url": "/bookings/example/pass/"}
    assert calls[0]["requests_session"] is not None
    assert calls[0]["timeout"] == 5
    assert calls[0]["ttl"] == 600


class _PushFailure(Exception):
    def __init__(self, status_code):
        self.response = type("Response", (), {"status_code": status_code})()
        super().__init__("sensitive endpoint must not be logged")


@override_settings(**VAPID_SETTINGS)
def test_send_push_removes_expired_subscription(push_user, monkeypatch):
    payload = _subscription(5)
    PushSubscription.objects.create(user=push_user, endpoint=payload["endpoint"], **payload["keys"])
    monkeypatch.setattr("notifications.push.webpush", lambda **kwargs: (_ for _ in ()).throw(_PushFailure(410)))
    assert send_push(push_user, "SIGROOM", "แจ้งเตือน", "/notifications/") == {"sent": 0, "removed": 1, "failed": 0}
    assert not PushSubscription.objects.exists()


@override_settings(**VAPID_SETTINGS)
def test_send_push_failure_isolated_per_device_and_does_not_log_secret(push_user, monkeypatch, caplog):
    first = _subscription(6)
    second = _subscription(7)
    PushSubscription.objects.create(user=push_user, endpoint=first["endpoint"], **first["keys"])
    PushSubscription.objects.create(user=push_user, endpoint=second["endpoint"], **second["keys"])

    def fake_webpush(**kwargs):
        if kwargs["subscription_info"]["endpoint"] == first["endpoint"]:
            raise _PushFailure(500)

    monkeypatch.setattr("notifications.push.webpush", fake_webpush)
    counts = send_push(push_user, "SIGROOM", "แจ้งเตือน", "/notifications/")
    assert counts == {"sent": 1, "removed": 0, "failed": 1}
    failed = PushSubscription.objects.get(endpoint=first["endpoint"])
    success = PushSubscription.objects.get(endpoint=second["endpoint"])
    assert failed.failed_count == 1
    assert success.failed_count == 0 and success.last_success_at is not None
    assert "web_push_failed" in caplog.text
    assert "sensitive endpoint" not in caplog.text
    assert first["endpoint"] not in caplog.text


@override_settings(**VAPID_SETTINGS)
def test_service_worker_has_root_scope_and_no_store_of_pages(client):
    response = client.get(reverse("push_service_worker"))
    assert response.status_code == 200
    assert response["Service-Worker-Allowed"] == "/"
    assert response["Cache-Control"] == "no-cache"
    text = response.content.decode()
    assert "showNotification" in text
    assert "caches.open" not in text
    assert "fetch(" not in text
