"""Shorts από κοινόχρηστο φάκελο Google Drive → YouTube Shorts + Instagram Reels (τρέχει στο GitHub).

Ο φάκελος (DRIVE_FOLDER_ID) έχει έναν υποφάκελο ανά εκπομπή (βλ. config.yaml → drive_shorts.shows).
Όποιος ρίχνει ένα βίντεο (π.χ. από το PosterMyWall) σε υποφάκελο εκπομπής:
  1. προστίθεται στο τέλος το outro της Elabet (assets/outro.mp4), όπως στα retro
  2. ανεβαίνει ΑΜΕΣΩΣ στο Instagram (Reel) και στο YouTube (ιδιωτικό → έλεγχος copyright → δημόσιο)
  3. τίτλος = όνομα αρχείου, hashtags: #elabet #elaoposeisai #<εκπομπή> #trifillakiagr + ποδόσφαιρο/μπάσκετ
  4. το αρχείο μετακινείται στο «✅ Ανέβηκαν» (ή στο «⚠️ Σφάλμα» + email αν κάτι πάει στραβά)

  python src/drive_shorts.py --check    # γράφει found=true/false (γρήγορο, για το workflow)
  python src/drive_shorts.py            # επεξεργασία + ανάρτηση
"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parent.parent
DONE_NAME = "✅ Ανέβηκαν"
FAIL_NAME = "⚠️ Σφάλμα"
VIDEO_MIME = ("video/",)
MIN_AGE = timedelta(minutes=2)          # περιμένουμε να ολοκληρωθεί το ανέβασμα στο Drive
UPLOAD_BRANCH = "drive-upload"          # προσωρινό δημόσιο link για το Instagram


# ---------------- Drive ----------------

def drive():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
        client_id=os.environ["YT_CLIENT_ID"].strip(), client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def children(svc, folder_id, folders=None):
    q = f"'{folder_id}' in parents and trashed = false"
    if folders is True:
        q += " and mimeType = 'application/vnd.google-apps.folder'"
    elif folders is False:
        q += " and mimeType != 'application/vnd.google-apps.folder'"
    out, token = [], None
    while True:
        r = svc.files().list(q=q, fields="nextPageToken, files(id,name,mimeType,createdTime,modifiedTime,size,lastModifyingUser(displayName))",
                             pageToken=token, pageSize=200, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        out += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            return out


def ensure_folder(svc, parent, name):
    for f in children(svc, parent, folders=True):
        if f["name"] == name:
            return f["id"]
    return svc.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]},
                              fields="id", supportsAllDrives=True).execute()["id"]


def move(svc, file_id, old_parent, new_parent, new_name=None):
    body = {"name": new_name} if new_name else {}
    svc.files().update(fileId=file_id, addParents=new_parent, removeParents=old_parent, body=body,
                       fields="id", supportsAllDrives=True).execute()


def download(svc, file_id, path):
    from googleapiclient.http import MediaIoBaseDownload
    with io.FileIO(path, "wb") as fh:
        dl = MediaIoBaseDownload(fh, svc.files().get_media(fileId=file_id, supportsAllDrives=True), chunksize=16 << 20)
        done = False
        while not done:
            _, done = dl.next_chunk()


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return unicodedata.normalize("NFC", "".join(c for c in s if not unicodedata.combining(c)))


def pending_files(svc, root_id, shows_cfg):
    """[(file, show_key, show_folder_id)] για βίντεο που περιμένουν σε υποφακέλους εκπομπών."""
    now = datetime.now(timezone.utc)
    by_name = {_norm(v["folder"]): k for k, v in shows_cfg.items()}
    found = []
    for sub in children(svc, root_id, folders=True):
        key = by_name.get(_norm(sub["name"]))
        if not key:
            continue
        for f in children(svc, sub["id"], folders=False):
            if not f["mimeType"].startswith(VIDEO_MIME):
                continue
            mod = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
            if now - mod >= MIN_AGE:
                found.append((f, key, sub["id"]))
    return sorted(found, key=lambda x: x[0]["createdTime"])


# ---------------- κείμενα ----------------

FOOTBALL_WORDS = ("ποδοσφαιρ", "football", "paofc", "pao fc", " fc", "γκολ", "νιστρουπ", "neestrup", "λεωφορ",
                  "superleague", "super league", "conference", "europa league", "champions league")
BASKET_WORDS = ("μπασκετ", "basket", "paobc", "pao bc", " bc", "euroleague", "ευρωλιγκ", "aktor", "ομπραντοβιτ",
                "obradovic", "ζοτς", "καλαθ")


def sport_of(title, show_sport):
    t = f" {_norm(title)} "
    fb = any(w in t for w in FOOTBALL_WORDS)
    bk = any(w in t for w in BASKET_WORDS)
    if fb and not bk:
        return "football"
    if bk and not fb:
        return "basketball"
    return show_sport if show_sport in ("football", "basketball") else "both"


def clean_title(filename):
    t = Path(filename).stem
    t = re.sub(r"\s*-\s*Made with PosterMyWall.*$", "", t, flags=re.I)
    t = re.sub(r"\s*\(\d+\)$", "", t)                       # «(2)» από διπλά κατεβάσματα
    t = re.sub(r"[_]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–")
    return t or "Trifillakia.gr"


def texts(title, show_key, cfg):
    dc = cfg["drive_shorts"]
    show = dc["shows"][show_key]
    sport = sport_of(title, show.get("sport", "both"))
    tags = ["#elabet", "#elaoposeisai", show["hashtag"], "#trifillakiagr"]
    tags += dc["sport_hashtags"][sport].split()
    seen, uniq = set(), []
    for t in tags:
        if t and t.lower() not in seen:
            seen.add(t.lower()); uniq.append(t)
    hashtags = " ".join(uniq)
    yt_tail = f"#elaoposeisai #shorts {show['hashtag']}"
    room = 100 - len(yt_tail) - 1
    t = title if len(title) <= room else title[:room].rsplit(" ", 1)[0].rstrip(" ,-–:") + "…"
    yt_title = f"{t} {yt_tail}"
    head = f"☘️ {title}"
    show_line = f"🎙️ Από την εκπομπή «{show['name']}» του Trifillakia.gr" if show_key != "TRIFILLAKIA" else "🎙️ Trifillakia.gr"
    full = "\n\n".join([head, show_line, dc.get("follow", "").strip(), cfg.get("footer", ""), hashtags])
    full = re.sub(r"\n{3,}", "\n\n", full).strip()
    return yt_title, full, sport


# ---------------- μοντάζ ----------------

def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(path):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
    return dur, "Audio:" in r.stderr


def add_outro(src, out, max_seconds):
    """Κάθετο 1080x1920 (με θολό φόντο αν το βίντεο δεν είναι κάθετο) + outro Elabet στο τέλος."""
    W, H = 1080, 1920
    outro = ROOT / "assets" / "outro.mp4"
    dur, has_a = probe(src)
    dur = min(dur, max_seconds)
    odur, o_has_a = probe(outro)
    fc = (
        f"[0:v]fps=30,split[a][b];"
        f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:2,eq=brightness=-0.08[bg];"
        f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[main];"
        + (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[ma];" if has_a
           else f"anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f}[ma];")
        + f"[1:v]scale={W}:{H},fps=30,setsar=1,format=yuv420p[ov];"
        + (f"[1:a]aresample=48000,aformat=channel_layouts=stereo[oa];" if o_has_a
           else f"anullsrc=r=48000:cl=stereo,atrim=0:{odur:.3f}[oa];")
        + "[main][ma][ov][oa]concat=n=2:v=1:a=1[v][aout]"
    )
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-t", f"{dur:.3f}", "-i", str(src), "-i", str(outro),
                    "-filter_complex", fc, "-map", "[v]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
                    "-profile:v", "high", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
    return dur


# ---------------- δημόσιο link για το Instagram ----------------

def publish_temp_link(path, name):
    """Βάζει το βίντεο μόνο του σε orphan branch (force push) και επιστρέφει raw link."""
    repo = os.environ.get("GITHUB_REPOSITORY", "matthaios13/trifillakia-auto")
    work = Path(tempfile.mkdtemp())
    def git(*a):
        subprocess.run(["git", *a], cwd=work, check=True, capture_output=True)
    git("init", "-q", "-b", UPLOAD_BRANCH)
    shutil.copy(path, work / name)
    git("add", "--", name)
    git("-c", "user.name=trifillakia-bot", "-c", "user.email=actions@users.noreply.github.com", "commit", "-qm", "upload")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    remote = f"https://x-access-token:{token}@github.com/{repo}.git" if token else f"https://github.com/{repo}.git"
    git("push", "-qf", remote, f"{UPLOAD_BRANCH}:{UPLOAD_BRANCH}")
    shutil.rmtree(work, ignore_errors=True)
    return f"https://raw.githubusercontent.com/{repo}/{UPLOAD_BRANCH}/{name}"


# ---------------- κύρια ροή ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    dc = cfg.get("drive_shorts", {})
    root_id = os.environ.get("DRIVE_FOLDER_ID", "").strip()
    if not dc.get("active") or not root_id:
        print("drive_shorts ανενεργό ή χωρίς DRIVE_FOLDER_ID")
        if args.check and os.environ.get("GITHUB_OUTPUT"):
            open(os.environ["GITHUB_OUTPUT"], "a").write("found=false\n")
        return
    svc = drive()
    files = pending_files(svc, root_id, dc["shows"])
    if args.check:
        print(f"found={'true' if files else 'false'} ({len(files)})")
        if os.environ.get("GITHUB_OUTPUT"):
            open(os.environ["GITHUB_OUTPUT"], "a").write(f"found={'true' if files else 'false'}\n")
        return
    if not files:
        print("Τίποτα καινούριο στο Drive.")
        return

    import main as poster
    import publish
    state = poster.load_state()
    done_id = ensure_folder(svc, root_id, DONE_NAME)
    fail_id = ensure_folder(svc, root_id, FAIL_NAME)
    pub = cfg["publish"]
    failures = []

    for f, show_key, parent in files:
        item_id = f"drive-{f['id']}"
        if item_id in state["posted_ids"]:          # ήδη ανέβηκε (π.χ. απέτυχε μόνο η μετακίνηση)
            move(svc, f["id"], parent, done_id)
            continue
        title = clean_title(f["name"])
        who = (f.get("lastModifyingUser") or {}).get("displayName", "")
        yt_title, full, sport = texts(title, show_key, cfg)
        print(f"▶ [{show_key}] {f['name']} ({who}) → {yt_title}")
        work = Path(tempfile.mkdtemp())
        entry = {"slot": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M") + " (drive)", "source_id": item_id,
                 "source_title": f"[{dc['shows'][show_key]['name']}] {title}", "title": yt_title,
                 "uploader": who, "sport": sport, "ok": False}
        errors = []
        try:
            src = work / ("in" + Path(f["name"]).suffix.lower())
            download(svc, f["id"], src)
            out = work / f"{f['id']}.mp4"
            sc = cfg.get("subtitles", {})
            if sc.get("active"):
                try:
                    import subs
                    subbed = work / "subbed.mp4"
                    if subs.burn(src, subbed, sc):
                        src = subbed
                        print("  υπότιτλοι: ✓")
                    else:
                        print("  υπότιτλοι: δεν βρέθηκε ομιλία")
                except Exception as e:   # οι υπότιτλοι δεν σταματούν την ανάρτηση
                    errors.append(f"Υπότιτλοι (ανέβηκε χωρίς): {e}")
            add_outro(src, out, dc.get("max_seconds", 170))
            if pub.get("youtube"):
                try:
                    yt_id = publish.youtube_upload(out, yt_title, full, privacy="private",
                                                   paid_promotion=pub.get("youtube_paid_promotion", True))
                    entry.update(youtube=f"https://youtube.com/shorts/{yt_id}", yt_id=yt_id,
                                 yt_uploaded=datetime.now(timezone.utc).isoformat(),
                                 yt_state="pending" if pub.get("youtube_auto_public") else "private")
                    print("  YouTube (ιδιωτικό → δημόσιο μετά τον έλεγχο):", entry["youtube"])
                except Exception as e:
                    errors.append(f"YouTube: {e}")
            if pub.get("instagram"):
                try:
                    url = publish_temp_link(out, f"{f['id']}.mp4")
                    entry["instagram"] = publish.instagram_upload(url, f"{title}\n\n{full.split(chr(10) * 2, 1)[1]}")
                    print("  Instagram:", entry["instagram"])
                except Exception as e:
                    errors.append(f"Instagram: {e}")
        except Exception as e:
            errors.append(f"Μοντάζ/κατέβασμα: {e}")
        finally:
            shutil.rmtree(work, ignore_errors=True)

        entry["ok"] = bool(entry.get("youtube") or entry.get("instagram"))
        entry["errors"] = errors
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if entry["ok"]:
            state["posted_ids"].append(item_id)
            move(svc, f["id"], parent, done_id, f"{stamp} {f['name']}")
        else:
            move(svc, f["id"], parent, fail_id, f"{stamp} {f['name']}")
        state["log"].append(entry)
        poster.save_state(state)
        if errors:
            failures.append(f"**{f['name']}** ({who})\n" + "\n".join(f"- {e}" for e in errors))

    if failures:
        poster.open_issue("Shorts από Drive: πρόβλημα στην ανάρτηση",
                          "\n\n".join(failures) + "\n\nΤα αρχεία που δεν ανέβηκαν καθόλου είναι στον φάκελο «⚠️ Σφάλμα» στο Drive.")
        sys.exit(1)


if __name__ == "__main__":
    main()
