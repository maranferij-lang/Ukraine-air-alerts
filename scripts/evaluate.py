"""Round 3: LightGBM for target (b) next to the three baselines, on the same test rows.

    python scripts/evaluate.py

Rows: test = last 30 full days of official data. A row is used only if its 7-day feature
lookback and its target window stay clear of known outages, which drops the rows right after the
2026-08-29..09-02 outage. Train = every row whose target window closes before the test month.

Model, per H: one LightGBM for all oblasts (oblast categorical), target (b).
  validation fit: train rows before the last train week; early stopping and the F1 threshold are
                  chosen on the last train week
  test fit:       all train rows, with the validation fit's number of trees. The threshold is the
                  validation fit's (known approximation: picked on a slightly different model).
Target (a) is reported as "1 if active at t, else model(b)".
Baselines: persistence and same-hour-yesterday are 0/1 and reported as is (no threshold search).
Train frequency: threshold picked on the last train week from a table fitted without that week
(same approximation); the test scores use the table fitted on all of train.

Writes results/*.md|csv and figures/model_vs_baselines_h6.png, figures/reliability_h6.png.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.baselines import frequency_table, same_hour_yesterday, train_frequency
from src.dataset import HORIZONS, TEST_DAYS, build_rows, split
from src.features import FEATURES, build_features, load_neighbours
from src.metrics import (best_f1_threshold, brier_decomposition, reliability_table, summarize)

LOOKBACK = pd.Timedelta(days=7)  # longest feature window (share_7d, starts_7d)
PARAMS = {"objective": "binary", "metric": "binary_logloss", "learning_rate": 0.05, "num_leaves": 31,
          "min_data_in_leaf": 200, "seed": 0, "deterministic": True, "force_row_wise": True,
          "num_threads": 4, "verbose": -1}
MAX_TREES = 2000
PREDICTORS = {"model": "LightGBM", "persistence": "same as now", "yesterday": "same hour yesterday",
              "frequency": "train freq oblast x hour x weekday"}
TARGETS = {"b_start": "(b) new alert starts in (t, t+H]",
           "a_active": "(a) active in (t, t+H]  [model = active at t, else model(b)]"}
COLORS = {"model": "#6250d6", "persistence": "#2a78d6", "yesterday": "#eb6834", "frequency": "#1baf7a"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
OUT = ROOT / "results"
FIG = ROOT / "figures"


def fit_predict(X, y, m):
    """Validation fit -> number of trees and last-week scores; test fit -> test scores."""
    y = y.astype(int)
    fit_rows, week = m["before_last_week"], m["last_week"]
    dtrain = lgb.Dataset(X[fit_rows], y[fit_rows])
    dweek = lgb.Dataset(X[week], y[week], reference=dtrain)
    val = lgb.train(PARAMS, dtrain, num_boost_round=MAX_TREES, valid_sets=[dweek],
                    callbacks=[lgb.early_stopping(100, verbose=False)])
    n_trees = val.best_iteration
    final = lgb.train(PARAMS, lgb.Dataset(X[m["train"]], y[m["train"]]), num_boost_round=n_trees)
    scores = pd.Series(np.nan, index=X.index)
    scores[week] = val.predict(X[week], num_iteration=n_trees)
    scores[m["test"]] = final.predict(X[m["test"]])
    return scores, n_trees, final


def md_table(df, floatfmt="{:.3f}"):
    cells = df.map(lambda v: floatfmt.format(v) if isinstance(v, float) else str(v))
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(r) + " |" for r in cells.itertuples(index=False)]
    return "\n".join(lines)


def comparison_plot(res, path):
    metrics = ["auc_within_oblast", "brier", "precision", "recall", "f1"]
    labels = ["AUC within oblast", "Brier (lower is better)", "precision", "recall", "F1"]
    sub = res[res["H"] == 6]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True, facecolor=SURFACE)
    for ax, target in zip(axes, TARGETS):
        d = sub[sub["target"] == target].set_index("predictor")
        base = d["base_rate"].iloc[0]
        ax.axvline(base, color=INK2, lw=0.8, ls="--", label="test base rate")
        for j, name in enumerate(PREDICTORS):
            ax.scatter(d.loc[name, metrics].astype(float), np.arange(len(metrics)) + (j - 1.5) * 0.18,
                       s=42, color=COLORS[name], zorder=3, edgecolor=SURFACE, linewidth=1.5,
                       label=PREDICTORS[name])
        ax.set_yticks(range(len(metrics)), labels)
        ax.set_xlim(0, 1)
        short = "(b) new alert starts in (t, t+H]" if target == "b_start" else "(a) alert active in (t, t+H]"
        ax.set_title(f"{short}, H = 6\nbase rate {base:.2f}", loc="left", color=INK, fontsize=11)
        style(ax)
    axes[0].invert_yaxis()
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.16), ncol=5, frameon=False, fontsize=9)
    fig.subplots_adjust(left=0.17, right=0.98, top=0.78, bottom=0.08, wspace=0.08)
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor=SURFACE)


def reliability_plot(tables, path):
    fig, (ax, axn) = plt.subplots(2, 1, figsize=(6.5, 7), sharex=True, facecolor=SURFACE,
                                  gridspec_kw={"height_ratios": [3, 1.2], "hspace": 0.08})
    ax.plot([0, 1], [0, 1], color=INK2, lw=0.8, ls="--", label="perfect calibration")
    width = 0.035
    for j, (name, t) in enumerate(tables.items()):
        ax.plot(t["mean_predicted"], t["observed"], marker="o", ms=6, lw=1.6, color=COLORS[name],
                label=PREDICTORS[name])
        centers = np.array([float(i.split("-")[0]) + 0.05 for i in t.index])
        axn.bar(centers + (j - 0.5) * width, t["n"], width=width, color=COLORS[name])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_ylabel("observed share with a new alert", color=INK2)
    ax.set_title("(b) new alert starts in (t, t+6h]: reliability, test month, 10 bins",
                 loc="left", color=INK, fontsize=11)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    axn.set_ylabel("rows per bin", color=INK2)
    axn.set_xlabel("predicted probability", color=INK2)
    for a in (ax, axn):
        style(a)
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor=SURFACE)


def style(ax):
    ax.grid(color=GRID, lw=0.6)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2)


def main():
    rows, episodes, raw, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, rows["oblast"].unique())
    now = rows["now"].astype(float)

    results, calibration, importance, base_rates, decomposition = [], [], {}, {}, []
    reliability = {}
    for H in HORIZONS:
        m = split(rows, first, end, test_start, H, LOOKBACK)
        model_b, n_trees, final = fit_predict(feats[H], rows[f"b_start_{H}"], m)
        model_a = now.where(now == 1, model_b)
        print(f"H={H}: {n_trees} trees; rows train {m['train'].sum()}, validation fit "
              f"{m['before_last_week'].sum()}, last week {m['last_week'].sum()}, test {m['test'].sum()}")

        for target, model_scores in [("b_start", model_b), ("a_active", model_a)]:
            col = f"{target}_{H}"
            y = rows[col]
            predictors = {  # name: (scores used on test, scores used on the last train week or None)
                "model": (model_scores, model_scores),
                "persistence": (now, None),
                "yesterday": (same_hour_yesterday(rows, col), None),
                "frequency": (train_frequency(rows, frequency_table(rows[m["train"]], col)),
                              train_frequency(rows, frequency_table(rows[m["before_last_week"]], col))),
            }
            for name, (s_test, s_week) in predictors.items():
                assert s_test[m["test"]].notna().all(), (name, col)
                thr = None if s_week is None else best_f1_threshold(y[m["last_week"]], s_week[m["last_week"]])
                row = summarize(y[m["test"]], s_test[m["test"]], rows.loc[m["test"], "oblast"], thr)
                results.append({"target": target, "H": H, "predictor": name, "n_test": int(m["test"].sum()),
                                "base_rate": float(y[m["test"]].mean()), **row})
            if target == "b_start":
                for name in ["model", "frequency"]:
                    s = predictors[name][0][m["test"]]
                    d = brier_decomposition(y[m["test"]], s)
                    calibration.append({"H": H, "predictor": name, "mean_predicted": float(s.mean()),
                                        "observed": float(y[m["test"]].mean()),
                                        **{k: float(v) for k, v in d.items()}})
                    if H == 6:
                        reliability[name] = reliability_table(y[m["test"]], s)

        t = rows[m["test"]]
        base_rates[f"b_start_{H}"] = t.groupby("oblast")[f"b_start_{H}"].mean()
        ya, yb, nw = t[f"a_active_{H}"], t[f"b_start_{H}"], t["now"]
        decomposition.append({
            "H": H, "n_test": len(t), "base_rate_a": ya.mean(), "share_active_at_t": nw.mean(),
            "share_of_a_positives_active_at_t": (nw & ya).sum() / ya.sum(),
            "share_of_a_positives_new_start_while_quiet": (~nw & ya).sum() / ya.sum(),
            "rows_a_ne_now_or_b": int((ya != (nw | yb)).sum()),
        })
        gain = pd.Series(final.feature_importance("gain"), index=FEATURES)
        importance[f"H={H}"] = (gain / gain.sum()).sort_values(ascending=False)

    res = pd.DataFrame(results)
    res = res.sort_values(["target", "H"], ascending=[False, True], kind="stable").reset_index(drop=True)
    OUT.mkdir(exist_ok=True)
    res.to_csv(OUT / "test_table.csv", index=False, float_format="%.4f")
    fmt = res.assign(target=res["target"].map(TARGETS), predictor=res["predictor"].map(PREDICTORS))
    note = (f"Test origins from {test_start:%Y-%m-%d %H:%M} UTC (last {TEST_DAYS} days of official data); rows "
            "whose 7-day lookback or target window touches the outage are dropped. auc_within_oblast = mean of "
            "per-oblast AUCs (main number). Thresholds: max F1 on the last train week (model: validation fit; "
            "frequency: table without that week); 0/1 baselines are taken as is.\n\n")
    (OUT / "test_table.md").write_text(note + md_table(fmt) + "\n")

    br = pd.DataFrame(base_rates).sort_values("b_start_6", ascending=False)
    br.index.name = "oblast"
    (OUT / "base_rates_by_oblast.md").write_text(
        "Base rate of (b) new alert starts in (t, t+H] per oblast, test-month rows.\n\n"
        + md_table(br.reset_index()) + "\n")
    (OUT / "persistence_vs_target_a.md").write_text(
        "Target (a) on the test rows: how much is the current alert continuing.\n\n"
        + md_table(pd.DataFrame(decomposition)) + "\n")
    cal = pd.DataFrame(calibration)
    rel6 = pd.concat(reliability, names=["predictor", "bin"]).reset_index()
    (OUT / "calibration.md").write_text(
        "Target (b), test month. Brier = reliability - resolution + uncertainty (+ residual from 10 "
        "equal-width bins). Reliability: lower is better (miscalibration). Resolution: higher is better.\n\n"
        + md_table(cal, "{:.4f}") + "\n\nReliability table, H = 6:\n\n" + md_table(rel6) + "\n")
    imp = pd.DataFrame({h: [f"{name} ({100 * v:.1f}%)" for name, v in s.head(10).items()]
                        for h, s in importance.items()})
    imp.insert(0, "rank", range(1, 11))
    (OUT / "feature_importance.md").write_text(
        "Top 10 features by share of total gain, test-fit model per H.\n\n" + md_table(imp) + "\n")

    comparison_plot(res, FIG / "model_vs_baselines_h6.png")
    reliability_plot(reliability, FIG / "reliability_h6.png")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(res.drop(columns=["n_oblasts_auc"]).round(3).to_string(index=False))
        print(cal.round(4).to_string(index=False))
        print(pd.DataFrame(decomposition).round(3).to_string(index=False))
        print(br.round(3).to_string())
        print(imp.to_string(index=False))


if __name__ == "__main__":
    main()
