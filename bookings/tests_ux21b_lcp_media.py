"""
UX-21B Lodging About LCP & Media Delivery Polish — contract tests.

Validates:
1. Public 200 access without authentication.
2. Hero LCP image delivery contract:
   - Primary hero showcase image (room4p_3421.jpg) has loading="eager" and fetchpriority="high".
   - Hero image is NOT loading="lazy".
3. Layout stability and CLS protection:
   - Explicit width and height on hero and all showcase images.
   - Appropriate decoding="async" on images.
4. Below-the-fold image lazy loading discipline:
   - Exactly 10 below-the-fold images retain loading="lazy" (gallery 4, bath 3, rates notice 1, floor diagrams 2).
   - Old room experience images (lka-exp-img) are removed.
5. Preload hygiene:
   - No speculative or redundant <link rel="preload" as="image"> in template or rendered HTML.
6. Multi-instance asset caching & priority isolation:
   - room4p_3421.jpg appears exactly twice: in hero as eager/high, and in gallery as lazy.

Run with: uv run --env-file F:/ogn_ROOM/.env pytest bookings/tests_ux21b_lcp_media.py -v
"""

from pathlib import Path
import re
import pytest
from django.test import Client
from django.urls import reverse

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = WORKTREE_ROOT / "templates" / "lodging" / "lodging_about.html"

pytestmark = pytest.mark.django_db


def _read_template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def test_ux21b_public_access_200():
    """GET /lodging/about/ returns 200 without login redirect."""
    client = Client()
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200


def test_ux21b_hero_lcp_loading_and_fetchpriority(client):
    """Hero photo has loading='eager' and fetchpriority='high' to optimize LCP."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    # Match the hero main image tag
    hero_img_match = re.search(r'<img[^>]*class="[^"]*lka-hero-main-img[^"]*"[^>]*>', html)
    assert hero_img_match is not None, "Hero image with class lka-hero-main-img not found"
    hero_img_tag = hero_img_match.group(0)

    assert "room4p_3421.jpg" in hero_img_tag, "Hero image must reference room4p_3421.jpg"
    assert 'loading="eager"' in hero_img_tag, "Hero image must have loading='eager' for LCP"
    assert 'fetchpriority="high"' in hero_img_tag, "Hero image must have fetchpriority='high'"
    assert 'loading="lazy"' not in hero_img_tag, "Hero image must NOT have loading='lazy'"


def test_ux21b_image_dimensions_and_decoding_contract(client):
    """All 11 showcase images have explicit width and height (CLS guard) and decoding='async'."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    # Find all <img> tags inside lka-page-wrap
    page_wrap_match = re.search(r'<div class="lka-page-wrap">(.*?)</div>\s*\{% endblock %\}', html, re.DOTALL)
    content_to_scan = page_wrap_match.group(1) if page_wrap_match else html

    img_tags = re.findall(r'<img\s+[^>]+>', content_to_scan)
    assert len(img_tags) == 11, f"Expected 11 showcase images in lodging_about, found {len(img_tags)}"

    for tag in img_tags:
        assert re.search(r'width="\d+"', tag), f"Image tag missing explicit width: {tag}"
        assert re.search(r'height="\d+"', tag), f"Image tag missing explicit height: {tag}"
        assert 'decoding="async"' in tag, f"Image tag missing decoding='async': {tag}"


def test_ux21b_below_fold_images_remain_lazy(client):
    """Exactly 10 below-the-fold images retain loading='lazy', and lka-exp-img is absent."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    lazy_matches = re.findall(r'<img\s+[^>]*loading="lazy"[^>]*>', html)
    assert len(lazy_matches) == 10, (
        f"Expected exactly 10 below-the-fold images with loading='lazy', found {len(lazy_matches)}"
    )

    # Old room experience image class must be completely absent
    assert "lka-exp-img" not in html, "Old lka-exp-img class should not be present"

    # Check key sections below fold individually with exact expected counts
    below_fold_classes = [
        ("lka-gallery-img", 4),   # Gallery mosaic (4 images)
        ("lka-bath-img", 3),      # Bathroom amenities (3 images)
        ("lka-rates-img", 1),     # Rates document (1 image)
        ("lka-floor-img", 2),     # Floor diagrams (2 images)
    ]
    for cls_name, expected_count in below_fold_classes:
        matches = re.findall(rf'<img[^>]*class="[^"]*{cls_name}[^"]*"[^>]*>', html)
        assert len(matches) == expected_count, (
            f"Expected {expected_count} images for class {cls_name}, found {len(matches)}"
        )
        for tag in matches:
            assert 'loading="lazy"' in tag, f"Below-fold image {cls_name} must have loading='lazy': {tag}"
            assert 'loading="eager"' not in tag, f"Below-fold image {cls_name} must NOT have loading='eager'"
            assert 'fetchpriority="high"' not in tag, f"Below-fold image {cls_name} must NOT have fetchpriority='high'"


def test_ux21b_no_preload_spam(client):
    """No unnecessary <link rel="preload"> image tags to avoid duplicate fetches and network contention."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    preload_img_tags = re.findall(r'<link[^>]*rel="preload"[^>]*as="image"[^>]*>', html, re.IGNORECASE)
    assert len(preload_img_tags) == 0, f"Unexpected image preload tags found: {preload_img_tags}"


def test_ux21b_same_asset_multi_instance_priority_isolation(client):
    """room4p_3421.jpg appears exactly twice: in hero as eager/high, and in gallery as lazy."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    # Find all occurrences of room4p_3421.jpg in <img> tags
    matches = re.findall(r'<img[^>]*room4p_3421\.jpg[^>]*>', html)
    assert len(matches) == 2, f"Expected exactly 2 occurrences of room4p_3421.jpg, found {len(matches)}"

    # First instance is hero
    hero_instance = matches[0]
    assert 'loading="eager"' in hero_instance
    assert 'fetchpriority="high"' in hero_instance
    assert 'lka-hero-main-img' in hero_instance

    # Second instance is Stay Gallery
    gallery_instance = matches[1]
    assert 'loading="lazy"' in gallery_instance
    assert 'loading="eager"' not in gallery_instance
    assert 'fetchpriority="high"' not in gallery_instance
    assert 'lka-gallery-img' in gallery_instance
