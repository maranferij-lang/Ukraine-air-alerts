#!/bin/bash
# Remove the hourly job (the property list and the loaded job). The status log and the keychain items stay.
#   bash scripts/uninstall_hourly.sh
#   bash scripts/uninstall_hourly.sh --delete-secrets     also delete the three keychain items
set -u
LABEL="local.ukraine-air-alerts.hourly"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && echo "Stopped $LABEL." || echo "$LABEL was not loaded."
if [ -f "$PLIST" ]; then rm -f "$PLIST" && echo "Removed $PLIST."; else echo "No $PLIST."; fi
if [ "${1:-}" = "--delete-secrets" ]; then
  for s in ukraine-air-alerts.telegram-bot-token ukraine-air-alerts.telegram-chat-id ukraine-air-alerts.ukrainealarm-token; do
    security delete-generic-password -a "$USER" -s "$s" >/dev/null 2>&1 && echo "Deleted keychain item $s." || echo "No keychain item $s."
  done
fi
echo "The status log is still in ~/Library/Logs/ukraine-air-alerts/ (delete it by hand if you like)."
