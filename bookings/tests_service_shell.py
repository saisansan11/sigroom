"""PR-2: เมนูตามบริการ ลิงก์ต่อเนื่อง และรายการส่วนตัวไม่ปนหมวด."""
from datetime import datetime, time, timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import resolve, reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking, BookingAmendment, BookingSeries, Preemption
from bookings.role_home import current_service
from bookings.services import submit_booking
from bookings.urls import urlpatterns
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def shell_data():
    unit = Unit.objects.create(code="SHELL", name="หน่วยทดสอบเมนู")
    user = User.objects.create_user(username="shell", email="shell@signalschool.ac.th", unit=unit, phone="0811111111")
    user.groups.add(Group.objects.get_or_create(name="signalschool-teacher")[0])
    day = timezone.localdate() + timedelta(days=3)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    start = timezone.make_aware(datetime.combine(day, time(9)))
    rooms, bookings, series = {}, {}, {}
    for category in ("lodging", "online", "classroom", "meeting", "special", "lab"):
        room = Resource.objects.create(code=f"SHELL-{category}", name=f"ห้องทดสอบ {category}", room_category=category)
        ResourceRule.objects.create(resource=room, approval_policy=ResourceRule.ApprovalPolicy.AUTO)
        rooms[category] = room
        bookings[category] = Booking.objects.create(
            room=room, requester=user, unit=unit, title=f"งาน {category}",
            responsible_name="ผู้ทดสอบ", responsible_phone=user.phone,
            start_at=start, end_at=start + timedelta(hours=1), request_status=Booking.RequestStatus.APPROVED,
        )
        series[category] = BookingSeries.objects.create(
            room=room, created_by=user, unit=unit, freq="weekly", weekdays=[day.weekday()],
            start_date=day, requested_count=2, time_start=time(9), time_end=time(10),
        )
        Booking.objects.create(
            room=room, requester=user, unit=unit, title=f"ชุดการจอง {category}",
            responsible_name="ผู้ทดสอบ", responsible_phone=user.phone,
            start_at=start + timedelta(days=1), end_at=start + timedelta(days=1, hours=1),
            request_status=Booking.RequestStatus.APPROVED, series=series[category], series_index=1,
        )
    amendment = BookingAmendment.objects.create(booking=bookings["classroom"], submitted_by=user, base_revision=1)
    preemption = Preemption.objects.create(displaced=bookings["classroom"], incoming=bookings["meeting"], ordered_by=user)
    return {"user": user, "rooms": rooms, "bookings": bookings, "series": series, "day": day, "amendment": amendment, "preemption": preemption}


ROUTE_EXPECTATIONS = {
    "role_home": None, "calendar": None, "calendar_root": None, "about": None,
    "calendar_events": None, "book_search": None, "course_catalog_manage": None,
    "online_teaching_home": "online", "online_teaching_quick_book": "online",
    "online_teaching_profile": "online", "online_teaching_book": "online",
    "book_form": "classroom", "room_favorite_toggle": "classroom",
    "series_preview": "classroom", "series_create": "classroom",
    "series_detail": "classroom", "series_cancel_remaining": "classroom", "my_bookings": None,
    "booking_detail": "classroom", "booking_ics": "classroom", "booking_edit": "classroom",
    "booking_pass": "classroom", "booking_pass_qr_svg": "classroom",
    "booking_amend": "classroom", "booking_preempt": "classroom", "booking_cancel": "classroom",
    "booking_submit": "classroom", "booking_delete_draft": "classroom",
    "amendment_withdraw": "classroom", "preemption_acknowledge": "classroom",
    "lodging_start": "lodging", "lodging_index": "lodging", "lodging_room_detail": "lodging",
    "lodging_about": None, "service_staff_entry": "lodging", "lodging_manage": "lodging",
    "lodging_workspace": "lodging", "lodging_general_request": "lodging",
    "lodging_general_request_rooms": "lodging", "lodging_general_request_status": "lodging",
    "lodging_cohort_detail": "lodging", "lodging_cohort_edit": "lodging", "lodging_cohort_export_csv": "lodging",
    "lodging_cohort_qr_svg": "lodging", "lodging_portal": "lodging", "lodging_book_bed": "lodging",
    "lodging_reservation_manage": "lodging", "lodging_reservation_cancel": "lodging",
    "lodging_pass": "lodging", "lodging_checkin": "lodging", "lodging_checkin_qr_svg": "lodging",
}


@pytest.mark.parametrize("route_name", [route.name for route in urlpatterns])
def test_service_for_every_booking_url_name(route_name, shell_data):
    assert set(ROUTE_EXPECTATIONS) == {route.name for route in urlpatterns}
    route = next(route for route in urlpatterns if route.name == route_name)
    ident = shell_data["bookings"]["classroom"].pk
    if route_name in {"series_detail", "series_cancel_remaining"}:
        ident = shell_data["series"]["classroom"].pk
    elif route_name == "amendment_withdraw":
        ident = shell_data["amendment"].pk
    elif route_name == "preemption_acknowledge":
        ident = shell_data["preemption"].pk
    values = {"id": ident, "code": shell_data["rooms"]["classroom"].code, "number": 401, "service": "lodging", "slug": "shell", "token": uuid4(), "student_id": uuid4()}
    path = reverse(f"bookings:{route_name}", kwargs={key: values[key] for key in route.pattern.converters})
    request = RequestFactory().get(path, HTTP_X_SIGROOM_SERVICE="meeting")
    request.resolver_match = resolve(path)
    assert current_service(request) == ROUTE_EXPECTATIONS[route_name]


