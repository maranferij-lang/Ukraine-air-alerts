"""LightGBM for target (b) next to a logistic regression and the three baselines, on the same rows.

    python scripts/evaluate.py              # progress, files written, short summary
    python scripts/evaluate.py --verbose    # also print every table (they are all in results/)

Rows: test = last 30 full days of official data, minus rows whose [t-24h, t+H] touches a known
outage: 24 usable days (2026-08-07..08-28 and 2026-09-04..09-05). On Sep 4-5 the 7-day features
are computed over the observed part of their window (lookback incomplete); every number is also
reported for Aug 7-28 and Sep 4-5 separately. Train = every row whose target window closes before
the test month.

Predictors for target (b), per H:
  LightGBM                  all oblasts, oblast categorical, full history
  LightGBM from 2026-01-01  same features, trained on 2026 rows only
  logistic                  starts_7d + 24 hour dummies + oblast dummies (src/logit.py)
  persistence, same hour yesterday (0/1, reported as is), train frequency (static table)
Fitted predictors use a validation fit (train minus the last week) to pick the F1 threshold (and
LightGBM's number of trees) on the last train week; the test fit then uses all its training rows.
Known approximation: the threshold comes from the validation fit, not the test fit. The frequency
baseline's threshold likewise comes from a table fitted without the last week.
Target (a) is reported as "1 if active at t, else model(b)".

Writes results/*.md|csv and figures/model_vs_baselines_h6.png, figures/reliability_h6.png. Also
saves what scripts/predict.py needs to models/ (not committed): the three LightGBM test fits (one per
H), the train-frequency tables for target (b), and info.json with the data range and split.
"""
import argparse
import json
import sys
import textwrap
import time
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
from src import logit
from src.dataset import EVAL_LOOKBACK, HORIZONS, TEST_DAYS, build_rows, split
from src.features import FEATURES, HOURS_SINCE_CAP, MASKS, build_features, load_neighbours
from src.load import OFFICIAL_OUTAGES
from src.metrics import auc, best_f1_threshold, brier_decomposition, reliability_table, summarize
from src.targets import touches

POST_SWITCH_START = pd.Timestamp("2026-01-01", tz="UTC")
PARAMS = {"objective": "binary", "metric": "binary_logloss", "learning_rate": 0.05, "num_leaves": 31,
          "min_data_in_leaf": 200, "seed": 0, "deterministic": True, "force_row_wise": True,
          "num_threads": 4, "verbose": -1}
MAX_TREES = 2000
PREDICTORS = {"lgbm": "LightGBM", "lgbm_2026": "LightGBM from 2026-01-01",
              "logit": "logistic (starts_7d + hour + oblast)", "persistence": "same as now",
              "yesterday": "same hour yesterday", "frequency": "train freq oblast x hour x weekday"}
FITTED = ["lgbm", "lgbm_2026", "logit"]
PLOT_PREDICTORS = ["lgbm", "persistence", "yesterday", "frequency"]
PERIODS = {"all": "all 24 test days", "aug": "Aug 7-28 (7-day lookback complete)",
           "sep": "Sep 4-5 (7-day lookback partly in the outage)"}
TARGETS = {"b_start": "(b) new alert starts in (t, t+H]",
           "a_active": "(a) active in (t, t+H]  [model = active at t, else model(b)]"}
