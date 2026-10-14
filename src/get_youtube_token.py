"""Τρέχει ΜΙΑ φορά στον υπολογιστή σου για να πάρεις το YT_REFRESH_TOKEN.

  python src/get_youtube_token.py client_secret.json

Ανοίγει τον browser, συνδέεσαι με τον λογαριασμό του καναλιού Trifillakia και πατάς "Allow".
Μετά τυπώνει τα 3 secrets που βάζεις στο GitHub.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    sys.argv[1], scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
client = json.load(open(sys.argv[1]))
client = client.get("installed") or client.get("web")
print("\nΒάλε αυτά στο GitHub → Settings → Secrets and variables → Actions:\n")
print("YT_CLIENT_ID =", client["client_id"])
print("YT_CLIENT_SECRET =", client["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
