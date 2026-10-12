"""Picture of the model at work: five test days, two oblasts, hour by hour.

    python scripts/plot_timeline.py

Needs models/ (scripts/evaluate.py writes it); it only reads them, so nothing in results/ changes. The
probabilities are the saved H = 1 LightGBM's, on the same features evaluate.py scores the test set with.
The five days are the Aug 7-28 days (full 7-day lookback) where Kharkivska and Kyivska together had the
most alert starts: the window with the larger smaller-count, earliest first. Writes
figures/forecast_timeline.png and figures/forecast_timeline.csv (the numbers behind it).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.evaluate import COLORS, GRID, INK, INK2, SURFACE, style
from scripts.predict import load_models, resolve_oblast
from src.dataset import EVAL_LOOKBACK, HORIZONS, build_rows, load_inputs, split
from src.features import FEATURES, build_features, load_neighbours
from src.baselines import KYIV

H = 1
DAYS = 5
SHOWN = ["Kharkivska", "Kyivska"]
FIG = ROOT / "figures"


def pick_window(starts, first_day, last_day):
    """First day d (UTC) in [first_day, last_day - DAYS + 1] whose DAYS days have the most alert starts
    in the less active of the two oblasts; earlier days win ties."""
    best = None
    d = first_day
    while d + pd.Timedelta(days=DAYS - 1) <= last_day:
        n = [int(((s >= d) & (s < d + pd.Timedelta(days=DAYS))).sum()) for s in starts]
        if best is None or min(n) > best[0]:
            best = (min(n), d, n)
        d += pd.Timedelta(days=1)
    return best


def main():
    info, boosters, _ = load_models()
    official, raions = load_inputs()
    rows, episodes, raw, first, end = build_rows(official, raions)
    oblasts = sorted(rows["oblast"].unique())
    names = [resolve_oblast(s, oblasts) for s in SHOWN]
    test_start = pd.Timestamp(info["test_start"])
    m = split(rows, first, end, test_start, H, EVAL_LOOKBACK)
    aug = list(pd.date_range(test_start, pd.Timestamp("2026-08-28", tz="UTC"), freq="D"))

    starts = [episodes.loc[episodes["oblast"] == o, "start"] for o in names]
    n, day0, counts = pick_window(starts, aug[0], aug[-1])
    day1 = day0 + pd.Timedelta(days=DAYS)

    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, oblasts)
    rows = rows.assign(p=np.nan)
    sel = (rows["t"] >= day0) & (rows["t"] < day1)
    assert m["test"][sel].all(), "a shown hour is not a scored test row"
    rows.loc[sel, "p"] = boosters[H].predict(feats[H].loc[sel, FEATURES])

    fig, axes = plt.subplots(2, 1, figsize=(12, 6.4), sharex=True, facecolor=SURFACE)
    table = []
    for ax, o, short in zip(axes, names, SHOWN):
        r = rows[sel & (rows["oblast"] == o)].sort_values("t")
        x = r["t"].dt.tz_convert(KYIV).dt.tz_localize(None)
        under = r["now"].to_numpy().astype(bool)
        # light shading while an alert is active: whole hours at t that were under alert
        for xi, u in zip(x, under):
            if u:
                ax.axvspan(xi, xi + pd.Timedelta(hours=1), color=GRID, alpha=0.9, lw=0, zorder=0)
        ax.step(x, r["p"], where="post", color=COLORS["lgbm"], lw=1.8, zorder=3)
        s = episodes.loc[(episodes["oblast"] == o) & (episodes["start"] >= day0) & (episodes["start"] < day1), "start"]
        sx = s.dt.tz_convert(KYIV).dt.tz_localize(None)
        ax.scatter(sx, np.full(len(sx), 1.0), marker="v", s=46, color=COLORS["yesterday"], edgecolor=SURFACE,
                   linewidth=0.8, zorder=4, clip_on=False)
        ax.set_ylim(0, 1)
        ax.set_ylabel("chance of a new alert\nstarting in the next hour", color=INK2, fontsize=9)
        ax.set_title(f"{short}: {len(sx)} new alerts started in these 5 days", loc="left", color=INK, fontsize=11)
        style(ax)
        table.append(pd.DataFrame({"oblast": o, "hour_utc": r["t"].to_numpy(), "model_prob_h1": r["p"].to_numpy(),
                                   "under_alert_at_hour": under.astype(int)}))
    axes[0].plot([], [], color=COLORS["lgbm"], lw=1.8, label="model's chance for the next hour")
    axes[0].scatter([], [], marker="v", s=46, color=COLORS["yesterday"], label="a new alert actually started")
    axes[0].add_patch(plt.Rectangle((0, 0), 0, 0, color=GRID, label="an alert was already running"))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", frameon=False, fontsize=9, labelcolor=INK, ncol=3,
               bbox_to_anchor=(0.995, 0.975))
    axes[1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b\n%H:%M"))
    axes[1].xaxis.set_major_locator(matplotlib.dates.HourLocator(byhour=[0, 12]))
    axes[1].set_xlabel("Kyiv time", color=INK2)
    fig.suptitle(f"What the model said, hour by hour: five test days from {day0:%d %b %Y} (days it never saw)",
                 x=0.01, y=0.985, ha="left", color=INK, fontsize=12.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "forecast_timeline.png", dpi=130, bbox_inches="tight", facecolor=SURFACE)
    pd.concat(table).to_csv(FIG / "forecast_timeline.csv", index=False, float_format="%.4f")
    print(f"window {day0:%Y-%m-%d} to {(day1 - pd.Timedelta(days=1)):%Y-%m-%d} UTC; new alerts started: "
          + ", ".join(f"{s} {c}" for s, c in zip(SHOWN, counts)))
    print("wrote figures/forecast_timeline.png and figures/forecast_timeline.csv")


if __name__ == "__main__":
    main()
