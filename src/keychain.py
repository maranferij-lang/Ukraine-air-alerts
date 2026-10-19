"""The secrets of the alert bot and of the hourly job live only in the macOS keychain; this module reads them with `security find-generic-password`.

Three items (generic passwords, account = your user name), made by you with the commands in docs/DETAILS.md ("The alert bot"):
    ukraine-air-alerts.telegram-bot-token     the Telegram bot's token
    ukraine-air-alerts.telegram-chat-id       the chat id the bot writes to
    ukraine-air-alerts.ukrainealarm-token     the Ukraine Alarm API token
A secret is read into memory when needed and goes nowhere else: never into a file, a command line, an environment variable of a child process, a log line or an error
message. `security` is called without the secret on its command line (find-generic-password -w only PRINTS it, to the pipe this module reads). If the item is missing or the
keychain is locked the answer is None and nothing about why is passed on.
"""
import getpass
import os
import subprocess

SERVICES = {
    "telegram_token": "ukraine-air-alerts.telegram-bot-token",
    "telegram_chat": "ukraine-air-alerts.telegram-chat-id",
    "alarm_token": "ukraine-air-alerts.ukrainealarm-token",
}
SECURITY = os.environ.get("ALERT_SECURITY_BIN", "/usr/bin/security")  # the variable is for the offline tests (a fake `security`)


def account():
    return os.environ.get("USER") or getpass.getuser()


def get(key):
    """The secret stored under `key` (a key of SERVICES), or None."""
    try:
        r = subprocess.run([SECURITY, "find-generic-password", "-a", account(), "-s", SERVICES[key], "-w"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    value = r.stdout.rstrip("\n")
    return value or None


def present(key):
    """Is there an item for `key`? Asks for its attributes only, not for the secret."""
    try:
        r = subprocess.run([SECURITY, "find-generic-password", "-a", account(), "-s", SERVICES[key]], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0
