"""«ΣΑΝ ΣΗΜΕΡΑ» στο Trifillakia (PAO Retro): 1 ποδοσφαιρικό την ημέρα (09:00), ματς που έγινε την ίδια μέρα.

Κατάλογος με ημερομηνίες: football_dates.json των Παναθηναϊκών Νέων (στο Mac, από τις περιγραφές του
@microneuro — όχι AI). Ποτέ το ίδιο βίντεο με τα Παναθηναϊκά Νέα (διαβάζει τι έχει ανέβει ή περιμένει εκεί).
Νίκες πρώτα (Ευρώπη/ντέρμπι), μετά ισοπαλίες. Αν η μέρα δεν έχει, ±1..3 μέρες με «ΣΑΝ ΑΥΤΗ ΤΗΝ ΕΒΔΟΜΑΔΑ».
"""
import json
import random
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import requests

import brand

MONTHS = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου",
          "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"]
DERBY = ("ΟΛΥΜΠΙΑΚΟΣ", "ΑΕΚ", "ΠΑΟΚ", "ΑΡΗΣ")
CLOSING = ["Θυμάσαι αυτό το ματς; Γράψ' το στα σχόλια! 💚", "Πού ήσουν εκείνη τη μέρα; Γράψ' το στα σχόλια! ☘️",
           "Μια μέρα σαν σήμερα, στην ιστορία του Παναθηναϊκού! 💚"]


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").upper())
    return unicodedata.normalize("NFC", "".join(c for c in s if not unicodedata.combining(c)))


def dates_file(cfg):
    return Path((cfg.get("sansimera") or {}).get(
        "dates_file", "~/Library/Application Support/PanathinaikaneaAuto/football_dates.json")).expanduser()


def pn_ids():
    raw = "https://raw.githubusercontent.com/matthaios13/panathinaikanea-auto"
    try:
        ids = set(requests.get(f"{raw}/main/state/posted.json", timeout=30).json()["posted_ids"])
        r = requests.get(f"{raw}/queue/manifest.json", timeout=30)
        return ids | (set(r.json()) if r.ok else set())
    except Exception as e:
        raise RuntimeError(f"Δεν διαβάστηκαν τα Παναθηναϊκά Νέα ({e}) — δεν ρισκάρω διπλό βίντεο")


def _rank(c):
    derby = any(d in _norm(c["title"]) for d in DERBY)
    if c["outcome"] == "W":
        return 0 if c.get("european") or derby else 1
    if c["outcome"] == "D":
        return 2 if c.get("european") or derby else 3
    return 9


def pick(cfg, day, used_ids):
    """Ένα ματς για τη μέρα day. Επιστρέφει (match, label) ή (None, None)."""
    cat = json.loads(dates_file(cfg).read_text())
    src = cfg["source"]
    today = date.today()
    current = today.year if today.month >= 7 else today.year - 1
    used = set(used_ids) | pn_ids()
    pool = [c for c in cat.values()
            if c["id"] not in used and c.get("duration") and c["duration"] <= src["max_seconds"]
            and c.get("season_start") and c["season_start"] <= current - src.get("exclude_recent_seasons", 1)
            and not c.get("friendly") and _rank(c) < 9]
    for delta in [0, -1, -2, -3, 1, 2, 3]:   # πρώτα περασμένες μέρες: δεν «κλέβουμε» το ματς μιας επόμενης
        d = day + timedelta(days=delta)
        same = [c for c in pool if c["date"][5:] == d.strftime("%m-%d")]
        if same:
            rnd = random.Random(f"tri{day}")
            rnd.shuffle(same)
            same.sort(key=_rank)
            return same[0], ("ΣΑΝ ΣΗΜΕΡΑ" if delta == 0 else "ΣΑΝ ΑΥΤΗ ΤΗΝ ΕΒΔΟΜΑΔΑ")
    return None, None


def _teams(title):
    t = re.sub(r"\s+\d{4}/\d{2}.*$", "", title).strip()
    parts = re.split(r"\s+[-–]\s+", t, maxsplit=1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (t, "")


def texts(c, label, cfg):
    y, m, d = map(int, c["date"].split("-"))
    home, away = _teams(c["title"])
    comp, stadium = brand.comp_short(c.get("competition")), (c.get("stadium") or "").strip()
    rnd = random.Random(c["id"])
    today_label = label == "ΣΑΝ ΣΗΜΕΡΑ"
    head = (f"📅 Σαν σήμερα, {d} {MONTHS[m - 1]} {y}" if today_label
            else f"📅 Σαν αυτή την εβδομάδα, {d} {MONTHS[m - 1]} {y}")
    lines = [head, "", f"⚽ {home} – {away} {c['result']}"]
    if comp:
        lines.append(f"🏆 {comp}")
    if stadium:
        lines.append(f"🏟️ {stadium}")
    if c.get("scorers") and c["scorers"] not in ("-", "–"):
        lines.append(f"⚽ Σκόρερ: {c['scorers']}")
    lines += ["", rnd.choice(CLOSING if today_label else CLOSING[:2])]
    tail = [cfg["source"]["credit"], brand.footer(cfg), brand.tags(cfg, "#σανσημερα " + cfg["hashtags"]["football"])]
    short = lambda t: re.sub(r"ΠΑΝΑΘΗΝΑ[ΪΙ]ΚΟΣ", "ΠΑΟ", _norm(t))
    yt = f"{label} {y}: {short(home)} – {short(away)} {c['result']} ☘️"
    hs, as_ = brand.split_score(c["result"])
    t = _norm(c["title"])
    derby = any(x in t for x in DERBY)
    if c["outcome"] == "W":
        hook = "ΕΥΡΩΠΑΪΚΗ ΝΙΚΗ!" if c.get("european") else "ΝΙΚΗ ΣΤΟ ΝΤΕΡΜΠΙ!" if derby else rnd.choice(["ΤΡΙΠΟΝΤΟ!", "ΝΙΚΗ ΤΟΥ ΤΡΙΦΥΛΛΙΟΥ!"])
    else:
        hook = "ΕΥΡΩΠΑΪΚΗ ΒΡΑΔΙΑ!" if c.get("european") else "ΜΑΧΗ ΣΤΟ ΝΤΕΡΜΠΙ!" if derby else "ΑΠΟ ΤΟ ΑΡΧΕΙΟ!"
    lines_ = ["ΣΑΝ", "ΣΗΜΕΡΑ"] if today_label else ["ΣΑΝ ΑΥΤΗ", "ΤΗΝ", "ΕΒΔΟΜΑΔΑ"]
    card = {"hook": hook, "stamp": {"lines": lines_, "year": y}, "chip": f"{d} {MONTHS[m - 1]} {y}" + (f" · {comp}" if comp else ""),
            "home": home, "away": away, "hs": hs, "as": as_}
    return {"card": card, "overlay_title": f"{label}: {home} – {away} {c['result']}",
            "youtube_title": f"{yt} {brand.title_tags(cfg, '#shorts #panathinaikos')}",
            "full_description": "\n\n".join(["\n".join(lines)] + [t for t in tail if t]), "confident": True}
