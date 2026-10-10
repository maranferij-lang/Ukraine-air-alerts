"""Q3: build the hourly panel, one row per oblast per UTC hour.

    python scripts/build_panel.py                  # official, oblast = at least half its raions
    python scripts/build_panel.py --min-share 0    # official, oblast = any raion
    python scripts/build_panel.py --source volunteer

Writes data/processed/panel_<source>[_min<share>].csv.gz with columns
oblast, hour, active, active_at_start, minutes_active, n_starts, data_ok.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.load import OFFICIAL_OUTAGES, PERMANENT_ALERT_OBLASTS, data_end, load_official, load_volunteer
from src.panel import expand_to_raions, hourly_panel, merge_episodes, oblast_episodes


def build(source="official", min_share=0.5):
    if source == "official":
        alerts = load_official()
        alerts = alerts[~alerts["oblast"].isin(PERMANENT_ALERT_OBLASTS)]
        episodes = oblast_episodes(expand_to_raions(alerts), min_share)
        outages = OFFICIAL_OUTAGES
    else:
        alerts = load_volunteer()
        alerts = alerts[~alerts["oblast"].isin(PERMANENT_ALERT_OBLASTS)]
        episodes = merge_episodes(alerts)
        outages = []

    start = alerts["start"].min().ceil("D")  # first full UTC day
    end = data_end(alerts)
    panel = hourly_panel(episodes, start, end, oblasts=sorted(alerts["oblast"].unique()))
    panel["data_ok"] = True
    for a, b in outages:
        bad = (panel["hour"] >= pd.Timestamp(a, tz="UTC")) & (panel["hour"] < pd.Timestamp(b, tz="UTC"))
        panel.loc[bad, "data_ok"] = False
    return panel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["official", "volunteer"], default="official")
    ap.add_argument("--min-share", type=float, default=0.5,
                    help="official only: share of an oblast's raions that must be under alert")
    args = ap.parse_args()

    panel = build(args.source, args.min_share)
    name = f"panel_{args.source}" + (f"_min{args.min_share:g}" if args.source == "official" else "")
    out = ROOT / "data" / "processed" / f"{name}.csv.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out, index=False)

    ok = panel[panel["data_ok"]]
    print(f"wrote {out.relative_to(ROOT)}: {len(panel)} rows, {panel['oblast'].nunique()} oblasts, "
          f"hours {panel['hour'].min()} .. {panel['hour'].max()}")
    print(f"masked (data_ok=False): {(~panel['data_ok']).sum()} rows")
    print(f"share of hours active: {ok['active'].mean():.3f}, new starts per oblast-day: "
          f"{ok['n_starts'].sum() / len(ok) * 24:.2f}")


if __name__ == "__main__":
    main()
