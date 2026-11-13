"""Βρίσκει και κατεβάζει το επόμενο ρετρό βίντεο από το κανάλι-πηγή."""
import random
import re
import shutil
import sys
from pathlib import Path

import yt_dlp


def _base_opts():
    # Χωρίς cookies/λογαριασμό: ανώνυμο κατέβασμα, ένα-ένα με παύσεις
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "sleep_interval_requests": 1}
    deno = shutil.which("deno") or str(Path(sys.executable).with_name("deno"))
    if Path(deno).exists():
        opts["js_runtimes"] = {"deno": {"path": deno}}
    return opts


def list_channel(channel_url):
    opts = {**_base_opts(), "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
    return [{"id": e["id"], "title": e.get("title", "")} for e in info.get("entries", []) if e]


def fetch_info(video_id):
    with yt_dlp.YoutubeDL(_base_opts()) as ydl:
        return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)


def pick_next(cfg, posted_ids, catalog_limit=40):
    """Διαλέγει με προτεραιότητα: νίκες πρώτα, μετά ευρωπαϊκά ματς (βλ. catalog.py)."""
    import catalog
    src = cfg["source"]
    # Ενημερώνει τον κατάλογο με όσα νέα βίντεο έχουν ανέβει (λίγα κάθε φορά)
    cat = catalog.update(list_channel(src["channel_url"]), fetch_info, limit=catalog_limit)
    # Η τρέχουσα σεζόν ξεκινά τον Ιούλιο. Εξαιρούμε τις πιο πρόσφατες σεζόν (δικαιώματα τηλεόρασης).
    from datetime import date
    today = date.today()
    current = today.year if today.month >= 7 else today.year - 1
    newest_allowed = current - src.get("exclude_recent_seasons", 1)
    candidates = [c for c in cat.values()
                  if c["id"] not in posted_ids and c.get("duration") and c["duration"] <= src["max_seconds"]
                  and c.get("season_start") and c["season_start"] <= newest_allowed]
    if not candidates:
        raise RuntimeError("Δεν βρέθηκε κατάλληλο βίντεο (όλα έχουν ανέβει ή είναι πολύ μεγάλα)")
    choice = _mix_pick(cat, candidates, posted_ids)
    print(f"Επιλογή: {choice['title']} | {choice['competition']} | {choice['result']} (κατηγορία {_kind(choice)})")
    return fetch_info(choice["id"])


# ---- Μείγμα: ντέρμπι, ευρωπαϊκά, σημαντικά ελληνικά, και από όλες τις εποχές (όχι μόνο τα πρόσφατα) ----
DERBY = ("ΟΛΥΜΠΙΑΚΟΣ", "ΑΕΚ", "ΠΑΟΚ", "ΑΡΗΣ")
# Σειρά εναλλαγής: κάθε επόμενο ρετρό από την επόμενη κατηγορία
PATTERN = ["derby", "euro", "greek_big", "derby", "euro", "greek"]


def _kind(c):
    import catalog
    t, comp = catalog._norm(c.get("title")), catalog._norm(c.get("competition"))
    if c.get("european"):
        return "euro"
    if any(re.search(rf"(^|[^Α-Ω]){d}([^Α-Ω]|$)", t) for d in DERBY) and not c.get("friendly"):
        return "derby"
    if "ΚΥΠΕΛΛ" in comp or "ΤΕΛΙΚ" in comp or "ΗΜΙΤΕΛ" in comp or "PLAY" in comp:
        return "greek_big"
    return "greek" if not c.get("friendly") else "other"


def _mix_pick(cat, candidates, posted_ids):
    posted = [cat[i] for i in posted_ids if i in cat]
    want = PATTERN[len(posted) % len(PATTERN)]
    # Νίκες (και ισοπαλίες στα ντέρμπι) πρώτα· αν δεν υπάρχει τίποτα στην κατηγορία, η επόμενη.
    order = PATTERN[PATTERN.index(want):] + PATTERN[:PATTERN.index(want)]
    for k in order + ["other"]:
        pool = [c for c in candidates if _kind(c) == k and c.get("outcome") == "W"]
        if not pool:
            continue
        # Από την εποχή (δεκαετία) που έχει ανέβει λιγότερο μέχρι τώρα → απλωνόμαστε σε όλα τα χρόνια.
        used = {}
        for c in posted:
            if c.get("season_start"):
                used[c["season_start"] // 5] = used.get(c["season_start"] // 5, 0) + 1
        least = min(used.get(c["season_start"] // 5, 0) for c in pool)
        return random.choice([c for c in pool if used.get(c["season_start"] // 5, 0) == least])
    return random.choice(candidates)


def download(info, workdir):
    from imageio_ffmpeg import get_ffmpeg_exe
    workdir = Path(workdir)
    opts = {
        **_base_opts(),
        "format": "bv*[height<=1080]+ba/b[height<=1080]",
        "merge_output_format": "mp4",
        "ffmpeg_location": get_ffmpeg_exe(),
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "writethumbnail": True,
        "postprocessors": [{"key": "FFmpegThumbnailsConvertor", "format": "jpg"}],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([info["webpage_url"]])
    return workdir / f"{info['id']}.mp4", workdir / f"{info['id']}.jpg"
