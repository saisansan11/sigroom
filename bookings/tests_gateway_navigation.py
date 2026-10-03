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
    assert f'class="brand" href="{gateway}"' in header
    # PR-2: หน้าที่ไม่ได้เลือกบริการใช้โลโก้กลับ Gateway และไม่ปนเมนูบริการอื่น
    assert response.context["nav_service"] is None
    assert f'href="{reverse("login")}?next={calendar}"' in header
    assert "สถานะห้องวันนี้" not in header
    assert "จองห้องพัก" not in header
    assert "การจองของฉัน" not in header
    assert "งานปฏิบัติการ" not in header


def test_gateway_page_keeps_task_first_service_choices_and_marks_gateway_current(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    header = _header(html)

    assert response.context["nav_service"] is None
    assert f'class="brand" href="{reverse("bookings:lodging_about")}"' in header
    assert 'aria-current="page"' not in header
    assert '>หน้าแรก</a>' not in header
    assert '‹ บริการทั้งหมด' not in header
    assert "จองห้องพัก" in html
    assert "จองห้องสอนออนไลน์" in html
    assert "จองห้องเรียน" in html
    assert "จองห้องประชุม" in html
    assert "กำลังพัฒนาระบบ" not in html