COLORS = {"lgbm": "#6250d6", "persistence": "#2a78d6", "yesterday": "#eb6834", "frequency": "#1baf7a"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
OUT = ROOT / "results"
FIG = ROOT / "figures"
MODELS = ROOT / "models"
T0 = time.time()


def say(msg):
    print(f"{msg} [{time.time() - T0:.0f}s]", flush=True)


def wrote(path):
    print(f"wrote {path.relative_to(ROOT)}", flush=True)


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


def fit_predict_logit(F, y, m, oblasts):
    """Same protocol as fit_predict: validation fit for last-week scores, test fit on all train."""
    X = pd.DataFrame(logit.design(F, oblasts), index=F.index)
    w_val, it_val = logit.fit(X[m["before_last_week"]].to_numpy(), y[m["before_last_week"]])
    w, it = logit.fit(X[m["train"]].to_numpy(), y[m["train"]])
    scores = pd.Series(np.nan, index=F.index)
    scores[m["last_week"]] = logit.predict(X[m["last_week"]].to_numpy(), w_val)
    scores[m["test"]] = logit.predict(X[m["test"]].to_numpy(), w)
    return scores, it, w


def check_state_features_outside_outages(F, rows, test):
    """hours_since_end / hours_since_start must not point into a masked outage on any test row."""
    t = rows.loc[test, "t"]
    f = F[test]
    last_end = t - pd.to_timedelta(f["hours_since_end"].where(f["hours_since_end"] < HOURS_SINCE_CAP), unit="h")
    start = t - pd.to_timedelta(f["hours_since_start"].where(f["now"] == 1), unit="h")
    bad = 0
    for a, b in OFFICIAL_OUTAGES:
        a, b = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
        bad += int(((last_end >= a) & (last_end < b)).sum() + ((start >= a) & (start < b)).sum())
    assert bad == 0, f"{bad} test rows have state features pointing into an outage"


def per_oblast_auc(y, s, oblast):
    return pd.Series({ob: auc(y[idx], s[idx]) for ob, idx in oblast.groupby(oblast).groups.items()})


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
        for j, name in enumerate(PLOT_PREDICTORS):
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
    ax.set_title("(b) new alert starts in (t, t+6h]: reliability, 24 test days, 10 bins",
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


def baseline_notes(res, models, period_names, labels=None):
    """Lines naming every (model, period) where a baseline has the higher within-oblast AUC at some H,
    so a summary that shows one baseline cannot hide a better one. labels: display names for model keys."""
    label = lambda name: (labels or {}).get(name) or model_label(name)
    b = res[res["target"] == "b_start"].set_index(["H", "predictor", "period"])["auc_within_oblast"]
    notes = []
    for period, title in period_names.items():
        for model in models:
            for base in ["persistence", "yesterday", "frequency"]:
                hs = [H for H in HORIZONS if b[(H, base, period)] > b[(H, model, period)]]
                if hs:
                    notes.append(f"Note: {title}, {PREDICTORS.get(base, base)} has a higher within-oblast AUC than "
                                 f"{label(model)} at H = {', '.join(map(str, hs))}.")
    return notes


def model_label(name):
    return {"lgbm_2026_news": "LightGBM from 2026-01-01 + news"}.get(name, PREDICTORS.get(name, name))


def where_to_look(files, extra=None):
    """Print where the outputs are and which files to open first (files: [(relative path, why)])."""
    lines = ["", "Where to look", f"  tables: {OUT}", f"  figures: {FIG}", "  open these first:"]
    lines += [f"    {path}: {why}" for path, why in files]
    if extra:
        lines += ["  next:", f"    {extra}"]
    print("\n".join(lines))


def summary(res):
    """What the headline numbers mean, in plain words: target (b), the model next to the three simple rules,
    all 24 test days and Sep 4-5 alone, plus a note wherever any simple rule beats the model on within-oblast AUC."""
    b = res[res["target"] == "b_start"].set_index(["H", "predictor", "period"])
    auc_ = lambda H, name, period="all": b.loc[(H, name, period), "auc_within_oblast"]
    brier_ = lambda H, name, period="all": b.loc[(H, name, period), "brier"]
    wrap = lambda text: textwrap.wrap(text, 100, subsequent_indent="      ")
    lines = ["", "What the numbers say. The question: will a NEW alert start in an oblast within the next H hours?",
             "Test: 24 days (Aug 7-28 and Sep 4-5), 24 oblasts, one model for all of them.",
             "  AUC = how well the model ranks risky hours above quiet ones inside one oblast (0.5 = coin flip, 1.0 = perfect).",
             "  Brier = how close the probabilities are to what happened (lower is better).", ""]
    for H in HORIZONS:
        lines += wrap(f"H={H}: the model ranks risky hours inside an oblast at {auc_(H, 'lgbm'):.3f}. The simple rules: "
                      f"same as now {auc_(H, 'persistence'):.3f}, same hour yesterday {auc_(H, 'yesterday'):.3f}, "
                      f"train frequency {auc_(H, 'frequency'):.3f}. Brier: model {brier_(H, 'lgbm'):.3f}, "
                      f"train frequency {brier_(H, 'frequency'):.3f}.")
    lines += [""] + wrap("Sep 4-5 alone (48 origins per oblast, so noisy; the 7-day history is scaled from the hours the "
                         "feed had): the model ranks at "
                         + ", ".join(f"{auc_(H, 'lgbm', 'sep'):.3f}" for H in HORIZONS) + " for H = 1, 3, 6; train frequency at "
                         + ", ".join(f"{auc_(H, 'frequency', 'sep'):.3f}" for H in HORIZONS) + ".")
    lines += baseline_notes(res, ["lgbm"], {"all": "on all 24 test days", "sep": "on Sep 4-5"})
    print("\n".join(lines))
    where_to_look([("results/test_table.md", "every number next to the three simple rules"),
                   ("figures/model_vs_baselines_h6.png", "the same comparison as a picture, for H = 6"),
                   ("results/feature_importance.md", "what the model looks at")],
                  extra='python scripts/predict.py --at "2026-09-05 14:00" --oblast Kyivska   (what the model said at one hour)')


def main():
    ap = argparse.ArgumentParser(description="LightGBM for target (b) next to the logistic regression and the "
                                             "three baselines; writes results/, figures/ and models/.")
    ap.add_argument("--verbose", action="store_true", help="also print every table (they are all in results/)")
    args = ap.parse_args()

    rows, episodes, raw, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    oblasts = sorted(rows["oblast"].unique())
    say(f"rows: {rows['oblast'].nunique()} oblasts x {rows['t'].nunique()} hours, {first:%Y-%m-%d} to "
        f"{end:%Y-%m-%d} UTC, test from {test_start:%Y-%m-%d}")
    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, oblasts)
    say(f"features: {len(FEATURES)} per row, for H = {', '.join(map(str, HORIZONS))}")
    MODELS.mkdir(exist_ok=True)
    info = {"data_first": first.isoformat(), "data_end": end.isoformat(), "test_start": test_start.isoformat(),
            "horizons": HORIZONS, "features": FEATURES, "trees": {}, "train_rows": {}}
    now = rows["now"].astype(float)
    lookback_complete = ~touches(rows, OFFICIAL_OUTAGES, before=pd.Timedelta(days=7), after=pd.Timedelta(0))
    y_now = rows["now"]

    frozen = {"oblasts": oblasts, "thresholds": {}, "logit_weights": {}}  # saved for scripts/forward_test.py
    results, calibration, importance, base_rates, decomposition = [], [], {}, {}, []
    reliability, wins, lowest_bin = {}, [], None
    for H in HORIZONS:
        m = split(rows, first, end, test_start, H, EVAL_LOOKBACK)
        test = m["test"]
        check_state_features_outside_outages(feats[H], rows, test)
        periods = {"all": test, "aug": test & lookback_complete, "sep": test & ~lookback_complete}
        yb = rows[f"b_start_{H}"]

        m26 = {**m, "train": m["train"] & (rows["t"] >= POST_SWITCH_START),
               "before_last_week": m["before_last_week"] & (rows["t"] >= POST_SWITCH_START)}
        fitted = {}
        fitted["lgbm"], trees, final = fit_predict(feats[H], yb, m)
        fitted["lgbm_2026"], trees26, _ = fit_predict(feats[H], yb, m26)
        fitted["logit"], it, w = fit_predict_logit(feats[H], yb, m, oblasts)
        say(f"H={H}: fitted LightGBM ({trees} trees), LightGBM from 2026-01-01 ({trees26} trees), "
            f"logistic ({it} iterations); train {m['train'].sum()} rows, test {test.sum()} rows")
        if args.verbose:
            print(f"     logistic starts_7d coef {w[0]:.3f}; train rows from 2026: {m26['train'].sum()}, last week "
                  f"{m['last_week'].sum()}, test = Aug {periods['aug'].sum()} + Sep 4-5 {periods['sep'].sum()}")
        final.save_model(str(MODELS / f"lgbm_b_start_h{H}.txt"))
        frequency_table(rows[m["train"]], f"b_start_{H}").rename("rate").reset_index().to_csv(
            MODELS / f"frequency_b_start_h{H}.csv", index=False)
        frozen["thresholds"][str(H)] = {}
        frozen["logit_weights"][str(H)] = [float(v) for v in w]
        info["trees"][str(H)] = int(trees)
        info["train_rows"][str(H)] = int(m["train"].sum())

        for target in ["b_start", "a_active"]:
            col = f"{target}_{H}"
            y = rows[col]
            predictors = {  # name: (scores on test, scores on the last train week or None for 0/1)
                name: ((s, s) if target == "b_start" else (now.where(y_now, s), now.where(y_now, s)))
                for name, s in fitted.items()
            }
            predictors["persistence"] = (now, None)
            predictors["yesterday"] = (same_hour_yesterday(rows, col), None)
            predictors["frequency"] = (train_frequency(rows, frequency_table(rows[m["train"]], col)),
                                       train_frequency(rows, frequency_table(rows[m["before_last_week"]], col)))
            for name, (s_test, s_week) in predictors.items():
                assert s_test[test].notna().all(), (name, col)
                thr = None if s_week is None else best_f1_threshold(y[m["last_week"]], s_week[m["last_week"]])
                if target == "b_start":
                    frozen["thresholds"][str(H)][name] = thr
                for period, mask in periods.items():
                    row = summarize(y[mask], s_test[mask], rows.loc[mask, "oblast"], thr)
                    results.append({"target": target, "H": H, "predictor": name, "period": period,
                                    "n_test": int(mask.sum()), "base_rate": float(y[mask].mean()), **row})
            if target == "b_start":
                f4 = feats[H]["freq4w"]
                wk = m["last_week"] & f4.notna()  # rolling 4-week frequency used as a score: threshold from the same last train week
                frozen["thresholds"][str(H)]["freq4w"] = best_f1_threshold(y[wk], f4[wk])
                for name in ["lgbm", "lgbm_2026", "logit", "frequency"]:
                    s = predictors[name][0][test]
                    d = brier_decomposition(y[test], s)
                    calibration.append({"H": H, "predictor": name, "mean_predicted": float(s.mean()),
                                        "observed": float(y[test].mean()), **{k: float(v) for k, v in d.items()}})
                    if H == 6 and name in ("lgbm", "frequency"):
                        reliability[name] = reliability_table(y[test], s)
                for period, mask in periods.items():
                    per = {name: per_oblast_auc(y[mask], predictors[name][0][mask], rows.loc[mask, "oblast"])
                           for name in ["lgbm", "lgbm_2026", "logit", "frequency"]}
                    for a, b in [("lgbm", "frequency"), ("lgbm", "logit"), ("lgbm_2026", "lgbm")]:
                        both = per[a].notna() & per[b].notna()
                        wins.append({"H": H, "period": PERIODS[period], "comparison": f"{PREDICTORS[a]} vs {PREDICTORS[b]}",
                                     "oblasts_compared": int(both.sum()),
                                     "first_wins": int((per[a] > per[b])[both].sum())})
                if H == 6:
                    t6 = rows[test].assign(p=fitted["lgbm"][test], y=y[test])
                    low = t6[t6["p"] < 0.1]
                    lowest_bin = low.groupby("oblast").agg(rows_in_bin=("p", "size"), mean_predicted=("p", "mean"),
                                                           observed=("y", "mean"))
                    lowest_bin["share_of_bin"] = lowest_bin["rows_in_bin"] / len(low)
                    lowest_bin["oblast_rows_in_test"] = t6.groupby("oblast").size()
                    lowest_bin = lowest_bin.sort_values("rows_in_bin", ascending=False)

        t = rows[test]
        base_rates[f"b_start_{H}"] = t.groupby("oblast")[f"b_start_{H}"].mean()
        ya, yb_t, nw = t[f"a_active_{H}"], t[f"b_start_{H}"], t["now"]
        decomposition.append({
            "H": H, "n_test": len(t), "base_rate_a": ya.mean(), "share_active_at_t": nw.mean(),
            "share_of_a_positives_active_at_t": (nw & ya).sum() / ya.sum(),
            "share_of_a_positives_new_start_while_quiet": (~nw & ya).sum() / ya.sum(),
            "rows_a_ne_now_or_b": int((ya != (nw | yb_t)).sum()),
        })
        gain = pd.Series(final.feature_importance("gain"), index=FEATURES)
        importance[f"H={H}"] = (gain / gain.sum()).sort_values(ascending=False)

    res = pd.DataFrame(results)
    res = res.sort_values(["target", "H"], ascending=[False, True], kind="stable").reset_index(drop=True)
    OUT.mkdir(exist_ok=True)
    res.to_csv(OUT / "test_table.csv", index=False, float_format="%.4f")
    wrote(OUT / "test_table.csv")
    labels = dict(target=lambda d: d["target"].map(TARGETS), predictor=lambda d: d["predictor"].map(PREDICTORS),
                  period=lambda d: d["period"].map(PERIODS))
    main_tab = res[res["period"] == "all"].drop(columns="period").assign(**{k: v for k, v in labels.items() if k != "period"})
    note = (f"Test origins: last {TEST_DAYS} days of official data from {test_start:%Y-%m-%d} UTC, minus rows whose "
            "[t-24h, t+H] touches the 2026-08-29..09-02 outage: 24 days (Aug 7-28, Sep 4-5). auc_within_oblast = "
            "mean of per-oblast AUCs (main number). Thresholds: max F1 on the last train week (fitted predictors: "
            "validation fit; frequency: table without that week); 0/1 baselines are taken as is. "
            "The same numbers split by period are in test_table_by_period.md.\n\n")
    (OUT / "test_table.md").write_text(note + md_table(main_tab) + "\n")
    wrote(OUT / "test_table.md")
    by_period = res.assign(**labels)[["target", "H", "predictor", "period", "n_test", "base_rate",
                                      "auc_within_oblast", "n_oblasts_auc", "brier", "precision", "recall", "f1"]]
    (OUT / "test_table_by_period.md").write_text(
        "Every predictor on all 24 test days, on Aug 7-28 only and on Sep 4-5 only (same thresholds). On Sep 4-5 "
        "the 7-day features are computed over the observed part of their window. Sep 4-5 is 48 origins per "
        "oblast: within-oblast AUC there covers only oblasts with both outcomes and is very noisy.\n\n"
        + md_table(by_period) + "\n")
    wrote(OUT / "test_table_by_period.md")

    br = pd.DataFrame(base_rates)
    br.index.name = "oblast"
    # rate first, oblast name second: oblasts with the same rate (three have exactly one new alert) must come out in the same order on every machine,
    # and the default sort is not stable (a Mac with numpy 2.0.2 swapped two of them)
    br = br.reset_index().sort_values(["b_start_6", "oblast"], ascending=[False, True], kind="stable").set_index("oblast")
    (OUT / "base_rates_by_oblast.md").write_text(
        "Base rate of (b) new alert starts in (t, t+H] per oblast, test rows (24 days).\n\n"
        + md_table(br.reset_index()) + "\n")
    wrote(OUT / "base_rates_by_oblast.md")
    (OUT / "persistence_vs_target_a.md").write_text(
        "Target (a) on the test rows: how much is the current alert continuing.\n\n"
        + md_table(pd.DataFrame(decomposition)) + "\n")
    wrote(OUT / "persistence_vs_target_a.md")
    cal = pd.DataFrame(calibration).assign(predictor=lambda d: d["predictor"].map(PREDICTORS))
    rel6 = pd.concat(reliability, names=["predictor", "bin"]).reset_index()
    (OUT / "calibration.md").write_text(
        "Target (b), test rows. Brier = reliability - resolution + uncertainty (+ residual from 10 "
        "equal-width bins). Reliability: lower is better (miscalibration). Resolution: higher is better.\n\n"
        + md_table(cal, "{:.4f}") + "\n\nReliability table, H = 6:\n\n" + md_table(rel6) + "\n")
    wrote(OUT / "calibration.md")
    imp = pd.DataFrame({h: [f"{name} ({100 * v:.1f}%)" for name, v in s.head(10).items()]
                        for h, s in importance.items()})
    imp.insert(0, "rank", range(1, 11))
    (OUT / "feature_importance.md").write_text(
        "Top 10 features by share of total gain, full-history LightGBM test fit, per H.\n\n" + md_table(imp) + "\n")
    wrote(OUT / "feature_importance.md")
    wins = pd.DataFrame(wins)
    (OUT / "oblast_wins.md").write_text(
        "Target (b): in how many oblasts the first predictor has the higher within-oblast AUC, on all 24 test days "
        "and on each period separately.\n\n"
        + md_table(wins) + "\n")
    wrote(OUT / "oblast_wins.md")
    (OUT / "lowest_bin_h6.md").write_text(
        "LightGBM, target (b), H = 6, test rows with predicted probability < 0.1, by oblast.\n\n"
        + md_table(lowest_bin.reset_index()) + "\n")
    wrote(OUT / "lowest_bin_h6.md")

    comparison_plot(res[res["period"] == "all"], FIG / "model_vs_baselines_h6.png")
    wrote(FIG / "model_vs_baselines_h6.png")
    reliability_plot(reliability, FIG / "reliability_h6.png")
    wrote(FIG / "reliability_h6.png")
    (MODELS / "info.json").write_text(json.dumps(info, indent=1) + "\n")
    (MODELS / "frozen.json").write_text(json.dumps(frozen, indent=1) + "\n")
    print("wrote models/ (LightGBM per H, train-frequency tables, info.json) for scripts/predict.py", flush=True)
    summary(res)
    if not args.verbose:
        return
    print()
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        print(main_tab.drop(columns=["n_oblasts_auc", "target"]).assign(t=res.loc[main_tab.index, "target"])
              .round(3).to_string(index=False))
        print(res[res["period"] != "all"][["target", "H", "predictor", "period", "n_test", "base_rate",
              "auc_within_oblast", "n_oblasts_auc", "brier", "f1"]].round(3).to_string(index=False))
        print(cal.round(4).to_string(index=False))
        print(wins.to_string(index=False))
        print(lowest_bin.round(3).to_string())
        print(imp.to_string(index=False))


if __name__ == "__main__":
    main()