@pytest.mark.parametrize("route_name", ["book_search", "calendar", "calendar_events"])
@pytest.mark.parametrize("category,expected", [("classroom", "classroom"), ("meeting", "meeting"), ("online", "online"), ("lodging", "lodging"), ("lab", None), ("unknown", None), ("", None)])
def test_category_service_uses_resolved_route_and_query(route_name, category, expected):
    path = reverse(f"bookings:{route_name}")
    request = RequestFactory().get(path, {"category": category}, HTTP_X_SIGROOM_SERVICE="online")
    request.resolver_match = resolve(path)
    assert current_service(request) == (None if route_name == "book_search" and category not in {"classroom", "meeting"} else expected)


@pytest.mark.parametrize("name", ["login", "notifications:list", "approvals:queue", "usage:list", "reports:dashboard", "bookings:about", "bookings:lodging_about"])
def test_pages_outside_services_ignore_service_query_and_headers(name):
    path = reverse(name)
    request = RequestFactory().get(path, {"category": "meeting", "service": "online"}, HTTP_X_SIGROOM_SERVICE="lodging")
    request.resolver_match = resolve(path)
    assert current_service(request) is None


@pytest.mark.parametrize("service,category", [("online", "online"), ("lodging", "lodging"), ("classroom", "classroom"), ("meeting", "special")])
def test_object_routes_use_actual_room_even_with_conflicting_query(shell_data, service, category):
    for name, ident in (("book_form", shell_data["rooms"][category].code), ("booking_detail", shell_data["bookings"][category].pk), ("booking_edit", shell_data["bookings"][category].pk), ("series_detail", shell_data["series"][category].pk)):
        path = reverse(f"bookings:{name}", args=[ident])
        request = RequestFactory().get(path, {"category": "classroom", "service": "classroom"})
        request.resolver_match = resolve(path)
        assert current_service(request) == service


@pytest.mark.parametrize("service,expected", [("lodging", "lodging"), ("online", "online"), ("learning", None), ("unknown", None)])
def test_staff_routes_keep_combined_learning_operations_outside_booking_services(service, expected):
    path = reverse("bookings:service_staff_entry", args=[service])
    request = RequestFactory().get(path)
    request.resolver_match = resolve(path)
    assert current_service(request) == expected


@pytest.mark.parametrize("service", ["online", "lodging", "classroom", "meeting"])
@pytest.mark.parametrize("tab", ["upcoming", "drafts", "past", "closed"])
def test_my_bookings_filters_every_status_and_series_and_preserves_tabs(client, shell_data, service, tab):
    client.force_login(shell_data["user"])
    category = service
    booking = shell_data["bookings"][category]
    if tab == "drafts":
        booking.request_status = Booking.RequestStatus.DRAFT
    elif tab == "closed":
        booking.request_status = Booking.RequestStatus.CANCELLED
    elif tab == "past":
        booking.start_at = timezone.now() - timedelta(days=2)
        booking.end_at = booking.start_at + timedelta(hours=1)
    booking.save()
    response = client.get(reverse("bookings:my_bookings"), {"service": service, "tab": tab})
    assert response.status_code == 200
    expected_categories = {"meeting", "special"} if service == "meeting" else {service}
    assert booking in response.context["bookings"]
    assert {item.room.room_category for item in response.context["bookings"]} <= expected_categories
    assert {item.room.room_category for item in response.context["series_items"]} == expected_categories
    html = response.content.decode()
    for other_tab in ("upcoming", "drafts", "past", "closed"):
        assert f'?tab={other_tab}&amp;service={service}' in html
    new_url = reverse("bookings:online_teaching_home") if service == "online" else reverse("bookings:lodging_start") if service == "lodging" else reverse("bookings:book_search") + f"?category={service}"
    assert f'href="{new_url}"' in html


@pytest.mark.parametrize("service", ["", "unknown"])
def test_my_bookings_without_valid_service_keeps_all_categories(client, shell_data, service):
    client.force_login(shell_data["user"])
    response = client.get(reverse("bookings:my_bookings"), {"service": service})
    assert {item.room.room_category for item in response.context["bookings"]} == set(shell_data["rooms"])
    assert len(response.context["series_items"]) == len(shell_data["rooms"])
    assert response.context["nav_service"] is None


