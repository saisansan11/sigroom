"""Deterministic UX-22 media generator for /lodging/about/."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import sys
from typing import Dict, List, Tuple

from PIL import Image, ImageOps

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_DIR = WORKTREE_ROOT / "static" / "img" / "showcase"
GENERATED_DIR = SHOWCASE_DIR / "generated"

WEBP_QUALITY = 80
WEBP_METHOD = 6
AVIF_QUALITY = 65
PHOTO_STEMS = (
    "bath1",
    "bath2",
    "bath3",
    "room2p_222",
    "room2p_444",
    "room4p_3421",
    "room4p_4444",
)
PNG_STEMS = ("floor4", "floor5", "rates")
TARGET_WIDTHS = (640, 1280)


@dataclass(frozen=True)
class VariantSpec:
    stem: str
    source_filename: str
    filename: str
    target_width: int
    target_height: int
    fmt: str
    lossless: bool = False


def get_expected_variants(showcase_dir: Path = SHOWCASE_DIR) -> List[VariantSpec]:
    """Return the exact expected manifest without ever upscaling source media."""
    specs: List[VariantSpec] = []

    for stem in PHOTO_STEMS:
        source_filename = f"{stem}.jpg"
        source_path = showcase_dir / source_filename
        if not source_path.exists():
            continue
        with Image.open(source_path) as im:
            src_w, src_h = im.size
        for width in TARGET_WIDTHS:
            if width > src_w:
                continue
            height = round(src_h * (width / src_w))
            specs.append(
                VariantSpec(stem, source_filename, f"{stem}-{width}.avif", width, height, "AVIF")
            )
            specs.append(
                VariantSpec(stem, source_filename, f"{stem}-{width}.webp", width, height, "WEBP")
            )

    for stem in PNG_STEMS:
        source_filename = f"{stem}.png"
        source_path = showcase_dir / source_filename
        if not source_path.exists():
            continue
        with Image.open(source_path) as im:
            width, height = im.size
        specs.append(
            VariantSpec(stem, source_filename, f"{stem}.webp", width, height, "WEBP", lossless=True)
        )

    return specs


def _render_variant_bytes(source_path: Path, spec: VariantSpec) -> bytes:
    """Encode one expected variant in memory using the canonical deterministic settings."""
    with Image.open(source_path) as source:
        image = ImageOps.exif_transpose(source)

        if spec.lossless:
            if image.size != (spec.target_width, spec.target_height):
                raise ValueError(f"Lossless variant {spec.filename} must preserve intrinsic dimensions")
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            buffer = BytesIO()
            image.save(
                buffer,
                format="WEBP",
                lossless=True,
                method=WEBP_METHOD,
                exact=True,
            )
            return buffer.getvalue()

        if image.mode != "RGB":
            image = image.convert("RGB")
        if image.size != (spec.target_width, spec.target_height):
            image = image.resize(
                (spec.target_width, spec.target_height),
                Image.Resampling.LANCZOS,
            )

        buffer = BytesIO()
        if spec.fmt == "WEBP":
            image.save(
                buffer,
                format="WEBP",
                quality=WEBP_QUALITY,
                method=WEBP_METHOD,
            )
        elif spec.fmt == "AVIF":
            image.save(buffer, format="AVIF", quality=AVIF_QUALITY)
        else:
            raise ValueError(f"Unsupported format {spec.fmt}")
        return buffer.getvalue()


def generate_variant(source_path: Path, spec: VariantSpec, output_path: Path) -> int:
    """Generate one variant at the caller-supplied destination."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _render_variant_bytes(source_path, spec)
    output_path.write_bytes(payload)
    return len(payload)


