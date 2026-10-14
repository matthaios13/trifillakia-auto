"""Τίτλοι και περιγραφή ΧΩΡΙΣ κόστος: φτιάχνονται από τα στοιχεία που γράφει ο @microneuro
στην περιγραφή κάθε βίντεο (ΗΜΕΡΟΜΗΝΙΑ, ΔΙΟΡΓΑΝΩΣΗ, ΓΗΠΕΔΟ, ΑΠΟΤΕΛΕΣΜΑ, ΣΚΟΡΕΡΣ, ΕΙΣΙΤΗΡΙΑ)."""
import random
import re

import catalog

MONTHS = {
    "ΙΑΝΟΥΑΡΙΟΥ": ("Ιανουαρίου", 1), "ΦΕΒΡΟΥΑΡΙΟΥ": ("Φεβρουαρίου", 2), "ΜΑΡΤΙΟΥ": ("Μαρτίου", 3),
    "ΑΠΡΙΛΙΟΥ": ("Απριλίου", 4), "ΜΑΙΟΥ": ("Μαΐου", 5), "ΙΟΥΝΙΟΥ": ("Ιουνίου", 6),
    "ΙΟΥΛΙΟΥ": ("Ιουλίου", 7), "ΑΥΓΟΥΣΤΟΥ": ("Αυγούστου", 8), "ΣΕΠΤΕΜΒΡΙΟΥ": ("Σεπτεμβρίου", 9),
    "ΟΚΤΩΒΡΙΟΥ": ("Οκτωβρίου", 10), "ΝΟΕΜΒΡΙΟΥ": ("Νοεμβρίου", 11), "ΔΕΚΕΜΒΡΙΟΥ": ("Δεκεμβρίου", 12),
}

PREFIX = {  # σύντομη ετικέτα πάνω στη μπάρα
    "euro_W": ["ΕΥΡΩΠΑΪΚΗ ΝΙΚΗ", "ΜΕΓΑΛΗ ΝΥΧΤΑ ΣΤΗΝ ΕΥΡΩΠΗ"],
    "W": ["ΝΙΚΗ ΤΟΥ ΤΡΙΦΥΛΛΙΟΥ", "ΤΡΙΠΟΝΤΟ"],
    "friendly_W": ["ΦΙΛΙΚΗ ΝΙΚΗ"],
    "euro_D": ["ΕΥΡΩΠΑΪΚΗ ΒΡΑΔΙΑ"],
    "euro_L": ["ΕΥΡΩΠΑΪΚΗ ΒΡΑΔΙΑ"],
    "other": ["ΑΠΟ ΤΟ ΑΡΧΕΙΟ"],
}
HEADLINE = {
    "euro_W": ["Μεγάλη ευρωπαϊκή νίκη για το «τριφύλλι»!", "Ο Παναθηναϊκός λάμπει στην Ευρώπη!"],
    "W": ["Νίκη για τους «πράσινους»!", "Το «τριφύλλι» παίρνει το τρίποντο!"],
    "friendly_W": ["Φιλική νίκη για το «τριφύλλι»!"],
    "euro_D": ["Ευρωπαϊκή βραδιά για τον Παναθηναϊκό!"],
    "euro_L": ["Ευρωπαϊκή βραδιά για τον Παναθηναϊκό!"],
    "other": ["Στιγμές από το αρχείο του Παναθηναϊκού!"],
}
CLOSING = {
    "W": ["Μια νίκη που έμεινε στη μνήμη των φίλων του Παναθηναϊκού! 💚",
          "Από τις στιγμές που κάνουν κάθε «πράσινο» περήφανο! ☘️",
          "Θυμάσαι πού ήσουν σε αυτό το ματς; Γράψ' το στα σχόλια! 💚"],
    "other": ["Στιγμές από την ιστορία του «τριφυλλιού»! ☘️",
              "Θυμάσαι αυτό το ματς; Γράψ' το στα σχόλια! 💚"],
}


def _field(desc, *names):
    for name in names:
        m = re.search(rf"{name}\s*:\s*(.+)", desc)
        if m and m.group(1).strip() not in ("-", "–"):
            return m.group(1).strip()
    return ""


def _date(raw):
    """'9 ΔΕΚΕΜΒΡΙΟΥ 2003' → ('9 Δεκεμβρίου 2003', '9/12/2003')."""
    m = re.match(r"(\d{1,2})\s+(\S+)\s+(\d{4})", catalog._norm(raw))
    if not m or m.group(2) not in MONTHS:
        return raw, raw
    name, num = MONTHS[m.group(2)]
    return f"{int(m.group(1))} {name} {m.group(3)}", f"{int(m.group(1))}/{num}/{m.group(3)}"


def _kind(c):
    if c["outcome"] == "W":
        return "euro_W" if c["european"] else "friendly_W" if c["friendly"] else "W"
    if c["european"]:
        return "euro_D" if c["outcome"] == "D" else "euro_L"
    return "other"


def generate(info, cfg):
    desc = info.get("description") or ""
    c = catalog.parse(info)
    kind = _kind(c)
    teams = re.sub(r"\s+\d{4}/\d{2}.*$", "", info.get("title", "")).strip()
    teams = re.sub(r"\s+[-–]\s+", " – ", teams)
    match = f"{teams} {c['result']}".strip()

    date_long, date_short = _date(_field(desc, "ΗΜΕΡΟΜΗΝΙΑ"))
    comp = _field(desc, "ΔΙΟΡΓΑΝΩΣΗ")
    stadium = _field(desc, "ΓΗΠΕΔΟ")
    scorers = _field(desc, "ΣΚΟΡΕΡΣ", "ΣΚΟΡΕΡ")
    fans = _field(desc, "ΕΙΣΙΤΗΡΙΑ", "ΘΕΑΤΕΣ")

    prefix = random.choice(PREFIX[kind])
    overlay = f"{prefix}: {match}" if len(prefix) + len(match) <= 42 else match

    lines = [f"☘️ {match}: {random.choice(HEADLINE[kind])}", ""]
    if date_short:
        lines.append(f"📅 {date_short}")
    if comp:
        lines.append(f"🏆 {comp}")
    if stadium:
        lines.append(f"🏟️ {stadium}")
    if fans:
        lines.append(f"👥 {fans} θεατές")
    if scorers:
        lines.append(f"⚽ Σκόρερ: {scorers}")
    lines += ["", random.choice(CLOSING["W" if c["outcome"] == "W" else "other"])]
    body = "\n".join(lines)
    if date_long:
        body = f"{date_long}\n{body}"

    hashtags = cfg["hashtags"][cfg["source"]["sport"]]
    tail = [cfg["source"]["credit"], cfg.get("footer"), hashtags]
    return {
        "overlay_title": overlay,
        "youtube_title": f"🔥 {match}! ☘️ #elaoposeisai #paofc #shorts",
        "full_description": "\n\n".join([body] + [t for t in tail if t]),
        "confident": bool(c["result"]),
    }
