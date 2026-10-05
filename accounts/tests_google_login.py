from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import pytest
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from accounts.social import safe_login_next
from audit.models import AuditLog
from bookings.lodging_models import CourseLodgingCohort, CourseStudentEnrollment, CourseStudentLodging
from bookings.lodging_services import assign_lodging_bed, can_access_lodging_management, require_student_cohort, release_lodging_reservation
from bookings.models import Booking
from bookings.services import submit_booking
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def google_settings(settings):
    settings.GOOGLE_LOGIN_ENABLED = True
    settings.PUBLIC_BASE_URL = "https://sigroom.example"
    settings.SESSION_COOKIE_SAMESITE = "Lax"
    settings.SOCIALACCOUNT_PROVIDERS = {"google": {
        "APP": {"client_id": "test-client", "secret": "test-only"},
        "SCOPE": ["openid", "email", "profile"],
        "AUTH_PARAMS": {"hd": "signalschool.ac.th", "prompt": "select_account"},
        "OAUTH_PKCE_ENABLED": True,
    }}


@pytest.fixture
def existing():
    return User.objects.create_user(username="registered", email="registered@signalschool.ac.th", password="Password-2569")


@pytest.fixture
def cohort():
    unit = Unit.objects.create(code="GOOGLE", name="กองการศึกษา")
    supervisor = User.objects.create_user(username="course-staff", email="course-staff@signalschool.ac.th", unit=unit)
    room = Resource.objects.create(code="G-DORM", name="ห้องพัก", resource_type="room", room_category="lodging", capacity=4)
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นสำหรับ Google", slug="google-class", supervisor=supervisor, unit=unit,
        check_in_date=today + timedelta(days=1), check_out_date=today + timedelta(days=3),
        allocation_status="allocated", is_active=True, beds_per_room=4,
    )
    cohort.rooms.add(room)
    return cohort


def claims(email="registered@signalschool.ac.th", **overrides):
    return {"sub": "google-uid-123", "email": email, "email_verified": True,
            "hd": "signalschool.ac.th", "name": "นักเรียน ทดสอบ", **overrides}


def callback(client, data, next_url=""):
    start = client.post(reverse("google_login"), {"next": next_url})
    assert start.status_code == 302
    state = parse_qs(urlsplit(start.url).query)["state"][0]
    with patch("allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token",
               return_value={"access_token": "discarded-test-token", "id_token": "test-signed-token"}), \
         patch("accounts.google_views._verify_and_decode", return_value=data) as verify:
        response = client.get(reverse("google_callback"), {"state": state, "code": "test-code"})
        verify.assert_called_once()
        assert verify.call_args.kwargs["verify_signature"] is True
    return response


def test_disabled_google_has_no_button_or_routes(client, settings):
    settings.GOOGLE_LOGIN_ENABLED = False
    assert "เข้าสู่ระบบด้วย Google" not in client.get(reverse("accounts:login")).content.decode()
    assert client.post(reverse("google_login")).status_code == 404
    assert client.get(reverse("google_login")).status_code == 404
    assert client.get(reverse("google_callback")).status_code == 404
    assert client.get(reverse("socialaccount_login_error")).status_code == 404


def test_google_start_is_post_csrf_and_canonical(client, google_settings, settings):
    settings.ALLOWED_HOSTS = ["testserver", "untrusted.example"]
    settings.USE_X_FORWARDED_HOST = True
    assert client.get(reverse("google_login")).status_code == 405
    assert Client(enforce_csrf_checks=True).post(reverse("google_login")).status_code == 403
    login = client.get(reverse("accounts:login"))
    html = login.content.decode()
    assert 'method="post" action="/auth/google/login/"' in html
    assert "csrfmiddlewaretoken" in html and "เข้าสู่ระบบด้วย Google" in html
    response = client.post(reverse("google_login") + "?process=connect&auth_params=hd%3Devil.example", {},
                           HTTP_HOST="untrusted.example", HTTP_X_FORWARDED_HOST="untrusted.example")
    query = parse_qs(urlsplit(response.url).query)
    assert urlsplit(response.url).netloc == "accounts.google.com"
    assert query["redirect_uri"] == ["https://sigroom.example/auth/google/login/callback/"]
    assert query["hd"] == ["signalschool.ac.th"]
    assert query["code_challenge_method"] == ["S256"]


def test_callback_rejects_absent_or_wrong_state_without_network(client, google_settings):
    with patch("allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token") as exchange:
        for state in ("", "forged-state"):
            response = client.get(reverse("google_callback"), {"state": state, "code": "forged-code"})
            assert response.status_code == 302 and response.url == reverse("accounts:login")
        exchange.assert_not_called()
    assert "_auth_user_id" not in client.session


