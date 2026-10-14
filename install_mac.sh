#!/bin/zsh
# Εγκατάσταση στο Mac: φτιάχνει το περιβάλλον και βάζει το Mac να ετοιμάζει βίντεο
# κάθε μέρα στις 09:00 και 21:00 (και όταν ανοίγει/ξυπνάει αν έχασε την ώρα).
set -e
DATA="$HOME/Library/Application Support/TrifillakiaAuto"
REPO_URL="https://github.com/matthaios13/trifillakia-auto.git"
PLIST="$HOME/Library/LaunchAgents/gr.trifillakia.prepare.plist"
mkdir -p "$DATA"

echo "→ Κατέβασμα κώδικα"
if [ -d "$DATA/repo/.git" ]; then git -C "$DATA/repo" pull -q --rebase --autostash
else git clone -q "$REPO_URL" "$DATA/repo"; fi

echo "→ Python 3.12 και βιβλιοθήκες (μία φορά, λίγα λεπτά)"
if [ ! -x "$DATA/venv/bin/python" ]; then
  /usr/bin/python3 -m venv "$DATA/bootstrap"
  "$DATA/bootstrap/bin/pip" install -q --upgrade pip uv
  "$DATA/bootstrap/bin/uv" venv -q -p 3.12 "$DATA/venv"
fi
VIRTUAL_ENV="$DATA/venv" "$DATA/bootstrap/bin/uv" pip install -q -U -r "$DATA/repo/requirements.txt"

echo "→ Πρόγραμμα εκτέλεσης"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>gr.trifillakia.prepare</string>
  <key>ProgramArguments</key><array>
    <string>$DATA/venv/bin/python</string>
    <string>$DATA/repo/src/prepare.py</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$DATA/venv/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>TRIFILLAKIA_DATA</key><string>$DATA</string>
  </dict>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>RunAtLoad</key><true/>
  <key>LowPriorityIO</key><true/>
  <key>Nice</key><integer>10</integer>
  <key>StandardOutPath</key><string>$DATA/prepare.log</string>
  <key>StandardErrorPath</key><string>$DATA/prepare.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "✓ Έτοιμο. Ημερολόγιο: $DATA/prepare.log"
