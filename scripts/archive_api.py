"""Save Ukraine Alarm API data into data/api_archive/ so we build our own alert history (run on your own machine).

    export UA_ALARM_TOKEN=...                                  (in your shell; read from there only, never printed or saved)
    python scripts/archive_api.py                              daily run: regions, the alerts active now, the last 3 days
    python scripts/archive_api.py --from 2026-09-07 --to 2026-10-17    backfill a range of days (resumable)

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


def main():
    ap = argparse.ArgumentParser(description="Save Ukraine Alarm API data into data/api_archive/ (token from UA_ALARM_TOKEN).")
    ap.add_argument("--from", dest="start", help="first day to backfill, YYYY-MM-DD (UTC); with --to")
    ap.add_argument("--to", dest="end", help="last day to backfill, YYYY-MM-DD (UTC)")
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
    (OUT / "date_history").mkdir(parents=True, exist_ok=True)
    fetched = kept = failed = skipped = 0
    refetch_from = today - timedelta(days=REFETCH_DAYS - 1)
    fatal = None

    def check_fatal(status):
        if status in (401, 403):
            return f"Stopping: HTTP {status} (the token is refused or the request is blocked). Nothing more was asked."
        if status == 429 and c.n429 >= 6:
            return "Stopping: HTTP 429 keeps coming back. Run it again later."
        return None

    if mode == "daily":
        (OUT / "regions").mkdir(exist_ok=True)
        (OUT / "active").mkdir(exist_ok=True)
        t = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        s, data, raw = c.get("/api/v3/regions")
        log(t, "regions", "", s, len(data.get("states") or []) if s == 200 else "", len(raw))
        fatal = check_fatal(s)
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
            t = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
            s, data, raw = c.get("/api/v3/alerts")
            log(t, "alerts", "", s, len(data) if s == 200 else "", len(raw))
            fatal = check_fatal(s)
            if s == 200:
                (OUT / "active" / f"active_{t.replace('-', '').replace(':', '')}.json").write_bytes(raw)
                print(f"active alerts: {len(data)} regions, saved")
            else:
                print(f"active alerts: HTTP {s}")

    for d in days:
        if fatal:
            break
        f = OUT / "date_history" / f"{d:%Y%m%d}.json"
        if f.exists() and d < refetch_from:
            skipped += 1
            continue
        t = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        s, data, raw = c.get("/api/v3/alerts/dateHistory", {"date": f"{d:%Y%m%d}"})
        n = len(data) if s == 200 and isinstance(data, list) else ""
        log(t, "dateHistory", d.isoformat(), s, n, len(raw))
        fatal = check_fatal(s)
        if s != 200 or n == "":
            failed += 1
            print(f"{d}: HTTP {s}, not saved")
        elif n == 0 and f.exists() and json.loads(f.read_text()):
            kept += 1
            print(f"{d}: HTTP 200 but no alerts; the saved file with alerts is kept")
        else:
            f.write_bytes(raw)
            fetched += 1
            print(f"{d}: {n} alerts saved")
    print(f"{mode}: {fetched} days saved, {skipped} already there, {kept} kept, {failed} failed; {c.calls} requests, {c.n429} x HTTP 429, gap now {c.gap:.1f} s")
    if fatal:
        return stop(fatal)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
