"""The hourly job (run by launchd, see scripts/install_hourly.sh): `predict.py --now` with the Ukraine Alarm token from the keychain, then the alert bot, then nothing else.

    python scripts/hourly_job.py                 one run
    python scripts/hourly_job.py --print-plist   the launchd property list (no secret in it); used by scripts/install_hourly.sh

What it writes is a status log, nothing more: one line per step with its exit code, no forecast table, no token, no chat id. The output of the two steps is captured and
dropped, apart from the bot's own status line (counts and HTTP status codes only). The forecast itself goes where it always goes (data/predictions/log.csv, output/).
If the forecast step fails the bot step is not run (its input would be old). A run that is missed because the Mac sleeps is simply missed: launchd runs the job once when the Mac wakes,
not once per missed hour.
"""
import argparse
import plistlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = "local.ukraine-air-alerts.hourly"
MINUTE = 7  # past the hour: the last completed hour has been in the API for a few minutes by then
LOG_DIR = Path.home() / "Library" / "Logs" / "ukraine-air-alerts"


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(line):
    print(f"{stamp()} {line}", flush=True)


def run_predict():
    """predict.py --now with the token from the keychain; returns (exit code, captured text that is not kept)."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "predict.py"), "--now", "--token-from-keychain"], capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout + r.stderr


def run_bot():
    """alert_bot.py; returns (exit code, its stdout: status lines only)."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "alert_bot.py")], capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout


def plist(python=None):
    """The launchd job: every hour at minute 7, the repository as working directory, a status log under ~/Library/Logs. Environment: only a minimal PATH (no variable holds a secret)."""
    return {"Label": LABEL,
            "ProgramArguments": [str(python or sys.executable), str(ROOT / "scripts" / "hourly_job.py")],
            "WorkingDirectory": str(ROOT),
            "StartCalendarInterval": {"Minute": MINUTE},
            "StandardOutPath": str(LOG_DIR / "hourly.log"), "StandardErrorPath": str(LOG_DIR / "hourly.log"),
            "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            "ProcessType": "Background", "RunAtLoad": False}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Hourly job: predict.py --now, then the alert bot.")
    ap.add_argument("--print-plist", action="store_true", help="print the launchd property list and exit")
    ap.add_argument("--python", help="the Python to put in the property list (default: the one running this)")
    a = ap.parse_args(argv)
    if a.print_plist:
        sys.stdout.buffer.write(plistlib.dumps(plist(a.python)))
        return 0
    code, _ = run_predict()
    log(f"forecast step: exit {code}" + ("" if code == 0 else " (the alert step is skipped)"))
    if code != 0:
        return code
    bcode, out = run_bot()
    status = [ln for ln in out.splitlines() if ln.startswith("alert_bot:")]
    log(f"alert step: exit {bcode}" + (f"; {status[-1]}" if status else ""))
    return bcode


if __name__ == "__main__":
    sys.exit(main())
