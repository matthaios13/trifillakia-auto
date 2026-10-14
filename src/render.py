"""Μοντάζ: φτιάχνει το κάθετο βίντεο 1080x1920 με το template του Trifillakia.

Διάταξη (όπως το template του PosterMyWall):
  - πάνω: φωτογραφία (thumbnail του βίντεο-πηγή)
  - μέση: πράσινη μπάρα με τον τίτλο
  - κάτω: το βίντεο ΟΛΟΚΛΗΡΟ σε πλάτος, ώστε να φαίνεται το λογότυπο της πηγής,
          με θολό φόντο από το ίδιο βίντεο
  - Elabet badge πάνω δεξιά, ΕΕΕΠ 21+ κάτω αριστερά, Trifillakia κάτω δεξιά
  - στο τέλος το outro της Elabet
"""
import subprocess
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

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


def build_overlay(photo_path, title, out_png):
    """Στατικό layer με διάφανη 'τρύπα' εκεί που παίζει το βίντεο."""
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    photo = trim_black(Image.open(photo_path).convert("RGB"))
    photo = ImageOps.fit(photo, (W, SPLIT_Y - LINE), Image.LANCZOS, centering=(0.5, 0.35))
    canvas.paste(photo, (0, LINE))

    draw.rectangle((0, 0, W, LINE - 1), fill=GREEN_LINE)
    draw.rectangle((0, SPLIT_Y, W, SPLIT_Y + LINE - 1), fill=GREEN_LINE)
    draw.rectangle((0, H - LINE, W, H), fill=GREEN_LINE)

    # Μπάρα τίτλου
    pad_x, pad_y, gap = 45, 14, 0
    font, lines = fit_title(greek_caps(title), BANNER_X[1] - BANNER_X[0] - 2 * pad_x)
    asc, desc = font.getmetrics()
    line_h = asc + desc
    text_h = len(lines) * line_h + (len(lines) - 1) * gap
    box_h = text_h + 2 * pad_y
    top = BANNER_CENTER_Y - box_h // 2
    draw.rounded_rectangle((BANNER_X[0], top, BANNER_X[1], top + box_h), radius=48, fill=BANNER_GREEN)
    y = top + pad_y
    for line in lines:
        x = (W - font.getlength(line)) / 2
        draw.text((x, y), line, font=font, fill="white")
        y += line_h + gap

    # Λογότυπα
    badge = Image.open(ASSETS / "elabet_badge.png").convert("RGBA")
    canvas.alpha_composite(badge, (1028 - badge.width, 58))
    eeep = Image.open(ASSETS / "eeep_21.png").convert("RGBA")
    canvas.alpha_composite(eeep, (40, 1800))
    logo = Image.open(ASSETS / "trifillakia_logo.png").convert("RGBA")
    canvas.alpha_composite(logo, (1025 - logo.width, 1800))

    canvas.save(out_png)


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


def render(video_path, photo_path, title, out_path, max_seconds=None):
    dur = probe_duration(video_path)
    if max_seconds:
        dur = min(dur, max_seconds)
    crop = detect_crop(video_path, dur)
    crop_f = f"crop={crop}," if crop else ""
    work = Path(out_path).with_suffix("")
    overlay_png = f"{work}_overlay.png"
    build_overlay(photo_path, title, overlay_png)

    outro = ASSETS / "outro.mp4"
    fc = (
        f"[0:v]{crop_f}fps=30,split[a][b];"
        f"[a]scale={W}:{VIDEO_H}:force_original_aspect_ratio=increase,crop={W}:{VIDEO_H},boxblur=25:2,eq=brightness=-0.08[bg];"
        f"[b]scale={W}:-2:flags=lanczos[fg];"
        f"color=black:s={W}x{H}:r=30:d={dur:.3f}[base];"
        f"[base][bg]overlay=0:{VIDEO_Y}:shortest=1[c1];"
        f"[c1][fg]overlay=0:{VIDEO_Y}+({VIDEO_H}-overlay_h)/2:shortest=1[c2];"
        f"[c2][1:v]overlay=0:0:shortest=1,setsar=1,format=yuv420p[main];"
        + (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f}[ma];" if has_audio(video_path)
           else f"anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f}[ma];") +
        f"[2:v]scale={W}:{H},fps=30,setsar=1,format=yuv420p[ov];"
        + (f"[2:a]aresample=48000,aformat=channel_layouts=stereo[oa];" if has_audio(outro)
           else f"anullsrc=r=48000:cl=stereo,atrim=0:{probe_duration(outro):.3f}[oa];") +
        f"[main][ma][ov][oa]concat=n=2:v=1:a=1[v][aout]"
    )
    cmd = [
        ffmpeg_exe(), "-v", "error", "-y",
        "-t", f"{dur:.3f}", "-i", str(video_path),
        "-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", overlay_png,
        "-i", str(outro),
        "-filter_complex", fc, "-map", "[v]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "faster", "-crf", "21", "-maxrate", "2500k", "-bufsize", "5M", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path


if __name__ == "__main__":
    # python src/render.py video.mp4 photo.jpg "Τίτλος" out.mp4
    render(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
