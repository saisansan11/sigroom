"""UX-22 contracts for the lodging responsive media pipeline."""

from pathlib import Path
import re
import shutil

import pytest
from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse
from PIL import Image, ImageOps

from scripts.generate_showcase_media import (
    GENERATED_DIR,
    SHOWCASE_DIR,
    check_variants,
    generate_all,
    get_expected_variants,
)

pytestmark = pytest.mark.django_db

PHOTO_FALLBACKS = (
    "room4p_3421.jpg",
    "room2p_444.jpg",
    "room4p_3421.jpg",
    "room2p_444.jpg",
    "room2p_222.jpg",
    "room4p_3421.jpg",
    "room4p_4444.jpg",
    "bath1.jpg",
    "bath2.jpg",
    "bath3.jpg",
)
PNG_FALLBACKS = ("floor4.png", "floor5.png", "rates.png")


def _about_html(client: Client) -> str:
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    return response.content.decode("utf-8")


def _picture_blocks(html: str) -> list[str]:
    return re.findall(r'<picture\b[^>]*>(.*?)</picture>', html, re.DOTALL)


def test_ux22_public_access_200(client):
    assert client.get(reverse("bookings:lodging_about")).status_code == 200


def test_ux22_photo_picture_source_order_and_original_fallback(client):
    html = _about_html(client)
    photo_blocks = [block for block in _picture_blocks(html) if ".jpg" in block]
    assert len(photo_blocks) == 10

    for block in photo_blocks:
        sources = re.findall(r'<source\b[^>]+>', block)
        assert len(sources) == 2
        assert 'type="image/avif"' in sources[0] and ".avif" in sources[0]
        assert 'type="image/webp"' in sources[1] and ".webp" in sources[1]
        imgs = re.findall(r'<img\b[^>]+>', block)
        assert len(imgs) == 1 and ".jpg" in imgs[0]

    for filename in PHOTO_FALLBACKS:
        assert f"img/showcase/{filename}" in html


def test_ux22_png_diagrams_use_lossless_webp_with_original_fallback(client):
    html = _about_html(client)
    picture_blocks = _picture_blocks(html)
    assert len(picture_blocks) == 13

    for filename in PNG_FALLBACKS:
        stem = Path(filename).stem
        blocks = [block for block in picture_blocks if filename in block]
        assert len(blocks) == 1
        block = blocks[0]
        sources = re.findall(r'<source\b[^>]+>', block)
        assert len(sources) == 1
        assert 'type="image/webp"' in sources[0]
        assert f"generated/{stem}.webp" in sources[0]
        imgs = re.findall(r'<img\b[^>]+>', block)
        assert len(imgs) == 1
        assert f"img/showcase/{filename}" in imgs[0]


def test_ux22_generated_manifest_exists_and_is_valid():
    specs = get_expected_variants(SHOWCASE_DIR)
    assert len(specs) == 29
    assert {spec.filename for spec in specs if spec.lossless} == {
        "floor4.webp",
        "floor5.webp",
        "rates.webp",
    }

    for spec in specs:
        path = GENERATED_DIR / spec.filename
        assert path.exists(), spec.filename
        with Image.open(path) as image:
            assert image.size == (spec.target_width, spec.target_height)
            assert image.format == spec.fmt


def test_ux22_png_webp_is_pixel_lossless_and_materially_smaller():
    for spec in get_expected_variants(SHOWCASE_DIR):
        if not spec.lossless:
            continue
        source_path = SHOWCASE_DIR / spec.source_filename
        generated_path = GENERATED_DIR / spec.filename
        with Image.open(source_path) as source, Image.open(generated_path) as generated:
            source_rgba = ImageOps.exif_transpose(source).convert("RGBA")
            generated_rgba = generated.convert("RGBA")
            assert source_rgba.size == generated_rgba.size
            assert source_rgba.tobytes() == generated_rgba.tobytes()
        reduction = 1.0 - generated_path.stat().st_size / source_path.stat().st_size
        assert reduction >= 0.60


