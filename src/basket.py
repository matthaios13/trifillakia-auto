"""Ρετρό ΜΠΑΣΚΕΤ του Παναθηναϊκού (κανάλι-πηγή του config «basket»).

Οι τίτλοι της πηγής έχουν πάντα τη μορφή «1998-99 ΠΑΝΑΘΗΝΑΙΚΟΣ-ΟΣΦΠ 72-56 [ΤΕΛΙΚΟΣ ΚΥΠΕΛΛΟΥ]».
Από εκεί βγαίνουν όλα τα στοιχεία (χωρίς AI → κανένα λάθος σε ομάδες/σκορ/γένος):
  • μόνο μπάσκετ: και τα δύο σκορ ≥ 30 (το κανάλι έχει και βόλεϊ/ποδόσφαιρο)
  • μόνο νίκες του ΠΑΟ
  • εναλλαγή: ντέρμπι → Ευρώπη → τελικός/μπαράζ → ντέρμπι → πρωτάθλημα, από όλες τις εποχές.
"""
import random
import re
import unicodedata

PAO = "ΠΑΝΑΘΗΝΑΙΚΟΣ"
GREEK_CLUBS = ("ΟΣΦΠ", "ΟΛΥΜΠΙΑΚΟΣ", "ΑΕΚ", "ΠΑΟΚ", "ΑΡΗΣ", "ΠΑΝΙΩΝΙΟΣ", "ΜΑΡΟΥΣΙ", "ΠΑΝΕΛΛΗΝΙΟΣ", "ΠΕΡΙΣΤΕΡΙ",
               "ΚΟΛΟΣΣΟΣ", "ΠΑΓΚΡΑΤΙ", "ΣΠΟΡΤΙΓΚ", "ΗΡΑΚΛΗΣ", "ΛΑΡΙΣΑ", "ΤΡΙΚΑΛΑ", "ΡΕΘΥΜΝΟ", "ΕΣΠΕΡΟΣ", "ΦΑΡΟΣ",
               "ΙΩΝΙΚΟΣ", "ΑΠΟΛΛΩΝ", "ΜΑΚΕΔΟΝΙΚΟΣ", "ΔΑΦΝΗ", "ΠΕΙΡΑΙΚΟΣ", "ΠΑΠΑΓΟΥ", "ΜΑΡΚΟΠΟΥΛΟ", "ΚΑΒΑΛΑ",
               "ΚΑΟΔ", "ΙΚΑΡΟΣ", "ΑΙΓΑΛΕΩ", "ΑΜΠΕΛΟΚΗΠΟΙ", "ΗΛΥΣΙΑΚΟΣ", "ΚΗΦΙΣΙΑ", "ΚΑΡΔΙΤΣΑ", "ΛΑΥΡΙΟ", "ΠΡΟΜΗΘΕΑΣ",
               "ΑΠΟΛΛΩΝ", "ΚΡΙ ΚΡΙ", "ΗΦΑΙΣΤΟΣ", "ΟΛΥΜΠΙΑ", "ΑΓΡΙΝΙΟ", "ΕΘΝΙΚΟΣ", "ΑΠΟΛΛΩΝ")
DERBY = {"ΟΣΦΠ": "ΟΛΥΜΠΙΑΚΟΣ", "ΑΕΚ": "ΑΕΚ", "ΠΑΟΚ": "ΠΑΟΚ", "ΑΡΗΣ": "ΑΡΗΣ"}
PATTERN = ["derby", "euro", "big", "derby", "greek"]
TITLE_RE = re.compile(r"^(\d{4})-(\d{2})\s+(.+?)\s*-\s*(.+?)\s+(\d{2,3})\s*-\s*(\d{2,3})\s*(.*)$")
LATIN = str.maketrans("ABEZHIKMNOPTYXabekmnoptxy", "ΑΒΕΖΗΙΚΜΝΟΡΤΥΧαβεκμνορτχυ")

# Πώς γράφουμε τις ομάδες: κεφαλαία (όπως η πηγή), χωρίς άρθρα → ποτέ λάθος γένος
DISPLAY = {"ΟΣΦΠ": "ΟΛΥΜΠΙΑΚΟΣ", "ΑΡΗΣ Θ.": "ΑΡΗΣ", "ΗΡΑΚΛΗΣ Θ.": "ΗΡΑΚΛΗΣ", "ΚΟΛΟΣΣΟΣ Ρ.": "ΚΟΛΟΣΣΟΣ ΡΟΔΟΥ",
           "ΦΑΡΟΣ ΚΕΡ.": "ΦΑΡΟΣ ΚΕΡΑΤΣΙΝΙΟΥ", "ΕΣΠΕΡΟΣ Κ.": "ΕΣΠΕΡΟΣ ΚΑΛΛΙΘΕΑΣ", "ΑΠΟΛΛΩΝ Π.": "ΑΠΟΛΛΩΝ ΠΑΤΡΑΣ",
           "ΣΚΑΒΟΛΙΝΙ Π.": "ΣΚΑΒΟΛΙΝΙ ΠΕΖΑΡΟ", "ΡΕΑΛ Μ.": "ΡΕΑΛ ΜΑΔΡΙΤΗΣ", "ΣΤΕΑΟΥΑ ΒΟΥΚ.": "ΣΤΕΑΟΥΑ ΒΟΥΚΟΥΡΕΣΤΙΟΥ",
           "ΠΑΡΤΙΖΑΝ Β.": "ΠΑΡΤΙΖΑΝ ΒΕΛΙΓΡΑΔΙΟΥ"}
