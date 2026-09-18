"""UI-5 Responsive, Accessibility (WCAG AA), and Performance tests."""
from pathlib import Path
from datetime import timedelta
import re

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ui5_setup():
    unit = Unit.objects.create(code="UI5", name="หน่วยทดสอบ UI-5")
    user = User.objects.create_user(
        username="ui5-user",
        email="ui5-user@example.test",
        password="Password-2569",
        unit=unit,
    )
    supervisor = User.objects.create_user(
        username="ui5-supervisor",
        email="ui5-supervisor@example.test",
        password="Password-2569",
        unit=unit,
    )
    room = Resource.objects.create(
        code="DORM-UI5-101",
        name="ห้องพักทดสอบ UI-5",
        building="อาคารทดสอบ UI-5",
        floor=1,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
    )
    ResourceRule.objects.create(resource=room)
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรทดสอบ UI-5",
        slug="ui5-course",
        supervisor=supervisor,
        unit=unit,
        check_in_date=today + timedelta(days=2),
        check_out_date=today + timedelta(days=8),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(room)
    student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ร.ต.",
        full_name="นักเรียน ทดสอบ UI-5",
        origin_unit="ส.พัน.UI5",
        phone="081-999-5555",
    )
    return {
        "unit": unit,
        "user": user,
        "supervisor": supervisor,
        "room": room,
        "cohort": cohort,
        "student": student,
    }


def test_guest_header_nav_semantics_and_aria_current(client):
    """Verify unauthenticated guest gets correct nav links, login cta, and aria-current."""
    resp_home = client.get(reverse("bookings:calendar"))
    assert resp_home.status_code == 200
    home_html = resp_home.content.decode()

    # On calendar / home, "สถานะห้องวันนี้" has aria-current="page"
    assert 'aria-current="page"' in home_html
    assert "สถานะห้องวันนี้" in home_html
    assert "จองห้องพัก" in home_html
    assert "เข้าสู่ระบบ" in home_html

    # On lodging index, "จองห้องพัก" gets aria-current="page"
    resp_lodging = client.get(reverse("bookings:lodging_index"))
    assert resp_lodging.status_code == 200
    lodging_html = resp_lodging.content.decode()
    assert 'aria-current="page"' in lodging_html
    assert 'href="/lodging/"' in lodging_html or 'href="/lodging"' in lodging_html


def test_app_css_touch_targets_meet_wcag():
    """Verify touch targets are at least 44x44px (2.75rem) in static/css/app.css."""
    css_path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    css_text = css_path.read_text(encoding="utf-8")

    # .fav-button must have 2.75rem min dimensions
    assert ".fav-button" in css_text
    assert "min-width: max(44px, 2.75rem)" in css_text
    assert "min-height: max(44px, 2.75rem)" in css_text

    # .room-gallery-nav must have 2.75rem dimensions
    gallery_nav_match = re.search(r"\.room-gallery-nav\s*\{([^}]+)\}", css_text)
    assert gallery_nav_match is not None
    gallery_nav_decl = gallery_nav_match.group(1)
    assert "min-width: max(44px, 2.75rem)" in gallery_nav_decl or "width: max(44px, 2.75rem)" in gallery_nav_decl
    assert "min-height: max(44px, 2.75rem)" in gallery_nav_decl or "height: max(44px, 2.75rem)" in gallery_nav_decl

    # .compact-button expands on mobile <= 50rem
    assert ".compact-button" in css_text
    assert "min-height: max(44px, 2.75rem)" in css_text

    # .category-pill has min-height: max(44px, 2.75rem)
    cat_pill_match = re.search(r"\.category-pill\s*\{([^}]+)\}", css_text)
    assert cat_pill_match is not None
    assert "min-height: max(44px, 2.75rem)" in cat_pill_match.group(1)



def test_app_css_responsive_table_touch_scrolling():
    """Verify table containers include -webkit-overflow-scrolling: touch for smooth mobile scrolling."""
    css_path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    css_text = css_path.read_text(encoding="utf-8")

    assert "-webkit-overflow-scrolling: touch" in css_text
    assert ".table-wrap, .table-scroll" in css_text
    table_match = re.search(r"\.table-wrap,\s*\.table-scroll\s*\{([^}]+)\}", css_text)
    assert table_match is not None
    assert "-webkit-overflow-scrolling: touch" in table_match.group(1)


def test_app_css_reduced_motion_and_focus_visible():
    """Verify prefers-reduced-motion media query and focus-visible outline are present."""
    css_path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    css_text = css_path.read_text(encoding="utf-8")

    assert "@media (prefers-reduced-motion: reduce)" in css_text
    assert "scroll-behavior: auto" in css_text
    assert ":focus-visible" in css_text
    assert "outline: .18rem solid var(--cyan)" in css_text


def test_image_performance_attributes_in_templates():
    """Verify images include width, height, loading='lazy' (or explicit LCP hero eager), and decoding='async' to prevent layout shift."""
    templates_dir = Path(settings.BASE_DIR) / "templates"
    checked_images = 0

    for html_file in templates_dir.glob("**/*.html"):
        content = html_file.read_text(encoding="utf-8")
        # Find all img tags
        img_tags = re.findall(r"<img\s+[^>]+>", content)
        for img in img_tags:
            # Narrowly designated LCP hero exception:
            # Only the primary above-the-fold hero image ('lka-hero-main-img') is permitted
            # to be eager, and MUST have BOTH loading="eager" and fetchpriority="high".
            is_lcp_hero = "lka-hero-main-img" in img
            if is_lcp_hero:
                assert 'loading="eager"' in img, f"LCP hero must have loading='eager' in {html_file.name}: {img}"
                assert 'fetchpriority="high"' in img, f"LCP hero must have fetchpriority='high' in {html_file.name}: {img}"
                assert 'loading="lazy"' not in img, f"LCP hero must not have loading='lazy' in {html_file.name}: {img}"
            else:
                # All other images across templates MUST remain loading="lazy" and NOT eager
                assert 'loading="lazy"' in img, f"Missing loading='lazy' in {html_file.name}: {img}"
                assert 'loading="eager"' not in img, f"Non-hero image must not have loading='eager' in {html_file.name}: {img}"
                assert 'fetchpriority="high"' not in img, f"Non-hero image must not have fetchpriority='high' in {html_file.name}: {img}"

            assert 'decoding="async"' in img, f"Missing decoding='async' in {html_file.name}: {img}"
            assert 'width="' in img, f"Missing width attribute in {html_file.name}: {img}"
            assert 'height="' in img, f"Missing height attribute in {html_file.name}: {img}"
            checked_images += 1

    assert checked_images >= 5, f"Expected at least 5 images with performance attributes, found {checked_images}"



def test_student_portal_modal_a11y_and_reduced_motion(client, ui5_setup):
    """Verify student portal includes modal focus management and reduced motion support."""
    cohort = ui5_setup["cohort"]
    resp = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
    assert resp.status_code == 200
    html = resp.content.decode()

    # Check focus restoration in modal functions
    assert "lastFocusedElement" in html
    assert "bookingModal" in html
    assert "roomGalleryDialog" in html

    # Check reduced motion handling in scrollToNextFreeBed
    assert "prefers-reduced-motion" in html
