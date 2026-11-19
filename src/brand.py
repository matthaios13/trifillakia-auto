"""PAO Retro: το «σήμα» των ρετρό βίντεο (ποδόσφαιρο + μπάσκετ) και ο διακόπτης της χορηγίας Elabet.

Η ΕΕΕΠ (Νοέμβριος 2026) επιτρέπει Elabet μόνο σε εκπομπές και shorts από εκπομπές — όχι σε ιστορικές
αναδρομές, μέχρι να εγκριθεί το νέο εμπορικό πλάνο. Με retro_brand.sponsor: true (στο config.yaml)
ξαναμπαίνουν όλα μαζί: σήμα Elabet πάνω δεξιά, ΕΕΕΠ 21+, outro Elabet, #elabet #elaoposeisai,
«21+ | Παίξε υπεύθυνα» και η σήμανση πληρωμένης προώθησης. Οι εκπομπές (drive_shorts) δεν επηρεάζονται.
"""


def _rb(cfg):
    return cfg.get("retro_brand") or {}


def sponsor(cfg):
    return bool(_rb(cfg).get("sponsor"))


def name(cfg):
    return _rb(cfg).get("name", "PAO Retro")


def tags(cfg, base):
    """Hashtags + (με χορηγία) τα #elabet #elaoposeisai."""
    extra = _rb(cfg).get("sponsor_hashtags", "") if sponsor(cfg) else ""
    return " ".join(x for x in (base.strip(), extra.strip()) if x)


def title_tags(cfg, base):
    """Hashtags στο τέλος του τίτλου: με χορηγία μπαίνει πρώτο το #elaoposeisai."""
    return f"#elaoposeisai {base}".strip() if sponsor(cfg) else base.strip()


def footer(cfg):
    return cfg.get("footer") if sponsor(cfg) else None


def title(cfg, t):
    """«PAO Retro | …» μπροστά στον τίτλο (όταν είναι ανοιχτό το title_prefix)."""
    if not _rb(cfg).get("title_prefix") or t.startswith(name(cfg)):
        return t
    return f"{name(cfg)} | {t}"
