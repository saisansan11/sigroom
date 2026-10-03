import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _header(html: str) -> str:
    return html.split('<header class="site-header">', 1)[1].split("</header>", 1)[0]


def test_guest_brand_and_gateway_navigation_point_to_service_gateway(client):
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200
    header = _header(response.content.decode("utf-8"))

    gateway = reverse("bookings:lodging_about")
    calendar = reverse("bookings:calendar")
    lodging = reverse("bookings:lodging_index")

    assert f'class="brand" href="{gateway}"' in header
    assert f'href="{gateway}">หน้าแรก</a>' in header
    assert f'href="{calendar}">สถานะห้องวันนี้</a>' in header
    assert f'href="{lodging}">จองห้องพัก</a>' in header


def test_gateway_page_keeps_three_service_choices_and_marks_gateway_current(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    header = _header(html)

    assert 'aria-current="page"' in header
    assert '>หน้าแรก</a>' in header
    assert "จองห้องพัก" in html
    assert "จองห้องสอน" in html
    assert "ห้องเรียน / ห้องประชุม" in html
    assert "กำลังพัฒนาระบบ" in html
