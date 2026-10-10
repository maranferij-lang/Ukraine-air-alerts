"""Sanity checks for the aggregated GDELT series (data/news/gdelt_events_ukraine_hourly.csv).

    python scripts/check_gdelt_events.py

1. gaps: hours with fewer than 4 of their 15-minute files, and hours with all files but no events
2. heavy days: days with the most oblasts under alert at the same time (official panel); do the
   GDELT counts rise on those days or the day after?
3. figures/gdelt_weekly.png: GDELT events per week next to official alert starts per week
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def main():
    g = pd.read_csv(ROOT / "data" / "news" / "gdelt_events_ukraine_hourly.csv", parse_dates=["hour"])
    panel = pd.read_csv(ROOT / "data" / "processed" / "panel_official_min0.5.csv.gz", parse_dates=["hour"])
    panel = panel[(panel["hour"] >= g["hour"].min()) & (panel["hour"] <= g["hour"].max())]

    print("=== 1. gaps")
    print(f"hours: {len(g)}; complete (4 files): {(g['files'] == 4).sum()}; partial: {((g['files'] > 0) & (g['files'] < 4)).sum()}; "
          f"no file at all: {(g['files'] == 0).sum()}")
    gap = g["files"] < 4
    runs = (gap != gap.shift()).cumsum()[gap]
    for _, r in g[gap].groupby(runs):
        print(f"   {r['hour'].min():%Y-%m-%d %H:00} .. {r['hour'].max():%Y-%m-%d %H:00} UTC: {len(r)} h, files {r['files'].tolist()[:8]}")
    silent = g[(g["files"] == 4) & (g["events_all"] == 0)]
    print(f"complete hours with zero Ukraine events: {len(silent)}")

    print("\n=== 2. heavy days (official alerts) vs GDELT")
    ok = panel[panel["data_ok"]]
    per_hour = ok.groupby("hour")["active"].sum()                      # oblasts under alert in the hour
    heavy = per_hour.groupby(per_hour.index.floor("D")).max().rename("max_oblasts_under_alert")
    starts = ok.groupby(ok["hour"].dt.floor("D"))["n_starts"].sum().rename("alert_starts")
    daily = g.set_index("hour").resample("D")[["events_all", "events_conflict", "events_aerial"]].sum()
    daily["files"] = g.set_index("hour")["files"].resample("D").sum()
    d = daily.join(heavy).join(starts).dropna()
    d = d[d["files"] == 96]                                                # complete GDELT days only
    for col in ["events_conflict", "events_aerial"]:
        d[f"{col}_next_day"] = d[col].shift(-1)
    top = d.sort_values(["max_oblasts_under_alert", "alert_starts"], ascending=False).head(10)
    med = d[["events_conflict", "events_aerial"]].median()
    print(f"median day: conflict {med['events_conflict']:.0f}, aerial {med['events_aerial']:.0f}")
    print(top[["max_oblasts_under_alert", "alert_starts", "events_conflict", "events_conflict_next_day",
               "events_aerial", "events_aerial_next_day"]].to_string())
    for col in ["events_conflict", "events_aerial"]:
        same = d[col].corr(d["alert_starts"], method="spearman")
        nxt = d[f"{col}_next_day"].corr(d["alert_starts"], method="spearman")
        print(f"Spearman, daily {col} vs official alert starts: same day {same:.2f}, GDELT next day {nxt:.2f}")

    print("\n=== 3. weekly plot")
    week = lambda s: s.resample("W-MON", label="left", closed="left").sum()
    gi = g.set_index("hour")
    gw = week(gi[["events_conflict", "events_aerial", "files"]].assign(hours=1))
    gw = gw[gw["hours"] == 168]                       # drop partial weeks at the edges of the range
    aw = week(ok.set_index("hour")["n_starts"]).reindex(gw.index)
    gaps_w = gw.index[gw["files"] < gw["hours"] * 4]  # weeks with a missing 15-minute file
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, facecolor=SURFACE,
                                   gridspec_kw={"hspace": 0.15})
    ax1.step(gw.index, gw["events_conflict"], where="post", color="#2a78d6", lw=1.4,
             label="GDELT events in Ukraine, CAMEO 18-20 (assault, fight, mass violence)")
    ax1.step(gw.index, gw["events_aerial"], where="post", color="#eb6834", lw=1.4,
             label="of which CAMEO 195x (aerial weapons)")
    ax1.set_title("GDELT 2.0 events located in Ukraine, by week added to GDELT (UTC)", loc="left", color=INK, fontsize=11)
    ax1.set_ylabel("events per week", color=INK2)
    ax2.step(aw.index, aw.values, where="post", color="#1baf7a", lw=1.4, label="official oblast alert starts (24 oblasts)")
    ax2.set_title("Official alerts, same weeks", loc="left", color=INK, fontsize=11)
    ax2.set_ylabel("alert starts per week", color=INK2)
    for ax in (ax1, ax2):
        for w in gaps_w:
            ax.axvspan(w, w + pd.Timedelta(days=7), color=GRID, alpha=0.7, lw=0)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(INK2)
        ax.tick_params(colors=INK2)
        ax.legend(loc="upper left", frameon=False, fontsize=9)
    note = ("Grey: week with a missing GDELT 15-minute file. " if len(gaps_w) else "") + "Partial first and last weeks dropped. "
    fig.text(0.01, 0.005, note + "Official series excludes the 2026-08-29..09-02 outage hours.", fontsize=8, color=INK2)
    out = ROOT / "figures" / "gdelt_weekly.png"
    fig.savefig(out, dpi=130, bbox_inches="tight", facecolor=SURFACE)
    print(f"wrote {out.relative_to(ROOT)}; weeks with missing GDELT files: {[f'{w:%Y-%m-%d}' for w in gaps_w]}")


if __name__ == "__main__":
    main()
