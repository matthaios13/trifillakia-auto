"""Γράφει τίτλο μπάρας, τίτλο YouTube και περιγραφή με το Claude (με web search για σωστά στοιχεία)."""
import json
import re

import anthropic

MODEL = "claude-opus-5-5"

EXAMPLE = """ΤΙΤΛΟΣ ΜΠΑΡΑΣ: Η 3άρα με ανατροπή στο Ibrox
ΤΙΤΛΟΣ YOUTUBE: 🔥 Ο ΠΑΝΑΘΗΝΑΪΚΟΣ ΤΡΕΛΑΝΕ ΤΗ ΓΛΑΣΚΩΒΗ! 1-3 ΜΕΣΑ ΣΤΟ IBROX! #elaoposeisai #paofc #shorts
ΠΕΡΙΓΡΑΦΗ:
☘️ Ρέιντζερς – Παναθηναϊκός 1-3: Η μεγάλη ευρωπαϊκή ανατροπή στη Γλασκώβη!

📅 9/12/2003
🏆 Champions League – Φάση ομίλων, 6η αγωνιστική
🏟️ Ibrox Stadium, Γλασκώβη
👥 48.588 θεατές

Ο Παναθηναϊκός ταξίδεψε στη Σκωτία για την τελευταία αγωνιστική της φάσης των ομίλων του Champions League, γνωρίζοντας πως είχε μπροστά του μια δύσκολη αποστολή απέναντι στη Ρέιντζερς. Σε μια καυτή έδρα, με σχεδόν 50.000 θεατές, οι «πράσινοι» κλήθηκαν να δείξουν χαρακτήρα.

Η αναμέτρηση δεν ξεκίνησε ιδανικά για το «τριφύλλι», καθώς ο Μολς έδωσε το προβάδισμα στη Ρέιντζερς στο 28ο λεπτό. Μόλις τέσσερα λεπτά αργότερα, ο Ζουτάουτας ισοφάρισε στο 32'.

Στο δεύτερο ημίχρονο, ο Άγγελος Μπασινάς βρήκε δίχτυα στο 62ο λεπτό, ολοκληρώνοντας την ανατροπή. Το κερασάκι στην τούρτα ήρθε στο 80', όταν ο Εμάνουελ Ολισαντέμπε διαμόρφωσε το τελικό 1-3. ☘️🔥

Μια νίκη που έμεινε στη μνήμη των φίλων του Παναθηναϊκού! 💚"""

SYSTEM = f"""Γράφεις κείμενα για τα Shorts/Reels της σελίδας Trifillakia.gr (φίλαθλοι Παναθηναϊκού).
Κάθε βίντεο είναι στιγμιότυπα από ιστορικό αγώνα του Παναθηναϊκού.

Βήματα:
1. Ψάξε στο web τα στοιχεία του αγώνα: ημερομηνία, διοργάνωση/αγωνιστική, γήπεδο, θεατές, σκόρ, σκόρερ και λεπτά.
2. Γράψε κείμενα στο ύφος του παραδείγματος.

Κανόνες ακρίβειας: γράψε ΜΟΝΟ στοιχεία που επιβεβαίωσες. Αν δεν βρεις κάτι (π.χ. θεατές ή λεπτά γκολ),
παράλειψέ το — μην το μαντέψεις. Αν δεν βρεις καθόλου τον αγώνα, βάλε "confident": false.

Παράδειγμα ύφους:
{EXAMPLE}

Απάντησε στο τέλος ΜΟΝΟ με ένα JSON object (χωρίς markdown) με κλειδιά:
- "overlay_title": σύντομος πιασάρικος τίτλος για την μπάρα του βίντεο, 3-7 λέξεις, χωρίς emoji, χωρίς hashtags
- "youtube_title": με emoji, κεφαλαία, έως 90 χαρακτήρες ΜΑΖΙ με τα hashtags "#elaoposeisai #paofc #shorts" στο τέλος
- "description": η περιγραφή όπως στο παράδειγμα (χωρίς hashtags στο τέλος)
- "date_line": ημερομηνία αγώνα γραμμένη όπως "9 Δεκεμβρίου 2003" ή "" αν δεν τη βρήκες
- "confident": true/false"""


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"Δεν βρέθηκε JSON στην απάντηση: {text[:300]}")
    return json.loads(m.group(0))


def generate(info, cfg):
    client = anthropic.Anthropic()
    user = (
        f"Τίτλος βίντεο-πηγή: {info.get('title')}\n"
        f"Περιγραφή βίντεο-πηγή: {(info.get('description') or '')[:1500]}\n"
        f"Άθλημα: {cfg['source']['sport']}"
    )
    messages = [{"role": "user", "content": user}]
    for _ in range(5):  # συνέχιση αν το web search κάνει pause_turn
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            messages=messages,
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}],
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    if resp.stop_reason == "refusal":
        raise RuntimeError("Το μοντέλο αρνήθηκε να γράψει κείμενο")
    text = "".join(b.text for b in resp.content if b.type == "text")
    data = _extract_json(text)

    hashtags = cfg["hashtags"][cfg["source"]["sport"]]
    body = data["description"].strip()
    if data.get("date_line"):
        body = f"{data['date_line']}\n{body}"
    tail = [cfg["source"]["credit"], cfg.get("footer"), hashtags]
    data["full_description"] = "\n\n".join([body] + [t for t in tail if t])
    return data


if __name__ == "__main__":
    import sys
    import yaml
    cfg = yaml.safe_load(open(__file__.rsplit("/src/", 1)[0] + "/config.yaml"))
    out = generate({"title": sys.argv[1], "description": ""}, cfg)
    print(json.dumps(out, ensure_ascii=False, indent=2))
