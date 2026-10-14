"""Κύριο πρόγραμμα: ελέγχει αν είναι ώρα για ανάρτηση και κάνει όλη τη δουλειά.

  python src/main.py            # κανονική λειτουργία (από το GitHub Actions)
  python src/main.py --force    # ανάρτηση τώρα, αγνοώντας το ωράριο
  python src/main.py --dry-run  # φτιάχνει βίντεο + κείμενο χωρίς να ανεβάσει τίποτα
"""
import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import caption  # noqa: E402
import publish  # noqa: E402
import render  # noqa: E402
import source  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "posted.json"


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"posted_ids": [], "log": []}


def save_state(state):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def due_slot(cfg, state, now):
    """Επιστρέφει το slot (π.χ. '2026-10-14 14:00') που πρέπει να γίνει τώρα, ή None."""
    sch = cfg["schedule"]
    done = {e["slot"] for e in state["log"] if e.get("ok")}
    for hhmm in reversed(sch["slots"]):
        h, m = map(int, hhmm.split(":"))
        slot_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
        key = slot_time.strftime("%Y-%m-%d %H:%M")
        if slot_time <= now < slot_time + timedelta(hours=sch["grace_hours"]) and key not in done:
            return key
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    state = load_state()
    now = datetime.now(ZoneInfo(cfg["schedule"]["timezone"]))
    slot = due_slot(cfg, state, now)
    if args.force or args.dry_run:
        slot = slot or now.strftime("%Y-%m-%d %H:%M") + " (manual)"
    if not slot:
        print(f"{now:%H:%M} — δεν είναι ώρα ανάρτησης.")
        return

    info = source.pick_next(cfg, set(state["posted_ids"]))
    print(f"[{slot}] Βίντεο: {info['title']} ({info['id']}, {info['duration']}s)")

    work = Path(tempfile.mkdtemp())
    video, thumb = source.download(info, work)
    text = caption.generate(info, cfg)
    print("Τίτλος μπάρας:", text["overlay_title"])
    print("Τίτλος YouTube:", text["youtube_title"])
    if not text.get("confident", True):
        print("⚠️ Το AI δεν είναι σίγουρο για τα στοιχεία του αγώνα — έλεγξε την περιγραφή.")

    out = ROOT / "output" / f"{info['id']}.mp4"
    out.parent.mkdir(exist_ok=True)
    render.render(video, thumb, text["overlay_title"], out, max_seconds=cfg["source"]["max_seconds"])
    (out.with_suffix(".txt")).write_text(
        f"{text['youtube_title']}\n\n{text['full_description']}\n", encoding="utf-8")
    print("Βίντεο έτοιμο:", out)

    if args.dry_run:
        return

    entry = {"slot": slot, "source_id": info["id"], "source_title": info["title"],
             "title": text["youtube_title"], "ok": False}
    errors = []
    pub = cfg["publish"]
    if pub.get("youtube"):
        try:
            entry["youtube"] = publish.youtube_upload(
                out, text["youtube_title"], text["full_description"],
                privacy=pub.get("youtube_privacy", "private"),
                paid_promotion=pub.get("youtube_paid_promotion", True))
            print("YouTube:", entry["youtube"])
        except Exception as e:  # συνεχίζουμε στο Instagram ακόμα κι αν αποτύχει το YouTube
            errors.append(f"YouTube: {e}")
    if pub.get("instagram"):
        try:
            ig_caption = f"{text['youtube_title'].replace(' #shorts', '')}\n\n{text['full_description']}"
            entry["instagram"] = publish.instagram_upload(out, ig_caption)
            print("Instagram:", entry["instagram"])
        except Exception as e:
            errors.append(f"Instagram: {e}")

    entry["ok"] = bool(entry.get("youtube") or entry.get("instagram"))
    entry["errors"] = errors
    if entry["ok"]:
        state["posted_ids"].append(info["id"])
    state["log"].append(entry)
    save_state(state)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)  # το GitHub στέλνει email όταν αποτυγχάνει κάτι


if __name__ == "__main__":
    main()