def test_registered_account_logs_in_case_insensitively_and_keeps_audit(client, google_settings, existing):
    response = callback(client, claims("REGISTERED@SIGNALSCHOOL.AC.TH"))
    assert response.status_code == 302 and response.url == reverse("bookings:role_home")
    assert client.session["_auth_user_id"] == str(existing.pk)
    assert User.objects.count() == 1 and SocialAccount.objects.get().user == existing
    assert AuditLog.objects.filter(actor=existing, action="login").exists()
    entry = AuditLog.objects.get(action="login_google")
    assert "registered@" not in str(entry.after) and "google-uid-123" not in str(entry.after)
    assert SocialToken.objects.count() == 0 and SocialApp.objects.count() == 0


@pytest.mark.parametrize("overrides,reason", [
    ({"email_verified": False}, "unverified"), ({"email_verified": "true"}, "unverified"),
    ({"email_verified": 1}, "unverified"), ({"email": "person@gmail.com"}, "domain"),
    ({"hd": "evil.example"}, "hd"), ({"hd": None}, "hd"),
    ({"email": "missing@signalschool.ac.th"}, "not_registered"),
])
def test_bad_claims_do_not_create_users(client, google_settings, existing, overrides, reason):
    response = callback(client, claims(**overrides))
    assert response.status_code == 302 and response.url == reverse("accounts:login")
    assert User.objects.count() == 1 and SocialAccount.objects.count() == 0
    assert "_auth_user_id" not in client.session
    assert AuditLog.objects.get(action="login_google_rejected").after["reason"] == reason


def test_inactive_and_changed_uid_are_rejected(client, google_settings, existing):
    existing.is_active = False
    existing.save(update_fields=["is_active"])
    assert callback(client, claims()).url == reverse("accounts:login")
    assert AuditLog.objects.filter(action="login_google_rejected", after__reason="inactive").exists()
    existing.is_active = True
    existing.save(update_fields=["is_active"])
    SocialAccount.objects.create(user=existing, provider="google", uid="original-uid")
    assert callback(client, claims()).url == reverse("accounts:login")
    assert AuditLog.objects.filter(action="login_google_rejected", after__reason="uid_mismatch").exists()


def test_uid_cannot_move_between_email_accounts(client, google_settings, existing):
    other = User.objects.create_user(username="other", email="other@signalschool.ac.th")
    SocialAccount.objects.create(user=other, provider="google", uid="google-uid-123")
    assert callback(client, claims()).url == reverse("accounts:login")
    assert SocialAccount.objects.get().user == other
    assert "_auth_user_id" not in client.session


@pytest.mark.parametrize("target", ["https://evil.example/path", "//evil.example/path", r"/\evil.example/path"])
def test_next_cannot_redirect_outside_configured_origin(client, google_settings, existing, target):
    assert safe_login_next(target) == ""
    assert callback(client, claims(), target).url == reverse("bookings:role_home")


def test_only_google_routes_exist(client, google_settings):
    for path in ("/auth/signup/", "/auth/login/", "/auth/password/reset/", "/auth/google/login/token/", "/auth/connections/"):
        assert client.get(path).status_code == 404


def test_signed_token_failure_or_missing_id_token_prevents_login(client, google_settings, existing):
    response = client.post(reverse("google_login"))
    state = parse_qs(urlsplit(response.url).query)["state"][0]
    with patch("allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token",
               return_value={"access_token": "test", "id_token": "invalid"}), \
         patch("accounts.google_views._verify_and_decode", side_effect=OAuth2Error("invalid signature")):
        assert client.get(reverse("google_callback"), {"state": state, "code": "code"}).url == reverse("accounts:login")
    assert "_auth_user_id" not in client.session
    response = client.post(reverse("google_login"))
    state = parse_qs(urlsplit(response.url).query)["state"][0]
    with patch("allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token",
               return_value={"access_token": "test-no-id-token"}), \
         patch("accounts.google_views._verify_and_decode") as verify:
        assert client.get(reverse("google_callback"), {"state": state, "code": "code"}).url == reverse("accounts:login")
        verify.assert_not_called()
    assert "_auth_user_id" not in client.session


