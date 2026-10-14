"""Κατάλογος αγώνων του καναλιού-πηγή με αποτέλεσμα και διοργάνωση, για να διαλέγουμε με προτεραιότητα.

Προτεραιότητα (μικρότερο = πρώτο):
  0  νίκη σε ευρωπαϊκό αγώνα
  1  νίκη σε επίσημο εγχώριο αγώνα
  2  νίκη σε φιλικό
  3  ευρωπαϊκός αγώνας με ισοπαλία ή ήττα
  4  όλα τα υπόλοιπα
"""
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Ο κατάλογος ζει στο Mac (φάκελος δεδομένων), όχι στο GitHub
CATALOG = Path(os.environ.get("TRIFILLAKIA_DATA", ROOT / "state")) / "catalog.json"

EURO_WORDS = ("CHAMPIONS", "EUROPA", "UEFA", "CONFERENCE", "INTERTOTO", "ΠΡΩΤΑΘΛΗΤΡΙΩΝ",
              "ΚΥΠΕΛΛΟΥΧΩΝ", "ΚΟΚ", "ΕΚΘΕΣΕΩΝ", "ΕΥΡΩΠ", "SUPER CUP", "SUPERCUP")
PAO = "ΠΑΝΑΘΗΝΑΙΚΟΣ"


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").upper())
    return unicodedata.normalize("NFC", "".join(c for c in s if not unicodedata.combining(c)))


def _field(desc, name):
    m = re.search(rf"{name}\s*:\s*(.+)", desc)
    return m.group(1).strip() if m else ""


def parse(info):
    title, desc = info.get("title", ""), _norm(info.get("description", ""))
    comp = _field(desc, "ΔΙΟΡΓΑΝΩΣΗ")
    res = _field(desc, "ΑΠΟΤΕΛΕΣΜΑ")
    score = re.search(r"(\d+)\s*[-–]\s*(\d+)", res)
    teams = re.split(r"\s+[-–]\s+", re.sub(r"\s+\d{4}/\d{2}.*$", "", title).strip(), maxsplit=1)

    outcome = None
    if score and len(teams) == 2:
        home, away = int(score.group(1)), int(score.group(2))
        if PAO in _norm(teams[0]):
            pao, opp = home, away
        elif PAO in _norm(teams[1]):
            pao, opp = away, home
        else:
            pao = opp = None
        if pao is not None:
            outcome = "W" if pao > opp else "D" if pao == opp else "L"

    friendly = "ΦΙΛΙΚ" in comp
    european = (not friendly) and any(w in comp for w in EURO_WORDS)
    if outcome == "W":
        rank = 0 if european else 2 if friendly else 1
    elif european:
        rank = 3
    else:
        rank = 4
    season = re.search(r"(\d{4})/\d{2}", title)
    return {
        "id": info["id"], "title": title,
        "season_start": int(season.group(1)) if season else None, "duration": info.get("duration"),
        "competition": comp, "result": score.group(0) if score else "",
        "outcome": outcome, "european": european, "friendly": friendly, "rank": rank,
    }


def load():
    return json.loads(CATALOG.read_text()) if CATALOG.exists() else {}


def save(cat):
    CATALOG.parent.mkdir(exist_ok=True)
    CATALOG.write_text(json.dumps(cat, ensure_ascii=False, indent=1))


def update(channel_entries, fetch_info, limit=None, workers=1, pause=2.0):
    """Προσθέτει στον κατάλογο τα βίντεο που λείπουν (π.χ. καινούρια ανεβάσματα)."""
    cat = load()
    missing = [e["id"] for e in channel_entries if e["id"] not in cat]
    if limit is not None:
        missing = missing[:limit]

    def work(vid):
        time.sleep(pause)  # αργά και ευγενικά, για να μη μας κόψει το YouTube
        try:
            return parse(fetch_info(vid))
        except Exception as e:  # π.χ. βίντεο που αφαιρέθηκε
            print(f"skip {vid}: {e}")
            return None

    with ThreadPoolExecutor(workers) as ex:
        for i, item in enumerate(ex.map(work, missing), 1):
            if item:
                cat[item["id"]] = item
            if i % 100 == 0:
                save(cat)
                print(f"κατάλογος: {i}/{len(missing)}")
    save(cat)
    return cat
