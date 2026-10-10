"""News experiment: "LightGBM from 2026-01-01" with and without the two national GDELT columns.

    python scripts/evaluate_news.py

Same rows, split, training rows, protocol and thresholds as scripts/evaluate.py (main). The only
difference between the two 2026 models is the two extra columns news_24h and news_yesterday
(src/news.py). Next to them: the full-history LightGBM of main (no news, it has no news history)
and the three baselines. Checks that every row it shares with main reproduces results/test_table.csv.
Target (b) is modelled; target (a) is reported as "1 if active at t, else model(b)", as on main.

Also: a day-block bootstrap (resampling the 24 test days, 1000 times) of the difference "with news
minus without" in within-oblast AUC and Brier, the number of trees each fit stopped at, and the
feature importance of the news model.
Writes results/news/*.md|csv.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts.evaluate import (PERIODS, POST_SWITCH_START, TARGETS, check_state_features_outside_outages,
                              fit_predict, md_table, per_oblast_auc)
from src.baselines import frequency_table, same_hour_yesterday, train_frequency
from src.dataset import EVAL_LOOKBACK, HORIZONS, TEST_DAYS, build_rows, split
from src.features import FEATURES, build_features, load_neighbours
from src.load import OFFICIAL_OUTAGES
from src.metrics import auc, best_f1_threshold, brier, summarize
from src.news import NEWS_FEATURES, load_news, news_features
from src.targets import touches

PREDICTORS = {"lgbm": "LightGBM full history (main, no news)", "lgbm_2026": "LightGBM from 2026-01-01",
              "lgbm_2026_news": "LightGBM from 2026-01-01 + news", "persistence": "same as now",
              "yesterday": "same hour yesterday", "frequency": "train freq oblast x hour x weekday"}
N_BOOT = 1000
OUT = ROOT / "results" / "news"


def day_bootstrap(y, s_with, s_without, oblast, day, n=N_BOOT, seed=0):
    """Resample whole test days with replacement; difference (with - without) in within-oblast AUC
    and in Brier. Returns the point difference and the 2.5% / 97.5% percentiles."""
    y, s_with, s_without = np.asarray(y, bool), np.asarray(s_with, float), np.asarray(s_without, float)
    oblast, day = np.asarray(oblast), np.asarray(day)
    days, obs = np.unique(day), np.unique(oblast)
    pos = {(o, d): np.flatnonzero((oblast == o) & (day == d)) for o in obs for d in days}
    rng = np.random.default_rng(seed)

    def diff(drawn):
        a = []
        for o in obs:
            idx = np.concatenate([pos[(o, d)] for d in drawn])
            a.append(auc(y[idx], s_with[idx]) - auc(y[idx], s_without[idx]))
        idx = np.concatenate([pos[(o, d)] for o in obs for d in drawn])
        return np.nanmean(a), brier(y[idx], s_with[idx]) - brier(y[idx], s_without[idx])

    point = diff(days)
    boot = np.array([diff(rng.choice(days, len(days))) for _ in range(n)])
    lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)
    return {"auc_diff": point[0], "auc_lo": lo[0], "auc_hi": hi[0],
            "brier_diff": point[1], "brier_lo": lo[1], "brier_hi": hi[1],
            "share_auc_diff_gt_0": float((boot[:, 0] > 0).mean())}


def main():
    rows, episodes, raw, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    oblasts = sorted(rows["oblast"].unique())
    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, oblasts)
    news = news_features(rows["t"], load_news())
    now = rows["now"].astype(float)
    y_now = rows["now"]
    lookback_complete = ~touches(rows, OFFICIAL_OUTAGES, before=pd.Timedelta(days=7), after=pd.Timedelta(0))
    day = rows["t"].dt.floor("D")

    results, importance, splits, wins, boot, tree_counts = [], {}, {}, [], [], []
    for H in HORIZONS:
        m = split(rows, first, end, test_start, H, EVAL_LOOKBACK)
        test = m["test"]
        check_state_features_outside_outages(feats[H], rows, test)
        assert news[test].notna().all().all(), "news features missing on test rows"
        periods = {"all": test, "aug": test & lookback_complete, "sep": test & ~lookback_complete}
        yb = rows[f"b_start_{H}"]
        m26 = {**m, "train": m["train"] & (rows["t"] >= POST_SWITCH_START),
               "before_last_week": m["before_last_week"] & (rows["t"] >= POST_SWITCH_START)}
        Xn = feats[H].join(news)[FEATURES + NEWS_FEATURES]

        fitted, trees = {}, {}
        fitted["lgbm"], trees["lgbm"], _ = fit_predict(feats[H], yb, m)
        fitted["lgbm_2026"], trees["lgbm_2026"], _ = fit_predict(feats[H], yb, m26)
        fitted["lgbm_2026_news"], trees["lgbm_2026_news"], final = fit_predict(Xn, yb, m26)
        tree_counts.append({"H": H, **{PREDICTORS[k]: v for k, v in trees.items()}})
        nan_train = int(Xn.loc[m26["train"], NEWS_FEATURES].isna().any(axis=1).sum())
        print(f"H={H}: trees {trees}; train rows from 2026 {m26['train'].sum()} ({nan_train} without a full news "
              f"window, NaN), last week {m['last_week'].sum()}, test {test.sum()} = Aug {periods['aug'].sum()} "
              f"+ Sep 4-5 {periods['sep'].sum()}", flush=True)

        for target in ["b_start", "a_active"]:
            col = f"{target}_{H}"
            y = rows[col]
            predictors = {name: (s, s) if target == "b_start" else (now.where(y_now, s),) * 2
                          for name, s in fitted.items()}
            predictors["persistence"] = (now, None)
            predictors["yesterday"] = (same_hour_yesterday(rows, col), None)
            predictors["frequency"] = (train_frequency(rows, frequency_table(rows[m["train"]], col)),
                                       train_frequency(rows, frequency_table(rows[m["before_last_week"]], col)))
            for name, (s_test, s_week) in predictors.items():
                assert s_test[test].notna().all(), (name, col)
                thr = None if s_week is None else best_f1_threshold(y[m["last_week"]], s_week[m["last_week"]])
                for period, mask in periods.items():
                    row = summarize(y[mask], s_test[mask], rows.loc[mask, "oblast"], thr)
                    results.append({"target": target, "H": H, "predictor": name, "period": period,
                                     "n_test": int(mask.sum()), "base_rate": float(y[mask].mean()), **row})
            if target == "b_start":
                for period, mask in periods.items():
                    per = {name: per_oblast_auc(y[mask], fitted[name][mask], rows.loc[mask, "oblast"])
                           for name in ["lgbm_2026_news", "lgbm_2026"]}
                    both = per["lgbm_2026_news"].notna() & per["lgbm_2026"].notna()
                    wins.append({"H": H, "period": PERIODS[period], "oblasts_compared": int(both.sum()),
                                 "with_news_higher_auc": int((per["lgbm_2026_news"] > per["lgbm_2026"])[both].sum())})
                b = day_bootstrap(y[test], fitted["lgbm_2026_news"][test], fitted["lgbm_2026"][test],
                                  rows.loc[test, "oblast"], day[test])
                boot.append({"H": H, "test_days": int(day[test].nunique()), **b})

        gain = pd.Series(final.feature_importance("gain"), index=FEATURES + NEWS_FEATURES)
        split_n = pd.Series(final.feature_importance("split"), index=FEATURES + NEWS_FEATURES)
        importance[f"H={H}"] = (gain / gain.sum()).sort_values(ascending=False)
        splits[H] = split_n / split_n.sum()

    res = pd.DataFrame(results)
    res = res.sort_values(["target", "H"], ascending=[False, True], kind="stable").reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "test_table.csv", index=False, float_format="%.4f")

    # every row shared with main must reproduce main's numbers
    main = pd.read_csv(ROOT / "results" / "test_table.csv")
    key = ["target", "H", "predictor", "period"]
    num = ["n_test", "base_rate", "auc_within_oblast", "brier", "auc_pooled", "precision", "recall", "f1"]
    ours = pd.read_csv(OUT / "test_table.csv")
    both = ours.merge(main, on=key, suffixes=("", "_main"))
    assert len(both) == len(ours[ours["predictor"] != "lgbm_2026_news"]), "rows missing from main's table"
    diff = sum(int((both[c] != both[f"{c}_main"]).sum()) for c in num)
    print(f"rows shared with main: {len(both)}, values compared: {len(both) * len(num)}, differences: {diff}")
    assert diff == 0

    labels = dict(target=lambda d: d["target"].map(TARGETS), predictor=lambda d: d["predictor"].map(PREDICTORS),
                  period=lambda d: d["period"].map(PERIODS))
    main_tab = res[res["period"] == "all"].drop(columns="period").assign(
        **{k: v for k, v in labels.items() if k != "period"})
    note = (f"News experiment (branch news). Test origins: last {TEST_DAYS} days of official data from "
            f"{test_start:%Y-%m-%d} UTC, minus rows whose [t-24h, t+H] touches the 2026-08-29..09-02 outage: 24 days "
            "(Aug 7-28, Sep 4-5), the same rows as main. Both 2026 models train on the same 2026 rows; '+ news' adds "
            "news_24h and news_yesterday (GDELT conflict events in Ukraine, national, by time added to GDELT, "
            "lag 1h). Every row except '+ news' reproduces results/test_table.csv on main exactly. auc_within_oblast "
            "= mean of per-oblast AUCs (main number). Thresholds: max F1 on the last train week; 0/1 baselines as is. "
            "By period: test_table_by_period.md.\n\n")
    (OUT / "test_table.md").write_text(note + md_table(main_tab) + "\n")
    by_period = res.assign(**labels)[["target", "H", "predictor", "period", "n_test", "base_rate",
                                      "auc_within_oblast", "n_oblasts_auc", "brier", "precision", "recall", "f1"]]
    (OUT / "test_table_by_period.md").write_text(
        "Every predictor on all 24 test days, on Aug 7-28 only and on Sep 4-5 only (same thresholds). On Sep 4-5 "
        "the 7-day alert features are computed over the observed part of their window; the news features have "
        "no gap there. Sep 4-5 is 48 origins per oblast: within-oblast AUC there is very noisy.\n\n"
        + md_table(by_period) + "\n")

    imp = pd.DataFrame({h: [f"{name} ({100 * v:.1f}%)" for name, v in s.items()] for h, s in importance.items()})
    imp.insert(0, "rank", range(1, len(imp) + 1))
    news_imp = pd.DataFrame([{"H": H, "feature": f, "rank by gain": int(list(importance[f"H={H}"].index).index(f)) + 1,
                              "share of gain": importance[f"H={H}"][f], "share of splits": splits[H][f]}
                             for H in HORIZONS for f in NEWS_FEATURES])
    (OUT / "feature_importance.md").write_text(
        f"LightGBM from 2026-01-01 + news, test fit, all {len(FEATURES) + len(NEWS_FEATURES)} features by share of "
        "total gain, per H.\n\n" + md_table(imp) + "\n\nThe two news features:\n\n" + md_table(news_imp) + "\n")
    wins = pd.DataFrame(wins)
    boot = pd.DataFrame(boot)
    (OUT / "news_vs_no_news.md").write_text(
        "Target (b). In how many oblasts the model with news has the higher within-oblast AUC than the same "
        "model without news:\n\n" + md_table(wins) + "\n\n"
        f"Day-block bootstrap on all 24 test days ({N_BOOT} resamples of whole days, seed 0): difference with news "
        "minus without, within-oblast AUC (higher is better) and Brier (lower is better), point value and 95% "
        "percentile interval; share_auc_diff_gt_0 = share of resamples where news has the higher AUC.\n\n"
        + md_table(boot, "{:.4f}") + "\n\n"
        "Number of trees chosen by early stopping on the last train week (validation fit, 100 rounds patience); "
        "the test fit uses the same number:\n\n" + md_table(pd.DataFrame(tree_counts)) + "\n")

    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 200):
        print(main_tab.drop(columns=["n_oblasts_auc", "target"]).assign(t=res.loc[main_tab.index, "target"])
              .round(3).to_string(index=False))
        print(res[res["period"] != "all"][["target", "H", "predictor", "period", "n_test", "base_rate",
              "auc_within_oblast", "n_oblasts_auc", "brier", "f1"]].round(3).to_string(index=False))
        print(wins.to_string(index=False))
        print(boot.round(4).to_string(index=False))
        print(imp.to_string(index=False))
        print(news_imp.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
