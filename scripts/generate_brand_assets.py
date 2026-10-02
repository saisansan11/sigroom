"""สร้างไฟล์โลโก้ที่ปรับขนาดแล้วจากชุดต้นฉบับ SIGROOM_Web_Assets (raster) ลง static/img/brand/

ใช้: uv run python scripts/generate_brand_assets.py <โฟลเดอร์ต้นฉบับ>
ต้นฉบับเป็น PNG/WebP แบบโปร่งใส จึงสร้างเฉพาะขนาดที่หน้าเว็บใช้จริง (ไม่ใช้ไฟล์ใหญ่เต็มขนาด)
"""
import sys
from pathlib import Path

from PIL import Image

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\RTA\Downloads\SIGROOM_Web_Assets")
OUT = Path(__file__).resolve().parents[1] / "static" / "img" / "brand"
OUT.mkdir(parents=True, exist_ok=True)
PAPER = (245, 241, 230, 255)


def load(name):
    return Image.open(SRC / name).convert("RGBA")


def fit_w(im, w):
    return im.resize((w, round(im.height * w / im.width)), Image.Resampling.LANCZOS)


def save(im, name, **kw):
    path = OUT / name
    if name.endswith(".webp"):
        im.save(path, "WEBP", quality=kw.get("quality", 88), method=6)
    else:
        im.save(path, "PNG", optimize=True)
    print(f"{name} {im.size} {path.stat().st_size}")


horizontal = load("sigroom-logo-horizontal-transparent.png")
for w, tag in ((108, "1x"), (216, "2x")):
    im = fit_w(horizontal, w)
    save(im, f"sigroom-logo-horizontal-{tag}.webp")
    save(im, f"sigroom-logo-horizontal-{tag}.png")

stacked = load("sigroom-logo-stacked-transparent.png")
box = stacked.getchannel("A").getbbox()
stacked = stacked.crop(box)
for w in (480, 960):
    im = fit_w(stacked, w)
    save(im, f"sigroom-logo-stacked-{w}.webp", quality=86)
save(fit_w(stacked, 480), "sigroom-logo-stacked-480.png")

mark = load("sigroom-mark-transparent.png")
mark = mark.crop(mark.getchannel("A").getbbox())
side = max(mark.size)
sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
sq.paste(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
for w in (128, 256):
    save(sq.resize((w, w), Image.Resampling.LANCZOS), f"sigroom-mark-{w}.webp")

# favicon / PWA
for n in (32, 64):
    save(load(f"sigroom-favicon-{n}.png"), f"favicon-{n}.png")
f512 = load("sigroom-favicon-512-transparent.png")
ico_src = Image.open(SRC / "sigroom-favicon-64.png").convert("RGBA")
ico_src.save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
print("favicon.ico", (OUT / "favicon.ico").stat().st_size)

light = load("sigroom-app-icon-light-512.png")
save(light, "pwa-icon-512.png")
save(light.resize((192, 192), Image.Resampling.LANCZOS), "pwa-icon-192.png")
# iOS เติมพื้นดำให้ PNG โปร่งใส จึงใช้ไอคอนพื้นขาวแทนเวอร์ชันโปร่งใส
save(light.resize((180, 180), Image.Resampling.LANCZOS), "apple-touch-icon-180.png")

# maskable: โลโก้ (ไอคอนโปร่งใส) ย่อให้อยู่ใน safe zone 80% บนพื้นกระดาษ
mask = Image.new("RGBA", (512, 512), PAPER)
glyph = f512.crop(f512.getchannel("A").getbbox())
target = int(512 * 0.64)  # เนื้อโลโก้ไม่เกิน ~64% ของด้านกว้าง เผื่อขอบตัดวงกลม
scale = target / max(glyph.size)
glyph = glyph.resize((round(glyph.width * scale), round(glyph.height * scale)), Image.Resampling.LANCZOS)
mask.alpha_composite(glyph, ((512 - glyph.width) // 2, (512 - glyph.height) // 2))
save(mask, "pwa-icon-maskable-512.png")
