"""Pull GDELT 2.0 event files and aggregate events located in Ukraine per UTC hour.

    python scripts/fetch_gdelt_events.py --start 2026-01-01 --end 2026-09-08

Reads every 15-minute export file (https://data.gdeltproject.org/gdeltv2/<slot>.export.CSV.zip) in
[start, end), keeps rows with ActionGeo_CountryCode == "UP" (Ukraine) and counts them per hour of
DATEADDED, i.e. when the record was added to GDELT, not when the event happened. Raw files are
processed in memory and not kept. Writes to data/news/:
  gdelt_events_ukraine_hourly.csv  hour, files (15-min files found, 0-4), events_all,
                                   events_conflict (CAMEO root 18 assault, 19 fight, 20 mass violence),
                                   events_aerial (CAMEO 195x: employ aerial weapons, incl. drones)
  gdelt_conflict_adm1_hourly.csv   hour, adm1, events_conflict (rows with a count only)
  gdelt_adm1_names.csv             adm1 code -> most common ActionGeo_FullName (to map oblasts)
  FETCH_INFO.md                    when, range, files expected / found / missing
"""
import argparse
import csv
import io
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "news"
URL = "https://data.gdeltproject.org/gdeltv2/{}.export.CSV.zip"
UA = {"User-Agent": "ukraine-air-alerts course project (aggregates GDELT events per hour)"}
COUNTRY, ADM1, FULLNAME, EVENTCODE, ROOT, DATEADDED = 53, 54, 52, 26, 28, 59
CONFLICT_ROOTS = {"18", "19", "20"}


def fetch(slot):
    """Counts for one 15-minute file, or None if the file does not exist."""
    url = URL.format(slot.strftime("%Y%m%d%H%M%S"))
    for attempt in range(4):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return slot, None
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"could not fetch {url}")
    counts, adm1, names, added_mismatch = Counter(), Counter(), defaultdict(Counter), 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace")
        for r in csv.reader(text, delimiter="\t"):
            if len(r) < 61 or r[COUNTRY] != "UP":
                continue
            hour = r[DATEADDED][:10]  # YYYYMMDDHH of DATEADDED
            added_mismatch += r[DATEADDED] != slot.strftime("%Y%m%d%H%M%S")
            counts[(hour, "events_all")] += 1
            if r[ROOT] in CONFLICT_ROOTS:
                counts[(hour, "events_conflict")] += 1
                adm1[(hour, r[ADM1])] += 1
                names[r[ADM1]][r[FULLNAME]] += 1
            if r[EVENTCODE].startswith("195"):
                counts[(hour, "events_aerial")] += 1
    return slot, (counts, adm1, names, added_mismatch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--end", default="2026-09-08", help="exclusive")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    slots = pd.date_range(args.start, args.end, freq="15min", inclusive="left").to_pydatetime()
    pulled_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    counts, adm1, names = Counter(), Counter(), defaultdict(Counter)
    files_per_hour, missing, mismatched = Counter(), [], 0
    with ThreadPoolExecutor(args.workers) as pool:
        for i, (slot, res) in enumerate(pool.map(fetch, slots), 1):
            if res is None:
                missing.append(slot)
            else:
                c, a, n, mm = res
                counts.update(c)
                adm1.update(a)
                for k, v in n.items():
                    names[k].update(v)
                mismatched += mm
                files_per_hour[slot.strftime("%Y%m%d%H")] += 1
            if i % 2000 == 0:
                print(f"{i}/{len(slots)} files, {len(missing)} missing", flush=True)

    hours = pd.date_range(args.start, args.end, freq="h", inclusive="left")
    keys = hours.strftime("%Y%m%d%H")
    hourly = pd.DataFrame({
        "hour": hours.strftime("%Y-%m-%d %H:00:00+00:00"),
        "files": [files_per_hour[k] for k in keys],
        **{col: [counts[(k, col)] for k in keys] for col in ["events_all", "events_conflict", "events_aerial"]},
    })
    OUT.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(OUT / "gdelt_events_ukraine_hourly.csv", index=False)
    pd.DataFrame([{"hour": pd.Timestamp(datetime.strptime(h, "%Y%m%d%H"), tz="UTC"), "adm1": a, "events_conflict": n}
                  for (h, a), n in sorted(adm1.items())]).to_csv(OUT / "gdelt_conflict_adm1_hourly.csv", index=False)
    pd.DataFrame([{"adm1": a, "most_common_name": c.most_common(1)[0][0], "events_conflict": sum(c.values())}
                  for a, c in sorted(names.items())]).to_csv(OUT / "gdelt_adm1_names.csv", index=False)

    missing_days = Counter(s.strftime("%Y-%m-%d") for s in missing)
    lines = [
        "# GDELT events pull", "",
        f"- pulled at: {pulled_at}",
        f"- range: {args.start} to {args.end} (exclusive), 15-minute export files from {URL.format('<slot>')}",
        f"- files expected: {len(slots)}, found: {len(slots) - len(missing)}, missing (404): {len(missing)}",
        f"- rows whose DATEADDED differs from their file's slot: {mismatched}",
        "- filter: ActionGeo_CountryCode == UP; conflict = CAMEO root 18/19/20; aerial = CAMEO 195x",
        "- timestamp: DATEADDED (when the record entered GDELT), floored to the hour, UTC", "",
        "Missing files per day (days with any):", "",
        *[f"- {d}: {n}" for d, n in sorted(missing_days.items())],
    ]
    (OUT / "FETCH_INFO.md").write_text("\n".join(lines) + "\n")
    print(f"done: {len(slots) - len(missing)} files, {len(missing)} missing, "
          f"{hourly['events_all'].sum()} Ukraine events, {mismatched} DATEADDED/slot mismatches")


if __name__ == "__main__":
    main()
