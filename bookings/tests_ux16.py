"""UX-16 Student Digital Pass Mobile Clarity tests and contracts."""
from datetime import timedelta
from pathlib import Path
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


def _read_template() -> str:
    template_path = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "lodging"
        / "student_pass.html"
    )
    return template_path.read_text(encoding="utf-8")


def _read_css() -> str:
    css_path = (
        Path(__file__).resolve().parent.parent
        / "static"
        / "css"
        / "app.css"
    )
    return css_path.read_text(encoding="utf-8")


def _ux16_section(css: str) -> str:
    marker = "/* UX-16 Student Digital Pass Mobile Clarity */"
    assert marker in css, f"Marker '{marker}' must exist in app.css"
    return css.split(marker, 1)[1]


@pytest.fixture
def ux16_setup():
    unit = Unit.objects.create(code="SIG-UX16", name="หน่วยทดสอบบัตรดิจิทัล UX-16")
    supervisor = User.objects.create_user(
        username="supervisor_ux16_test",
        email="supervisor_ux16@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ต.",
        first_name="ธีรศักดิ์",
        last_name="ผู้กำกับรุ่น",
    )
    superuser = User.objects.create_superuser(
        username="admin_ux16_test",
        email="admin_ux16@signalschool.ac.th",
        password="Password-2569",
    )
    room = Resource.objects.create(
        code="DORM-UX16-202",
        name="ห้องนอนทดสอบ 202",
        building="อาคารนอน 2",
        floor=2,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
    )
    ResourceRule.objects.create(resource=room)
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรการสื่อสารดิจิทัลและเทคโนโลยีสารสนเทศเพื่อความมั่นคงทางยุทธวิธี รุ่นที่ 16",
        slug="ux16-course",
        supervisor=supervisor,
        unit=unit,
        check_in_date=today + timedelta(days=2),
        check_out_date=today + timedelta(days=16),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        note="นำบัตรดิจิทัลมาแสดงต่อเวรรับรายงานตัว",
    )
    cohort.rooms.add(room)
    owner = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ร.อ.",
        full_name="กิตติศักดิ์ มหาดำรงค์กุลไพศาลวิจิตร",
        origin_unit="กองพันทหารสื่อสารที่ 101 กรมทหารสื่อสารที่ 1 รักษาพระองค์",
        phone="089-999-9999",
        note="ข้อมูลส่วนตัวเฉพาะเจ้าของบัตรเท่านั้น",
    )
    roommate = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=2,
        rank="ร.ท.",
        full_name="เพื่อนร่วมห้อง นิรนามพิทักษ์ไพรวัลย์",
        origin_unit="กองพันทหารสื่อสารซ่อนเร้น",
        phone="088-888-8888",
        note="ข้อมูลลับของเพื่อนร่วมห้องห้ามเปิดเผย",
    )
    return {
        "unit": unit,
        "supervisor": supervisor,
        "superuser": superuser,
        "room": room,
        "cohort": cohort,
        "owner": owner,
        "roommate": roommate,
    }


def test_student_pass_template_semantics_and_no_duplicate_mobile_dom():
    """1. Template semantics: exactly one keycard element with role=button tabindex=0 aria-pressed=false,
    and no duplicate mobile/desktop DOM trees.
    """
    template = _read_template()

    # No duplicate responsive trees
    assert "mobile-only" not in template
    assert "desktop-only" not in template

    # Exactly one keycard container
    assert template.count('id="keycard"') == 1

    # Keycard semantics
    assert 'role="button"' in template
    assert 'tabindex="0"' in template
    assert 'aria-pressed="false"' in template

    # Front and back card faces present in single card
    assert "keycard-front" in template
    assert "keycard-back" in template
    assert "keycard-actions-bar" in template


def test_student_pass_css_marker_and_mobile_breakpoint():
    """2. Exact CSS marker and max-width: 47.99rem mobile breakpoint."""
    css = _read_css()
    assert "/* UX-16 Student Digital Pass Mobile Clarity */" in css

    ux16_css = _ux16_section(css)
    assert "@media (max-width: 47.99rem)" in ux16_css


def test_mobile_keycard_animation_and_reduced_motion_contract():
    """3. Mobile keycard animation:none / transform:none and prefers-reduced-motion contract.

    Critical repair: Does NOT assume the first @media (prefers-reduced-motion: reduce) block
    is the keycard block and does NOT slice arbitrary characters. app.css has an earlier
    global reduced-motion reset and a keycard-specific reduced-motion block. Deterministically
    scans all reduced-motion blocks for .keycard with animation: none.
    """
    css = _read_css()
    ux16_css = _ux16_section(css)

    # 1. In mobile breakpoint, keycard float animation and 3D transform are disabled
    assert "animation: none" in ux16_css
    assert "transform: none" in ux16_css

    # 2. Deterministically scan all prefers-reduced-motion blocks across app.css
    reduced_motion_chunks = css.split("@media (prefers-reduced-motion: reduce)")
    assert len(reduced_motion_chunks) > 1, "app.css must contain prefers-reduced-motion blocks"

    found_keycard_reduced_motion = False
    for chunk in reduced_motion_chunks[1:]:
        depth = 0
        started = False
        captured = []
        for ch in chunk:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
                if started and depth == 0:
                    break
            if started:
                captured.append(ch)
        block = "".join(captured)

        # Check if this reduced motion block specifies .keycard with animation: none
        if ".keycard" in block and re.search(r"animation\s*:\s*none", block):
            found_keycard_reduced_motion = True
            break

    assert found_keycard_reduced_motion, (
        "Expected at least one @media (prefers-reduced-motion: reduce) block in app.css "
        "containing '.keycard' and 'animation: none;'"
    )


