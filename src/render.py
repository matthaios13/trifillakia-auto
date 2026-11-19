"""Μοντάζ PAO Retro (Trifillakia): κάθετο 1080x1920, μοντέρνο template.

  ┌──────────────────────────────┐
  │ (σήμα) PAO RETRO      [Elabet]│  Elabet μόνο με sponsor=True (μετά την έγκριση ΕΕΕΠ)
  │        ΙΣΤΟΡΙΚΕΣ ΣΤΙΓΜΕΣ      │
  │ ╭──────────────────────────╮ │
  │ │          ΒΙΝΤΕΟ          │ │  κάρτα με στρογγυλές γωνίες, πράσινο πλαίσιο με
  │ ╰──────────────────────────╯ │  φως που γυρίζει αργά γύρω-γύρω (1 γύρος / 12'')
  │ [1985-86 · ΠΡΩΤΑΘΛΗΜΑ]        │
  │ ΤΡΙΠΟΝΤΟ!  / ΣΑΝ ΣΗΜΕΡΑ       │
  │ ┌ ΠΑΝΑΘΗΝΑΪΚΟΣ          3 ┐   │
  │ └ ΠΑΝΑΧΑΪΚΗ             0 ┘   │
  │          Trifillakia.gr       │
  └──────────────────────────────┘
Στο τέλος: outro Elabet (sponsor=True) ή κάρτα PAO Retro 2,5''.
"""
import subprocess
import sys
import unicodedata
from pathlib import Path

import math
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

W, H = 1080, 1920
GREEN_LINE = (16, 186, 104)
BANNER_GREEN = (1, 75, 28)
LINE = 10                      # πάχος πράσινων γραμμών
SPLIT_Y = 813                  # γραμμή ανάμεσα σε φωτογραφία και βίντεο
VIDEO_Y = SPLIT_Y + LINE       # αρχή περιοχής βίντεο
VIDEO_H = H - LINE - VIDEO_Y   # ύψος περιοχής βίντεο
BANNER_CENTER_Y = 760
BANNER_X = (30, 1050)
RETRO_SIZE = 230               # σήμα PAO Retro
ENDCARD_SECONDS = 3.5


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def greek_caps(text):
    """Κεφαλαία χωρίς τόνους (κρατάει τα διαλυτικά: ΠΑΝΑΘΗΝΑΪΚΟΣ)."""
    out = unicodedata.normalize("NFD", text.upper())
    out = "".join(ch for ch in out if ch not in ("́", "̀", "͂"))
    return unicodedata.normalize("NFC", out)


def load_font(size):
    f = ImageFont.truetype(str(ASSETS / "Alegreya.ttf"), size)
    f.set_variation_by_name("ExtraBold")
    return f


