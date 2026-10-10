"""Q2: alerts per week over the whole period, unsmoothed.

Top: official rows per week by level, plus the raw file count (with upstream's duplicate rows).
Bottom: oblast-level alert starts per week summed over the 24 oblasts, under two oblast
definitions, next to the volunteer feed.

    python scripts/plot_weekly.py   ->  figures/alerts_per_week.png, figures/alerts_per_week.csv
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.load import (OFFICIAL_OUTAGES, PERMANENT_ALERT_OBLASTS, data_end, load_official,
                      load_volunteer)
from src.panel import merge_episodes, official_episodes

INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LEVEL_COLORS = {"oblast": "#2a78d6", "raion": "#eb6834", "hromada": "#1baf7a"}
SERIES_COLORS = {"official, >= half of raions": "#008300", "official, any raion": "#6250d6",
                 "volunteer": "#e87ba4"}


def weekly(starts, first, last):
    """Count timestamps per Mon-Sun week; keep only weeks fully inside [first, last)."""
    weeks = starts.dt.tz_localize(None).dt.to_period("W-SUN")
    counts = starts.groupby(weeks).size()
    full = pd.period_range(first.tz_localize(None).ceil("D"), last.tz_localize(None), freq="W-SUN")
    full = full[(full.start_time >= first.tz_localize(None)) & (full.end_time < last.tz_localize(None))]
    return counts.reindex(full, fill_value=0)


def main():
    raw = load_official(dedupe=False)
    off = load_official()
    vol = load_volunteer()
    off_end, vol_end = data_end(off), data_end(vol)
    off_first = off["start"].min().ceil("D")
    vol_first = vol["start"].min().ceil("D")

    keep = ~off["oblast"].isin(PERMANENT_ALERT_OBLASTS)
    vol_keep = vol[~vol["oblast"].isin(PERMANENT_ALERT_OBLASTS)]

    table = pd.DataFrame({
        "official_rows_raw_file": weekly(raw["start"], off_first, off_end),
        **{f"official_rows_{lvl}": weekly(off.loc[off["level"] == lvl, "start"], off_first, off_end)
           for lvl in LEVEL_COLORS},
        "official_starts_half_raions": weekly(official_episodes(off[keep], 0.5)[0]["start"], off_first, off_end),
        "official_starts_any_raion": weekly(official_episodes(off[keep], 0.0)[0]["start"], off_first, off_end),
        "volunteer_rows": weekly(vol["start"], vol_first, vol_end),
        "volunteer_starts": weekly(merge_episodes(vol_keep)["start"], vol_first, vol_end),
    })
    table.index = table.index.start_time
    table.index.name = "week_start_monday"
    out_csv = ROOT / "figures" / "alerts_per_week.csv"
    out_csv.parent.mkdir(exist_ok=True)
    table.to_csv(out_csv, float_format="%.0f")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8.5), sharex=True, facecolor=SURFACE,
                                   gridspec_kw={"height_ratios": [1, 1], "hspace": 0.12})
    x = table.index
    bar_w = pd.Timedelta(days=6)  # 1-day gap between weekly bars

    bottom = pd.Series(0.0, index=x)
    for lvl, color in LEVEL_COLORS.items():
        col = table[f"official_rows_{lvl}"]
        ax1.bar(x, col.fillna(0), width=bar_w, bottom=bottom, color=color, align="edge",
                linewidth=0, label=f"official rows, level = {lvl}")
        bottom += col.fillna(0)
    ax1.step(x, table["official_rows_raw_file"], where="post", color=INK2, lw=1.0,
             label="official rows as in the raw file (with upstream duplicates)")
    ax1.set_ylabel("rows per week", color=INK2)
    ax1.set_title("Official feed: one row per alerted location", loc="left", color=INK, fontsize=11)

    for name, col in [("official, >= half of raions", "official_starts_half_raions"),
                      ("official, any raion", "official_starts_any_raion"),
                      ("volunteer", "volunteer_starts")]:
        ax2.step(x, table[col], where="post", color=SERIES_COLORS[name], lw=1.2, label=name)
    ax2.set_ylabel("oblast alert starts per week\n(sum over 24 oblasts)", color=INK2)
    ax2.set_title("Oblast-level alert starts: two official definitions vs the volunteer feed",
                  loc="left", color=INK, fontsize=11)

    # context bands and lines, labelled directly
    switch = (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-01-01"))
    outage = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in OFFICIAL_OUTAGES]
    for ax in (ax1, ax2):
        ax.axvspan(*switch, color=GRID, alpha=0.6, lw=0, zorder=0)
        for a, b in outage:
            ax.axvspan(a, b, color="#c9c8c2", lw=0, zorder=0)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(INK2)
        ax.tick_params(colors=INK2)
        ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
    ax1.axvline(pd.Timestamp("2026-01-25"), color=INK2, lw=0.8, ls=":")
    ymax = ax1.get_ylim()[1]
    ax2.text(switch[0], ax2.get_ylim()[0] + 15, " oblast -> raion level\n switch (Jul-Dec 2025)",
             va="bottom", fontsize=8.5, color=INK2)
    ax1.text(pd.Timestamp("2026-01-25"), ymax * 0.97, " raw file duplicates\n end 2026-01-25",
             va="top", fontsize=8.5, color=INK2)
    ax1.text(outage[0][0], ymax * 0.78, "official outage\n29 Aug-2 Sep 2026 ",
             va="top", ha="right", fontsize=8.5, color=INK2)
    fig.text(0.01, 0.005, "Weeks Mon-Sun (UTC), partial first/last weeks dropped. Official complete weeks "
             f"end before {off_end:%Y-%m-%d}; volunteer before {vol_end:%Y-%m-%d}. Data: "
             "Vadimkin/ukrainian-air-raid-sirens-dataset (see data/raw/PULL_INFO.md).",
             fontsize=8, color=INK2)
    out_png = ROOT / "figures" / "alerts_per_week.png"
    fig.savefig(out_png, dpi=130, bbox_inches="tight", facecolor=SURFACE)
    print(f"wrote {out_png.relative_to(ROOT)} and {out_csv.relative_to(ROOT)} ({len(table)} weeks)")


if __name__ == "__main__":
    main()