def test_long_thai_text_wrapping_and_portrait_card_contract(client, ux16_setup):
    """4. Long Thai text wrapping and portrait/sufficient-height card sizing contract."""
    css = _read_css()
    ux16_css = _ux16_section(css)

    # Card sizing contract for content-safe dynamic grid/height pass
    assert "width: 100%" in ux16_css
    assert "max-width: 26rem" in ux16_css
    assert "height: auto" in ux16_css
    assert "grid-template-areas" in ux16_css

    # Text wrapping contract to prevent overflow on narrow screens
    assert "overflow-wrap: anywhere" in ux16_css
    assert "word-break: break-word" in ux16_css

    # Render student pass view with long Thai name and unit
    cohort = ux16_setup["cohort"]
    owner = ux16_setup["owner"]
    response = client.get(reverse("bookings:lodging_pass", args=[cohort.slug, owner.pk]))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert owner.full_name in html
    assert cohort.title in html
    assert owner.room.code in html


def test_actions_bar_single_column_and_touch_target_contract():
    """5. Actions bar single-column full-width layout with interactive targets >= 44px."""
    css = _read_css()
    ux16_css = _ux16_section(css)

    # Single-column stacked action area
    assert ".keycard-actions-bar" in ux16_css
    assert "flex-direction: column" in ux16_css
    assert "width: 100%" in ux16_css

    # Touch targets min-height >= 44px
    assert (
        "min-height: 44px" in ux16_css
        or "min-height: max(44px" in ux16_css
        or "min-height: 48px" in ux16_css
    )

    # Template actions presence
    template = _read_template()
    assert 'class="keycard-actions-bar"' in template
    assert 'id="copyPassBtn"' in template
    assert "แชร์เข้า LINE" in template
    assert 'class="keycard-save-tip"' in template


def test_keycard_and_actions_visible_focus_styles():
    """6. Keycard and action elements visible focus styles with cyan outlines."""
    css = _read_css()
    ux16_css = _ux16_section(css)

    # Keycard itself has focus-visible in stylesheet
    assert ".keycard:focus-visible" in css or ".keycard:focus-visible" in ux16_css
    assert "var(--cyan)" in css

    # Actions have focus-visible cyan outlines in UX-16 mobile clarity section
    assert ":focus-visible" in ux16_css
    assert "outline" in ux16_css
    assert "var(--cyan)" in ux16_css


def test_keycard_flip_script_and_keyboard_aria_contract():
    """7. Keycard flip script: click and Enter/Space keyboard navigation with ARIA toggle."""
    template = _read_template()

    # Retains single interactive card button with ARIA semantics
    assert template.count('id="keycard"') == 1
    assert 'role="button"' in template
    assert 'tabindex="0"' in template
    assert 'aria-pressed="false"' in template

    # Inline script event listeners and keyboard controls
    assert "toggleFlip" in template
    assert "is-flipped" in template
    assert "aria-pressed" in template
    assert "aria-label" in template
    assert "click" in template
    assert "keydown" in template
    assert "Enter" in template
    assert ("' '" in template or '" "' in template or "Space" in template or "Spacebar" in template)


def test_student_pass_privacy_and_security_headers_regression(client, ux16_setup):
    """8. Privacy protection and security response headers regression."""
    cohort = ux16_setup["cohort"]
    owner = ux16_setup["owner"]
    roommate = ux16_setup["roommate"]

    url = reverse("bookings:lodging_pass", args=[cohort.slug, owner.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Security & caching headers
    assert response["Cache-Control"] == "private, no-store, must-revalidate"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Robots-Tag"] == "noindex, nofollow"

    # Owner details present
    assert owner.full_name in content
    assert owner.room.code in content
    assert f"เตียง {owner.bed_number}" in content

    # Owner personal note and phone are omitted from pass for privacy
    assert owner.phone not in content
    assert owner.note not in content

    # Roommate PII must NEVER be exposed on another student's pass
    assert roommate.full_name not in content
    assert roommate.origin_unit not in content
    assert roommate.phone not in content
    assert roommate.note not in content

    # Roommate's bed is properly masked
    assert f"เตียง {roommate.bed_number}: มีผู้เข้าพักแล้ว" in content
