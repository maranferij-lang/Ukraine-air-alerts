#!/bin/bash
# Install the hourly job on a Mac: every hour at minute 7, `predict.py --now` then the alert bot (scripts/hourly_job.py).
#   bash scripts/install_hourly.sh
# Needs the three keychain items first (see docs/DETAILS.md, "The alert bot"); it refuses to install if one is missing or the config is wrong.
# Nothing secret goes into the property list. Remove it again with scripts/uninstall_hourly.sh.
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
LABEL="local.ukraine-air-alerts.hourly"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGS="$HOME/Library/Logs/ukraine-air-alerts"
[ -x "$PY" ] || { echo "No $PY: create the virtual environment first (python3 -m venv .venv; pip install -r requirements.txt)."; exit 1; }
"$PY" "$REPO/scripts/alert_bot.py" --check || { echo "Fix the problems above first (nothing was installed)."; exit 1; }
mkdir -p "$HOME/Library/LaunchAgents" "$LOGS"
"$PY" "$REPO/scripts/hourly_job.py" --python "$PY" --print-plist > "$PLIST.tmp"
mv "$PLIST.tmp" "$PLIST"
chmod 644 "$PLIST"
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Installed: $LABEL runs every hour at minute 7. Status log: $LOGS/hourly.log"
echo "Run it once now (optional):  launchctl kickstart gui/$(id -u)/$LABEL"
