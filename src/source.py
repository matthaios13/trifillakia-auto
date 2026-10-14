"""Βρίσκει και κατεβάζει το επόμενο ρετρό βίντεο από το κανάλι-πηγή."""
import random
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
    best = min(c["rank"] for c in candidates)
    choice = random.choice([c for c in candidates if c["rank"] == best])
    print(f"Επιλογή: {choice['title']} | {choice['competition']} | {choice['result']} (προτεραιότητα {best})")
    return fetch_info(choice["id"])


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