def wrap(text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_title(text, max_w, max_lines=2):
    for size in range(84, 44, -2):
        font = load_font(size)
        lines = wrap(text, font, max_w)
        if len(lines) <= max_lines and all(font.getlength(l) <= max_w for l in lines):
            return font, lines
    return font, lines


def trim_black(img, thresh=28):
    """Κόβει μαύρες μπάρες γύρω από το thumbnail."""
    mask = img.convert("L").point(lambda v: 255 if v > thresh else 0)
    bbox = mask.getbbox()
    if bbox and (bbox[2] - bbox[0]) > img.width * 0.4 and (bbox[3] - bbox[1]) > img.height * 0.4:
        return img.crop(bbox)
    return img



# ------------------------------------------------------------------ μοντέρνο template
GREEN = (16, 186, 104)
NEON = (90, 255, 140)
CARD_X, CARD_W, CARD_Y, RAD = 40, 1000, 300, 36
LAP_SECONDS = 12            # ένας πλήρης γύρος του φωτός (αργά, να μη μπερδεύει)
FPS = 30
CACHE = Path(os.environ.get("TRIFILLAKIA_DATA", ROOT.parent)) / "cache"


def fira(size):
    return ImageFont.truetype(str(ASSETS / "FiraSansExtraCondensed-Black.ttf"), size)


def fit_font(draw, text, max_w, start, minimum=40):
    for s in range(start, minimum - 1, -2):
        if draw.textlength(text, font=fira(s)) <= max_w:
            return fira(s)
    return fira(minimum)


def card_height(aspect):
    """Ύψος κάρτας βίντεο: 16:9 → 563, 4:3 → 750 (μέγιστο)."""
    return int(min(750, max(480, round(CARD_W / aspect))))


def background():
    """Καθαρό σκούρο πράσινο (όχι θολό) με ακτίνες προβολέων και διακριτικές γραμμές γηπέδου."""
    f = CACHE / "bg_v1.png"
    if f.exists():
        return Image.open(f).convert("RGBA")
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(6 + 8 * (1 - k)), int(48 - 26 * k), int(24 - 12 * k)))
    bg = bg.convert("RGBA")
    rays = Image.new("RGBA", (W, H))
    rd = ImageDraw.Draw(rays)
    for x0, ang in ((-200, 62), (1280, 118)):
        for i in range(5):
            a = math.radians(ang + i * 7 - 14)
            rd.polygon([(x0, -100), (x0 + 2600 * math.cos(a) - 60, -100 + 2600 * math.sin(a)),
                        (x0 + 2600 * math.cos(a) + 60, -100 + 2600 * math.sin(a))], fill=(140, 255, 180, 10))
    bg.alpha_composite(rays.filter(ImageFilter.GaussianBlur(18)))
    pl = Image.new("RGBA", (W, H))
    pd = ImageDraw.Draw(pl)
    pd.ellipse((W / 2 - 330, 1300, W / 2 + 330, 1960), outline=(255, 255, 255, 16), width=4)
    pd.line([(0, 1630), (W, 1630)], fill=(255, 255, 255, 16), width=4)
    bg.alpha_composite(pl)
    noise = Image.effect_noise((W, H), 18).convert("L").point(lambda v: int(v * 0.06))
    bg = Image.composite(Image.new("RGBA", (W, H), (255, 255, 255, 255)), bg, noise)
    CACHE.mkdir(parents=True, exist_ok=True)
    bg.save(f)
    return bg


