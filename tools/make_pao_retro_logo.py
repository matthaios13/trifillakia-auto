"""Φτιάχνει το σήμα PAO Retro (assets/pao_retro_logo.png): στρογγυλό, ρετρό, με τριφύλλι.
python tools/make_pao_retro_logo.py"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

A = Path(__file__).resolve().parent.parent / "assets"
S = 4                      # supersampling
N = 600                    # τελικό μέγεθος
Z = N * S
CREAM = (241, 231, 200, 255)
GOLD = (214, 182, 104, 255)
DARK = (6, 52, 24, 255)
MID = (10, 92, 42, 255)
BRIGHT = (16, 186, 104, 255)
FIRA = str(A / "FiraSansExtraCondensed-Black.ttf")


def f(size):
    return ImageFont.truetype(FIRA, size * S)


def circle(d, r, **kw):
    c = Z / 2
    d.ellipse((c - r, c - r, c + r, c + r), **kw)


def shamrock(d, cx, cy, r, fill):
    for ang in (-90, 30, 150):
        a = math.radians(ang)
        for side in (-1, 1):  # κάθε φύλλο = δύο κύκλοι (καρδιά)
            b = a + side * 0.42
            x, y = cx + math.cos(b) * r * 0.95, cy + math.sin(b) * r * 0.95
            d.ellipse((x - r * 0.62, y - r * 0.62, x + r * 0.62, y + r * 0.62), fill=fill)
        x, y = cx + math.cos(a) * r * 1.25, cy + math.sin(a) * r * 1.25
        d.polygon([(cx, cy), (x + math.cos(a + 1.57) * r * 0.55, y + math.sin(a + 1.57) * r * 0.55),
                   (x - math.cos(a + 1.57) * r * 0.55, y - math.sin(a + 1.57) * r * 0.55)], fill=fill)
    d.ellipse((cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35), fill=fill)
    d.line([(cx, cy), (cx + r * 0.55, cy + r * 1.7)], fill=fill, width=int(r * 0.22))


def arc_text(img, text, radius, size, fill, start_deg, bottom=False, spacing=1.0):
    """Κείμενο γύρω από τον κύκλο (πάνω: δεξιόστροφα, κάτω: ανάποδα ώστε να διαβάζεται)."""
    font = f(size)
    widths = [font.getlength(ch) * spacing for ch in text]
    total = sum(widths)
    ang = math.degrees(total / radius)
    cur = start_deg - ang / 2 if not bottom else start_deg + ang / 2
    for ch, w in zip(text, widths):
        step = math.degrees(w / radius)
        mid = cur + step / 2 if not bottom else cur - step / 2
        t = Image.new("RGBA", (int(w * 2 + 40), int(size * S * 2)), (0, 0, 0, 0))
        ImageDraw.Draw(t).text((t.width / 2, t.height / 2), ch, font=font, fill=fill, anchor="mm")
        rot = -(mid + 90) if not bottom else -(mid - 90)
        t = t.rotate(rot, resample=Image.BICUBIC, expand=True)
        x = Z / 2 + radius * math.cos(math.radians(mid)) - t.width / 2
        y = Z / 2 + radius * math.sin(math.radians(mid)) - t.height / 2
        img.alpha_composite(t, (int(x), int(y)))
        cur = cur + step if not bottom else cur - step


def main():
    img = Image.new("RGBA", (Z, Z), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    R = Z / 2 - 6 * S
    # σκιά
    sh = Image.new("RGBA", (Z, Z), (0, 0, 0, 0))
    circle(ImageDraw.Draw(sh), R, fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6 * S)))
    circle(d, R, fill=CREAM)                       # εξωτερικό κρεμ δαχτυλίδι
    circle(d, R - 12 * S, fill=DARK)               # ζώνη με κείμενο
    circle(d, R - 74 * S, fill=CREAM)              # λεπτή κρεμ γραμμή
    circle(d, R - 80 * S, fill=MID)                # εσωτερικός δίσκος
    # ακτίνες «ήλιου» ρετρό στον εσωτερικό δίσκο
    rays = Image.new("RGBA", (Z, Z), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for k in range(24):
        a0, a1 = math.radians(k * 15), math.radians(k * 15 + 7.5)
        rd.polygon([(Z / 2, Z / 2), (Z / 2 + Z * math.cos(a0), Z / 2 + Z * math.sin(a0)),
                    (Z / 2 + Z * math.cos(a1), Z / 2 + Z * math.sin(a1))], fill=(255, 255, 255, 14))
    mask = Image.new("L", (Z, Z), 0)
    circle(ImageDraw.Draw(mask), R - 80 * S, fill=255)
    img.paste(Image.alpha_composite(img, rays), (0, 0), mask)
    d = ImageDraw.Draw(img)
    # κείμενα στο δαχτυλίδι
    ring_r = R - 43 * S
    arc_text(img, "ΙΣΤΟΡΙΑ · ΘΡΥΛΟΙ · ΑΝΑΜΝΗΣΕΙΣ", ring_r, 34, CREAM, -90, spacing=1.12)
    arc_text(img, "ΑΠΟ ΤΟ 1908", ring_r, 34, GOLD, 90, bottom=True, spacing=1.18)
    # τριφύλλι πάνω
    shamrock(d, Z / 2, Z / 2 - 140 * S, 34 * S, BRIGHT)
    # PAO
    d.text((Z / 2, Z / 2 + 6 * S), "PAO", font=f(170), fill=CREAM, anchor="mm",
           stroke_width=5 * S, stroke_fill=DARK)
    # κορδέλα RETRO
    by, bh, bw = Z / 2 + 112 * S, 76 * S, 380 * S
    tail = 46 * S
    for side in (-1, 1):  # άκρες κορδέλας
        x0 = Z / 2 + side * (bw / 2 - 10 * S)
        x1 = x0 + side * tail
        d.polygon([(x0, by - bh / 2 + 18 * S), (x1, by - bh / 2 + 18 * S), (x1 - side * 18 * S, by + 18 * S),
                   (x1, by + bh / 2 + 18 * S), (x0, by + bh / 2 + 18 * S)], fill=(140, 110, 50, 255))
    d.rounded_rectangle((Z / 2 - bw / 2, by - bh / 2, Z / 2 + bw / 2, by + bh / 2), radius=10 * S, fill=GOLD,
                        outline=CREAM, width=4 * S)
    d.text((Z / 2, by + 2 * S), "R E T R O", font=f(64), fill=DARK, anchor="mm")
    img.resize((N, N), Image.LANCZOS).save(A / "pao_retro_logo.png")
    print("✓", A / "pao_retro_logo.png")


if __name__ == "__main__":
    main()
