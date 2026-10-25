"""ΜΙΑ φορά στο Mac: σύνδεση YouTube + Google Drive και δημιουργία του κοινόχρηστου φακέλου Shorts.

  python src/setup_drive.py ~/Downloads/client_secret_XXXX.json

1. Ανοίγει τον browser: συνδέεσαι με τον λογαριασμό Google του καναλιού και πατάς «Allow»
   (ζητά YouTube + Drive). Το νέο κλειδί μπαίνει κατευθείαν στα GitHub secrets.
2. Φτιάχνει στο Drive τον φάκελο «Trifillakia – Shorts για ανέβασμα» με έναν υποφάκελο ανά εκπομπή
   και βάζει το ID του στη μεταβλητή DRIVE_FOLDER_ID του GitHub.
Μετά μοιράζεσαι τον φάκελο με τα παιδιά (Κοινή χρήση → Επεξεργαστής).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
REPO = "matthaios13/trifillakia-auto"
SCOPES = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/drive"]
ROOT_NAME = "Trifillakia – Shorts για ανέβασμα"

paths = [p for p in sys.argv[1:] if "installed" in json.load(open(p))]
if not paths:
    sys.exit("Δώσε το αρχείο client_secret (τύπου Desktop app).")
secret_file = paths[-1]
gh = shutil.which("gh") or str(Path.home() / ".local/bin/gh")

print("Άνοιξε ο browser: διάλεξε τον λογαριασμό του καναλιού Trifillakia και πάτα «Allow»…")
creds = InstalledAppFlow.from_client_secrets_file(secret_file, scopes=SCOPES).run_local_server(
    port=0, access_type="offline", prompt="consent")
client = json.load(open(secret_file))["installed"]
for name, value in {"YT_CLIENT_ID": client["client_id"], "YT_CLIENT_SECRET": client["client_secret"],
                    "YT_REFRESH_TOKEN": creds.refresh_token}.items():
    subprocess.run([gh, "secret", "set", name, "--repo", REPO], input=value, text=True, check=True, capture_output=True)
    print(f"✓ {name} αποθηκεύτηκε στο GitHub")

svc = build("drive", "v3", credentials=creds, cache_discovery=False)


def folder(name, parent=None):
    q = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    q += f" and '{parent}' in parents" if parent else " and 'root' in parents"
    found = svc.files().list(q=q, fields="files(id)").execute().get("files", [])
    if found:
        return found[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        body["parents"] = [parent]
    return svc.files().create(body=body, fields="id").execute()["id"]


cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
root_id = folder(ROOT_NAME)
for show in cfg["drive_shorts"]["shows"].values():
    folder(show["folder"], root_id)
folder("✅ Ανέβηκαν", root_id)
folder("⚠️ Σφάλμα", root_id)
subprocess.run([gh, "variable", "set", "DRIVE_FOLDER_ID", "--repo", REPO, "--body", root_id], check=True, capture_output=True)
print(f"✓ Φάκελος Drive έτοιμος: https://drive.google.com/drive/folders/{root_id}")
print("  Μοιράσου τον με τα παιδιά: δεξί κλικ → Κοινή χρήση → πρόσθεσε τα email τους ως «Επεξεργαστής».")
subprocess.run(["open", f"https://drive.google.com/drive/folders/{root_id}"])
