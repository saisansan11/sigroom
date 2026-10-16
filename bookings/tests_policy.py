"""
การทดสอบศูนย์นโยบาย (Policy Center) และ Footer สองภาษาของ SIGROOM
ทดสอบการเข้าถึงแบบสาธารณะ (ไม่ต้องเข้าสู่ระบบ), ความถูกต้องของ H1/Title,
สารบัญ, การเชื่อมโยงข้ามเอกสาร, ข้อมูลคุกกี้และสิทธิส่วนบุคคล, และข้อความ Footer ที่อนุมัติ
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


EXACT_FOOTER_TH = "© 2569 แผนกวิชาการสื่อสารประเภทวิทยุและการสงครามอิเล็กทรอนิกส์ กองการศึกษา โรงเรียนทหารสื่อสาร กรมการทหารสื่อสาร สงวนลิขสิทธิ์"
EXACT_FOOTER_EN = "© 2026 Radio Communications and Electronic Warfare Department, Education Division, Signal School, Royal Thai Signal Corps. All rights reserved."
EXACT_AUTHOR_TH = "สร้างสรรค์และดูแลระบบโดย ร.ต. วสันต์ ทัศนามล"
EXACT_AUTHOR_EN = "Created & Maintained by 2nd Lt. Wasan Thatsanamol"


def test_policy_routes_publicly_accessible(client):
    """ผู้ใช้งานทั่วไปที่ไม่ได้ล็อกอินต้องเข้าถึงทั้ง ๔ หน้าได้ (HTTP 200)"""
    routes = ["privacy", "cookies", "terms", "disclaimer"]
    for route in routes:
        response = client.get(reverse(route))
        assert response.status_code == 200, f"Route {route} failed with {response.status_code}"
        assert response.status_code == client.get(f"/{route}/").status_code


def test_policy_pages_have_distinct_titles_and_h1(client):
    """ตรวจสอบว่าแต่ละหน้ามี Title และ H1 ถูกต้องเฉพาะตัว ไม่เกิดบั๊กชื่อซ้ำกับ disclaimer"""
    expected = [
        ("privacy", "นโยบายความเป็นส่วนตัว"),
        ("cookies", "นโยบายคุกกี้"),
        ("terms", "นโยบายเว็บไซต์"),
        ("disclaimer", "ข้อจำกัดความรับผิดชอบ"),
    ]
    for route, expected_title in expected:
        response = client.get(reverse(route))
        content = response.content.decode("utf-8")
        assert f"<title>{expected_title} · SIGROOM</title>" in content or f"{expected_title}" in content
        assert f"<h1>{expected_title}</h1>" in content or f">{expected_title}<" in content


def test_policy_pages_have_cross_links(client):
    """ทุกหน้านโยบายต้องมีแถบนำทางและลิงก์เชื่อมโยงข้ามไปยังอีก ๓ หน้าที่เหลือ"""
    pages = ["privacy", "cookies", "terms", "disclaimer"]
    for current in pages:
        response = client.get(reverse(current))
        content = response.content.decode("utf-8")
        for target in pages:
            target_url = reverse(target)
            assert target_url in content, f"Page {current} missing link to {target_url}"


def test_privacy_policy_covers_required_data_points(client):
    """หน้านโยบายความเป็นส่วนตัวต้องครอบคลุมประเภทข้อมูลและบทบาทตามข้อกำหนด"""
    response = client.get(reverse("privacy"))
    content = response.content.decode("utf-8")

    # ตรวจสอบหัวข้อข้อมูลระบุตัวตนและบัญชีผู้ใช้
    assert "ยศ" in content
    assert "เลขประจำตัวทหาร" in content
    assert "ตำแหน่ง" in content
    assert "โทรศัพท์" in content
    assert "อีเมล" in content

    # ตรวจสอบการจองห้อง ที่พัก และการอนุมัติ
    assert "ห้องเรียน" in content
    assert "ห้องประชุม" in content
    assert "ห้องสอนออนไลน์" in content
    assert "ที่พัก" in content or "เตียง" in content
    assert "อนุมัติ" in content

    # ตรวจสอบการระบุสถานะฉบับร่างรอยืนยัน (To-Be-Confirmed)
    assert "To Be Confirmed" in content or "รอยืนยัน" in content


def test_cookie_policy_reflects_django_settings(client):
    """นโยบายคุกกี้ต้องสะท้อนการตั้งค่าจริงของ Django (sessionid/__session, 12h, CSRF, ไม่ใช้ Auth.js)"""
    response = client.get(reverse("cookies"))
    content = response.content.decode("utf-8")

    assert ("__session" in content) or ("sessionid" in content)
    assert "12" in content  # 12 ชั่วโมง
    assert "csrftoken" in content or "CSRF" in content
    assert "Auth.js" in content  # ชี้แจงว่าไม่ใช้ Auth.js


def test_approved_footer_text_rendered_identically(client):
    """ข้อความ Footer สองภาษาและผู้พัฒนาต้องตรงทุกตัวอักษรตามที่ได้รับอนุมัติ"""
    response = client.get(reverse("privacy"))
    content = response.content.decode("utf-8")

    assert EXACT_FOOTER_TH in content
    assert EXACT_FOOTER_EN in content
    assert EXACT_AUTHOR_TH in content
    assert EXACT_AUTHOR_EN in content


def test_footer_rendered_on_general_pages(client):
    """Footer ต้องปรากฏบนหน้าทั่วไป เช่น หน้ารู้จักระบบ (/about/)"""
    response = client.get(reverse("bookings:about"))
    content = response.content.decode("utf-8")

    assert EXACT_FOOTER_TH in content
    assert EXACT_FOOTER_EN in content
    assert EXACT_AUTHOR_TH in content
    assert EXACT_AUTHOR_EN in content
