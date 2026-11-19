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

import basket  # noqa: E402
import caption  # noqa: E402
import render  # noqa: E402
import brand  # noqa: E402
import sansimera  # noqa: E402
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
        # μόνο ό,τι είναι staged: τα .mp4 που σβήσαμε από τον δίσκο φαίνονται «deleted» στο status
        if git("diff", "--cached", "--name-only", cwd=self.dir):
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
    ap.add_argument("--sport", choices=["football", "basketball", "sansimera"], default="football", help="με --one")
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
        def sport_of(i):
            f = q.dir / f"{i}.json"
            return json.loads(f.read_text()).get("sport", "football") if f.exists() else "football"
        from datetime import date, timedelta
        today = date.today()
        def meta_of(i):
            f = q.dir / f"{i}.json"
            return json.loads(f.read_text()) if f.exists() else {}
        for i in [i for i in q.manifest if sport_of(i) == "sansimera" and meta_of(i).get("air_date", "") < str(today)]:
            q.remove(i)   # «Σαν σήμερα» που πέρασε η μέρα του χωρίς να ανέβει
        have = {"football": 0, "basketball": 0, "sansimera": 0}
        for i in q.manifest:
            have[sport_of(i)] += 1
        ss = cfg.get("sansimera") or {}
        ss_days = set()
        if ss.get("active"):
            have_days = {meta_of(i).get("air_date") for i in q.manifest if sport_of(i) == "sansimera"}
            ss_days = [today + timedelta(days=k) for k in range(cfg["queue"]["days_ahead"])
                       if str(today + timedelta(days=k)) not in have_days]
        bk = cfg.get("basket") or {}
        days = cfg["queue"]["days_ahead"]
        targets = {"football": days * len(cfg["schedule"]["slots"]),
                   "basketball": days * len(bk.get("slots", [])) if bk.get("active") else 0}
        if args.one:
            jobs = [("sansimera", d) for d in ss_days][:1] if args.sport == "sansimera" else [args.sport]
        else:
            jobs = [("sansimera", d) for d in ss_days]   # πρώτα αυτά: είναι δεμένα με ημερομηνία
            nf = max(0, targets["football"] - have["football"])
            nb = max(0, targets["basketball"] - have["basketball"])
            # εναλλάξ, ώστε να γεμίζουν και οι δύο ουρές ταυτόχρονα
            while nf or nb:
                if nf:
                    jobs.append("football"); nf -= 1
                if nb:
                    jobs.append("basketball"); nb -= 1
        print(f"Στην ουρά: ποδόσφαιρο {have['football']}/{targets['football']}, "
              f"μπάσκετ {have['basketball']}/{targets['basketball']}, σαν σήμερα {have['sansimera']} | φτιάχνω: {len(jobs)}")
        made = 0
        first_fb = True
        for sport in jobs:
            day = None
            if isinstance(sport, tuple):
                sport, day = sport
            work = Path(tempfile.mkdtemp(prefix="trifillakia-work-"))
            try:
                if sport == "sansimera":
                    c, label = sansimera.pick(cfg, day, posted | set(q.manifest))
                    if not c:
                        print(f"– {day}: δεν βρέθηκε «Σαν σήμερα»")
                        continue
                    info = source.fetch_info(c["id"])
                    video, thumb = source.download(info, work)
                    text = sansimera.texts(c, label, cfg)
                    max_s = cfg["source"]["max_seconds"]
                elif sport == "basketball":
                    info = basket.pick_next(cfg, posted | set(q.manifest))
                    video, thumb = source.download(info, work)
                    text = basket.generate(info, cfg)
                    max_s = bk.get("max_seconds", 170)
                else:
                    info = source.pick_next(cfg, posted | set(q.manifest), catalog_limit=60 if first_fb else 0)
                    first_fb = False
                    video, thumb = source.download(info, work)
                    text = caption.generate(info, cfg)
                    max_s = cfg["source"]["max_seconds"]
                out = work / "out" / f"{info['id']}.mp4"
                out.parent.mkdir()
                render.render(video, thumb, text["card"], out, max_seconds=max_s, sponsor=brand.sponsor(cfg))
                meta = {
                    "source_title": info["title"],
                    "overlay_title": text["overlay_title"],
                    "youtube_title": text["youtube_title"],
                    "full_description": text["full_description"],
                    "confident": text.get("confident", True),
                    "sport": sport,
                    "sponsor": brand.sponsor(cfg),   # Elabet μέσα στο βίντεο;
                }
                if sport in ("basketball", "sansimera"):
                    meta["fixed_title"] = True  # ο τίτλος είναι ήδη έτοιμος (basket.py / sansimera.py)
                if sport == "sansimera":
                    meta.update(air_date=str(day), label=label, match_date=c["date"])
                q.add(out, meta)
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
