import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from accounts.models import Unit, User
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db

PASSWORD = "Password-2569"


def _user(username, *, unit=None, superuser=False):
    return User.objects.create_user(
        username=username,
        email=f"{username}@signalschool.ac.th",
        password=PASSWORD,
        unit=unit,
        is_superuser=superuser,
        is_staff=superuser,
    )


def _room(code, category, *, unit=None):
    room = Resource.objects.create(
        code=code,
        name=f"ห้อง {code}",
        building="อาคารทดสอบ A3",
        floor="1",
        resource_type=Resource.Type.ROOM,
        room_category=category,
        capacity=8,
        owner_unit=unit,
    )
    ResourceRule.objects.create(resource=room)
    return room


def _managed_strip(html):
    marker = '<nav class="managed-service-strip"'
    if marker not in html:
        return ""
    return html.split(marker, 1)[1].split("</nav>", 1)[0]


def test_role_home_requires_login(client):
    response = client.get(reverse("bookings:role_home"))
    assert response.status_code == 302
    assert reverse("login") in response.url


def test_general_user_goes_to_gateway(client):
    unit = Unit.objects.create(code="A3-GEN", name="หน่วยผู้ใช้ทั่วไป")
    user = _user("a3-general", unit=unit)
    client.force_login(user)
    response = client.get(reverse("bookings:role_home"))
    assert response.status_code == 302
    assert response.url == reverse("bookings:lodging_about")


def test_superuser_goes_to_gateway_not_lodging(client):
    admin = _user("a3-admin", superuser=True)
    client.force_login(admin)
    response = client.get(reverse("bookings:role_home"))
    assert response.status_code == 302
    assert response.url == reverse("bookings:lodging_about")


def test_lodging_manager_goes_to_lodging_first(client):
    unit = Unit.objects.create(code="A3-LODGE", name="หน่วยงานที่พัก")
    user = _user("a3-lodging", unit=unit)
    user.user_permissions.add(Permission.objects.get(codename="add_courselodgingcohort"))
    client.force_login(user)

    response = client.get(reverse("bookings:role_home"))
    assert response.status_code == 302
    assert response.url == reverse("bookings:service_staff_entry", args=["lodging"])

    final = client.get(response.url)
    assert final.status_code == 302
    assert final.url == reverse("bookings:lodging_workspace")


@pytest.mark.parametrize(
    ("category", "service"),
    [
        (Resource.Category.ONLINE, "online"),
        (Resource.Category.MEETING, "learning"),
        (Resource.Category.SPECIAL, "learning"),
    ],
)
def test_custodian_routes_to_matching_service(client, category, service):
    unit = Unit.objects.create(code=f"A3-{category[:8]}", name=f"หน่วย {category}")
    user = _user(f"a3-{category}", unit=unit)
    room = _room(f"A3-{category[:8]}", category, unit=unit)
    room.custodians.add(user)
    client.force_login(user)

    response = client.get(reverse("bookings:role_home"))
    assert response.status_code == 302
    assert response.url == reverse("bookings:service_staff_entry", args=[service])


def test_multi_service_manager_prefers_lodging_and_sees_switcher(client):
    unit = Unit.objects.create(code="A3-MULTI", name="หน่วยหลายบริการ")
    user = _user("a3-multi", unit=unit)
    user.user_permissions.add(Permission.objects.get(codename="add_courselodgingcohort"))
    online = _room("A3-ONLINE", Resource.Category.ONLINE, unit=unit)
    online.custodians.add(user)
    client.force_login(user)

    start = client.get(reverse("bookings:role_home"))
    assert start.status_code == 302
    assert start.url == reverse("bookings:service_staff_entry", args=["lodging"])

    html = client.get(reverse("bookings:lodging_about")).content.decode("utf-8")
    strip = _managed_strip(html)
    assert "งานของฉัน:" in strip
    assert reverse("bookings:service_staff_entry", args=["lodging"]) in strip
    assert reverse("bookings:service_staff_entry", args=["online"]) in strip
    assert "จองห้องให้ตัวเอง" in strip


def test_single_service_manager_sees_self_booking_link_without_service_switch(client):
    unit = Unit.objects.create(code="A3-ONE", name="หน่วยบริการเดียว")
    user = _user("a3-one", unit=unit)
    room = _room("A3-ONE-ON", Resource.Category.ONLINE, unit=unit)
    room.custodians.add(user)
    client.force_login(user)

    html = client.get(reverse("bookings:lodging_about")).content.decode("utf-8")
    strip = _managed_strip(html)
    assert "จองห้องให้ตัวเอง" in strip
    assert reverse("bookings:service_staff_entry", args=["online"]) not in strip


def test_password_login_defaults_to_role_home(client):
    unit = Unit.objects.create(code="A3-LOGIN", name="หน่วยล็อกอิน")
    _user("a3-login", unit=unit)
    response = client.post(reverse("login"), {"username": "a3-login", "password": PASSWORD})
    assert response.status_code == 302
    assert response.url == reverse("bookings:role_home")


def test_login_next_still_wins_over_role_home(client):
    unit = Unit.objects.create(code="A3-NEXT", name="หน่วย next")
    _user("a3-next", unit=unit)
    target = reverse("bookings:my_bookings")
    response = client.post(
        reverse("login") + f"?next={target}",
        {"username": "a3-next", "password": PASSWORD, "next": target},
    )
    assert response.status_code == 302
    assert response.url == target
