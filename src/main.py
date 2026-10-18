"""Αναρτήσεις (τρέχει στο GitHub): στις ώρες του config παίρνει το επόμενο έτοιμο βίντεο
από την ουρά (branch "queue", που τη γεμίζει το Mac με το prepare.py) και το ανεβάζει.

  python src/main.py --check   # γράφει due=true/false (για το workflow)
  python src/main.py           # ανάρτηση αν είναι ώρα
  python src/main.py --force   # ανάρτηση τώρα
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "posted.json"
QUEUE = ROOT / "queue"          # checkout του branch "queue"
LOW_QUEUE = 6                   # ειδοποίηση όταν μένουν τόσα ή λιγότερα


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"posted_ids": [], "log": []}


def save_state(state):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def load_cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text())


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


def pending(state):
    manifest = QUEUE / "manifest.json"
    if not manifest.exists():
        return []
    posted = set(state["posted_ids"])
    return [i for i in json.loads(manifest.read_text()) if i not in posted]


def public_url(item_id):
    """Δημόσιο link του βίντεο στο branch queue (το repository είναι δημόσιο)."""
    repo = os.environ.get("GITHUB_REPOSITORY", "matthaios13/trifillakia-auto")
    return f"https://raw.githubusercontent.com/{repo}/queue/{item_id}.mp4"


def fetch_video(item_id):
    """Μόνο για YouTube: κατεβάζει το αρχείο από το δημόσιο link."""
    import tempfile
    import requests
    path = Path(tempfile.mkdtemp()) / f"{item_id}.mp4"
    with requests.get(public_url(item_id), stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return path


def youtube_title(meta, cfg):
    """Τίτλος Shorts με «αγκίστρι» (βλ. titles.py) + τα hashtags του config στο τέλος."""
    import titles
    return titles.youtube_title(meta, cfg["publish"].get("youtube_title_hashtags", "").strip())


def from_queue_history(item_id, ext):
    """Παίρνει ένα αρχείο από το ιστορικό του branch queue (για βίντεο που έχουν ήδη αναρτηθεί)."""
    commits = subprocess.run(["git", "-C", str(QUEUE), "rev-list", "HEAD", "--", f"{item_id}{ext}"],
                             capture_output=True, text=True, check=True).stdout.split()
    for c in commits:
        r = subprocess.run(["git", "-C", str(QUEUE), "show", f"{c}:{item_id}{ext}"], capture_output=True)
        if r.returncode == 0:
            return r.stdout
    raise RuntimeError(f"Δεν βρέθηκε το {item_id}{ext} στο ιστορικό της ουράς")


def youtube_repost(cfg, state, item_id):
    import tempfile
    import publish
    entry = next((e for e in reversed(state["log"]) if e.get("source_id") == item_id and e.get("ok")), None)
    if not entry:
        sys.exit(f"Δεν βρέθηκε ανάρτηση για {item_id}")
    if entry.get("yt_id"):
        sys.exit(f"Έχει ήδη ανέβει στο YouTube: {entry['youtube']}")
    meta = json.loads(from_queue_history(item_id, ".json"))
    path = Path(tempfile.mkdtemp()) / f"{item_id}.mp4"
    path.write_bytes(from_queue_history(item_id, ".mp4"))
    pub = cfg["publish"]
    yt_id = publish.youtube_upload(path, youtube_title(meta, cfg), meta["full_description"],
                                   privacy="private", paid_promotion=pub.get("youtube_paid_promotion", True))
    entry.update(youtube=f"https://youtube.com/shorts/{yt_id}", yt_id=yt_id,
                 yt_uploaded=datetime.now(ZoneInfo("UTC")).isoformat(),
                 yt_state="pending" if pub.get("youtube_auto_public") else "private")
    print(f"YouTube (ιδιωτικό): {entry['youtube']}  ← {meta['source_title']}")


def open_issue(title, body):
    """Issue στο GitHub = email σε σένα."""
    if not os.environ.get("GITHUB_ACTIONS"):
        print(title, body)
        return
    subprocess.run(["gh", "issue", "create", "--title", title, "--body", body])


def review_youtube(cfg, state):
    """Ιδιωτικά βίντεο YouTube που ανέβηκαν πριν από ≥ N λεπτά: αν είναι καθαρά γίνονται δημόσια,
    αλλιώς μένουν ιδιωτικά και έρχεται ειδοποίηση."""
    pub = cfg["publish"]
    if not pub.get("youtube") or not pub.get("youtube_auto_public"):
        return False
    import publish
    now = datetime.now(ZoneInfo("UTC"))
    min_wait = timedelta(minutes=pub.get("youtube_review_minutes", 30))
    changed = False
    for e in state["log"]:
        if e.get("yt_state") != "pending":
            continue
        uploaded = datetime.fromisoformat(e["yt_uploaded"])
        if now - uploaded < min_wait:
            continue
        try:
            verdict, why = publish.youtube_check(e["yt_id"])
        except Exception as ex:
            print(f"YouTube έλεγχος {e['yt_id']}: σφάλμα {ex}")
            continue
        if verdict == "wait" and now - uploaded < timedelta(hours=48):
            print(f"YouTube {e['yt_id']}: {why} — ξανακοιτάζω αργότερα")
            continue
        if verdict == "ok":
            publish.youtube_make_public(e["yt_id"])
            e["yt_state"] = "public"
            print(f"YouTube {e['yt_id']}: καθαρό → ΔΗΜΟΣΙΟ")
        else:
            e["yt_state"] = "held"
            e["yt_reason"] = why
            open_issue(f"YouTube: έμεινε ιδιωτικό — {e['source_title']}",
                       f"Το βίντεο https://youtube.com/shorts/{e['yt_id']} δεν έγινε δημόσιο.\n"
                       f"Λόγος: {why}\n\nΔες το στο YouTube Studio → Περιεχόμενο.")
            print(f"YouTube {e['yt_id']}: ΚΡΑΤΙΕΤΑΙ ιδιωτικό ({why})")
        changed = True
    return changed


def notify_low_queue(left):
    """Ανοίγει issue στο GitHub (έρχεται email) όταν η ουρά αδειάζει."""
    if left > LOW_QUEUE or not os.environ.get("GITHUB_ACTIONS"):
        return
    title = "Η ουρά βίντεο αδειάζει — άνοιξε το Mac"
    open_issues = subprocess.run(["gh", "issue", "list", "--state", "open", "--search", title, "--json", "number"],
                                 capture_output=True, text=True).stdout
    if open_issues.strip() in ("", "[]"):
        subprocess.run(["gh", "issue", "create", "--title", title, "--body",
                        f"Έχουν μείνει {left} έτοιμα βίντεο. Άνοιξε το Mac για να ετοιμάσει καινούρια."])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--youtube-check", action="store_true")
    ap.add_argument("--youtube-repost", metavar="ID", help="ανέβασε στο YouTube ένα βίντεο που έχει ήδη βγει στο Instagram")
    ap.add_argument("--review-now", action="store_true", help="έλεγχος YouTube χωρίς αναμονή 30 λεπτών")
    args = ap.parse_args()

    cfg = load_cfg()
    state = load_state()
    if args.youtube_check:
        import publish
        print("Συνδεδεμένο κανάλι YouTube:", publish.youtube_channel())
        return
    if args.youtube_repost:
        youtube_repost(cfg, state, args.youtube_repost)
        save_state(state)
        return
    if args.review or args.review_now:
        if args.review_now:
            cfg["publish"]["youtube_review_minutes"] = 0
        if review_youtube(cfg, state):
            save_state(state)
        return
    now = datetime.now(ZoneInfo(cfg["schedule"]["timezone"]))
    slot = due_slot(cfg, state, now) if cfg.get("active") else None
    if args.force:
        slot = slot or now.strftime("%Y-%m-%d %H:%M") + " (manual)"

    if args.check:
        print(f"due={'true' if slot else 'false'}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"due={'true' if slot else 'false'}\n")
        return
    if not slot:
        print(f"{now:%H:%M} — δεν είναι ώρα ανάρτησης (ή active: false).")
        return

    queue = pending(state)
    if not queue:
        notify_low_queue(0)
        sys.exit("Η ουρά είναι άδεια — δεν υπάρχει έτοιμο βίντεο.")
    item_id = queue[0]
    meta = json.loads((QUEUE / f"{item_id}.json").read_text())
    video_url = public_url(item_id)
    print(f"[{slot}] {meta['source_title']} → {meta['youtube_title']}")

    import publish
    entry = {"slot": slot, "source_id": item_id, "source_title": meta["source_title"],
             "title": meta["youtube_title"], "ok": False}
    errors = []
    pub = cfg["publish"]
    if pub.get("youtube"):
        try:
            yt_id = publish.youtube_upload(
                fetch_video(item_id), youtube_title(meta, cfg), meta["full_description"],
                privacy="private", paid_promotion=pub.get("youtube_paid_promotion", True))
            entry.update(youtube=f"https://youtube.com/shorts/{yt_id}", yt_id=yt_id,
                         yt_uploaded=datetime.now(ZoneInfo("UTC")).isoformat(),
                         yt_state="pending" if pub.get("youtube_auto_public") else "private")
            print("YouTube (ιδιωτικό):", entry["youtube"])
        except Exception as e:  # συνεχίζουμε στο Instagram ακόμα κι αν αποτύχει το YouTube
            errors.append(f"YouTube: {e}")
    if pub.get("instagram"):
        try:
            ig_caption = f"{meta['youtube_title'].replace(' #shorts', '')}\n\n{meta['full_description']}"
            entry["instagram"] = publish.instagram_upload(video_url, ig_caption)
            print("Instagram:", entry["instagram"])
        except Exception as e:
            errors.append(f"Instagram: {e}")

    entry["ok"] = bool(entry.get("youtube") or entry.get("instagram"))
    entry["errors"] = errors
    if entry["ok"]:
        state["posted_ids"].append(item_id)
    state["log"].append(entry)
    save_state(state)
    notify_low_queue(len(queue) - (1 if entry["ok"] else 0))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)  # το GitHub στέλνει email όταν αποτυγχάνει κάτι


if __name__ == "__main__":
    main()
