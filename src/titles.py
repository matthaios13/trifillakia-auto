"""Τίτλοι YouTube Shorts με «αγκίστρι» — ενθουσιώδεις αλλά πάντα με πραγματικά στοιχεία του αγώνα
(το YouTube τιμωρεί τους παραπλανητικούς τίτλους). Χωρίς AI, χωρίς κόστος."""
import random
import re
import unicodedata

PAO = "ΠΑΝΑΘΗΝΑΙΚΟΣ"  # χωρίς διαλυτικά: συγκρίνουμε πάντα με _norm()
DERBY = ("ΟΛΥΜΠΙΑΚ", "ΑΕΚ", "ΠΑΟΚ")

HOOKS = {
    "derby_W": ["ΤΟ ΝΤΕΡΜΠΙ ΠΟΥ ΔΕΝ ΞΕΧΝΙΕΤΑΙ! 🔥", "ΝΙΚΗ ΣΤΟ ΝΤΕΡΜΠΙ! ☘️🔥", "ΕΤΣΙ ΚΕΡΔΙΖΑΜΕ ΤΟ ΝΤΕΡΜΠΙ! 😍"],
    "euro_big_W": ["ΠΑΡΤΙΔΑ ΣΤΗΝ ΕΥΡΩΠΗ! 😳", "ΤΟ ΤΡΙΦΥΛΛΙ ΙΣΟΠΕΔΩΣΕ! 🔥", "ΕΥΡΩΠΑΪΚΟ ΣΟΚ! 😱"],
    "euro_away_W": ["ΑΛΩΣΗ ΣΤΗΝ ΕΥΡΩΠΗ! 😱", "ΤΡΕΛΑ ΕΚΤΟΣ ΕΔΡΑΣ! 🔥", "ΕΠΟΣ ΜΑΚΡΙΑ ΑΠΟ ΤΗΝ ΑΘΗΝΑ! ☘️"],
    "euro_W": ["ΜΑΓΙΚΗ ΕΥΡΩΠΑΪΚΗ ΒΡΑΔΙΑ! ✨", "ΤΟ ΤΡΙΦΥΛΛΙ ΛΑΜΠΕΙ ΣΤΗΝ ΕΥΡΩΠΗ! ☘️", "ΑΥΤΗ Η ΝΙΚΗ ΕΜΕΙΝΕ ΣΤΗΝ ΙΣΤΟΡΙΑ! 🔥"],
    "big_W": ["ΠΑΡΤΙΔΑ! 😳", "ΣΑΡΩΣΕ ΤΟ ΤΡΙΦΥΛΛΙ! 🔥", "ΓΚΟΛ ΜΕ ΤΟ ΤΣΟΥΒΑΛΙ! ⚽"],
    "away_W": ["ΑΛΩΣΗ ΕΚΤΟΣ ΕΔΡΑΣ! 🔥", "ΝΙΚΗ ΜΑΚΡΙΑ ΑΠΟ ΤΗ ΛΕΩΦΟΡΟ! 💪"],
    "close_W": ["ΝΙΚΗ ΜΕ ΑΓΩΝΙΑ ΜΕΧΡΙ ΤΕΛΟΥΣ! 😰", "ΘΡΙΛΕΡ ΜΕ ΧΑΠΙ ΕΝΤ! ☘️"],
    "W": ["ΘΥΜΑΣΑΙ ΑΥΤΗ ΤΗ ΝΙΚΗ; 😍", "ΕΤΣΙ ΠΑΙΖΕΙ ΤΟ ΤΡΙΦΥΛΛΙ! ☘️", "ΤΡΙΠΟΝΤΟ ΜΕ ΣΤΥΛ! 🔥"],
    "friendly_W": ["ΦΙΛΙΚΟ… ΑΛΛΑ ΤΙ ΦΙΛΙΚΟ! 😳", "ΣΟΟΥ ΤΟΥ ΤΡΙΦΥΛΛΙΟΥ! ☘️"],
    "euro_D": ["ΜΑΧΗ ΜΕΧΡΙ ΤΕΛΟΥΣ ΣΤΗΝ ΕΥΡΩΠΗ! 💪", "ΕΥΡΩΠΑΪΚΗ ΒΡΑΔΙΑ ΜΕ ΑΓΩΝΙΑ! 😰"],
    "euro_L": ["ΜΙΑ ΕΥΡΩΠΑΪΚΗ ΒΡΑΔΙΑ ΠΟΥ ΘΥΜΟΜΑΣΤΕ! 📼", "ΤΙ ΕΓΙΝΕ ΣΕ ΑΥΤΟ ΤΟ ΜΑΤΣ; 😮"],
    "other": ["ΘΥΜΑΣΑΙ ΑΥΤΟ ΤΟ ΜΑΤΣ; 📼", "ΑΠΟ ΤΟ ΑΡΧΕΙΟ ΤΟΥ ΤΡΙΦΥΛΛΙΟΥ! ☘️"],
}
VINTAGE = ["ΣΠΑΝΙΟ ΒΙΝΤΕΟ ΑΠΟ ΤΟ {year}! 📼", "ΘΗΣΑΥΡΟΣ ΑΠΟ ΤΟ {year}! 📼"]


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").upper())
    return unicodedata.normalize("NFC", "".join(c for c in s if not unicodedata.combining(c)))


