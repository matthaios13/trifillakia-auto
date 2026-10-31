"""Αυτόματοι ελληνικοί υπότιτλοι για τα Shorts (χωρίς κόστος: faster-whisper στο GitHub).

  1. αναγνώριση ομιλίας (Whisper, ελληνικά, χρόνος ανά λέξη)
  2. διόρθωση ονομάτων (config.yaml → subtitles.glossary / replace)
  3. «καμένοι» υπότιτλοι karaoke μέσα στο πεδίο υποτίτλων του template
     (η λέξη που ακούγεται τονίζεται με χρώμα + μικρό «pop»)

Αν το βίντεο δεν έχει το πεδίο υποτίτλων του template, οι υπότιτλοι μπαίνουν σε δικό τους
σκούρο πλαίσιο στο κάτω-μεσαίο μέρος.
"""
import json
import re
import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "assets" / "fonts" / "FiraSansExtraCondensed-Black.ttf"
W, H = 1080, 1920
CARD = (60, 1067, 1020, 1297)          # πεδίο υποτίτλων του template Shorts (x0, y0, x1, y1)


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


# ---------------- 1. αναγνώριση ----------------

def transcribe(video, glossary, model_size="medium"):
    """Groq (Whisper large-v3, δωρεάν, όπως στο Μπάλα 24) αν υπάρχει GROQ_API_KEY· αλλιώς faster-whisper τοπικά."""
    import os
    if os.environ.get("GROQ_API_KEY", "").strip():
        try:
            return _groq(video, glossary)
        except Exception as e:
            print(f"  Groq απέτυχε ({e}) — τοπική αναγνώριση")
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    prompt = ", ".join(glossary) + "." if glossary else None
    segs, _ = model.transcribe(str(video), language="el", word_timestamps=True, vad_filter=True,
                               beam_size=5, initial_prompt=prompt, condition_on_previous_text=False)
    words = []
    for s in segs:
        for w in s.words or []:
            t = w.word.strip()
            if t:
                words.append({"start": w.start, "end": w.end, "text": t})
    return words


def _groq(video, glossary):
    import os, tempfile, requests
    audio = Path(tempfile.mkdtemp()) / "a.mp3"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(audio)], check=True)
    with open(audio, "rb") as fh:
        r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                          headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY'].strip()}"},
                          files={"file": ("a.mp3", fh, "audio/mpeg")},
                          data={"model": "whisper-large-v3", "language": "el", "response_format": "verbose_json",
                                "timestamp_granularities[]": "word", "temperature": "0",
                                "prompt": (", ".join(glossary) + ".")[:800] if glossary else ""},
                          timeout=300)
    r.raise_for_status()
    return [{"start": w["start"], "end": w["end"], "text": w["word"].strip()} for w in r.json().get("words", []) if w["word"].strip()]


# ---------------- 2. διορθώσεις ----------------