def test_oauth_state_is_consumed_once(client, google_settings, existing):
    start = client.post(reverse("google_login"))
    state = parse_qs(urlsplit(start.url).query)["state"][0]
    with patch("allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token",
               return_value={"access_token": "test", "id_token": "signed"}) as exchange, \
         patch("accounts.google_views._verify_and_decode", return_value=claims()):
        first = client.get(reverse("google_callback"), {"state": state, "code": "code"})
        assert first.status_code == 302
        client.get(reverse("google_callback"), {"state": state, "code": "code"})
        assert exchange.call_count == 1


def test_registered_google_keeps_initial_password_requirement(client, google_settings, existing):
    existing.must_change_password = True
    existing.save(update_fields=["must_change_password"])
    callback(client, claims())
    assert client.get(reverse("bookings:role_home")).url == reverse("accounts:first_password_change")


def enroll(cohort, user=None, email="new-student@signalschool.ac.th"):
    return CourseStudentEnrollment.objects.create(cohort=cohort, email=email, user=user,
        rank="นนส.", origin_unit="โรงเรียนทหารสื่อสาร", phone="0812345678")


def test_qr_google_creates_only_preloaded_student_and_returns_to_beds(client, google_settings, cohort):
    enrollment = enroll(cohort)
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    response = callback(client, claims(enrollment.email), target)
    assert response.status_code == 302 and response.url == target
    user = User.objects.get(email=enrollment.email)
    assert user.is_lodging_student and not user.is_staff and not user.is_superuser
    assert not user.has_usable_password() and not user.groups.exists() and not user.user_permissions.exists()
    assert user.get_full_name() == "นักเรียน ทดสอบ"
    enrollment.refresh_from_db()
    assert enrollment.user == user
    assert AuditLog.objects.filter(actor=user, action="google_student_created").exists()
    portal = client.get(target)
    assert portal.status_code == 200
    html = portal.content.decode()
    assert 'value="นักเรียน ทดสอบ"' in html and 'value="0812345678"' in html
    for path in ("/online/", "/approvals/", "/lodging/manage/", "/book/", "/admin/"):
        assert client.get(path).status_code == 403
    assert not can_access_lodging_management(user)


def test_qr_does_not_grant_membership_without_roster(client, google_settings, cohort):
    # โหมดรายชื่อเท่านั้น: ผู้จัดหลักสูตรปิด "login แล้วจองได้ทันที" ของรุ่นนี้
    CourseLodgingCohort.objects.filter(pk=cohort.pk).update(open_enrollment=False)
    before = User.objects.count()
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    assert callback(client, claims("new-student@signalschool.ac.th"), target).url == reverse("accounts:login")
    assert User.objects.count() == before


def test_rejected_qr_for_different_cohort_does_not_create_account(client, google_settings, cohort):
    enrollment = enroll(cohort)
    wrong_cohort = CourseLodgingCohort.objects.create(title="อีกรุ่น", slug="wrong-qr", supervisor=cohort.supervisor,
        check_in_date=cohort.check_in_date, check_out_date=cohort.check_out_date,
        allocation_status="allocated", is_active=True)
    before = User.objects.count()
    target = reverse("bookings:lodging_portal", args=[wrong_cohort.slug])
    assert callback(client, claims(enrollment.email), target).url == reverse("accounts:login")
    assert User.objects.count() == before


def test_student_beds_are_own_cohort_and_pass_requires_owner(client, google_settings, cohort):
    enrollment = enroll(cohort)
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    callback(client, claims(enrollment.email), target)
    user = User.objects.get(email=enrollment.email)
    other = CourseLodgingCohort.objects.create(title="อีกหลักสูตร", slug="other-google", supervisor=cohort.supervisor,
        unit=cohort.unit, check_in_date=cohort.check_in_date, check_out_date=cohort.check_out_date,
        allocation_status="allocated", is_active=True)
    assert client.get(reverse("bookings:lodging_portal", args=[other.slug])).status_code == 403
    with pytest.raises(PermissionDenied):
        require_student_cohort(user, other)
    room = cohort.rooms.get()
    response = client.post(reverse("bookings:lodging_book_bed", args=[cohort.slug]), {
        "room_id": room.pk, "bed_number": 1, "rank": enrollment.rank,
        "full_name": "forged name", "origin_unit": enrollment.origin_unit, "phone": enrollment.phone})
    assert response.status_code == 302
    student = CourseStudentLodging.objects.get(user=user)
    assert student.full_name == user.get_full_name()
    assert client.get(response.url).status_code == 200
    assert client.post(reverse("bookings:lodging_book_bed", args=[cohort.slug]), {
        "room_id": room.pk, "bed_number": 2, "rank": enrollment.rank,
        "origin_unit": enrollment.origin_unit, "phone": "0890000000"}).status_code == 302
    assert CourseStudentLodging.objects.filter(user=user).count() == 1
    client.logout()
    assert client.get(response.url).status_code == 403
    assert client.get(reverse("bookings:lodging_pass", args=[cohort.slug, student.pk])).status_code == 403
    with pytest.raises(PermissionDenied):
        release_lodging_reservation(student=student, outcome="cancelled", access_token=student.self_service_access.pk)


