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
    secret_file, scopes=["https://www.googleapis.com/auth/youtube"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
client = json.load(open(secret_file))
client = client.get("installed") or client.get("web")
print("\nΒάλε αυτά στο GitHub → Settings → Secrets and variables → Actions:\n")
print("YT_CLIENT_ID =", client["client_id"])
print("YT_CLIENT_SECRET =", client["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