def _plain(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def fix_words(words, replace):
    """replace: {"λάθος": "σωστό"} ή {"δύο λέξεις": "σωστό"} — χωρίς τόνους/κεφαλαία, κρατά τη στίξη."""
    rep = {tuple(_plain(k).split()): v for k, v in (replace or {}).items()}
    longest = max((len(k) for k in rep), default=1)
    core = lambda t: re.match(r"^(\W*)(.*?)(\W*)$", t)
    out, i = [], 0
    while i < len(words):
        for n in range(min(longest, len(words) - i), 0, -1):
            seq = words[i:i + n]
            key = tuple(_plain(core(w["text"]).group(2)) for w in seq)
            if key in rep:
                first, last = core(seq[0]["text"]), core(seq[-1]["text"])
                out.append({"start": seq[0]["start"], "end": seq[-1]["end"],
                            "text": first.group(1) + rep[key] + last.group(3)})
                i += n
                break
        else:
            out.append(dict(words[i])); i += 1
    return out


HALLUCINATION_START = ("υποτιτλοι", "υποτιτλισμος", "subtitles", "subtitle", "authorwave", "amara", "υποτιτλους")
HALLUCINATION_PHRASES = (
    ("ευχαριστω", "που", "παρακολουθησατε"), ("ευχαριστω", "για", "την", "παρακολουθηση"),
    ("ευχαριστουμε", "που", "παρακολουθησατε"), ("μην", "ξεχασετε", "να", "κανετε", "subscribe"),
)


def drop_hallucinations(words):
    """Βγάζει φράσεις που «επινοεί» το Whisper σε σιωπή/μουσική (π.χ. «Υπότιτλοι AUTHORWAVE»)."""
    plain = [re.sub(r"\W", "", _plain(w["text"])) for w in words]
    keep = [True] * len(words)
    for i, p in enumerate(plain):
        if any(p.startswith(h) for h in HALLUCINATION_START):
            j = i
            # η φράση κρατά έως 6 λέξεις / 3 δευτερόλεπτα (π.χ. «Υπότιτλοι από την κοινότητα Amara.org»)
            while j < len(words) and j - i < 7 and words[j]["start"] - words[i]["start"] < 3.0:
                keep[j] = False
                if re.search(r"[.!?]$", words[j]["text"]):
                    break
                j += 1
        for ph in HALLUCINATION_PHRASES:
            if tuple(plain[i:i + len(ph)]) == ph:
                for k in range(i, i + len(ph)):
                    keep[k] = False
    return [w for w, k in zip(words, keep) if k]


def caps(s):
    """Κεφαλαία χωρίς τόνους (ελληνικός κανόνας), διαλυτικά μένουν."""
    s = unicodedata.normalize("NFD", s.upper())
    s = "".join(c for c in s if c not in "́̀͂")
    return unicodedata.normalize("NFC", s)


# ---------------- 3. ομαδοποίηση σε φράσεις ----------------

def chunks(words, max_chars=26, max_words=5, gap=0.55):
    out, cur = [], []
    for w in words:
        if cur:
            text_len = len(" ".join(x["text"] for x in cur + [w]))
            pause = w["start"] - cur[-1]["end"]
            if text_len > max_chars or len(cur) >= max_words or pause > gap or re.search(r"[.!?;·]$", cur[-1]["text"]):
                out.append(cur); cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def display(t):
    """Κεφαλαία χωρίς τόνους, χωρίς κόμματα/τελείες (όπως στο Total Basket)."""
    t = caps(t).replace("{", "(").replace("}", ")")
    return t.strip(",.;:·…\"«»") or t


def merge_hyphens(words):
    """«Πάλμερ» + «-Μπράουν» → «Πάλμερ-Μπράουν»."""
    out = []
    for w in words:
        if out and (w["text"].startswith("-") or out[-1]["text"].endswith("-")):
            out[-1] = {"start": out[-1]["start"], "end": w["end"], "text": out[-1]["text"] + w["text"]}
        else:
            out.append(dict(w))
    return out


def _font(px):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONT), px)


def _ass_time(t):
    t = max(0, t)
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _rrect(w, h, r):
    """Στρογγυλεμένο ορθογώνιο σε ASS drawing."""
    return (f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} l 0 {r} b 0 0 0 0 {r} 0")


def _fit(chunk_words, px, max_w):
    """Σπάει φράσεις που δεν χωράνε σε μία γραμμή."""
    f = _font(px); out = []
    for ch in chunk_words:
        cur = []
        for w in ch:
            trial = " ".join(caps(x["text"]) for x in cur + [w])
            if cur and f.getlength(trial) > max_w:
                out.append(cur); cur = []
            cur.append(w)
        if cur:
            out.append(cur)
    return out