EXTRA = {"ΤΕΛΙΚΟΣ ΚΥΠΕΛΛΟΥ": "Τελικός Κυπέλλου Ελλάδας", "ΜΠΑΡΑΖ": "Μπαράζ"}
PAO_NAME = "ΠΑΝΑΘΗΝΑΪΚΟΣ"


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").upper().translate(LATIN))
    s = unicodedata.normalize("NFC", "".join(c for c in s if not unicodedata.combining(c)))
    return re.sub(r"\s+", " ", s).strip()


def _nice(raw):
    n = _norm(raw)
    return PAO_NAME if PAO in n else DISPLAY.get(n, n)


def parse(title):
    """'1998-99 ΠΑΝΑΘΗΝΑΙΚΟΣ-ΟΣΦΠ 72-56' → στοιχεία, ή None αν δεν είναι αγώνας μπάσκετ του ΠΑΟ."""
    m = TITLE_RE.match((title or "").strip())
    if not m:
        return None
    s1, s2 = int(m[5]), int(m[6])
    if s1 < 30 or s2 < 30:          # βόλεϊ (3-0), ποδόσφαιρο κ.λπ.
        return None
    home, away, extra = m[3].strip(), m[4].strip(), _norm(m[7])
    pao_home, pao_away = PAO in _norm(home), PAO in _norm(away)
    if pao_home == pao_away:
        return None
    opp = away if pao_home else home
    pao, opp_pts = (s1, s2) if pao_home else (s2, s1)
    on = _norm(opp)
    derby = next((v for k, v in DERBY.items() if re.match(rf"{k}(\s|\.|$)", on)), None)
    greek = derby or any(on.startswith(g) for g in GREEK_CLUBS)
    friendly = "ΦΙΛΙΚ" in extra or "ΕΘΝΙΚΗ" in on
    final = "ΤΕΛΙΚ" in extra
    kind = ("big" if (final or "ΜΠΑΡΑΖ" in extra) and not friendly else "derby" if derby
            else "euro" if not greek and not friendly else "greek" if not friendly else "other")
    start = int(m[1])
    return {"season": f"{m[1]}-{m[2]}", "season_start": start, "home": _nice(home), "away": _nice(away),
            "opp": _nice(opp), "pao_home": pao_home, "score": f"{s1}-{s2}", "pao": pao, "opp_pts": opp_pts,
            "won": pao > opp_pts, "margin": pao - opp_pts, "kind": kind, "derby": derby,
            "extra": m[7].strip(), "final": final}


# ---------------------------------------------------------------- επιλογή
_ENTRIES = None


