"""Q4: three numbers to check by hand. Needs the panels from scripts/build_panel.py
(default, --min-share 0 and --source volunteer).

    python scripts/hand_checks.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.load import PERMANENT_ALERT_OBLASTS, load_official, load_volunteer
from src.panel import official_episodes

PROCESSED = ROOT / "data" / "processed"
pd.set_option("display.width", 200)


def utc(s):
    return pd.Timestamp(s, tz="UTC")


off = load_official()
vol = load_volunteer()

print("=== 1. Alerts in Kyiv oblast (Kyivska oblast, NOT Kyiv City) in September 2026")
for tz in ["UTC", "Europe/Kyiv"]:
    a = pd.Timestamp("2026-09-01", tz=tz)
    b = pd.Timestamp("2026-10-01", tz=tz)
    n = ((vol["oblast"] == "Kyivska oblast") & (vol["start"] >= a) & (vol["start"] < b)).sum()
    print(f"volunteer rows, started_at in September ({tz} month boundaries): {n}")
sep = off[(off["oblast"] == "Kyivska oblast") & (off["start"] >= utc("2026-09-01")) & (off["start"] < utc("2026-10-01"))]
print(f"official rows (cleaned), September 2026 UTC: {len(sep)}  by level: {sep['level'].value_counts().to_dict()}"
      f"  distinct start timestamps: {sep['start'].nunique()}  covering {sep['start'].min()} .. {sep['start'].max()}")
keep = ~off["oblast"].isin(PERMANENT_ALERT_OBLASTS)
ep, _ = official_episodes(off[keep])
ep_sep = ep[(ep["oblast"] == "Kyivska oblast") & (ep["start"] >= utc("2026-09-01")) & (ep["start"] < utc("2026-10-01"))]
print(f"official oblast episodes (>= half of raions, restarts <= 5 min joined) starting in Sep 2026 UTC: {len(ep_sep)}")
print("NB official data stops 2026-09-07 05:40 UTC and has nothing 2026-08-29..09-02 13:48 UTC.")

print("\n=== 2. Longest single alert (one raw row, cleaned official / volunteer)")
off_d = off.assign(days=(off["end"] - off["start"]).dt.total_seconds() / 86400)
cols = ["oblast", "raion", "hromada", "level", "start", "end", "days"]
print("official, any level:")
print(off_d.nlargest(3, "days")[cols].round({"days": 2}).to_string(index=False))
print("official, oblast or raion level only:")
print(off_d[off_d["level"] != "hromada"].nlargest(3, "days")[cols].round({"days": 2}).to_string(index=False))
vol_d = vol.assign(days=(vol["end"] - vol["start"]).dt.total_seconds() / 86400)
print("volunteer:")
print(vol_d.nlargest(3, "days").round({"days": 2}).to_string(index=False))
print("NB Luhansk (since 2022-04-04) and Crimea (since 2022-12-10) permanent alerts are not in the data.")

print("\n=== 3. Share of hours with an active alert, Kharkiv vs Lviv, last 90 days of data")
for name, path in [("official, >= half of raions", "panel_official_min0.5.csv.gz"),
                   ("official, any raion", "panel_official_min0.csv.gz"),
                   ("volunteer", "panel_volunteer.csv.gz")]:
    p = pd.read_csv(PROCESSED / path, parse_dates=["hour"])
    end = p["hour"].max() + pd.Timedelta(hours=1)
    w = p[(p["hour"] >= end - pd.Timedelta(days=90)) & p["data_ok"]]
    for ob in ["Kharkivska oblast", "Lvivska oblast"]:
        x = w[w["oblast"] == ob]
        print(f"{name:28s} {ob:18s} window [{end - pd.Timedelta(days=90):%Y-%m-%d}, {end:%Y-%m-%d}) "
              f"usable hours {len(x)}: share of hours active {x['active'].mean():.3f}, "
              f"share of time under alert {x['minutes_active'].sum() / (60 * len(x)):.3f}")