def test_filtered_list_does_not_expose_other_requester_or_series(client, shell_data):
    other = User.objects.create_user(username="shell-other", email="shell-other@signalschool.ac.th", unit=shell_data["user"].unit)
    booking = shell_data["bookings"]["classroom"]
    series = shell_data["series"]["classroom"]
    booking.requester = other
    booking.save(update_fields=["requester"])
    series.created_by = other
    series.save(update_fields=["created_by"])
    client.force_login(shell_data["user"])
    response = client.get(reverse("bookings:my_bookings"), {"service": "classroom"})
    assert not response.context["bookings"]
    assert not response.context["series_items"]


def test_detail_series_and_draft_delete_continue_in_same_service(client, shell_data):
    class BackLinkParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a" and "btn-my-bookings" in attrs.get("class", "").split():
                self.links.append(attrs.get("href"))

    client.force_login(shell_data["user"])
    # special อยู่ในบริการ meeting และไม่ใช่รายการ incoming ของกรณี preemption ใน fixture
    for route, item in (("booking_detail", shell_data["bookings"]["special"]), ("series_detail", shell_data["series"]["special"])):
        response = client.get(reverse(f"bookings:{route}", args=[item.pk]))
        assert response.status_code == 200
        assert response.context["nav_service"] == "meeting"
        parser = BackLinkParser()
        parser.feed(response.content.decode())
        assert parser.links == [reverse("bookings:my_bookings") + "?service=meeting"]
    draft = shell_data["bookings"]["special"]
    draft.request_status = Booking.RequestStatus.DRAFT
    draft.save(update_fields=["request_status"])
    response = client.post(reverse("bookings:booking_delete_draft", args=[draft.pk]))
    assert response.status_code == 302
    assert response.url == reverse("bookings:my_bookings") + "?service=meeting"


@pytest.mark.parametrize("service", ["online", "lodging", "classroom", "meeting"])
def test_desktop_and_mobile_navigation_only_link_current_service(client, shell_data, service):
    client.force_login(shell_data["user"])
    response = client.get(reverse("bookings:my_bookings"), {"service": service})
    header = response.content.decode().split('<header class="site-header">', 1)[1].split("</header>", 1)[0]
    assert header.count('‹ บริการทั้งหมด') == 2
    assert header.count(f'?service={service}') == (0 if service == "lodging" else 2)
    for other in {"online", "lodging", "classroom", "meeting"} - {service}:
        assert f'?service={other}' not in header
        assert f'?category={other}' not in header
    assert "งานปฏิบัติการ" not in header


def test_guest_lodging_nav_and_gateway_have_contextual_links(client):
    start_html = client.get(reverse("bookings:lodging_start")).content.decode()
    header = start_html.split('<header class="site-header">', 1)[1].split("</header>", 1)[0]
    assert header.count('‹ บริการทั้งหมด') == 2
    assert "ข้าราชการทหาร" in start_html and "บุคคลทั่วไป" not in start_html
    request_page = client.get(reverse("bookings:lodging_general_request"))
    assert request_page.status_code == 200
    assert "ข้าราชการทหาร" in request_page.content.decode()
    gateway_header = client.get(reverse("bookings:lodging_about")).content.decode().split('<header class="site-header">', 1)[1].split("</header>", 1)[0]
    assert '‹ บริการทั้งหมด' not in gateway_header
    assert '?category=' not in gateway_header


@pytest.mark.parametrize("category,label", [("classroom", "ห้องเรียน"), ("meeting", "ห้องประชุม")])
def test_search_locked_category_heading_form_results_and_followup_links(client, shell_data, category, label):
    client.force_login(shell_data["user"])
    params = {"category": category, "date": shell_data["day"].isoformat(), "start": "09:00", "end": "10:00"}
    response = client.get(reverse("bookings:book_search"), params)
    assert response.status_code == 200
    html = response.content.decode()
    assert f"<h1>จอง{label}</h1>" in html
    assert f'name="category" value="{category}"' in html
    assert 'type="radio" name="category"' not in html
    assert 'booking-path-switcher' not in html
    result_categories = {item.room.room_category for item in response.context["available"] + response.context["unavailable"]}
    assert result_categories == ({"meeting", "special"} if category == "meeting" else {"classroom"})
    assert parse_qs(response.context["query_string"])["category"] == [category]
    # สร้างการถือครองจริงเพื่อให้ได้คำแนะนำทั้งเลื่อนเวลาและเปลี่ยนวัน
    for room_category in result_categories:
        booking = shell_data["bookings"][room_category]
        booking.request_status = Booking.RequestStatus.DRAFT
        booking.save()
        submit_booking(booking)
    full = client.get(reverse("bookings:book_search"), params)
    assert full.context["suggestions"]
    assert {row["item"].kind for row in full.context["suggestions"]} == {"shift", "next_date"}
    for row in full.context["suggestions"]:
        assert parse_qs(urlsplit(row["url"]).query)["category"] == [category]
    partial = client.get(reverse("bookings:book_search"), params, HTTP_HX_REQUEST="true")
    assert f"ไม่มี{label}ว่างในช่วงนี้" in partial.content.decode()
    form = client.get(reverse("bookings:book_form", args=[shell_data["rooms"][category].code]), {"category": "meeting" if category == "classroom" else "classroom"})
    assert parse_qs(form.context["search_query"])["category"] == [category]
