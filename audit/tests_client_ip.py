"""การอ่าน IP ผู้ใช้ที่ปลอมไม่ได้ (audit log + throttle คำขอที่พักสาธารณะ) — ตรวจบัค 30 ก.ย. 2569"""
from datetime import date, timedelta

import pytest
from django.test import RequestFactory, override_settings
from django.urls import reverse

from accounts.models import Unit, User
from audit.context import request_ip
from audit.models import AuditLog
from bookings.lodging_models import PublicLodgingThrottle
from config.security import client_ip_configuration_warning
from resources.models import Resource

rf = RequestFactory()
FORGED_CHAIN = "6.6.6.6, 203.0.113.9, 35.191.0.1"  # ค่าแรกผู้ใช้ใส่เอง · ถัดมา proxy เติม


def _req(xff=None, **extra):
    meta = {"REMOTE_ADDR": "169.254.1.1", **extra}
    if xff is not None:
        meta["HTTP_X_FORWARDED_FOR"] = xff
    return rf.get("/", **meta)


@override_settings(CLIENT_IP_HEADER="", TRUSTED_PROXY_HOPS=None)
def test_unconfigured_keeps_legacy_first_value():
    assert request_ip(_req(FORGED_CHAIN)) == "6.6.6.6"
    assert request_ip(_req()) == "169.254.1.1"


@override_settings(CLIENT_IP_HEADER="", TRUSTED_PROXY_HOPS=2)
def test_hops_counts_from_right_and_ignores_forged_prefix():
    assert request_ip(_req(FORGED_CHAIN)) == "203.0.113.9"
    assert request_ip(_req("203.0.113.9, 35.191.0.1")) == "203.0.113.9"


@override_settings(CLIENT_IP_HEADER="", TRUSTED_PROXY_HOPS=2)
def test_hops_with_short_chain_falls_back_to_remote_addr():
    assert request_ip(_req("203.0.113.9")) == "169.254.1.1"


@override_settings(CLIENT_IP_HEADER="", TRUSTED_PROXY_HOPS=0)
def test_zero_hops_ignores_forwarded_header():
    assert request_ip(_req(FORGED_CHAIN)) == "169.254.1.1"


@override_settings(CLIENT_IP_HEADER="X-Platform-Client-Ip", TRUSTED_PROXY_HOPS=None)
def test_platform_header_takes_precedence():
    assert request_ip(_req(FORGED_CHAIN, HTTP_X_PLATFORM_CLIENT_IP="198.51.100.7")) == "198.51.100.7"
    assert request_ip(_req(FORGED_CHAIN)) == "6.6.6.6"  # header หาย → ใช้กติกา hops (ยังไม่ตั้ง = แบบเดิม)


def test_configuration_warning_only_for_unconfigured_production():
    assert client_ip_configuration_warning(False, "", None)
    assert client_ip_configuration_warning(True, "", None) == ""
    assert client_ip_configuration_warning(False, "X-Real-Ip", None) == ""
    assert client_ip_configuration_warning(False, "", 0) == ""


@pytest.mark.django_db
@override_settings(CLIENT_IP_HEADER="", TRUSTED_PROXY_HOPS=2)
def test_failed_login_audit_records_trusted_ip(client):
    client.post(reverse("login"), {"username": "nobody", "password": "x"}, HTTP_X_FORWARDED_FOR=FORGED_CHAIN)
    entry = AuditLog.objects.filter(action="login_failed").latest("pk")
    assert entry.ip == "203.0.113.9"


@pytest.fixture
def lodging_room():
    Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")
    return Resource.objects.create(
        code="DORM-401", name="ห้องพัก 401", capacity=2, room_category=Resource.Category.LODGING
    )


def _post_request(client, room, phone, xff):
    check_in = date.today() + timedelta(days=10)
    return client.post(
        reverse("bookings:lodging_general_request"),
        {
            "room": room.pk, "check_in": check_in.isoformat(), "check_out": (check_in + timedelta(days=1)).isoformat(),
            "guest_name": "นายทดสอบ", "phone": phone, "note": "",
        },
        HTTP_X_FORWARDED_FOR=xff,
    )


@pytest.mark.django_db
@override_settings(CLIENT_IP_HEADER="", TRUSTED_PROXY_HOPS=2, PUBLIC_LODGING_RATE_CLIENT_LIMIT=2)
def test_public_lodging_client_limit_keys_on_trusted_ip_not_cookie(client, lodging_room):
    for index in range(3):
        client.cookies.clear()  # ผู้ยิงทิ้ง cookie ทุกครั้ง + เปลี่ยนเบอร์ + ปลอมค่าแรกของ XFF
        _post_request(client, lodging_room, f"08100000{index:02d}", f"10.0.0.{index}, 203.0.113.9, 35.191.0.1")
    rows = PublicLodgingThrottle.objects.filter(scope=PublicLodgingThrottle.Scope.CLIENT)
    assert rows.count() == 1
    assert rows.get().count == 2  # ครั้งที่ 3 ถูกปฏิเสธ


@pytest.mark.django_db
def test_client_ip_page_superuser_only(client):
    unit = Unit.objects.create(code="HQ", name="กองบังคับการ")
    user = User.objects.create_user(username="u1", email="u1@signalschool.ac.th", password="Password-2569", unit=unit)
    admin = User.objects.create_superuser(username="a1", email="a1@signalschool.ac.th", password="Password-2569")
    url = reverse("client_ip_diagnostics")
    client.force_login(user)
    assert client.get(url).status_code == 403
    client.force_login(admin)
    response = client.get(url, HTTP_X_FORWARDED_FOR=FORGED_CHAIN)
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    assert [row["hops"] for row in response.context["chain_rows"]] == [3, 2, 1]