def test_direct_general_booking_service_rejects_student(cohort):
    user = User.objects.create_user(username="limited", email="limited@signalschool.ac.th", is_lodging_student=True)
    room = Resource.objects.create(code="G-CLASS", name="ห้องเรียน", resource_type="room", room_category="classroom")
    now = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    booking = Booking(requester=user, unit=cohort.unit, room=room, title="จองห้อง", start_at=now, end_at=now + timedelta(hours=1))
    with pytest.raises(ValidationError, match="บัญชีนักเรียน"):
        submit_booking(booking)
    assert not Booking.objects.filter(requester=user).exists()


def test_new_student_can_cancel_own_bed_and_cannot_cancel_others(client, google_settings, cohort):
    enrollment = enroll(cohort)
    callback(client, claims(enrollment.email), reverse("bookings:lodging_portal", args=[cohort.slug]))
    user = User.objects.get(email=enrollment.email)
    student = assign_lodging_bed(cohort=cohort, room_id=cohort.rooms.get().pk, bed_number=1,
        rank="นนส.", full_name=user.get_full_name(), origin_unit="โรงเรียน", phone=enrollment.phone, student_user=user)
    other = User.objects.create_user(username="other-student", email="other-student@signalschool.ac.th", is_lodging_student=True)
    with pytest.raises(PermissionDenied):
        release_lodging_reservation(student=student, outcome="cancelled", access_token=student.self_service_access.pk,
                                    self_service_user=other)
    token = student.self_service_access.pk
    cancel_url = reverse("bookings:lodging_reservation_cancel", args=[cohort.slug, token])
    assert client.post(cancel_url).status_code == 302
    assert not CourseStudentLodging.objects.filter(pk=student.pk).exists()


def test_lodging_login_gate_preserves_exact_qr_next(client, cohort):
    for name in ("lodging_index", "lodging_portal"):
        path = reverse("bookings:" + name, args=[cohort.slug] if name == "lodging_portal" else [])
        response = client.get(path)
        assert response.status_code == 302
        assert parse_qs(urlsplit(response.url).query)["next"] == [path]


def test_legacy_token_pass_remains_public(client, cohort):
    student = assign_lodging_bed(cohort=cohort, room_id=cohort.rooms.get().pk, bed_number=1,
        rank="นนส.", full_name="นักเรียนเดิม", origin_unit="โรงเรียน", phone="0899999999")
    assert student.user_id is None
    assert client.get(reverse("bookings:lodging_pass", args=[cohort.slug, student.pk])).status_code == 200
    assert client.get(reverse("bookings:lodging_reservation_manage", args=[cohort.slug, student.self_service_access.pk])).status_code == 200


def test_student_can_read_public_room_inspector_without_cohort_membership(client, cohort):
    room = Resource.objects.create(code="DORM-423", name="ห้องข้อมูลสาธารณะ", floor="4", capacity=2,
                                   resource_type="room", room_category="lodging")
    cohort.rooms.add(room)
    CourseStudentLodging.objects.create(cohort=cohort, room=room, bed_number=1,
        rank="นนส.", full_name="PRIVATE NAME", origin_unit="PRIVATE UNIT", phone="0899999999")
    user = User.objects.create_user(username="inspector-student", email="inspector-student@signalschool.ac.th",
                                    is_lodging_student=True)
    client.force_login(user)
    response = client.get(reverse("bookings:lodging_room_detail", args=[423]))
    assert response.status_code == 200
    assert response.json()["room"]["id"] == str(room.pk)
    assert "PRIVATE" not in response.content.decode() and "0899999999" not in response.content.decode()
    assert client.get(reverse("bookings:lodging_portal", args=[cohort.slug])).status_code == 403
    assert client.get(reverse("bookings:online_teaching_home")).status_code == 403


