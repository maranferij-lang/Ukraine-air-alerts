"""Round 2: evaluate the three baselines on the test month. No model.

    python scripts/evaluate_baselines.py

Test = the last TEST_DAYS full days of official data, walk-forward: every score for origin t uses
only what is known at t (see src/baselines.py; checked by scripts/check_no_peeking.py).
Train = every origin whose target window closes before the test month starts.
F1 threshold = chosen on the last week of train, then frozen for test.

Writes results/baselines_test.{csv,md}, results/persistence_vs_target_a.md, figures/baselines_h6.png.
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

from src.baselines import frequency_table, persistence, same_hour_yesterday, train_frequency
from src.load import OFFICIAL_OUTAGES, PERMANENT_ALERT_OBLASTS, data_end, load_official
from src.metrics import auc, best_f1_threshold, brier, precision_recall_f1
from src.panel import official_episodes
from src.targets import active_now, make_rows, touches, y_active, y_start

HORIZONS = [1, 3, 6]
TEST_DAYS = 30
THRESHOLD_DAYS = 7
LOOKBACK = pd.Timedelta(hours=24)  # same-hour-yesterday needs t-24h
TARGETS = {"a_active": "(a) alert active in (t, t+H]", "b_start": "(b) new alert starts in (t, t+H]"}
BASELINES = {"persistence": "same as now", "yesterday": "same hour yesterday",
             "frequency": "train freq oblast x hour x weekday"}


def build_rows():
    official = load_official()
    official = official[~official["oblast"].isin(PERMANENT_ALERT_OBLASTS)]
    episodes, raw = official_episodes(official)
    first = official["start"].min().ceil("D")
    end = data_end(official)
    rows = make_rows(official["oblast"].unique(), first, end - pd.Timedelta(hours=1))
    rows["now"] = active_now(rows, raw)  # state at t from raw episodes: no knowledge of restarts
    for H in HORIZONS:
        rows[f"a_active_{H}"] = y_active(rows, episodes, H)
        rows[f"b_start_{H}"] = y_start(rows, episodes, H)
    return rows, episodes, raw, first, end


def split(rows, first, end, test_start, H):
    """Boolean masks (test, train, last_week) for horizon H. A row is usable when its lookback
    and its target window lie inside the data and away from known outages."""
    h = pd.Timedelta(hours=H)
    usable = ((rows["t"] - LOOKBACK >= first) & (rows["t"] + h <= end)
              & ~touches(rows, OFFICIAL_OUTAGES, before=LOOKBACK, after=h))
    test = usable & (rows["t"] >= test_start)
    train = usable & (rows["t"] + h <= test_start)
    last_week = train & (rows["t"] >= test_start - pd.Timedelta(days=THRESHOLD_DAYS))
    return test, train, last_week


def score_table(rows, first, end, test_start):
    results, decomposition = [], []
    for H in HORIZONS:
        test, train, last_week = split(rows, first, end, test_start, H)
        for target in TARGETS:
            col = f"{target}_{H}"
            scores = {
                "persistence": persistence(rows),
                "yesterday": same_hour_yesterday(rows, col),
                "frequency": train_frequency(rows, frequency_table(rows[train], col)),
            }
            y = rows[col]
            for name, s in scores.items():
                assert s[test | last_week].notna().all(), name
                thr = best_f1_threshold(y[last_week], s[last_week])
                precision, recall, f1 = precision_recall_f1(y[test], s[test], thr)
                within = [auc(g[col], s[g.index]) for _, g in rows[test].groupby("oblast")]
                results.append({
                    "target": target, "H": H, "baseline": name,
                    "n_test": int(test.sum()), "base_rate": y[test].mean(),
                    "brier": brier(y[test], s[test]), "auc": auc(y[test], s[test]),
                    "auc_within_oblast": np.nanmean(within), "n_oblasts_auc": int(np.sum(~np.isnan(within))),
                    "threshold": thr, "precision": precision, "recall": recall, "f1": f1,
                })
        # how much of target (a) is the current alert continuing
        t_rows = rows[test]
        ya, now, ys = t_rows[f"a_active_{H}"], t_rows["now"], t_rows[f"b_start_{H}"]
        quiet = ~now
        decomposition.append({
            "H": H, "n_test": len(t_rows), "base_rate_a": ya.mean(), "share_active_now": now.mean(),
            "share_of_a_positives_already_active_at_t": (now & ya).sum() / ya.sum(),
            "share_of_a_positives_from_new_start_while_quiet": (quiet & ya).sum() / ya.sum(),
            "base_rate_a_on_quiet_rows (= b on quiet rows)": ya[quiet].mean(),
            "base_rate_b_all_rows": ys.mean(),
            "rows_where_a != (now or b)": int((ya != (now | ys)).sum()),
        })
    return pd.DataFrame(results), pd.DataFrame(decomposition)


def md_table(df, floatfmt="{:.3f}"):
    cells = df.map(lambda v: floatfmt.format(v) if isinstance(v, float) else str(v))
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(r) + " |" for r in cells.itertuples(index=False)]
    return "\n".join(lines)


def write_markdown(res, dec, test_start, end, path_table, path_dec):
    fmt = res.copy()
    fmt["target"] = fmt["target"].map(TARGETS)
    fmt["baseline"] = fmt["baseline"].map(BASELINES)
    header = (f"Test origins {test_start:%Y-%m-%d %H:%M} .. {end:%Y-%m-%d %H:%M} UTC (last {TEST_DAYS} days of "
              f"official data), outage rows dropped. Threshold = max F1 on the last {THRESHOLD_DAYS} days of train. "
              "auc_within_oblast = mean of per-oblast AUCs (oblasts with both classes in test).\n\n")
    path_table.write_text(header + md_table(fmt) + "\n")
    path_dec.write_text("Target (a) on the test month: how much is the current alert continuing.\n\n"
                        + md_table(dec) + "\n")


def plot_h6(res, path):
    INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    colors = {"persistence": "#2a78d6", "yesterday": "#eb6834", "frequency": "#1baf7a"}
    metrics = ["brier", "auc", "auc_within_oblast", "precision", "recall", "f1"]
    labels = ["Brier (lower is better)", "AUC, pooled", "AUC, within oblast", "precision", "recall", "F1"]
    sub = res[res["H"] == 6]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True, facecolor=SURFACE)
    for ax, (target, title) in zip(axes, TARGETS.items()):
        d = sub[sub["target"] == target].set_index("baseline")
        base = d["base_rate"].iloc[0]
        ax.axvline(base, color=INK2, lw=0.8, ls="--", label="test base rate")
        for j, (name, color) in enumerate(colors.items()):
            ypos = np.arange(len(metrics)) + (j - 1) * 0.22
            ax.scatter(d.loc[name, metrics].astype(float), ypos, s=42, color=color, zorder=3,
                       edgecolor=SURFACE, linewidth=1.5, label=BASELINES[name])
        ax.set_yticks(range(len(metrics)), labels)
        ax.set_xlim(0, 1)
        ax.set_title(f"{title}, H = 6\nbase rate {base:.2f}", loc="left", color=INK, fontsize=11)
        ax.grid(axis="x", color=GRID, lw=0.6)
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(INK2)
        ax.tick_params(colors=INK2)
    axes[0].invert_yaxis()  # shared y axis: invert once
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.16), ncol=4, frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor=SURFACE)


def main():
    rows, episodes, raw, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    res, dec = score_table(rows, first, end, test_start)

    in_test = lambda e: ((e["start"] >= test_start) & (e["start"] < end)).sum()
    print(f"restarts within 5 min joined in the test month: {in_test(raw) - in_test(episodes)} "
          f"({in_test(raw)} raw episode starts -> {in_test(episodes)})")

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    res.to_csv(out / "baselines_test.csv", index=False, float_format="%.4f")
    write_markdown(res, dec, test_start, end - pd.Timedelta(hours=1), out / "baselines_test.md",
                   out / "persistence_vs_target_a.md")
    plot_h6(res, ROOT / "figures" / "baselines_h6.png")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(res.round(3).to_string(index=False))
        print(dec.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