def generate_all(
    showcase_dir: Path = SHOWCASE_DIR,
    generated_dir: Path = GENERATED_DIR,
) -> Dict[str, dict]:
    """Generate the complete manifest into generated_dir and return measured byte data."""
    generated_dir.mkdir(parents=True, exist_ok=True)
    report: Dict[str, dict] = {}

    for spec in get_expected_variants(showcase_dir):
        source_path = showcase_dir / spec.source_filename
        output_path = generated_dir / spec.filename
        original_size = source_path.stat().st_size
        variant_size = generate_variant(source_path, spec, output_path)
        report[spec.filename] = {
            "stem": spec.stem,
            "source_filename": spec.source_filename,
            "width": spec.target_width,
            "height": spec.target_height,
            "format": spec.fmt,
            "lossless": spec.lossless,
            "orig_size": original_size,
            "size": variant_size,
            "reduction_pct": (1.0 - variant_size / original_size) * 100.0,
        }

    return report


def check_variants(
    showcase_dir: Path = SHOWCASE_DIR,
    generated_dir: Path = GENERATED_DIR,
) -> Tuple[bool, List[str]]:
    """Detect missing, extra, corrupt, dimension/format, and stale generated media."""
    specs = get_expected_variants(showcase_dir)
    errors: List[str] = []
    expected_names = {spec.filename for spec in specs}
    actual_names = {path.name for path in generated_dir.iterdir() if path.is_file()} if generated_dir.exists() else set()

    for name in sorted(expected_names - actual_names):
        errors.append(f"Missing variant: {name}")
    for name in sorted(actual_names - expected_names):
        errors.append(f"Unexpected variant: {name}")

    for spec in specs:
        output_path = generated_dir / spec.filename
        if not output_path.exists():
            continue
        source_path = showcase_dir / spec.source_filename
        try:
            actual_bytes = output_path.read_bytes()
            expected_bytes = _render_variant_bytes(source_path, spec)
            if actual_bytes != expected_bytes:
                errors.append(f"Stale or non-deterministic variant: {spec.filename}")

            with Image.open(output_path) as generated:
                if generated.size != (spec.target_width, spec.target_height):
                    errors.append(
                        f"{spec.filename} size mismatch: expected "
                        f"{(spec.target_width, spec.target_height)}, got {generated.size}"
                    )
                if generated.format != spec.fmt:
                    errors.append(
                        f"{spec.filename} format mismatch: expected {spec.fmt}, got {generated.format}"
                    )

                if spec.lossless:
                    with Image.open(source_path) as source:
                        source_rgba = ImageOps.exif_transpose(source).convert("RGBA")
                        generated_rgba = generated.convert("RGBA")
                        if source_rgba.size != generated_rgba.size or source_rgba.tobytes() != generated_rgba.tobytes():
                            errors.append(f"Lossless pixel mismatch: {spec.filename}")
        except Exception as exc:
            errors.append(f"Error validating {spec.filename}: {exc}")

    return not errors, errors


def print_report(report: Dict[str, dict]) -> None:
    print(f"{'Filename':<24} {'Dimensions':<12} {'Orig (B)':<10} {'New (B)':<10} {'Savings':<10}")
    print("-" * 70)
    for name, data in sorted(report.items()):
        dims = f"{data['width']}x{data['height']}"
        print(
            f"{name:<24} {dims:<12} {data['orig_size']:<10} "
            f"{data['size']:<10} {data['reduction_pct']:>6.1f}%"
        )
    print("-" * 70)
    total_reference = sum(data["orig_size"] for data in report.values())
    total_generated = sum(data["size"] for data in report.values())
    reduction = (1.0 - total_generated / total_reference) * 100.0 if total_reference else 0.0
    print(f"Total generated variants: {len(report)}")
    print(f"Generated candidate bytes: {total_generated:,} B")
    print(f"Reference bytes for the same candidate set: {total_reference:,} B")
    print(f"Candidate-set byte reduction: {reduction:.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="UX-22 responsive media generator")
    parser.add_argument("--check", action="store_true", help="Verify the complete generated manifest without mutating it")
    args = parser.parse_args()

    if args.check:
        ok, errors = check_variants()
        if not ok:
            print("Variant check failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        print("All expected variants are present, exact, and current.")
        return 0

    print("Generating showcase media variants...")
    report = generate_all()
    print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