def pick_next(cfg, posted_ids):
    import source
    b = cfg["basket"]
    global _ENTRIES
    if _ENTRIES is None:
        _ENTRIES = source.list_channel(b["channel_url"])
    entries = _ENTRIES
    flat = {e["id"]: e for e in entries}
    cands, posted = [], []
    for e in entries:
        p = parse(e["title"])
        if not p or not p["won"] or p["kind"] == "other":
            continue
        p["id"] = e["id"]
        (posted if e["id"] in posted_ids else cands).append(p)
    cands = [c for c in cands if (flat[c["id"]].get("duration") or 0) <= b.get("max_seconds", 170)
             and (flat[c["id"]].get("duration") or 0) >= 15]
    if not cands:
        raise RuntimeError("Μπάσκετ: δεν απέμεινε κατάλληλο ρετρό")
    want = PATTERN[len(posted) % len(PATTERN)]
    order = PATTERN[PATTERN.index(want):] + PATTERN[:PATTERN.index(want)]
    used = {}
    for c in posted:
        used[c["season_start"] // 5] = used.get(c["season_start"] // 5, 0) + 1
    for k in order:
        pool = [c for c in cands if c["kind"] == k]
        if pool:
            least = min(used.get(c["season_start"] // 5, 0) for c in pool)
            choice = random.choice([c for c in pool if used.get(c["season_start"] // 5, 0) == least])
            break
    print(f"Μπάσκετ: {flat[choice['id']]['title']} (κατηγορία {choice['kind']})")
    info = source.fetch_info(choice["id"])
    info["basket"] = choice
    return info


# ---------------------------------------------------------------- κείμενα
HOOKS = {
    "derby": ["ΝΙΚΗ ΣΤΟ ΝΤΕΡΜΠΙ! 🔥", "ΤΟ ΝΤΕΡΜΠΙ ΠΟΥ ΔΕΝ ΞΕΧΝΙΕΤΑΙ! ☘️", "ΤΟ ΝΤΕΡΜΠΙ ΕΙΝΑΙ ΠΡΑΣΙΝΟ! 💚"],
    "euro": ["ΜΑΓΙΚΗ ΕΥΡΩΠΑΪΚΗ ΒΡΑΔΙΑ! ✨", "ΤΟ ΤΡΙΦΥΛΛΙ ΛΑΜΠΕΙ ΣΤΗΝ ΕΥΡΩΠΗ! ☘️", "ΕΥΡΩΠΑΪΚΗ ΝΙΚΗ! 🔥"],
    "final": ["ΤΟ ΚΥΠΕΛΛΟ ΕΙΝΑΙ ΠΡΑΣΙΝΟ! 🏆", "ΤΕΛΙΚΟΣ ΚΑΙ ΤΡΟΠΑΙΟ! 🏆☘️"],
    "big": ["ΝΙΚΗ ΣΤΟ ΜΠΑΡΑΖ! 🔥", "ΜΕΓΑΛΗ ΝΙΚΗ! ☘️"],
    "rout": ["ΠΑΡΤΙΔΑ ΣΤΟ ΠΑΡΚΕ! 😳", "ΣΑΡΩΣΕ ΤΟ ΤΡΙΦΥΛΛΙ! 🔥"],
    "close": ["ΝΙΚΗ ΜΕ ΑΓΩΝΙΑ ΜΕΧΡΙ ΤΕΛΟΥΣ! 😰", "ΘΡΙΛΕΡ ΜΕ ΠΡΑΣΙΝΟ ΦΙΝΑΛΕ! ☘️"],
    "greek": ["ΘΥΜΑΣΑΙ ΑΥΤΗ ΤΗ ΝΙΚΗ; 😍", "ΕΤΣΙ ΠΑΙΖΕΙ ΤΟ ΤΡΙΦΥΛΛΙ! ☘️"],
}
VINTAGE = ["ΣΠΑΝΙΟ ΒΙΝΤΕΟ ΑΠΟ ΤΟ {y}! 📼", "ΘΗΣΑΥΡΟΣ ΑΠΟ ΤΗ ΣΕΖΟΝ {s}! 📼"]
HEADLINE = {
    "derby": "Νίκη του Παναθηναϊκού στο ντέρμπι!",
    "euro": "Ευρωπαϊκή νίκη για τον Παναθηναϊκό!",
    "final": "Ο Παναθηναϊκός κατακτά το Κύπελλο!",
    "big": "Μεγάλη νίκη για τον Παναθηναϊκό!",
    "greek": "Νίκη για τους «πράσινους» στο παρκέ!",
}
CLOSING = ["Μια νίκη που έμεινε στη μνήμη των φίλων του Παναθηναϊκού! 💚",
           "Από τις στιγμές που κάνουν κάθε «πράσινο» περήφανο! ☘️",
           "Θυμάσαι πού ήσουν σε αυτό το ματς; Γράψ' το στα σχόλια! 💚"]


def generate(info, cfg):
    p = info["basket"]
    rnd = random.Random(info["id"])
    match = f"{p['home']} – {p['away']} {p['score']}"
    short = match.replace(PAO_NAME, "ΠΑΟ")
    k = "final" if p["final"] else p["kind"]
    hooks = list(HOOKS[k])
    if k == "greek":
        hooks += HOOKS["rout"] if p["margin"] >= 20 else HOOKS["close"] if p["margin"] <= 3 else []
    if p["season_start"] < 1990:
        hooks += [v.format(y=p["season_start"], s=p["season"]) for v in VINTAGE]
    hook = rnd.choice(hooks)
    tags = "#elaoposeisai #paobc #shorts"
    yt = f"{hook} {short}"
    if len(yt) + len(tags) + 1 > 100:
        yt = short
    lines = [f"🏀 {match}", f"☘️ {HEADLINE[k]}", "", f"📅 Σεζόν {p['season']}"]
    if p["extra"] and k in ("final", "big"):
        lines.append(f"🏆 {EXTRA.get(_norm(p['extra']), p['extra'])}")
    lines += ["", rnd.choice(CLOSING)]
    b = cfg["basket"]
    tail = [b.get("credit"), cfg.get("footer"), cfg["hashtags"]["basketball"]]
    overlay = f"{p['season']} · {short}"
    return {
        "overlay_title": overlay,
        "youtube_title": f"{yt} {tags}",
        "full_description": "\n\n".join(["\n".join(lines)] + [t for t in tail if t]),
        "confident": True,
    }
