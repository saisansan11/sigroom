from datetime import datetime, time, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking, Preemption
from bookings.services import booking_pass_context
from resources.models import Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def pass_data(settings):
    settings.PUBLIC_BASE_URL = "https://sigroom.example.test/"
    unit = Unit.objects.create(code="PASS", name="หน่วยบัตร")
    other_unit = Unit.objects.create(code="PASS-OTHER", name="หน่วยอื่น")
    users = {}
    for name in ("owner", "peer", "stranger", "staff", "approver", "infosec", "admin"):
        users[name] = User.objects.create_user(
            username=f"pass-{name}", email=f"pass-{name}@signalschool.ac.th",
            first_name=f"ผู้ทดสอบ {name}", unit=other_unit if name in {"stranger", "staff", "approver"} else unit,
            is_superuser=name == "admin", is_infosec_officer=name == "infosec",
        )
    room = Resource.objects.create(code="PASS-M", name="ห้องประชุมบัตร", resource_type=Resource.Type.ROOM,
                                   room_category=Resource.Category.MEETING, building="อาคารเรียน", floor="3")
    room.custodians.add(users["staff"])
    ResourceApprover.objects.create(resource=room, user=users["approver"], is_primary=True)
    start = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=3), time(9)))
    booking = Booking.objects.create(
        room=room, requester=users["owner"], unit=unit, title="กิจกรรมส่วนตัว",
        responsible_name="ผู้รับผิดชอบส่วนตัว", responsible_phone="0811111111", attendees=5,
        start_at=start, end_at=start + timedelta(hours=1), request_status=Booking.RequestStatus.PENDING,
        online_meeting_url="https://meet.google.com/private-meeting",
    )
    return {"booking": booking, "room": room, **users}


@pytest.mark.parametrize("minutes,expected", [(-30, 0), (0, 0), (15, .25), (30, .5), (60, 1), (120, 1)])
def test_progress_uses_lesson_elapsed_time_and_clamps(pass_data, minutes, expected):
    booking = pass_data["booking"]
    context = booking_pass_context(booking, pass_data["owner"], booking.start_at + timedelta(minutes=minutes))
    assert context["progress"] == expected
    assert float(context["cassette"]["progress"]) == expected
    assert .3 <= float(context["cassette"]["left_reel_scale"]) <= 1
    assert .3 <= float(context["cassette"]["right_reel_scale"]) <= 1


def test_progress_copes_with_zero_length_unsaved_legacy_record(pass_data):
    booking = pass_data["booking"]
    booking.end_at = booking.start_at
    assert booking_pass_context(booking, pass_data["owner"], booking.start_at)["progress"] == 1


@pytest.mark.parametrize("actor,allowed,online", [("owner", True, True), ("peer", True, False), ("stranger", False, False), ("staff", True, True), ("approver", True, True), ("infosec", True, True), ("admin", True, True)])
@pytest.mark.parametrize("route", ["booking_pass", "booking_pass_qr_svg"])
def test_pass_and_qr_authorization_and_stricter_online_privacy(client, pass_data, actor, allowed, online, route):
    client.force_login(pass_data[actor])
    booking = pass_data["booking"]
    response = client.get(reverse(f"bookings:{route}", args=[booking.pk]))
    assert response.status_code == (200 if allowed else 403)
    if allowed:
        assert "private" in response["Cache-Control"] and "no-store" in response["Cache-Control"]
        assert response["X-Robots-Tag"] == "noindex, nofollow"
        assert response["Referrer-Policy"] == "no-referrer"
        if route == "booking_pass":
            html = response.content.decode()
            assert (booking.online_meeting_url in html) is online
            assert "รออนุมัติ" in html and "ยังต้องรอผลพิจารณาก่อนใช้งาน" in html
    else:
        html = response.content.decode()
        for private in (booking.title, booking.responsible_name, booking.responsible_phone, booking.online_meeting_url):
            assert private not in html


@pytest.mark.parametrize("route", ["booking_pass", "booking_pass_qr_svg"])
def test_guest_requires_login_and_post_cannot_read_pass(client, pass_data, route):
    path = reverse(f"bookings:{route}", args=[pass_data["booking"].pk])
    response = client.get(path)
    assert response.status_code == 302 and reverse("login") in response.url
    client.force_login(pass_data["owner"])
    assert client.post(path).status_code == 405
    with pytest.raises(PermissionDenied):
        booking_pass_context(pass_data["booking"], AnonymousUser())


