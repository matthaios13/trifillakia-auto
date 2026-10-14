# Trifillakia auto-poster

Κάθε μέρα στις 10:00, 14:00 και 19:00 (ώρα Ελλάδας):
1. διαλέγει ένα ρετρό βίντεο του Παναθηναϊκού από το @microneuro που δεν έχει ξαναβγεί
2. το μοντάρει στο template (φωτογραφία, μπάρα τίτλου, Elabet, ΕΕΕΠ 21+, Trifillakia, outro). Το λογότυπο της πηγής μένει ορατό
3. γράφει τίτλο και περιγραφή με AI, που ψάχνει στο internet τα στοιχεία του αγώνα
4. ανεβάζει σε YouTube Shorts και Instagram Reels

Όλες οι ρυθμίσεις (ώρες, hashtags, κείμενα) βρίσκονται στο `config.yaml`.

## Εγκατάσταση (μία φορά)

### 1. GitHub
- Φτιάξε λογαριασμό στο github.com και ένα **private** repository, π.χ. `trifillakia-auto`.
- Ανέβασε όλα τα αρχεία αυτού του φακέλου.

### 2. Κλειδί AI (για τίτλους και κείμενα)
- Μπες στο console.anthropic.com, φτιάξε API key και βάλε λίγα χρήματα (π.χ. 10€).
- Κάθε βίντεο κοστίζει περίπου 0,05–0,15€.

### 3. YouTube
1. Στο console.cloud.google.com φτιάξε project και ενεργοποίησε το **YouTube Data API v3**.
2. Στο OAuth consent screen επίλεξε External και πρόσθεσε τον εαυτό σου ως Test user.
3. Στο Credentials πάτα Create OAuth client ID, επίλεξε τύπο **Desktop app** και κατέβασε το `client_secret.json`.
4. Στον υπολογιστή σου:
   ```bash
   pip install google-auth-oauthlib
   python src/get_youtube_token.py client_secret.json
   ```
   Θα τυπώσει τα `YT_CLIENT_ID`, `YT_CLIENT_SECRET` και `YT_REFRESH_TOKEN`.
5. Μέχρι να εγκρίνει η Google την εφαρμογή (YouTube API audit form), τα βίντεο ανεβαίνουν ως **private**. Μετά την έγκριση άλλαξε το `youtube_privacy: public` στο `config.yaml`.

### 4. Instagram
1. Ο λογαριασμός Instagram πρέπει να είναι **Business ή Creator** και συνδεδεμένος με σελίδα Facebook.
2. Στο developers.facebook.com φτιάξε app και πρόσθεσε το προϊόν «Instagram». Ζήτα τα δικαιώματα `instagram_basic`, `instagram_content_publish` και `pages_show_list`.
3. Πάρε **long-lived access token** και το **Instagram User ID**.

### 5. Secrets στο GitHub
Στο repository πήγαινε Settings → Secrets and variables → Actions → New repository secret:

| Όνομα | Τι είναι |
|---|---|
| `ANTHROPIC_API_KEY` | το κλειδί AI |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | από το βήμα 3 |
| `IG_USER_ID`, `IG_ACCESS_TOKEN` | από το βήμα 4 |
| `YT_COOKIES` | προαιρετικό, μόνο αν το YouTube μπλοκάρει τα κατεβάσματα (βλ. παρακάτω) |

### 6. Δοκιμή
Στην καρτέλα Actions επίλεξε Trifillakia auto-post, πάτα Run workflow και διάλεξε:
- `dry-run`: φτιάχνει βίντεο και κείμενο χωρίς να ανεβάσει τίποτα. Το βίντεο κατεβαίνει από το «Artifacts» στο κάτω μέρος της σελίδας.
- `force`: κάνει ανάρτηση αμέσως.

Μετά από αυτό τρέχει μόνο του. Αν αποτύχει κάτι, το GitHub σου στέλνει email.

## Συχνά προβλήματα
- **«Sign in to confirm you're not a bot»**: το YouTube μπλοκάρει τους servers του GitHub. Κάνε export τα cookies του YouTube (με την επέκταση «Get cookies.txt LOCALLY», από λογαριασμό που δεν είναι ο κύριος) και βάλε το περιεχόμενο στο secret `YT_COOKIES`. Αν συνεχίσει, το στήνουμε σε μικρό server.
- **Το token του Instagram λήγει** κάθε 60 μέρες: πρέπει να ανανεώνεται.
- Το ιστορικό αναρτήσεων βρίσκεται στο `state/posted.json`.

## Λογότυπα
Τα αρχεία στο `assets/` είναι **προσωρινά**, κομμένα από screenshot. Αντικατέστησέ τα με τα κανονικά, με τα ίδια ονόματα:
`elabet_badge.png`, `eeep_21.png`, `trifillakia_logo.png` (διάφανα PNG) και `outro.mp4` (το outro της Elabet).