def test_legacy_user_insert_works_after_student_flag_migration():
    # The old application omits this new column during rolling deployment/rollback.
    legacy = User(username="legacy-writer", email="legacy-writer@signalschool.ac.th", password="!")
    fields = [field for field in User._meta.concrete_fields
              if not field.primary_key and field.name != "is_lodging_student"]
    columns = ", ".join(connection.ops.quote_name(field.column) for field in fields)
    values = [field.get_db_prep_save(field.value_from_object(legacy), connection) for field in fields]
    placeholders = ", ".join(["%s"] * len(fields))
    table = connection.ops.quote_name(User._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
    assert User.objects.get(username="legacy-writer").is_lodging_student is False


# ---------- login แล้วจองได้ทันที (open_enrollment) ----------

def test_open_cohort_lets_verified_school_account_log_in_and_book(client, google_settings, cohort):
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    response = callback(client, claims("walk-in@signalschool.ac.th"), target)
    assert response.url == target
    user = User.objects.get(email="walk-in@signalschool.ac.th")
    assert user.is_lodging_student and not user.is_staff and not user.is_superuser
    assert not user.has_usable_password() and not user.groups.exists()
    enrollment = CourseStudentEnrollment.objects.get(cohort=cohort, email=user.email)
    assert enrollment.user_id == user.pk and enrollment.is_active
    assert AuditLog.objects.filter(action="student_auto_enrolled", entity_id=str(enrollment.pk)).exists()
    assert client.get(target).status_code == 200
    for path in ("/online/", "/approvals/", "/lodging/manage/", "/book/", "/admin/"):
        assert client.get(path).status_code == 403


@pytest.mark.parametrize("override", [
    {"email_verified": False},
    {"hd": "gmail.com"},
    {"email": "outsider@gmail.com"},
])
def test_open_cohort_still_rejects_unverified_or_outside_accounts(client, google_settings, cohort, override):
    before = User.objects.count()
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    data = claims(**{"email": "walk-in@signalschool.ac.th", **override})
    assert callback(client, data, target).url == reverse("accounts:login")
    assert User.objects.count() == before and not CourseStudentEnrollment.objects.exists()


def test_open_cohort_does_not_enroll_without_cohort_link_or_when_closed(client, google_settings, cohort):
    before = User.objects.count()
    assert callback(client, claims("walk-in@signalschool.ac.th")).url == reverse("accounts:login")
    CourseLodgingCohort.objects.filter(pk=cohort.pk).update(is_active=False)
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    assert callback(client, claims("walk-in@signalschool.ac.th"), target).url == reverse("accounts:login")
    assert User.objects.count() == before and not CourseStudentEnrollment.objects.exists()


def test_open_cohort_never_reopens_a_disabled_roster_row(client, google_settings, cohort):
    CourseStudentEnrollment.objects.create(cohort=cohort, email="blocked@signalschool.ac.th", is_active=False)
    before = User.objects.count()
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    assert callback(client, claims("blocked@signalschool.ac.th"), target).url == reverse("accounts:login")
    assert User.objects.count() == before
    assert not CourseStudentEnrollment.objects.get(email="blocked@signalschool.ac.th").is_active


def test_open_cohort_stops_at_bed_capacity_and_one_cohort_per_period(client, google_settings, cohort):
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    for index in range(4):  # 1 ห้อง x 4 เตียง
        CourseStudentEnrollment.objects.create(cohort=cohort, email=f"seat{index}@signalschool.ac.th")
    assert callback(client, claims("fifth@signalschool.ac.th"), target).url == reverse("accounts:login")
    assert not User.objects.filter(email="fifth@signalschool.ac.th").exists()

    CourseStudentEnrollment.objects.filter(email="seat3@signalschool.ac.th").delete()
    assert callback(Client(), claims("fifth@signalschool.ac.th", sub="uid-fifth"), target).url == target
    room = Resource.objects.create(code="G-DORM-2", name="ห้องพัก 2", resource_type="room", room_category="lodging", capacity=4)
    other = CourseLodgingCohort.objects.create(title="รุ่นซ้อนวัน", slug="overlap-class", supervisor=cohort.supervisor,
        unit=cohort.unit, check_in_date=cohort.check_in_date, check_out_date=cohort.check_out_date,
        allocation_status="allocated", is_active=True)
    other.rooms.add(room)
    other_target = reverse("bookings:lodging_portal", args=[other.slug])
    assert callback(Client(), claims("fifth@signalschool.ac.th", sub="uid-fifth"), other_target).url == reverse("accounts:login")
    assert not CourseStudentEnrollment.objects.filter(cohort=other).exists()


def test_open_cohort_does_not_auto_enroll_existing_staff_account(client, google_settings, cohort, existing):
    target = reverse("bookings:lodging_portal", args=[cohort.slug])
    callback(client, claims(existing.email), target)
    assert not CourseStudentEnrollment.objects.filter(email=existing.email).exists()
    existing.refresh_from_db()
    assert not existing.is_lodging_student
