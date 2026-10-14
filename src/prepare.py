"""Τρέχει στο Mac: γεμίζει την ουρά με έτοιμα βίντεο (μοντάζ + κείμενα) για τις επόμενες μέρες
και τα ανεβάζει στο GitHub (branch "queue"). Από εκεί το GitHub κάνει τις αναρτήσεις.

  python src/prepare.py            # γεμίζει την ουρά (το τρέχει μόνο του το Mac κάθε μέρα)
  python src/prepare.py --one      # φτιάχνει μόνο ένα βίντεο (για δοκιμή)

Το κατέβασμα από το YouTube γίνεται ανώνυμα (χωρίς λογαριασμό/cookies), ένα-ένα με παύσεις.
"""
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("TRIFILLAKIA_DATA", Path.home() / "Library/Application Support/TrifillakiaAuto"))
QREPO = DATA / "queue-repo"
os.environ["TRIFILLAKIA_DATA"] = str(DATA)

import caption  # noqa: E402
import render  # noqa: E402
import source  # noqa: E402


def git(*args, cwd=ROOT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True).stdout.strip()


def notify(msg):
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Trifillakia"'], check=False)


def load_api_key():
    """Το κλειδί AI φυλάσσεται στο Keychain του Mac (βλ. README)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    key = subprocess.run(["security", "find-generic-password", "-s", "trifillakia-anthropic", "-w"],
                         capture_output=True, text=True).stdout.strip()
    if not key:
        sys.exit("Δεν βρέθηκε κλειδί AI στο Keychain (trifillakia-anthropic). Δες το README.")
    os.environ["ANTHROPIC_API_KEY"] = key


def open_queue_repo():
    """Τοπικό αντίγραφο του branch queue."""
    remote = git("remote", "get-url", "origin")
    if not (QREPO / ".git").exists():
        QREPO.mkdir(parents=True, exist_ok=True)
        git("init", "-q", cwd=QREPO)
        git("remote", "add", "origin", remote, cwd=QREPO)
        if git("ls-remote", "--heads", "origin", "queue", cwd=QREPO):
            git("fetch", "-q", "origin", "queue", cwd=QREPO)
            git("checkout", "-q", "-B", "queue", "FETCH_HEAD", cwd=QREPO)
        else:
            git("checkout", "-q", "--orphan", "queue", cwd=QREPO)
    manifest = QREPO / "manifest.json"
    return json.loads(manifest.read_text()) if manifest.exists() else []


def publish_queue(manifest):
    """Ένα μόνο commit (χωρίς ιστορικό) ώστε το repo να μη μεγαλώνει με τα παλιά βίντεο."""
    (QREPO / "manifest.json").write_text(json.dumps(manifest, indent=1))
    git("checkout", "-q", "--orphan", "queue-new", cwd=QREPO)
    git("add", "-A", cwd=QREPO)
    git("-c", "user.name=trifillakia-mac", "-c", "user.email=mac@users.noreply.github.com",
        "commit", "-q", "-m", f"Ουρά: {len(manifest)} βίντεο", cwd=QREPO)
    git("branch", "-D", "queue", cwd=QREPO, check=False)
    git("branch", "-m", "queue", cwd=QREPO)
    git("push", "-q", "-f", "origin", "queue", cwd=QREPO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", action="store_true")
    args = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    lock = open(DATA / "prepare.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("Τρέχει ήδη.")

    git("pull", "-q", "--rebase", "--autostash")  # φρέσκο ιστορικό αναρτήσεων + ρυθμίσεις
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    posted = set(json.loads((ROOT / "state/posted.json").read_text())["posted_ids"])

    manifest = open_queue_repo()
    # Βγάζουμε από την ουρά ό,τι έχει ήδη αναρτηθεί
    for item in [i for i in manifest if i in posted]:
        for ext in (".mp4", ".json"):
            (QREPO / f"{item}{ext}").unlink(missing_ok=True)
    manifest = [i for i in manifest if i not in posted]

    target = 1 if args.one else cfg["queue"]["days_ahead"] * len(cfg["schedule"]["slots"])
    need = max(0, target - len(manifest)) if not args.one else 1
    print(f"Στην ουρά: {len(manifest)} | στόχος: {target} | φτιάχνω: {need}")
    if need == 0:
        publish_queue(manifest)
        return

    load_api_key()
    made = 0
    for n in range(need):
        work = Path(tempfile.mkdtemp())
        try:
            info = source.pick_next(cfg, posted | set(manifest), catalog_limit=60 if n == 0 else 0)
            video, thumb = source.download(info, work)
            text = caption.generate(info, cfg)
            render.render(video, thumb, text["overlay_title"], QREPO / f"{info['id']}.mp4",
                          max_seconds=cfg["source"]["max_seconds"])
            (QREPO / f"{info['id']}.json").write_text(json.dumps({
                "source_title": info["title"],
                "overlay_title": text["overlay_title"],
                "youtube_title": text["youtube_title"],
                "full_description": text["full_description"],
                "confident": text.get("confident", True),
            }, ensure_ascii=False, indent=1))
            for f in QREPO.glob(f"{info['id']}_overlay.png"):
                f.unlink()
            manifest.append(info["id"])
            made += 1
            print(f"✓ {info['title']} → {text['overlay_title']}")
            if made % 3 == 0:  # ανεβάζουμε σταδιακά, για να είναι διαθέσιμα νωρίς
                publish_queue(manifest)
        except Exception as e:
            print(f"✗ σφάλμα: {e}")
            if "not a bot" in str(e):
                notify("Το YouTube ζήτησε παύση — συνεχίζω αργότερα.")
                break
        finally:
            shutil.rmtree(work, ignore_errors=True)

    publish_queue(manifest)
    notify(f"Έτοιμα {made} νέα βίντεο. Στην ουρά: {len(manifest)}.")


if __name__ == "__main__":
    main()