def facts(meta):
    """Βγάζει ομάδες, σκορ, διοργάνωση, χρονιά από τα στοιχεία της ουράς."""
    title = re.sub(r"\s+\d{4}/\d{2}.*$", "", meta.get("source_title", "")).strip()
    teams = re.split(r"\s+[-–]\s+", title, maxsplit=1)
    score = re.search(r"(\d+)\s*-\s*(\d+)", meta.get("youtube_title", ""))
    desc = meta.get("full_description", "")
    comp = re.search(r"🏆\s*(.+)", desc)
    year = re.search(r"(\d{4})/\d{2}", meta.get("source_title", ""))
    f = {"home": teams[0], "away": teams[-1], "comp": _norm(comp.group(1)) if comp else "",
         "year": int(year.group(1)) if year else None, "outcome": None, "pao_home": PAO in _norm(teams[0])}
    if score and len(teams) == 2:
        h, a = int(score.group(1)), int(score.group(2))
        pao, opp = (h, a) if f["pao_home"] else (a, h)
        f.update(score=f"{h}-{a}", pao=pao, opp=opp,
                 outcome="W" if pao > opp else "D" if pao == opp else "L")
    return f


def _kind(f):
    comp, opp_name = f["comp"], _norm(f["away"] if f["pao_home"] else f["home"])
    friendly = "ΦΙΛΙΚ" in comp
    euro = not friendly and any(w in comp for w in ("CHAMPIONS", "EUROPA", "UEFA", "CONFERENCE", "ΚΥΠΕΛΛΟ ΠΡΩΤΑΘΛΗΤΡΙΩΝ",
                                                   "ΚΥΠΕΛΛΟΥΧΩΝ", "INTERTOTO", "ΕΚΘΕΣΕΩΝ"))
    if f["outcome"] == "W":
        margin = f["pao"] - f["opp"]
        if any(d in opp_name for d in DERBY):
            return "derby_W"
        if euro:
            return "euro_big_W" if margin >= 3 else "euro_away_W" if not f["pao_home"] else "euro_W"
        if friendly:
            return "friendly_W"
        if margin >= 3:
            return "big_W"
        if not f["pao_home"]:
            return "away_W"
        return "close_W" if margin == 1 else "W"
    if euro:
        return "euro_D" if f["outcome"] == "D" else "euro_L"
    return "other"


def youtube_title(meta, hashtags, seed=None, limit=100):
    f = facts(meta)
    rnd = random.Random(seed or meta.get("source_title"))
    short = lambda t: re.sub(PAO, "ΠΑΟ", _norm(t))
    match = f"{short(f['home'])} – {short(f['away'])}" + (f" {f['score']}" if f.get("score") else "")
    hooks = list(HOOKS[_kind(f)])
    if f["year"] and f["year"] < 1990:
        hooks += [v.format(year=f["year"]) for v in VINTAGE]
    rnd.shuffle(hooks)
    room = limit - len(hashtags) - 1
    for hook in hooks:
        title = f"{hook} {match}"
        if len(title) <= room:
            return f"{title} {hashtags}".strip()
    return f"{match[:room]} {hashtags}".strip()
