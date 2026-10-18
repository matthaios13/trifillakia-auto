"""Ανάρτηση σε YouTube Shorts και Instagram Reels μέσω των επίσημων API."""
import os
import time

import requests

API_VERSION = "v23.0"


def _graph(token):
    """Tokens από "Instagram Login" (ξεκινούν με IG) πάνε στο graph.instagram.com,
    tokens από Facebook Login στο graph.facebook.com."""
    host = "graph.instagram.com" if token.startswith("IG") else "graph.facebook.com"
    return f"https://{host}/{API_VERSION}"


# ---------------- YouTube ----------------

def _youtube():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
        client_id=os.environ["YT_CLIENT_ID"].strip(),
        client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def youtube_upload(video_path, title, description, privacy="private", paid_promotion=True):
    """Ανεβάζει το βίντεο (ιδιωτικό) και επιστρέφει το video id."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    yt = _youtube()
    body = {
        "snippet": {"title": title[:100], "description": description[:4900], "categoryId": "17",
                    "defaultLanguage": "el"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    parts = ["snippet", "status"]
    if paid_promotion:  # δήλωση «Περιέχει πληρωμένη προώθηση» (χορηγία Elabet)
        body["paidProductPlacementDetails"] = {"hasPaidProductPlacement": True}
        parts.append("paidProductPlacementDetails")

    def insert(parts):
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
        req = yt.videos().insert(part=",".join(parts), body=body, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        return resp["id"]

    try:
        return insert(parts)
    except HttpError as e:
        if "paidProductPlacementDetails" in parts and e.resp.status == 400:
            print("YouTube: η δήλωση πληρωμένης προώθησης δεν έγινε δεκτή από το API — "
                  "ανέβασμα χωρίς αυτήν (δήλωσέ την στο Studio).")
            return insert(["snippet", "status"])
        raise


def youtube_check(video_id):
    """Έλεγχος μετά το ανέβασμα. Επιστρέφει ("ok"|"wait"|"hold", εξήγηση)."""
    yt = _youtube()
    items = yt.videos().list(part="status,contentDetails", id=video_id).execute().get("items", [])
    if not items:
        return "hold", "το βίντεο δεν βρέθηκε (διαγράφηκε;)"
    v = items[0]
    st = v["status"]
    if st.get("uploadStatus") in ("rejected", "failed", "deleted"):
        return "hold", f"{st.get('uploadStatus')}: {st.get('rejectionReason') or st.get('failureReason')}"
    if st.get("uploadStatus") != "processed":
        return "wait", f"επεξεργασία ({st.get('uploadStatus')})"
    rr = v.get("contentDetails", {}).get("regionRestriction") or {}
    if rr.get("blocked") or ("allowed" in rr):
        return "hold", f"μπλοκάρισμα σε χώρες: {rr}"
    return "ok", "καθαρό"


def youtube_make_public(video_id):
    _youtube().videos().update(part="status", body={
        "id": video_id,
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "embeddable": True},
    }).execute()


# ---------------- Instagram ----------------

def instagram_upload(video_url, caption):
    """Το Instagram κατεβάζει μόνο του το βίντεο από δημόσιο link (video_url)."""
    token = os.environ["IG_ACCESS_TOKEN"].strip()
    user_id = os.environ["IG_USER_ID"].strip()
    GRAPH = _graph(token)

    r = requests.post(f"{GRAPH}/{user_id}/media", data={
        "media_type": "REELS", "video_url": video_url,
        "caption": caption[:2200], "share_to_feed": "true", "access_token": token,
    }, timeout=60)
    if not r.ok:
        raise RuntimeError(f"container {r.status_code}: {r.text[:500]}")
    container = r.json()["id"]
    print(f"Instagram container {container}")

    for _ in range(60):  # έως ~10 λεπτά επεξεργασία
        time.sleep(10)
        s = requests.get(f"{GRAPH}/{container}", params={"fields": "status_code,status", "access_token": token},
                         timeout=60).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing error: {s}")
    else:
        raise RuntimeError("Instagram: η επεξεργασία του βίντεο άργησε πολύ")

    r = requests.post(f"{GRAPH}/{user_id}/media_publish",
                      data={"creation_id": container, "access_token": token}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"publish {r.status_code}: {r.text[:500]}")
    media_id = r.json()["id"]
    link = requests.get(f"{GRAPH}/{media_id}", params={"fields": "permalink", "access_token": token},
                        timeout=60).json().get("permalink")
    return link or media_id
