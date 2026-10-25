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
os.environ["TRIFILLAKIA_DATA"] = str(DATA)

import caption  # noqa: E402
import render  # noqa: E402
import source  # noqa: E402


def git(*args, cwd=ROOT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True).stdout.strip()


def notify(msg):
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Trifillakia"'], check=False)


class Queue:
    """Η ουρά ζει ΜΟΝΟ στο GitHub (branch "queue"). Κάθε φορά κάνουμε ένα ελαφρύ αντίγραφο
    χωρίς τα βίντεο (μόνο τα .json), προσθέτουμε τα καινούρια και τα ανεβάζουμε.
    Στο Mac δεν μένει κανένα βίντεο."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="trifillakia-queue-"))
        remote = git("remote", "get-url", "origin")
        if git("ls-remote", "--heads", remote, "queue"):
            git("clone", "-q", "--filter=blob:none", "--no-checkout", "--single-branch", "-b", "queue",
                remote, str(self.dir))
            git("sparse-checkout", "set", "--no-cone", "/*.json", cwd=self.dir)
            git("checkout", "-q", "queue", cwd=self.dir)
        else:
            git("init", "-q", "-b", "queue", str(self.dir))
            git("remote", "add", "origin", remote, cwd=self.dir)
            git("sparse-checkout", "set", "--no-cone", "/*.json", cwd=self.dir)
        m = self.dir / "manifest.json"
        self.manifest = json.loads(m.read_text()) if m.exists() else []
        # Καθαρισμός: ό,τι δεν είναι έγκυρο έτοιμο βίντεο (π.χ. δοκιμαστικά αρχεία) φεύγει
        valid = []
        for item_id in self.manifest:
            meta = self.dir / f"{item_id}.json"
            if meta.exists() and "youtube_title" in json.loads(meta.read_text() or "{}"):
                valid.append(item_id)
        self.manifest = valid
        for meta in self.dir.glob("*.json"):
            if meta.name != "manifest.json" and meta.stem not in valid:
                self.manifest.append(meta.stem)
                self.remove(meta.stem)

    def remove(self, item_id):
        for ext in (".mp4", ".json"):
            git("rm", "-q", "--cached", "--sparse", "--ignore-unmatch", "--", f"{item_id}{ext}", cwd=self.dir)
            (self.dir / f"{item_id}{ext}").unlink(missing_ok=True)
        self.manifest.remove(item_id)

    def add(self, staged_mp4, meta):
        item_id = staged_mp4.stem
        shutil.move(str(staged_mp4), self.dir / staged_mp4.name)
        (self.dir / f"{item_id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        git("add", "--sparse", "--", staged_mp4.name, f"{item_id}.json", cwd=self.dir)
        (self.dir / staged_mp4.name).unlink()  # το βίντεο είναι πλέον μέσα στο git, σβήνουμε το αρχείο
        self.manifest.append(item_id)

    def push(self):
        (self.dir / "manifest.json").write_text(json.dumps(self.manifest, indent=1))
        git("add", "--sparse", "manifest.json", cwd=self.dir)
        if git("status", "--porcelain", cwd=self.dir):
            git("-c", "user.name=trifillakia-mac", "-c", "user.email=mac@users.noreply.github.com",
                "commit", "-q", "-m", f"Ουρά: {len(self.manifest)} βίντεο", cwd=self.dir)
            env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
            subprocess.run(["git", "push", "-q", "origin", "queue"], cwd=self.dir, check=True, env=env)
        # καθαρίζουμε τα αντικείμενα που ανέβηκαν ώστε να μη μένουν στον δίσκο
        git("gc", "-q", "--prune=now", cwd=self.dir, check=False)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


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

    before = git("rev-parse", "HEAD")
    git("pull", "-q", "--rebase", "--autostash")  # φρέσκο ιστορικό αναρτήσεων + ρυθμίσεις
    if git("rev-parse", "HEAD") != before:  # ήρθε νέος κώδικας: ξεκινάμε ξανά με αυτόν
        lock.close()
        os.execv(sys.executable, [sys.executable, *sys.argv])
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    posted = set(json.loads((ROOT / "state/posted.json").read_text())["posted_ids"])

    q = Queue()
    try:
        for item in [i for i in q.manifest if i in posted]:  # βγάζουμε ό,τι έχει αναρτηθεί
            q.remove(item)
        target = 1 if args.one else cfg["queue"]["days_ahead"] * len(cfg["schedule"]["slots"])
        need = 1 if args.one else max(0, target - len(q.manifest))
        print(f"Στην ουρά: {len(q.manifest)} | στόχος: {target} | φτιάχνω: {need}")
        made = 0
        for n in range(need):
            work = Path(tempfile.mkdtemp(prefix="trifillakia-work-"))
            try:
                info = source.pick_next(cfg, posted | set(q.manifest), catalog_limit=60 if n == 0 else 0)
                video, thumb = source.download(info, work)
                text = caption.generate(info, cfg)
                out = work / "out" / f"{info['id']}.mp4"
                out.parent.mkdir()
                render.render(video, thumb, text["overlay_title"], out, max_seconds=cfg["source"]["max_seconds"])
                q.add(out, {
                    "source_title": info["title"],
                    "overlay_title": text["overlay_title"],
                    "youtube_title": text["youtube_title"],
                    "full_description": text["full_description"],
                    "confident": text.get("confident", True),
                })
                made += 1
                print(f"✓ {info['title']} → {text['overlay_title']}")
                if made % 3 == 0:  # ανεβαίνουν σταδιακά ώστε να είναι διαθέσιμα νωρίς
                    q.push()
            except Exception as e:
                print(f"✗ σφάλμα: {e}")
                if "not a bot" in str(e):
                    notify("Το YouTube ζήτησε παύση — συνεχίζω στην επόμενη εκτέλεση.")
                    break
            finally:
                shutil.rmtree(work, ignore_errors=True)
        q.push()
        if made:
            notify(f"Έτοιμα {made} νέα βίντεο. Στην ουρά: {len(q.manifest)}.")
    finally:
        q.close()


if __name__ == "__main__":
    main()