def build_card_overlay(card, ch, out_png, sponsor=False):
    """Όλο το στατικό layer, με διάφανη «τρύπα» (στρογγυλές γωνίες) εκεί που παίζει το βίντεο.
    card: hook, chip, home, away, hs, as."""
    c = background()
    d = ImageDraw.Draw(c)
    hole = Image.new("L", (W, H), 255)
    ImageDraw.Draw(hole).rounded_rectangle((CARD_X, CARD_Y, CARD_X + CARD_W, CARD_Y + ch), RAD, fill=0)
    c.putalpha(hole)
    # σταθερό πράσινο περίγραμμα + απαλή λάμψη
    ring = Image.new("RGBA", (W, H))
    ImageDraw.Draw(ring).rounded_rectangle((CARD_X - 4, CARD_Y - 4, CARD_X + CARD_W + 4, CARD_Y + ch + 4),
                                           RAD + 4, outline=GREEN + (255,), width=6)
    c.alpha_composite(ring.filter(ImageFilter.GaussianBlur(10)))
    c.alpha_composite(ring)
    d = ImageDraw.Draw(c)
    # κεφαλίδα
    logo = Image.open(ASSETS / "pao_retro_logo.png").convert("RGBA").resize((170, 170), Image.LANCZOS)
    c.alpha_composite(logo, (56, 60))
    d.text((246, 88), "PAO RETRO", font=fira(64), fill="white")
    d.text((248, 160), "ΙΣΤΟΡΙΚΕΣ ΣΤΙΓΜΕΣ", font=fira(36), fill=GREEN)
    if sponsor:  # θέση Elabet: πάνω δεξιά
        badge = Image.open(ASSETS / "elabet_badge.png").convert("RGBA")
        c.alpha_composite(badge, (1028 - badge.width, 86))
    y = CARD_Y + ch + 50
    text_w = W - 140
    if card.get("stamp"):  # «ΣΑΝ ΣΗΜΕΡΑ»: σφραγίδα δεξιά από ετικέτα και τίτλο
        st = stamp(card["stamp"]["lines"], card["stamp"]["year"], size=260)
        c.alpha_composite(st, (W - st.width - 30, y - 20))
        d = ImageDraw.Draw(c)
        text_w = W - 140 - st.width
    # ετικέτα (σεζόν/ημερομηνία · διοργάνωση)
    chip = greek_caps(card.get("chip", ""))
    if chip:
        cf = fit_font(d, chip, text_w - 60, 40, 24)
        cw = d.textlength(chip, font=cf)
        d.rounded_rectangle((70, y, 70 + cw + 56, y + 68), 34, fill=GREEN)
        d.text((98, y + 34), chip, font=cf, fill=(3, 30, 14), anchor="lm")
        y += 90
    hook = greek_caps(card["hook"])
    hf = fit_font(d, hook, text_w, 150 if ch < 700 else 120, 60)
    d.text((66, y), hook, font=hf, fill="white")
    y += int(hf.size * 1.08) + 20
    # καρτέλα σκορ
    rows = [(card["home"], card.get("hs", "")), (card["away"], card.get("as", ""))]
    box_h = 250
    sc = Image.new("RGBA", (W, H))
    ImageDraw.Draw(sc).rounded_rectangle((56, y, W - 56, y + box_h), 40, fill=(0, 0, 0, 70),
                                         outline=GREEN + (140,), width=3)
    c.alpha_composite(sc)
    d = ImageDraw.Draw(c)
    pao_first = "ΠΑΝΑΘΗΝΑ" in greek_caps(card["home"])
    for i, (team, goals) in enumerate(rows):
        ty = y + 40 + i * 100
        team = greek_caps(team)
        tf = fit_font(d, team, W - 330, 72, 44)
        hi = (i == 0) == pao_first
        d.text((110, ty + 36), team, font=tf, fill="white" if hi else (200, 215, 205), anchor="lm")
        d.text((W - 110, ty + 36), str(goals), font=fira(72), fill=GREEN if hi else (200, 215, 205), anchor="rm")
    d.line([(110, y + box_h / 2), (W - 110, y + box_h / 2)], fill=(255, 255, 255, 50), width=2)
    # υποσέλιδο
    tl = Image.open(ASSETS / "trifillakia_logo.png").convert("RGBA")
    if sponsor:
        eeep = Image.open(ASSETS / "eeep_21.png").convert("RGBA")
        c.alpha_composite(eeep, (40, 1790))
        c.alpha_composite(tl, (1025 - tl.width, 1800))
    else:
        c.alpha_composite(tl, ((W - tl.width) // 2, 1760))
    d.rectangle((0, H - 8, W, H), fill=GREEN)
    c.save(out_png)


def stamp(lines, year, size=270):
    """Σφραγίδα «ΣΑΝ ΣΗΜΕΡΑ» (ρετρό, κρεμ/χρυσό με πράσινα γράμματα), λίγο στραβή σαν σφραγισμένη."""
    S = size * 3
    im = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(im)
    CREAM, GOLD, DK = (241, 231, 200, 255), (214, 182, 104, 255), (6, 52, 24, 255)
    d.ellipse((6, 6, S - 6, S - 6), fill=CREAM)
    d.ellipse((S * .05, S * .05, S * .95, S * .95), outline=DK, width=int(S * .025))
    d.ellipse((S * .1, S * .1, S * .9, S * .9), outline=GOLD, width=int(S * .012))
    for k in range(36):  # οδοντωτή άκρη σαν σφραγίδα
        a = math.radians(k * 10)
        x, y = S / 2 + S * .485 * math.cos(a), S / 2 + S * .485 * math.sin(a)
        d.ellipse((x - S * .018, y - S * .018, x + S * .018, y + S * .018), fill=(0, 0, 0, 0))
    fs = int(S * 0.2)
    while fs > 20 and max(fira(fs).getlength(l) for l in lines) > S * 0.6:
        fs -= 4
    f = fira(fs)
    total = len(lines) * fs * 0.95
    y = S * .44 - total / 2
    for l in lines:
        d.text((S / 2, y + fs * .45), l, font=f, fill=DK, anchor="mm")
        y += fs * 0.95
    d.rounded_rectangle((S * .26, S * .66, S * .74, S * .80), S * .05, fill=GREEN + (255,))
    d.text((S / 2, S * .73), str(year), font=fira(int(S * .12)), fill="white", anchor="mm")
    d.text((S / 2, S * .18), "PAO RETRO", font=fira(int(S * .07)), fill=DK, anchor="mm")
    im = im.rotate(12, resample=Image.BICUBIC, expand=False)
    sh = Image.new("RGBA", (S, S))
    sh.putalpha(im.getchannel("A").point(lambda v: v * 0.55))
    sh = sh.filter(ImageFilter.GaussianBlur(S * .02))
    out = Image.new("RGBA", (S + 40, S + 40))
    out.alpha_composite(sh, (30, 34))
    out.alpha_composite(im, (10, 10))
    return out.resize((size + 13, size + 13), Image.LANCZOS)


def _perimeter(x0, y0, w, h, r, n=1400):
    L = 2 * (w + h - 4 * r) + 2 * math.pi * r
    q = math.pi * r / 2
    pts = []
    for i in range(n):
        t = i / n * L
        for seg in range(8):
            ln = (w - 2 * r) if seg in (0, 4) else (h - 2 * r) if seg in (2, 6) else q
            if t <= ln or seg == 7:
                break
            t -= ln
        if seg == 0:
            pts.append((x0 + r + t, y0))
        elif seg == 2:
            pts.append((x0 + w, y0 + r + t))
        elif seg == 4:
            pts.append((x0 + w - r - t, y0 + h))
        elif seg == 6:
            pts.append((x0, y0 + h - r - t))
        else:
            cx, cy, a0 = {1: (x0 + w - r, y0 + r, -math.pi / 2), 3: (x0 + w - r, y0 + h - r, 0),
                          5: (x0 + r, y0 + h - r, math.pi / 2), 7: (x0 + r, y0 + r, math.pi)}[seg]
            a = a0 + t / r
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


PAD = 60   # περιθώριο γύρω από την κάρτα για τη λάμψη


def border_anim(ch):
    """Κινούμενο πλαίσιο (2 «κομήτες» φωτός, αντικριστά). Φτιάχνεται μία φορά ανά ύψος κάρτας (cache)."""
    out = CACHE / f"border_{ch}_v1.mov"
    if out.exists():
        return out
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = CACHE / f"border_{ch}_frames"
    tmp.mkdir(exist_ok=True)
    rw, rh = W, ch + 2 * PAD
    P = _perimeter(CARD_X - 4, PAD - 4, CARD_W + 8, ch + 8, RAD + 4)
    N = len(P)
    frames = LAP_SECONDS * FPS // 2          # με 2 κομήτες η κίνηση επαναλαμβάνεται κάθε μισό γύρο
    for f in range(frames):
        lay = Image.new("RGBA", (rw, rh))
        ld = ImageDraw.Draw(lay)
        for h0 in (0, N // 2):
            head = (h0 + int(f / (LAP_SECONDS * FPS) * N)) % N
            for k in range(240):
                x, y = P[(head - k) % N]
                a = 1 - k / 240
                r = 9 * a + 3
                ld.ellipse((x - r, y - r, x + r, y + r), fill=NEON + (int(255 * a),))
        glow = lay.filter(ImageFilter.GaussianBlur(16))
        fr = Image.new("RGBA", (rw, rh))
        fr.alpha_composite(glow)
        fr.alpha_composite(glow)
        fr.alpha_composite(lay)
        fr.save(tmp / f"{f:04d}.png")
    subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-framerate", str(FPS), "-i", str(tmp / "%04d.png"),
                    "-c:v", "qtrle", "-pix_fmt", "argb", str(out)], check=True)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return out


SOCIAL = [("instagram", "trifillakiagr"), ("facebook", "trifillakia.gr"), ("youtube", "trifillakia_gr"),
          ("x", "trifillakiagr")]


def social_icon(kind, size=150):
    """Εικονίδια Instagram / Facebook / YouTube / X (ζωγραφισμένα, χωρίς εξωτερικά αρχεία)."""
    S = size * 4
    im = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(im)
    r = S * 0.24
    if kind == "instagram":
        g = Image.new("RGBA", (S, S))
        gd = ImageDraw.Draw(g)
        c0, c1, c2 = (254, 218, 117), (214, 41, 118), (79, 91, 213)
        for i in range(S * 2):  # διαγώνιο gradient κίτρινο → ροζ → μωβ
            t = i / (S * 2)
            c = [int(c0[j] + (c1[j] - c0[j]) * t * 2) for j in range(3)] if t < 0.5 else \
                [int(c1[j] + (c2[j] - c1[j]) * (t - 0.5) * 2) for j in range(3)]
            gd.line([(i, S), (i - S, 0)], fill=tuple(c) + (255,), width=2)
        m = Image.new("L", (S, S))
        ImageDraw.Draw(m).rounded_rectangle((0, 0, S - 1, S - 1), r, fill=255)
        im.paste(g, (0, 0), m)
        w = int(S * 0.075)
        d.rounded_rectangle((S * .2, S * .2, S * .8, S * .8), S * .17, outline="white", width=w)
        d.ellipse((S * .35, S * .35, S * .65, S * .65), outline="white", width=w)
        d.ellipse((S * .66, S * .27, S * .74, S * .35), fill="white")
    elif kind == "facebook":
        d.rounded_rectangle((0, 0, S - 1, S - 1), r, fill=(24, 119, 242))
        f = ImageFont.truetype(str(ASSETS / "FiraSansExtraCondensed-Black.ttf"), int(S * 0.85))
        d.text((S * .55, S * .62), "f", font=f, fill="white", anchor="mm")
    elif kind == "youtube":
        d.rounded_rectangle((0, 0, S - 1, S - 1), r, fill=(255, 0, 0))
        d.polygon([(S * .38, S * .3), (S * .38, S * .7), (S * .72, S * .5)], fill="white")
    else:  # X
        d.rounded_rectangle((0, 0, S - 1, S - 1), r, fill=(0, 0, 0), outline=(70, 70, 70), width=int(S * .02))
        w = int(S * .07)
        d.polygon([(S * .26, S * .24), (S * .40, S * .24), (S * .74, S * .76), (S * .60, S * .76)], fill="white")
        d.line([(S * .72, S * .24), (S * .29, S * .76)], fill="white", width=w // 2)
    return im.resize((size, size), Image.LANCZOS)


def build_endcard(out_png):
    """Κάρτα τέλους: PAO Retro + Trifillakia + FOLLOW US με τα social."""
    c = background().copy()
    d = ImageDraw.Draw(c)
    d.rectangle((0, 0, W, LINE - 1), fill=GREEN_LINE)
    d.rectangle((0, H - LINE, W, H), fill=GREEN_LINE)
    retro = Image.open(ASSETS / "pao_retro_logo.png").convert("RGBA").resize((520, 520), Image.LANCZOS)
    c.alpha_composite(retro, ((W - 520) // 2, 220))
    t = "ΚΑΘΕ ΜΕΡΑ ΣΤΟ"
    d.text((W / 2, 830), t, font=fira(64), fill="white", anchor="mm")
    logo = Image.open(ASSETS / "trifillakia_logo.png").convert("RGBA")
    logo = logo.resize((int(logo.width * 1.9), int(logo.height * 1.9)), Image.LANCZOS)
    c.alpha_composite(logo, ((W - logo.width) // 2, 890))
    d.text((W / 2, 1210), "FOLLOW US", font=fira(96), fill=GREEN, anchor="mm")
    hf = ImageFont.truetype(str(ASSETS / "FiraSansExtraCondensed-Black.ttf"), 36)
    for i, (kind, handle) in enumerate(SOCIAL):
        cx = int(W * (i + 0.5) / len(SOCIAL))
        ic = social_icon(kind, 150)
        c.alpha_composite(ic, (cx - 75, 1310))
        d.text((cx, 1500), handle, font=hf, fill="white", anchor="mm")
    c.convert("RGB").save(out_png)


def probe_duration(path):
    """Διάρκεια σε δευτερόλεπτα (από την έξοδο του ffmpeg -i)."""
    import re
    r = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    h, mi, se = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(se)


def has_audio(path):
    r = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True)
    return "Audio:" in r.stderr


def detect_crop(path, dur):
    """Βρίσκει μαύρες μπάρες (π.χ. παλιό 4:3 μέσα σε 16:9) για να κοπούν."""
    import re
    from collections import Counter
    r = subprocess.run(
        [ffmpeg_exe(), "-ss", str(min(2, dur / 4)), "-t", "20", "-i", str(path),
         "-vf", "fps=2,cropdetect=limit=24:round=2:reset=1", "-f", "null", "-"],
        capture_output=True, text=True)
    found = re.findall(r"crop=(\d+:\d+:\d+:\d+)", r.stderr)
    return Counter(found).most_common(1)[0][0] if found else None


def render(video_path, photo_path, card, out_path, max_seconds=None, sponsor=False):
    """card: dict (hook, chip, home, away, hs, as). photo_path δεν χρησιμοποιείται πια (μένει για συμβατότητα)."""
    dur = probe_duration(video_path)
    if max_seconds:
        dur = min(dur, max_seconds)
    crop = detect_crop(video_path, dur)
    crop_f = f"crop={crop}," if crop else ""
    if crop:
        cw_, ch_ = map(int, crop.split(":")[:2])
    else:
        r = subprocess.run([ffmpeg_exe(), "-i", str(video_path)], capture_output=True, text=True)
        m = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", r.stderr)
        cw_, ch_ = (int(m[1]), int(m[2])) if m else (16, 9)
    ch = card_height(cw_ / ch_)
    work = Path(out_path).with_suffix("")
    ov = f"{work}_card.png"
    build_card_overlay(card, ch, ov, sponsor)
    border = border_anim(ch)

    end_png = f"{work}_end.png"
    build_endcard(end_png)
    extra_in = ["-loop", "1", "-framerate", "30", "-t", str(ENDCARD_SECONDS), "-i", end_png]
    tail_f = (f"[3:v]fps=30,setsar=1,format=yuv420p,fade=t=in:st=0:d=0.4[ev];"
              f"anullsrc=r=48000:cl=stereo,atrim=0:{ENDCARD_SECONDS}[ea];")
    segs, n = "[main][ma][ev][ea]", 2
    if sponsor:  # μετά την κάρτα, το outro της Elabet
        outro = ASSETS / "outro.mp4"
        extra_in += ["-i", str(outro)]
        tail_f += f"[4:v]scale={W}:{H},fps=30,setsar=1,format=yuv420p[ov];" + (
            f"[4:a]aresample=48000,aformat=channel_layouts=stereo[oa];" if has_audio(outro)
            else f"anullsrc=r=48000:cl=stereo,atrim=0:{probe_duration(outro):.3f}[oa];")
        segs, n = segs + "[ov][oa]", 3
    fc = (
        f"[0:v]{crop_f}fps=30,scale={CARD_W}:{ch}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={CARD_W}:{ch},setsar=1[v0];"
        f"color=black:s={W}x{H}:r=30:d={dur:.3f}[base];"
        f"[base][v0]overlay={CARD_X}:{CARD_Y}:shortest=1[c1];"
        f"[c1][1:v]overlay=0:0:shortest=1[c2];"
        f"[c2][2:v]overlay=0:{CARD_Y - PAD}:shortest=1,setsar=1,format=yuv420p[main];"
        + (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f}[ma];" if has_audio(video_path)
           else f"anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f}[ma];")
        + tail_f +
        f"{segs}concat=n={n}:v=1:a=1[v][aout]"
    )
    cmd = [
        ffmpeg_exe(), "-v", "error", "-y",
        "-t", f"{dur:.3f}", "-i", str(video_path),
        "-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", ov,
        "-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", str(border),
        *extra_in,
        "-filter_complex", fc, "-map", "[v]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "faster", "-crf", "21", "-maxrate", "2500k", "-bufsize", "5M", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path


