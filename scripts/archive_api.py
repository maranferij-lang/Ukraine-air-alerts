"""Save Ukraine Alarm API data into data/api_archive/ so we build our own alert history (run on your own machine).

    export UA_ALARM_TOKEN=...                                  (in your shell; read from there only, never printed or saved)
    python scripts/archive_api.py                              daily run: regions, the alerts active now, the last 3 days
    python scripts/archive_api.py --from 2026-09-07 --to 2026-10-17    backfill a range of days (resumable; --force refetches saved days too)

What is written (answers are saved as the API sent them, plus one line per call in log.csv):
  data/api_archive/date_history/YYYYMMDD.json   /api/v3/alerts/dateHistory?date=YYYYMMDD. The last 3 days are fetched again on every
                                                run, because an alert that was still running can get its end later. An older
                                                file is kept as it is. A new empty answer never replaces a file that has alerts.
  data/api_archive/active/active_<UTC time>.json  /api/v3/alerts at the moment of the run (daily mode only)
  data/api_archive/regions/regions_<UTC date>.json  /api/v3/regions, only when it differs from the newest saved copy
  data/api_archive/log.csv                      fetched_at_utc, endpoint, date, http_status, items, bytes (no token, no headers)
Calls are at least 6 s apart at first; HTTP 429 waits (Retry-After if sent), slows the pace down and retries. Stops on 401/403 (token refused or blocked) and after repeated 429.
What to commit is your call: the files are plain JSON.
"""
import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ukrainealarm import Client

OUT = ROOT / "data" / "api_archive"
REFETCH_DAYS = 3  # today and the 2 days before it are always fetched again


def log(client_time, endpoint, date, status, items, nbytes):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "log.csv"
    new = not path.exists()
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["fetched_at_utc", "endpoint", "date", "http_status", "items", "bytes"])
        w.writerow([client_time, endpoint, date, status, items, nbytes])


def now_utc():
    return datetime.now(timezone.utc)


def stop(msg):
    print(msg)
    return 2


def check_fatal(c, status):
    if status in (401, 403):
        return f"HTTP {status}: the token is refused or the request is blocked. Nothing more was asked."
    if status == 429 and c.n429 >= 6:
        return "HTTP 429 keeps coming back. Run it again later."
    return None


def fetch_days(c, days, refetch_from, force=False, say=print):
    """dateHistory for each day (datetime.date) into data/api_archive/date_history/: a day whose file exists and is older than refetch_from is skipped
    (unless force); the others are fetched. A new empty answer never replaces a file that has alerts.
    Returns {"saved": [...], "skipped": n, "kept": n, "failed": [days that could not be fetched], "fatal": message or None}."""
    (OUT / "date_history").mkdir(parents=True, exist_ok=True)
    out = {"saved": [], "skipped": 0, "kept": 0, "failed": [], "fatal": None}
    for d in days:
        if out["fatal"]:
            out["failed"].append(d)
            continue
        f = OUT / "date_history" / f"{d:%Y%m%d}.json"
        if f.exists() and d < refetch_from and not force:
            out["skipped"] += 1
            continue
        t = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        s, data, raw = c.get("/api/v3/alerts/dateHistory", {"date": f"{d:%Y%m%d}"})
        n = len(data) if s == 200 and isinstance(data, list) else ""
        log(t, "dateHistory", d.isoformat(), s, n, len(raw))
        out["fatal"] = check_fatal(c, s)
        if s != 200 or n == "":
            out["failed"].append(d)
            say(f"{d}: HTTP {s}, not saved")
        elif n == 0 and f.exists() and json.loads(f.read_text()):
            out["kept"] += 1
            say(f"{d}: HTTP 200 but no alerts; the saved file with alerts is kept")
        else:
            f.write_bytes(raw)
            out["saved"].append(d)
            say(f"{d}: {n} alerts saved")
    return out


def fetch_active(c, say=print):
    """The alerts active now (/api/v3/alerts), saved as a timestamped snapshot. Returns (status, data or None, fetched_at)."""
    (OUT / "active").mkdir(parents=True, exist_ok=True)
    t = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    s, data, raw = c.get("/api/v3/alerts")
    log(t, "alerts", "", s, len(data) if s == 200 and isinstance(data, list) else "", len(raw))
    if s == 200:
        (OUT / "active" / f"active_{t.replace('-', '').replace(':', '')}.json").write_bytes(raw)
        say(f"active alerts: {len(data)} regions, saved")
    else:
        say(f"active alerts: HTTP {s}")
    return s, data, t


def main():
    ap = argparse.ArgumentParser(description="Save Ukraine Alarm API data into data/api_archive/ (token from UA_ALARM_TOKEN).")
    ap.add_argument("--from", dest="start", help="first day to backfill, YYYY-MM-DD (UTC); with --to")
    ap.add_argument("--to", dest="end", help="last day to backfill, YYYY-MM-DD (UTC)")
    ap.add_argument("--force", action="store_true", help="fetch every day of the range again, also those already saved (the default skips saved days older than 3 days)")
    args = ap.parse_args()
    if bool(args.start) != bool(args.end):
        ap.error("--from and --to go together")
    c = Client()
    today = now_utc().date()
    if args.start:
        d0, d1 = (datetime.strptime(x, "%Y-%m-%d").date() for x in (args.start, args.end))
        if d1 < d0 or d1 > today:
            ap.error("need --from <= --to <= today (UTC)")
        days = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
        mode = "backfill"
    else:
        days = [today - timedelta(days=i) for i in range(REFETCH_DAYS - 1, -1, -1)]
        mode = "daily"
    fatal = None
    refetch_from = today - timedelta(days=REFETCH_DAYS - 1)

    if mode == "daily":
        (OUT / "regions").mkdir(parents=True, exist_ok=True)
        t = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        s, data, raw = c.get("/api/v3/regions")
        log(t, "regions", "", s, len(data.get("states") or []) if s == 200 else "", len(raw))
        fatal = check_fatal(c, s)
        if s == 200:
            saved = sorted((OUT / "regions").glob("regions_*.json"))
            if not saved or json.loads(saved[-1].read_text()) != data:
                (OUT / "regions" / f"regions_{t[:10].replace('-', '')}.json").write_bytes(raw)
                print("regions: saved (new or changed)")
            else:
                print("regions: unchanged")
        else:
            print(f"regions: HTTP {s}")
        if not fatal:
            s, _, _ = fetch_active(c)
            fatal = check_fatal(c, s)

    res = fetch_days(c, days, refetch_from, force=args.force) if not fatal else {"saved": [], "skipped": 0, "kept": 0, "failed": [], "fatal": fatal}
    fatal = fatal or res["fatal"]
    fetched, kept, failed, skipped = len(res["saved"]), res["kept"], len(res["failed"]), res["skipped"]
    print(f"{mode}: {fetched} days saved, {skipped} already there, {kept} kept, {failed} failed; {c.calls} requests, {c.n429} x HTTP 429, gap now {c.gap:.1f} s")
    if fatal:
        return stop("Stopping: " + fatal)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