def build_ass(words, path, box, box_col="&H3AF2B6&", box_txt="&H102802&"):
    """Στυλ Total Basket: μία γραμμή, 2-3 λέξεις, η λέξη που ακούγεται σε χρωματιστό κουτάκι.
    Χρώματα ASS σε BGR: &H3AF2B6& = lime #B6F23A, &H102802& = σκούρο πράσινο."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    px = 104
    max_w = (x1 - x0) - 110
    # Το libass ορίζει Fontsize = ascent+descent (όχι em όπως το PIL) → μετράμε στο ίδιο μέγεθος
    a0, d0 = _font(px).getmetrics()
    mpx = max(8, round(px * px / (a0 + d0)))
    f = _font(mpx)
    space = f.getlength(" ") * 2.6
    asc, desc = f.getmetrics()
    padx, pady = 14, 8
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Fira Sans Extra Condensed Black,{px},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,3,4,0,0,0,1
Style: Box,Fira Sans Extra Condensed Black,{px},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    all_ch = _fit(chunks(words, max_chars=24, max_words=3), mpx, max_w)
    last_end = 0.0                       # ποτέ δύο φράσεις μαζί στην οθόνη
    for ci, ch in enumerate(all_ch):
        texts = [display(w["text"]) for w in ch]
        widths = [f.getlength(t) for t in texts]
        total = sum(widths) + space * (len(texts) - 1)
        xs, x = [], cx - total / 2
        for wd in widths:
            xs.append(x); x += wd + space
        c_start = max(ch[0]["start"], last_end)
        c_end = ch[-1]["end"] + 0.25
        if ci + 1 < len(all_ch):
            c_end = min(c_end, all_ch[ci + 1][0]["start"])
        c_end = max(c_end, c_start + 0.12)
        bh = asc + desc + pady * 2
        for i in range(len(ch)):
            st = max(ch[i]["start"], last_end) if i else c_start
            en = min(max(ch[i + 1]["start"], st + 0.05), c_end) if i + 1 < len(ch) else c_end
            if en <= st:
                continue
            last_end = en
            T0, T1 = _ass_time(st), _ass_time(en)
            # κουτάκι πίσω από τη λέξη που ακούγεται (με μικρό «pop»)
            bw = widths[i] + padx * 2
            ev.append(f"Dialogue: 0,{T0},{T1},Box,,0,0,0,,{{\\an7\\pos({xs[i] - padx:.0f},{cy - bh / 2:.0f})"
                      f"\\1c{box_col}\\bord0\\shad0\\fscx106\\fscy106\\t(0,80,\\fscx100\\fscy100)\\p1}}{_rrect(bw, bh, 12)}")
            for j, t in enumerate(texts):
                col = f"\\1c{box_txt}\\shad0" if j == i else ""
                ev.append(f"Dialogue: 1,{T0},{T1},Sub,,0,0,0,,{{\\an4\\pos({xs[j]:.0f},{cy:.0f}){col}}}{t}")
    Path(path).write_text(hdr + "\n".join(ev) + "\n", encoding="utf-8")


# ---------------- ανίχνευση πεδίου υποτίτλων ----------------

def has_card(video):
    """Ελέγχει αν το βίντεο έχει το πεδίο υποτίτλων του template (πράσινη μπάρα αριστερά, σκούρο εσωτερικό)."""
    from PIL import Image
    import io
    png = subprocess.run([ffmpeg(), "-v", "error", "-ss", "1", "-i", str(video), "-frames:v", "1",
                          "-vf", f"scale={W}:{H}", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    if not png:
        return False
    im = Image.open(io.BytesIO(png)).convert("RGB")
    x0, y0, x1, y1 = CARD
    bar = [im.getpixel((67, y)) for y in range(y0 + 20, y1 - 20, 10)]
    bar_ok = sum(1 for r, g, b in bar if g > 170 and g > r and g > b + 40) >= len(bar) * 0.8
    inner = [im.getpixel((x, y)) for x in range(x0 + 60, x1 - 40, 60) for y in range(y0 + 30, y1 - 30, 40)]
    dark_ok = sum(1 for p in inner if max(p) < 90) >= len(inner) * 0.7
    return bar_ok and dark_ok


# ---------------- όλα μαζί ----------------

def burn(video, out, cfg_subs):
    """Επιστρέφει True αν μπήκαν υπότιτλοι (False αν δεν βρέθηκε ομιλία)."""
    glossary = cfg_subs.get("glossary", [])
    words = transcribe(video, glossary, cfg_subs.get("model", "medium"))
    words = fix_words(merge_hyphens(drop_hallucinations(words)), cfg_subs.get("replace", {}))
    if not words:
        return False
    card = has_card(video)
    box = CARD if card else (70, 1180, 1010, 1420)
    ass = Path(out).with_suffix(".ass")
    build_ass(words, ass, box)
    vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    if not card:   # δικό μας σκούρο πλαίσιο όταν δεν υπάρχει template
        x0, y0, x1, y1 = box
        vf += f",drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color=black@0.55:t=fill"
    font_dir = str(FONT.parent).replace("\\", "/").replace(":", "\\:")
    ass_p = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    vf += f",ass='{ass_p}':fontsdir='{font_dir}'"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vf", vf, "-c:v", "libx264", "-preset", "medium",
                    "-crf", "19", "-c:a", "copy", str(out)], check=True)
    Path(out).with_suffix(".json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return True


# ---------------- template εκπομπής (όταν το βίντεο δεν το έχει) ----------------

WIN = (36, 430, 1008, 567)              # παράθυρο βίντεο 16:9 του template (x, y, w, h)


def _frame(video, t=1.0):
    from PIL import Image
    import io
    png = subprocess.run([ffmpeg(), "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return Image.open(io.BytesIO(png)).convert("RGB") if png else None


def content_box(video):
    """Βρίσκει πού είναι η μετάδοση μέσα στο αρχείο. Στο κάθετο αρχείο του StreamYard η μετάδοση (16:9)
    είναι λωρίδα στη μέση με πράσινο γέμισμα πάνω-κάτω → επιστρέφει (x, y, w, h) της λωρίδας."""
    im = _frame(video, 2.0) or _frame(video, 0.5)
    if im is None:
        return None
    w, h = im.size
    if w >= h:                      # ήδη οριζόντιο
        return (0, 0, w, h)
    import numpy as np
    a = np.asarray(im).astype(float)
    v = np.abs(np.diff(a, axis=1)).mean(axis=(1, 2))      # λεπτομέρεια ανά γραμμή
    rows = np.where(v > 4)[0]
    if len(rows) == 0:
        return (0, 0, w, h)
    y0, y1 = int(rows.min()), int(rows.max())
    band = y1 - y0
    if band < h * 0.7:              # λωρίδα μετάδοσης → κρατάμε 16:9 γύρω της
        bh = int(round(w * 9 / 16)) // 2 * 2
        cy = (y0 + y1) / 2
        top = int(max(0, min(h - bh, y0 - 12 if band < bh else cy - bh / 2)))
        return (0, top // 2 * 2, w, bh)
    return (0, 0, w, h)


def apply_template(video, out, show_key, max_seconds=170):
    """Βάζει το βίντεο μέσα στο πλαίσιο του template της εκπομπής (assets/shorts_templates).
    Προτιμά το κινούμενο template (VP9 με διαφάνεια, loop 4") ώστε να κουνιούνται τα social εικονίδια."""
    base = ROOT / "assets" / "shorts_templates"
    key = show_key if (base / f"SHORTS_TEMPLATE_{show_key}.png").exists() else "TRIFILLAKIA"
    anim = base / f"SHORTS_TEMPLATE_{key}_animated.webm"
    if anim.exists():   # ο native vp9 decoder πετάει το alpha → libvpx-vp9
        tpl_in = ["-stream_loop", "-1", "-c:v", "libvpx-vp9", "-i", str(anim)]
    else:
        tpl_in = ["-loop", "1", "-i", str(base / f"SHORTS_TEMPLATE_{key}.png")]
    x, y, w, h = content_box(video)
    X, Y, VW, VH = WIN
    vf = (f"[0:v]crop={w}:{h}:{x}:{y},scale={VW}:{VH}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={VW}:{VH},setsar=1[clip];color=black:s={W}x{H}:r=30[bg];"
          f"[bg][clip]overlay={X}:{Y}:shortest=1[c1];[1:v]fps=30,format=rgba[tpl];"
          f"[c1][tpl]overlay=0:0:shortest=1,format=yuv420p[v]")
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-t", str(max_seconds), "-i", str(video), *tpl_in,
                    "-filter_complex", vf, "-map", "[v]", "-map", "0:a?", "-shortest", "-r", "30",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", str(out)], check=True)
    return out
