"""Hourly weather at each unit's administrative centre from the Open-Meteo Historical Weather API (round 22, feature group C; design: PROCESS_LOG.md).

    python scripts/fetch_weather.py                       2022-03-15 .. 2026-10-17, writes data/weather/<oblast>.csv (git-ignored) and data/weather/MANIFEST.md
    python scripts/fetch_weather.py --start 2026-10-01    only that range (merged into the existing files)

No key is needed (the free, non-commercial endpoint). One request per unit and calendar year; a polite pause between requests; on HTTP 429 (daily limit) it stops and says so,
keeping what it has. Variables: wind_speed_10m (m/s), cloud_cover (%), precipitation (mm, the sum of the hour that ends at the stamp), and visibility (m) if the API accepts it
(the archive API's documented list does not have it; the first request finds out and the manifest says which). Times are UTC.
Only the status code and the API's own one-line reason are ever printed.
"""
import argparse
import hashlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import requests

from src.features_extra import WEATHER_DIR, WEATHER_VARS
from src.geo_centres import CENTRES

URL = "https://archive-api.open-meteo.com/v1/archive"
FIRST, LAST = "2022-03-15", "2026-10-17"


def get(lat, lon, a, b, variables):
    for attempt in range(5):
        try:
            r = _get(lat, lon, a, b, variables)
            if r.status_code >= 500:
                raise requests.exceptions.RequestException(f"HTTP {r.status_code}")
            if r.status_code == 200:
                r.json()                                                  # a body that is not JSON is a transient fault too
            return r
        except (requests.exceptions.RequestException, ValueError) as e:      # a dropped TLS connection, a timeout: wait and retry
            print(f"network error ({type(e).__name__}), retry {attempt + 1}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise SystemExit("network error five times in a row; run again later (what is done is kept)")


def _get(lat, lon, a, b, variables):
    r = requests.get(URL, params={"latitude": lat, "longitude": lon, "start_date": a, "end_date": b, "hourly": ",".join(variables), "timezone": "UTC", "wind_speed_unit": "ms"}, timeout=60)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=FIRST)
    ap.add_argument("--end", default=LAST)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--refresh", action="store_true", help="download again even the units whose file already covers the whole range")
    args = ap.parse_args()
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    variables = list(WEATHER_VARS)
    years = list(range(pd.Timestamp(args.start).year, pd.Timestamp(args.end).year + 1))
    frames = {}
    for ob, (lat, lon) in CENTRES.items():
        path = WEATHER_DIR / f"{ob.replace(' ', '_')}.csv"
        if path.exists() and args.start == FIRST and args.end == LAST and not args.refresh:
            old = pd.read_csv(path, parse_dates=["time"]).set_index("time")
            if old.index.max() >= pd.Timestamp(LAST, tz="UTC"):
                frames[ob] = old.set_index(old.index.tz_localize("UTC") if old.index.tz is None else old.index)
                print(f"{ob}: already there ({len(old)} hours), skipped (--refresh downloads it again)", flush=True)
                continue
        parts = []
        for y in years:
            a, b = max(pd.Timestamp(args.start), pd.Timestamp(f"{y}-01-01")), min(pd.Timestamp(args.end), pd.Timestamp(f"{y}-12-31"))
            for attempt in range(3):
                r = get(lat, lon, f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}", variables)
                if r.status_code == 400 and "visibility" in variables and "visibility" in r.text:
                    variables = [v for v in variables if v != "visibility"]
                    print(f"the API does not accept visibility (HTTP 400: {r.json().get('reason', '')[:120]}); continuing without it", flush=True)
                    continue
                break
            if r.status_code == 429:
                print(f"HTTP 429: {r.json().get('reason', '')[:120]}. Stopped at {ob} {y}; run again later (what is done is kept).", flush=True)
                return 2
            if r.status_code != 200:
                print(f"HTTP {r.status_code} for {ob} {y}: {r.text[:120]}", flush=True)
                return 1
            h = r.json()["hourly"]
            parts.append(pd.DataFrame({"time": pd.to_datetime(h["time"], utc=True), **{v: h[v] for v in variables}}))
            time.sleep(args.pause)
        new = pd.concat(parts).drop_duplicates("time").set_index("time").sort_index()
        path = WEATHER_DIR / f"{ob.replace(' ', '_')}.csv"
        if path.exists() and args.start != FIRST:
            old = pd.read_csv(path, parse_dates=["time"]).set_index("time")
            old.index = old.index.tz_localize("UTC") if old.index.tz is None else old.index
            new = pd.concat([old[~old.index.isin(new.index)], new]).sort_index()
        new.reset_index().to_csv(path, index=False, float_format="%.2f")
        frames[ob] = new
        print(f"{ob}: {len(new)} hours, {new.index.min():%Y-%m-%d} to {new.index.max():%Y-%m-%d %H}:00", flush=True)
    lines = ["# Manifest: hourly weather per unit centre", "",
             "Produced by `scripts/fetch_weather.py` from the Open-Meteo Historical Weather API (archive-api.open-meteo.com, ERA5-based; free non-commercial endpoint). The CSVs are git-ignored; "
             "re-download them with the script and compare the SHA-256 prefixes below (the API may revise recent hours).", "",
             f"- range requested: {args.start} to {args.end}, UTC; variables requested: {', '.join(variables)}",
             "- **visibility: the API accepts the variable but returns null for every hour (the 'missing values' column is exactly that column), so it is not used**; features use wind, cloud cover and precipitation",
             "- precipitation is the sum of the hour that ends at the stamp; wind in m/s; cloud cover in %", "", "| unit | hours | missing values | SHA-256 of the file (prefix) |", "|---|---|---|---|"]
    for ob in CENTRES:
        p = WEATHER_DIR / f"{ob.replace(' ', '_')}.csv"
        d = frames.get(ob)
        lines.append(f"| {ob} | {len(d) if d is not None else 'n/a'} | {int(d.isna().sum().sum()) if d is not None else 'n/a'} | {hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else 'n/a'} |")
    (WEATHER_DIR / "MANIFEST.md").write_text("\n".join(lines) + "\n")
    print("wrote data/weather/MANIFEST.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
