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


def youtube_channel():
    """Όνομα του συνδεδεμένου καναλιού (έλεγχος σύνδεσης, χωρίς ανέβασμα)."""
    items = _youtube().channels().list(part="snippet", mine=True).execute().get("items", [])
    return items[0]["snippet"]["title"] if items else None


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


# ---------------- Facebook (Reels στη Σελίδα) ----------------

def _fb():
    """(page_id, token). Token Σελίδας με pages_manage_posts: FB_PAGE_TOKEN, αλλιώς το IG_ACCESS_TOKEN
    (αν είναι token Σελίδας από Facebook Login)."""
    token = (os.environ.get("FB_PAGE_TOKEN") or os.environ.get("IG_ACCESS_TOKEN") or "").strip()
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    if not page_id:
        page_id = requests.get(f"https://graph.facebook.com/{API_VERSION}/me", params={"access_token": token},
                               timeout=30).json().get("id", "")
    return page_id, token


def facebook_check():
    page_id, token = _fb()
    G = f"https://graph.facebook.com/{API_VERSION}"
    me = requests.get(f"{G}/{page_id}", params={"fields": "name", "access_token": token}, timeout=30).json()
    d = requests.get(f"{G}/debug_token", params={"input_token": token, "access_token": token}, timeout=30).json().get("data", {})
    return {"page": me.get("name") or me, "type": d.get("type"), "expires": d.get("expires_at"),
            "can_post": "pages_manage_posts" in d.get("scopes", [])}


def facebook_reel_upload(video_url, description):
    """Facebook Reel στη Σελίδα: το Facebook κατεβάζει το βίντεο από δημόσιο link."""
    page_id, token = _fb()
    G = f"https://graph.facebook.com/{API_VERSION}"
    r = requests.post(f"{G}/{page_id}/video_reels", data={"upload_phase": "start", "access_token": token}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"start {r.status_code}: {r.text[:500]}")
    vid = r.json()["video_id"]
    r = requests.post(f"https://rupload.facebook.com/video-upload/{API_VERSION}/{vid}",
                      headers={"Authorization": f"OAuth {token}", "file_url": video_url}, timeout=300)
    if not r.ok:
        raise RuntimeError(f"upload {r.status_code}: {r.text[:500]}")
    r = requests.post(f"{G}/{page_id}/video_reels", data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": description[:5000], "access_token": token}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"finish {r.status_code}: {r.text[:500]}")
    print(f"Facebook video {vid}")
    for _ in range(60):  # έως ~10 λεπτά επεξεργασία
        time.sleep(10)
        s = requests.get(f"{G}/{vid}", params={"fields": "status,permalink_url", "access_token": token}, timeout=60).json()
        st = s.get("status", {})
        if st.get("video_status") == "error" or st.get("processing_phase", {}).get("status") == "error":
            raise RuntimeError(f"Facebook processing error: {st}")
        if st.get("publishing_phase", {}).get("status") == "complete":
            break
    link = s.get("permalink_url") or f"/reel/{vid}"
    return link if link.startswith("http") else f"https://www.facebook.com{link}"


# ---------------- TikTok (μέσω totalsportsmedia.gr / TotalSports Publisher) ----------------

def _tiktok_token():
    """Φρέσκο access token του TikTok από το panel (TotalSports → TikTok), με το κλειδί TIKTOK_PUSH_KEY."""
    r = requests.post(os.environ.get("TIKTOK_TOKEN_URL", "https://totalsportsmedia.gr/wp-json/tsmg/v1/tiktok/token"),
                      headers={"X-TSMG-Key": os.environ["TIKTOK_PUSH_KEY"].strip()},
                      data={"username": os.environ.get("TIKTOK_ACCOUNT", "")}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"token {r.status_code}: {r.text[:300]}")
    return r.json()["access_token"]


def tiktok_upload(video_path, caption, mode="inbox"):
    """mode="inbox": στα πρόχειρα του TikTok (δημοσίευση από την εφαρμογή). mode="direct": απευθείας (μετά την έγκριση)."""
    token = _tiktok_token()
    API = "https://open.tiktokapis.com/v2"
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    size = os.path.getsize(video_path)
    chunk = size if size <= 64 * 1024 * 1024 else 10 * 1024 * 1024
    n = max(1, size // chunk)
    src = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": n}
    if mode == "direct":
        url, body = f"{API}/post/publish/video/init/", {"source_info": src, "post_info": {
            "title": caption[:2200], "privacy_level": "PUBLIC_TO_EVERYONE", "disable_comment": False,
            "disable_duet": False, "disable_stitch": False,
            # Επισήμανση χορηγίας (Elabet) σε όλα, όπως και στο YouTube.
            "brand_content_toggle": True, "brand_organic_toggle": False}}
    else:
        url, body = f"{API}/post/publish/inbox/video/init/", {"source_info": src}
    r = requests.post(url, headers=H, json=body, timeout=60).json()
    if not r.get("data", {}).get("upload_url"):
        raise RuntimeError(f"init: {r.get('error')}")
    with open(video_path, "rb") as fh:
        start = 0
        for i in range(n):
            length = size - start if i == n - 1 else chunk
            data = fh.read(length)
            u = requests.put(r["data"]["upload_url"], data=data, timeout=300, headers={
                "Content-Type": "video/mp4", "Content-Length": str(length),
                "Content-Range": f"bytes {start}-{start + length - 1}/{size}"})
            if u.status_code >= 300:
                raise RuntimeError(f"upload {u.status_code}: {u.text[:200]}")
            start += length
    pid = r["data"]["publish_id"]
    for _ in range(40):
        time.sleep(6)
        s = requests.post(f"{API}/post/publish/status/fetch/", headers=H, json={"publish_id": pid}, timeout=60).json().get("data", {})
        st = s.get("status")
        if st in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            return "TikTok: στα πρόχειρα (δημοσίευση από την εφαρμογή)" if st == "SEND_TO_USER_INBOX" else "TikTok: δημοσιεύτηκε"
        if st == "FAILED":
            raise RuntimeError(f"TikTok: {s.get('fail_reason')}")
    return f"TikTok: σε επεξεργασία ({pid})"


def instagram_video_url(permalink):
    """Το αρχείο βίντεο ενός δικού μας Reel (για παλιά βίντεο που δεν υπάρχουν πια στην ουρά)."""
    token = os.environ["IG_ACCESS_TOKEN"].strip()
    user_id = os.environ["IG_USER_ID"].strip()
    G = _graph(token)
    want = permalink.rstrip("/").split("/")[-1]
    url, params = f"{G}/{user_id}/media", {"fields": "permalink,media_url,media_type", "limit": 50, "access_token": token}
    for _ in range(20):
        j = requests.get(url, params=params, timeout=60).json()
        for m in j.get("data", []):
            if (m.get("permalink") or "").rstrip("/").split("/")[-1] == want and m.get("media_url"):
                return m["media_url"]
        url, params = j.get("paging", {}).get("next"), None
        if not url:
            break
    raise RuntimeError(f"δεν βρέθηκε στο Instagram: {permalink}")
