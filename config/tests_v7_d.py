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
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    assert [icon["sizes"] for icon in manifest["icons"]] == ["192x192", "512x512"]
    assert all(icon["type"] == "image/png" for icon in manifest["icons"])


def test_manifest_icons_have_declared_dimensions():
    for size in (192, 512):
        icon_path = finders.find(f"img/pwa-icon-{size}.png")
        assert icon_path is not None
        with Image.open(icon_path) as icon:
            assert icon.size == (size, size)


@pytest.mark.django_db
def test_base_template_links_manifest_and_ios_metadata(client):
    response = client.get(reverse("bookings:calendar"))
    content = response.content.decode()

    assert f'<link rel="manifest" href="{reverse("webmanifest")}">' in content
    assert '<meta name="theme-color" content="#102433">' in content
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in content
    assert 'rel="apple-touch-icon"' in content


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