def test_ux22_no_upscaling_enforced(client):
    html = _about_html(client)
    assert "room2p_222-1280" not in html
    assert not (GENERATED_DIR / "room2p_222-1280.avif").exists()
    assert not (GENERATED_DIR / "room2p_222-1280.webp").exists()
    assert "room2p_222-640.avif" in html
    assert "room2p_222-640.webp" in html


def test_ux22_hero_fallback_attributes_retained(client):
    html = _about_html(client)
    match = re.search(
        r'<div class="lka-hero-photo-frame">\s*<picture\b[^>]*>(.*?)</picture>',
        html,
        re.DOTALL,
    )
    assert match is not None
    img = re.search(r'<img\b[^>]+>', match.group(1)).group(0)
    for fragment in (
        "room4p_3421.jpg",
        'loading="eager"',
        'fetchpriority="high"',
        'decoding="async"',
        'width="640"',
        'height="480"',
        'class="lka-hero-main-img"',
    ):
        assert fragment in img
    assert 'loading="lazy"' not in img


def test_ux22_below_fold_lazy_discipline(client):
    html = _about_html(client)
    img_tags = re.findall(r'<img\b[^>]+>', html)
    assert len(img_tags) == 13
    lazy_tags = [tag for tag in img_tags if 'loading="lazy"' in tag]
    assert len(lazy_tags) == 12
    for tag in lazy_tags:
        assert 'loading="eager"' not in tag
        assert 'fetchpriority="high"' not in tag
        assert 'decoding="async"' in tag
        assert 'width="' in tag and 'height="' in tag


def test_ux22_no_preload_spam(client):
    html = _about_html(client)
    assert not re.search(
        r'<link[^>]*rel=["\']preload["\'][^>]*as=["\']image["\']',
        html,
        re.IGNORECASE,
    )


def test_ux22_every_generated_candidate_is_smaller_than_source():
    for spec in get_expected_variants(SHOWCASE_DIR):
        source = SHOWCASE_DIR / spec.source_filename
        generated = GENERATED_DIR / spec.filename
        assert generated.stat().st_size < source.stat().st_size
        if spec.target_width == 640 and not spec.lossless:
            reduction = 1.0 - generated.stat().st_size / source.stat().st_size
            assert reduction >= 0.50


def test_ux22_static_fallback_and_modern_assets_are_discoverable():
    for relative in (
        "img/showcase/room4p_3421.jpg",
        "img/showcase/floor4.png",
        "img/showcase/floor5.png",
        "img/showcase/rates.png",
        "img/showcase/generated/room4p_3421-640.avif",
        "img/showcase/generated/room4p_3421-640.webp",
        "img/showcase/generated/floor4.webp",
        "img/showcase/generated/floor5.webp",
        "img/showcase/generated/rates.webp",
    ):
        assert finders.find(relative), relative


def test_ux22_generator_check_detects_stale_corrupt_and_extra_files(tmp_path):
    generated = tmp_path / "generated"
    shutil.copytree(GENERATED_DIR, generated)

    ok, errors = check_variants(SHOWCASE_DIR, generated)
    assert ok, errors

    victim = generated / "room4p_3421-640.webp"
    original = victim.read_bytes()
    victim.write_bytes(original[:-8] + b"STALE123")
    ok, errors = check_variants(SHOWCASE_DIR, generated)
    assert not ok
    assert any("Stale or non-deterministic" in error or "Error validating" in error for error in errors)

    victim.write_bytes(original)
    (generated / "unexpected.webp").write_bytes(b"unexpected")
    ok, errors = check_variants(SHOWCASE_DIR, generated)
    assert not ok
    assert "Unexpected variant: unexpected.webp" in errors


def test_ux22_generate_all_honors_custom_directories(tmp_path):
    showcase = tmp_path / "showcase"
    generated = tmp_path / "generated"
    showcase.mkdir()
    shutil.copy2(SHOWCASE_DIR / "room2p_222.jpg", showcase / "room2p_222.jpg")

    report = generate_all(showcase, generated)
    assert set(report) == {"room2p_222-640.avif", "room2p_222-640.webp"}
    assert sorted(path.name for path in generated.iterdir()) == sorted(report)
    ok, errors = check_variants(showcase, generated)
    assert ok, errors
