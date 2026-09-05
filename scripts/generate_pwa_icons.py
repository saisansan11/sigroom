from pathlib import Path

from PIL import Image, ImageDraw


BACKGROUND = (11, 23, 33, 255)
SIGNAL_CYAN = (81, 216, 237, 255)
VIEWBOX_SIZE = 48


def generate_icon(size: int, output: Path) -> None:
    scale = 4
    canvas_size = size * scale
    image = Image.new("RGBA", (canvas_size, canvas_size), BACKGROUND)
    draw = ImageDraw.Draw(image)
    margin = canvas_size * 0.18
    mark_size = canvas_size * 0.64

    def point(x: int, y: int) -> tuple[int, int]:
        return (
            round(margin + (x / VIEWBOX_SIZE) * mark_size),
            round(margin + (y / VIEWBOX_SIZE) * mark_size),
        )

    stroke_width = max(1, round(mark_size * 3 / VIEWBOX_SIZE))
    draw.rounded_rectangle(
        (*point(2, 2), *point(46, 46)),
        radius=round(mark_size * 0.025),
        outline=SIGNAL_CYAN,
        width=stroke_width,
    )
    draw.line(
        [point(8, 30), point(15, 30), point(19, 18), point(24, 36), point(29, 24), point(33, 30), point(40, 30)],
        fill=SIGNAL_CYAN,
        width=stroke_width,
        joint="curve",
    )
    image.resize((size, size), Image.Resampling.LANCZOS).save(output, optimize=True)


output_dir = Path(__file__).resolve().parents[1] / "static" / "img"
for icon_size in (192, 512):
    generate_icon(icon_size, output_dir / f"pwa-icon-{icon_size}.png")