@pytest.mark.parametrize("actor,allowed", [("owner", True), ("peer", False), ("staff", False), ("infosec", True), ("admin", True)])
def test_sensitive_pass_keeps_detail_permission_boundary(client, pass_data, actor, allowed):
    booking = pass_data["booking"]
    booking.visibility = Booking.Visibility.SENSITIVE
    booking.save(update_fields=["visibility"])
    client.force_login(pass_data[actor])
    assert client.get(reverse("bookings:booking_pass", args=[booking.pk])).status_code == (200 if allowed else 403)


def test_qr_contains_only_canonical_detail_url_not_host_headers_or_pii(client, pass_data, settings):
    booking = pass_data["booking"]
    expected = "https://sigroom.example.test" + reverse("bookings:booking_detail", args=[booking.pk])
    context = booking_pass_context(booking, pass_data["owner"])
    assert context["qr_url"] == expected
    assert "?" not in context["qr_url"]
    settings.USE_X_FORWARDED_HOST = True
    client.force_login(pass_data["owner"])
    assert client.get(reverse("bookings:booking_pass_qr_svg", args=[booking.pk]), HTTP_X_FORWARDED_HOST="evil.example").status_code == 400
    with patch("bookings.lodging_services.generate_cohort_qr_svg", return_value=b"<svg />") as qr:
        response = client.get(reverse("bookings:booking_pass_qr_svg", args=[booking.pk]), HTTP_X_FORWARDED_HOST="testserver", HTTP_X_FORWARDED_PROTO="http")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/svg+xml"
    qr.assert_called_once_with(expected)
    for private in (booking.title, booking.requester.display_name, booking.responsible_phone, booking.online_meeting_url):
        assert private not in qr.call_args.args[0]


