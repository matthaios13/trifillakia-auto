# Trifillakia auto-poster

## Πώς δουλεύει
Δεν κοστίζει τίποτα: GitHub (δωρεάν), Instagram API (δωρεάν), χωρίς AI.

**Το Mac** (κάθε μέρα στις 09:00 και 21:00, ή όταν ανοίξει αν έχασε την ώρα):
1. διαλέγει ματς από το @microneuro με προτεραιότητα: νίκες σε Ευρώπη → νίκες → νίκες σε φιλικά → ευρωπαϊκά ματς με ισοπαλία ή ήττα. Ποτέ από την τρέχουσα σεζόν.
2. κατεβάζει ανώνυμα, χωρίς λογαριασμό και cookies, ένα βίντεο τη φορά, με παύσεις
3. μοντάρει (template, λογότυπα, outro). Το λογότυπο της πηγής μένει ορατό
4. γράφει τίτλο και κείμενο από τα στοιχεία του αγώνα (ημερομηνία, διοργάνωση, γήπεδο, σκορ, σκόρερ, θεατές)
5. κρατά πάντα **7 μέρες έτοιμα βίντεο** (21) στο GitHub, στο branch `queue`. Στο Mac δεν μένει κανένα βίντεο

**Το GitHub** κάνει τις αναρτήσεις στις 10:00, 14:00 και 19:00 στο **Instagram**, ακόμα κι αν το Mac είναι κλειστό. Όταν μείνουν 6 βίντεο ή λιγότερα, ανοίγει issue και σου έρχεται email να ανοίξεις το Mac.

Το YouTube είναι κλειστό (`youtube: false` στο `config.yaml`).

## Εγκατάσταση (μία φορά)

### 1. Εγκατάσταση στο Mac
```bash
zsh install_mac.sh
```

### 2. Instagram
1. Ο λογαριασμός πρέπει να είναι **Business ή Creator** και συνδεδεμένος με σελίδα Facebook.
2. Στο developers.facebook.com φτιάξε app και πρόσθεσε «Instagram». Τα δικαιώματα που χρειάζονται είναι `instagram_basic`, `instagram_content_publish` και `pages_show_list`.
3. Πάρε **long-lived access token** και το **Instagram User ID**.
4. Στο GitHub πήγαινε Settings → Secrets and variables → Actions και βάλε `IG_USER_ID` και `IG_ACCESS_TOKEN`.
5. Το token λήγει κάθε 60 μέρες και πρέπει να ανανεώνεται.

### 3. Ενεργοποίηση
Στο `config.yaml` άλλαξε `active: false` σε `active: true`.

## Χρήσιμα
- **Ημερολόγιο του Mac:** `~/Library/Application Support/TrifillakiaAuto/prepare.log`
- **Τα έτοιμα βίντεο** είναι μόνο στο GitHub (branch `queue`). Στο Mac δεν μένει κανένα βίντεο. Μία φορά την εβδομάδα καθαρίζονται όσα έχουν αναρτηθεί.
- **Ανάρτηση τώρα:** στο GitHub, Actions → Trifillakia auto-post → Run workflow → `force`
- **Ιστορικό αναρτήσεων:** `state/posted.json`
