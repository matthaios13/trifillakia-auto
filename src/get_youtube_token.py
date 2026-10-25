"""Τρέχει ΜΙΑ φορά στον υπολογιστή σου για να πάρεις το YT_REFRESH_TOKEN.

  python src/get_youtube_token.py client_secret.json

Ανοίγει τον browser, συνδέεσαι με τον λογαριασμό του καναλιού Trifillakia και πατάς "Allow".
Μετά τυπώνει τα 3 secrets που βάζεις στο GitHub.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# Αν δοθούν πολλά αρχεία (π.χ. client_secret_*.json), παίρνουμε αυτό τύπου Desktop ("installed")
paths = [p for p in sys.argv[1:] if "installed" in json.load(open(p))]
if not paths:
    sys.exit("Δεν βρέθηκε αρχείο client_secret τύπου Desktop app.")
secret_file = paths[-1]
flow = InstalledAppFlow.from_client_secrets_file(
    secret_file, scopes=["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/drive"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
client = json.load(open(secret_file))
client = client.get("installed") or client.get("web")
values = {"YT_CLIENT_ID": client["client_id"], "YT_CLIENT_SECRET": client["client_secret"],
          "YT_REFRESH_TOKEN": creds.refresh_token}

# Αν υπάρχει το gh (GitHub CLI), τα κλειδιά μπαίνουν κατευθείαν στα secrets χωρίς να εμφανιστούν.
import shutil
import subprocess
from pathlib import Path
gh = shutil.which("gh") or str(Path.home() / ".local/bin/gh")
if Path(gh).exists():
    for name, value in values.items():
        subprocess.run([gh, "secret", "set", name, "--repo", "matthaios13/trifillakia-auto"],
                       input=value, text=True, check=True, capture_output=True)
        print(f"✓ {name} αποθηκεύτηκε στο GitHub")
    print("Τέλος — μπορείς να κλείσεις τον browser.")
else:
    print("\nΒάλε αυτά στο GitHub → Settings → Secrets and variables → Actions:\n")
    for name, value in values.items():
        print(f"{name} = {value}")