@pytest.mark.parametrize("base", ["", "https://user:secret@example.test", "https://@example.test", "https://example.test/path", "https://example.test?q=secret", "https://example.test#part", "javascript:alert(1)", "https://example.test:wrong", "https://bad host.test", "https://example.test\\evil"])
def test_missing_or_unsafe_origin_keeps_card_readable_without_inventing_qr(client, pass_data, settings, base):
    settings.PUBLIC_BASE_URL = base
    booking = pass_data["booking"]
    context = booking_pass_context(booking, pass_data["owner"])
    assert context["qr_url"] == "" and context["cassette"]["qr_image_url"] == ""
    client.force_login(pass_data["owner"])
    response = client.get(reverse("bookings:booking_pass", args=[booking.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "QR ยังไม่พร้อมใช้งาน" in html and booking.title in html
    assert reverse("bookings:booking_ics", args=[booking.pk]) in html
    assert client.get(reverse("bookings:booking_pass_qr_svg", args=[booking.pk])).status_code == 503


@pytest.mark.parametrize("category,service", [("online", "online"), ("classroom", "classroom"), ("meeting", "meeting"), ("special", "meeting"), ("lodging", "lodging")])
def test_shared_card_and_actions_stay_in_actual_service(client, pass_data, category, service):
    booking = pass_data["booking"]
    booking.room.room_category = category
    booking.room.save(update_fields=["room_category"])
    client.force_login(pass_data["owner"])
    response = client.get(reverse("bookings:booking_pass", args=[booking.pk]), {"service": "untrusted"})
    assert response.status_code == 200 and response.context["nav_service"] == service
    assert "partials/cassette_pass.html" in [template.name for template in response.templates]
    html = response.content.decode()
    assert html.count('id="keycard"') == 1 and html.count('id="cassetteQrDialog"') == 1
    assert 'data-progress="0.000000"' in html
    assert f'data-service="{service}"' in html
    assert 'href="' + reverse("bookings:my_bookings") + f'?service={service}"' in html
    assert "รายงานตัว" not in html and "เช็กอิน" not in html
    ledger = html.split('class="cassette-ledger"', 1)[1]
    for essential in (booking.title, booking.room.name, booking.requester.display_name, "เริ่ม", "สิ้นสุด", "สถานะ", "รออนุมัติ", str(booking.pk)[:8]):
        assert essential in ledger
    actions = response.context["cassette"]["actions"]
    rebook = next(action["url"] for action in actions if action["label"] == "จองอีกครั้ง")
    if service == "online":
        assert rebook == reverse("bookings:online_teaching_home")
    elif service == "lodging":
        assert rebook == reverse("bookings:lodging_start")
    else:
        assert rebook == reverse("bookings:book_form", args=[booking.room.code]) + f"?rebook={booking.pk}"


def test_detail_and_my_bookings_have_pass_links(client, pass_data):
    booking = pass_data["booking"]
    client.force_login(pass_data["owner"])
    url = reverse("bookings:booking_pass", args=[booking.pk])
    for path in (reverse("bookings:booking_detail", args=[booking.pk]), reverse("bookings:my_bookings") + "?service=meeting"):
        html = client.get(path).content.decode()
        assert f'href="{url}"' in html and "ดูบัตรจอง" in html


@pytest.mark.parametrize("category,policy,status", [("classroom", "auto", "approved"), ("meeting", "required", "pending")])
def test_generic_submission_redirects_to_pass_and_preserves_approval_status(client, pass_data, category, policy, status):
    room = pass_data["room"]
    room.room_category = category
    room.save(update_fields=["room_category"])
    ResourceRule.objects.create(resource=room, approval_policy=policy)
    day = timezone.localdate(pass_data["booking"].start_at) + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    client.force_login(pass_data["owner"])
    response = client.post(reverse("bookings:book_form", args=[room.code]), {
        "date": day.isoformat(), "start_time": "09:00", "end_time": "10:00", "title": "กิจกรรมใหม่",
        "purpose": "meeting", "unit": str(pass_data["owner"].unit_id), "responsible_name": "ผู้รับผิดชอบ",
        "responsible_phone": "0811111111", "attendees": "5", "has_external_attendees": "False",
        "visibility": "normal", "action": "submit",
    })
    assert response.status_code == 302
    booking = Booking.objects.get(title="กิจกรรมใหม่")
    assert booking.request_status == status
    assert response.url == reverse("bookings:booking_pass", args=[booking.pk])
    assert booking.holds.filter(released_at__isnull=True).exists()


@pytest.mark.parametrize("route", ["booking_pass", "booking_pass_qr_svg"])
def test_displaced_requester_cannot_open_incoming_pass_even_in_same_unit(client, pass_data, route):
    incoming = pass_data["booking"]
    displaced = Booking.objects.create(
        room=pass_data["room"], requester=pass_data["peer"], unit=incoming.unit,
        title="ถูกย้าย", responsible_name="ผู้ถูกย้าย", responsible_phone="081",
        start_at=incoming.start_at, end_at=incoming.end_at,
    )
    Preemption.objects.create(displaced=displaced, incoming=incoming, ordered_by=pass_data["admin"],
                              ordered_by_position="ผู้สั่ง", reference_no="PASS-ORDER", reason="ทดสอบสิทธิ์")
    client.force_login(pass_data["peer"])
    response = client.get(reverse(f"bookings:{route}", args=[incoming.pk]))
    assert response.status_code == 403
    assert incoming.title not in response.content.decode()


def test_sensitive_approver_detail_does_not_offer_pass_outside_detail_permission(client, pass_data):
    booking = pass_data["booking"]
    booking.visibility = Booking.Visibility.SENSITIVE
    booking.save(update_fields=["visibility"])
    client.force_login(pass_data["approver"])
    response = client.get(reverse("bookings:booking_detail", args=[booking.pk]))
    assert response.status_code == 200
    assert booking.title in response.content.decode()  # สิทธิ์พิจารณาใน detail เดิมยังอยู่
    assert f'href="{reverse("bookings:booking_pass", args=[booking.pk])}"' not in response.content.decode()
    assert client.get(reverse("bookings:booking_pass", args=[booking.pk])).status_code == 403


@pytest.mark.parametrize("visibility", [Booking.Visibility.NORMAL, Booking.Visibility.SENSITIVE])
def test_delegate_keeps_original_detail_access_without_expanding_pass_rights(client, pass_data, visibility):
    from approvals.models import ApproverDelegation

    booking = pass_data["booking"]
    booking.visibility = visibility
    booking.save(update_fields=["visibility"])
    today = timezone.localdate()
    ApproverDelegation.objects.create(delegator=pass_data["approver"], delegate=pass_data["stranger"], start_date=today, end_date=today)
    client.force_login(pass_data["stranger"])
    response = client.get(reverse("bookings:booking_detail", args=[booking.pk]))
    assert response.status_code == 200 and booking.title in response.content.decode()
    assert "ดูบัตรจอง" not in response.content.decode()
    assert booking.online_meeting_url not in response.content.decode()
    assert client.get(reverse("bookings:booking_pass", args=[booking.pk])).status_code == 403
    assert client.get(reverse("bookings:booking_pass_qr_svg", args=[booking.pk])).status_code == 403
