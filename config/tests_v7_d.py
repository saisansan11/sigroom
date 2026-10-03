import json

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse
from PIL import Image

from accounts.models import Unit, User


def test_manifest_is_public_and_installable(client):
    response = client.get(reverse("webmanifest"))

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/manifest+json")
    manifest = json.loads(response.content)
    assert manifest["name"].startswith("SIGROOM")
    assert manifest["short_name"] == "SIGROOM"
    assert manifest["start_url"] == "/home/"
    assert manifest["display"] == "standalone"
    assert manifest["background_color"] == "#F5F1E6"
    assert manifest["theme_color"] == "#F5F1E6"
    assert [icon["sizes"] for icon in manifest["icons"]] == ["192x192", "512x512", "512x512"]
    assert all(icon["type"] == "image/png" for icon in manifest["icons"])


def _static_path_from_url(url):
    assert url.startswith("/static/")
    return finders.find(url.removeprefix("/static/"))


def test_manifest_icons_point_to_existing_files_with_declared_dimensions(client):
    manifest = json.loads(client.get(reverse("webmanifest")).content)

    for icon in manifest["icons"]:
        icon_path = _static_path_from_url(icon["src"])
        assert icon_path is not None, icon["src"]
        width, height = (int(n) for n in icon["sizes"].split("x"))
        with Image.open(icon_path) as image:
            assert image.size == (width, height)
    purposes = {icon["purpose"] for icon in manifest["icons"]}
    assert {"any", "maskable"} <= purposes


def test_maskable_icon_keeps_logo_inside_safe_zone(client):
    manifest = json.loads(client.get(reverse("webmanifest")).content)
    maskable = next(icon for icon in manifest["icons"] if icon["purpose"] == "maskable")

    with Image.open(_static_path_from_url(maskable["src"])).convert("RGB") as image:
        corner = image.getpixel((0, 0))
        background = Image.new("RGB", image.size, corner)
        from PIL import ImageChops

        left, top, right, bottom = ImageChops.difference(image, background).getbbox()
    assert corner == (245, 241, 230)
    assert left >= 512 * 0.1 and top >= 512 * 0.1
    assert right <= 512 * 0.9 and bottom <= 512 * 0.9


def test_favicon_root_redirects_to_existing_static_icon(client):
    response = client.get(reverse("favicon"))

    assert response.status_code == 302
    assert response.headers["Location"] == "/static/img/brand/favicon.ico"
    assert _static_path_from_url(response.headers["Location"]) is not None


@pytest.mark.django_db
def test_header_uses_logo_image_with_explicit_size(client):
    content = client.get(reverse("bookings:calendar")).content.decode()

    assert 'alt="SIGROOM" width="107" height="40"' in content
    assert "sigroom-logo-horizontal-2x.webp" in content


def test_splash_embeds_mark_without_external_requests():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "public" / "index.html").read_text(encoding="utf-8")

    assert 'src="data:image/webp;base64,' in html
    assert "http://" not in html and "https://" not in html
    assert len(html.encode()) < 20_000


@pytest.mark.django_db
def test_login_sheet_uses_approved_punch_clock_branding(client):
    content = client.get(reverse("login")).content.decode()

    assert 'class="login-punch-clock"' in content
    assert 'aria-hidden="true"' in content
    assert "SIGROOM" in content
    assert "ระบบจองห้อง รร.ส.สส." in content
    assert "ตอกบัตรเข้าระบบ" in content


@pytest.mark.django_db
def test_base_template_links_manifest_and_ios_metadata(client):
    response = client.get(reverse("bookings:calendar"))
    content = response.content.decode()

    assert f'<link rel="manifest" href="{reverse("webmanifest")}">' in content
    assert '<meta name="theme-color" content="#F5F1E6">' in content
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in content
    assert 'rel="icon" type="image/png" sizes="32x32" href="/static/img/brand/favicon-32.png"' in content
    assert 'rel="apple-touch-icon" sizes="180x180" href="/static/img/brand/apple-touch-icon-180.png"' in content


@pytest.mark.django_db
def test_account_menu_has_three_step_install_guides(client):
    unit = Unit.objects.create(code="PWA", name="หน่วยทดสอบ PWA")
    user = User.objects.create_user(
        username="pwa-user",
        email="pwa-user@signalschool.ac.th",
        password="Test-Password-2570!",
        unit=unit,
    )
    client.force_login(user)

    content = client.get(reverse("bookings:calendar")).content.decode()
    assert "ติดตั้งลงหน้าจอโฮม" in content
    assert "Android · Chrome" in content
    assert "iPhone · Safari" in content
    assert content.count("<ol>") == 4  # คู่มือ Android/iPhone แสดงในเมนูบัญชีทั้ง desktop และ mobile


@pytest.mark.django_db
def test_manifest_bypasses_initial_password_gate(client):
    user = User.objects.create_user(
        username="pwa-first-login",
        email="pwa-first-login@signalschool.ac.th",
        password="Initial-Password-2570!",
        must_change_password=True,
    )
    client.force_login(user)

    response = client.get(reverse("webmanifest"))
    assert response.status_code == 200
