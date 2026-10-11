"""Telegram experiment: "LightGBM from 2026-01-01" with and without per-oblast features from the Air Force channel.

    python scripts/evaluate_telegram.py              # progress, files written, short summary
    python scripts/evaluate_telegram.py --verbose    # also print every table

Same rows, split, training rows, protocol and thresholds as scripts/evaluate.py (main). The only
difference between the 2026 models is the seven columns of src/telegram_features.py, built with
  lag 0   posts published strictly before t
  lag 15  posts published before t - 15 minutes (the gain must not ride on the seconds between a post
          and a siren)
Next to them: the full-history LightGBM of main (it has no Telegram history) and the three baselines.
Checks that every row it shares with main reproduces results/test_table.csv. Target (b) is modelled;
target (a) is reported as "1 if active at t, else model(b)", as on main.

Also: a day-block bootstrap of "with minus without" per lag, per-oblast win counts, tree counts,
feature importance, and how the new columns behave over the months (a calendar proxy would show a trend).
Writes results/telegram/*.md|csv.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts.evaluate import (PERIODS, POST_SWITCH_START, TARGETS, baseline_notes,
                              check_state_features_outside_outages, fit_predict, md_table, per_oblast_auc)
from scripts.evaluate_news import day_bootstrap
from src.baselines import frequency_table, same_hour_yesterday, train_frequency
from src.dataset import EVAL_LOOKBACK, HORIZONS, TEST_DAYS, build_rows, split
from src.features import FEATURES, build_features, load_neighbours
from src.load import OFFICIAL_OUTAGES
from src.metrics import best_f1_threshold, summarize
from src.targets import touches
from src.telegram_features import TG_FEATURES, load_posts, tg_features

LAGS = {"tg0": pd.Timedelta(0), "tg15": pd.Timedelta(minutes=15)}
PREDICTORS = {"lgbm": "LightGBM full history (main)", "lgbm_2026": "LightGBM from 2026-01-01",
              "lgbm_2026_tg0": "LightGBM from 2026-01-01 + Telegram (posts < t)",
              "lgbm_2026_tg15": "LightGBM from 2026-01-01 + Telegram (posts < t-15min)",
              "persistence": "same as now", "yesterday": "same hour yesterday",
              "frequency": "train freq oblast x hour x weekday"}
OUT = ROOT / "results" / "telegram"
T0 = time.time()


def say(msg):
    print(f"{msg} [{time.time() - T0:.0f}s]", flush=True)


def wrote(path):
    print(f"wrote {path.relative_to(ROOT)}", flush=True)


def summary(res):
    b = res[res["target"] == "b_start"].set_index(["H", "predictor", "period"])
    cell = lambda H, name, period: (f"{b.loc[(H, name, period), 'auc_within_oblast']:.3f} / "
                                    f"{b.loc[(H, name, period), 'brier']:.3f}")
    lines = ["", "Summary. Target (b) new alert starts in (t, t+H]; within-oblast AUC / Brier: LightGBM from",
             "2026-01-01 with Telegram (posts < t) | with Telegram (posts < t-15min) | without | train-frequency",
             "baseline. All three baselines and the full-history model: results/telegram/test_table.md and",
             "results/telegram/test_table_by_period.md."]
    for period, title in [("all", "all 24 test days"), ("sep", "Sep 4-5 only (7-day features scaled)")]:
        lines.append(f"{title}:")
        for H in HORIZONS:
            lines.append(f"  H={H}  {cell(H, 'lgbm_2026_tg0', period)} | {cell(H, 'lgbm_2026_tg15', period)} | "
                         f"{cell(H, 'lgbm_2026', period)} | {cell(H, 'frequency', period)}")
    lines += baseline_notes(res, ["lgbm_2026_tg0", "lgbm_2026_tg15", "lgbm_2026"],
                            {"all": "on all 24 test days", "sep": "on Sep 4-5"}, labels=PREDICTORS)
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="LightGBM from 2026-01-01 with and without per-oblast Telegram "
                                             "features at lag 0 and 15 minutes; writes results/telegram/.")
    ap.add_argument("--verbose", action="store_true", help="also print every table")
    args = ap.parse_args()

    rows, episodes, raw, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    oblasts = sorted(rows["oblast"].unique())
    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, oblasts)
    posts = load_posts()
    say(f"posts: {len(posts)} from {posts['time'].min():%Y-%m-%d %H:%M} to {posts['time'].max():%Y-%m-%d %H:%M} UTC, "
        f"{(posts['units'].map(len) > 0).mean():.0%} name at least one oblast")
    tg = {name: tg_features(rows, posts, lag) for name, lag in LAGS.items()}
    now, y_now = rows["now"].astype(float), rows["now"]
    lookback_complete = ~touches(rows, OFFICIAL_OUTAGES, before=pd.Timedelta(days=7), after=pd.Timedelta(0))
    day = rows["t"].dt.floor("D")
    from_2026 = rows["t"] >= POST_SWITCH_START
    covered = rows["t"] - pd.Timedelta(hours=24) >= posts["time"].min()  # a full 24h of posts before t

    results, importance, splits, wins, boot, tree_counts = [], {}, {}, [], [], []
    for H in HORIZONS:
        m = split(rows, first, end, test_start, H, EVAL_LOOKBACK)
        test = m["test"]
        check_state_features_outside_outages(feats[H], rows, test)
        for name in LAGS:
            assert tg[name].drop(columns="tg_share6h")[test].notna().all().all(), "Telegram features missing on test rows"
        m26 = {**m, "train": m["train"] & from_2026, "before_last_week": m["before_last_week"] & from_2026}
        assert covered[m26["train"]].all(), "2026 training rows without a full 24h of posts before them"
        periods = {"all": test, "aug": test & lookback_complete, "sep": test & ~lookback_complete}
        yb = rows[f"b_start_{H}"]

        fitted, trees, finals = {}, {}, {}
        fitted["lgbm"], trees["lgbm"], _ = fit_predict(feats[H], yb, m)
        fitted["lgbm_2026"], trees["lgbm_2026"], _ = fit_predict(feats[H], yb, m26)
        for name in LAGS:
            X = feats[H].join(tg[name])[FEATURES + TG_FEATURES]
            fitted[f"lgbm_2026_{name}"], trees[f"lgbm_2026_{name}"], finals[name] = fit_predict(X, yb, m26)
        tree_counts.append({"H": H, **{PREDICTORS[k]: v for k, v in trees.items()}})
        say(f"H={H}: trees " + ", ".join(f"{k} {v}" for k, v in trees.items()))

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
                for lag_name in LAGS:
                    key = f"lgbm_2026_{lag_name}"
                    for period, mask in periods.items():
                        per = {n: per_oblast_auc(y[mask], fitted[n][mask], rows.loc[mask, "oblast"]) for n in (key, "lgbm_2026")}
                        both = per[key].notna() & per["lgbm_2026"].notna()
                        wins.append({"H": H, "lag": lag_name, "period": PERIODS[period], "oblasts_compared": int(both.sum()),
                                     "with_telegram_higher_auc": int((per[key] > per["lgbm_2026"])[both].sum())})
                    b = day_bootstrap(y[test], fitted[key][test], fitted["lgbm_2026"][test],
                                      rows.loc[test, "oblast"], day[test])
                    boot.append({"H": H, "lag": lag_name, "test_days": int(day[test].nunique()), **b})
        for name in LAGS:
            cols = FEATURES + TG_FEATURES
            gain = pd.Series(finals[name].feature_importance("gain"), index=cols)
            n_split = pd.Series(finals[name].feature_importance("split"), index=cols)
            importance[(H, name)] = (gain / gain.sum()).sort_values(ascending=False)
            splits[(H, name)] = n_split / n_split.sum()

    res = pd.DataFrame(results).sort_values(["target", "H"], ascending=[False, True], kind="stable").reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "test_table.csv", index=False, float_format="%.4f")
    wrote(OUT / "test_table.csv")

    main_tab = pd.read_csv(ROOT / "results" / "test_table.csv")
    key = ["target", "H", "predictor", "period"]
    num = ["n_test", "base_rate", "auc_within_oblast", "brier", "auc_pooled", "precision", "recall", "f1"]
    ours = pd.read_csv(OUT / "test_table.csv")
    both = ours.merge(main_tab, on=key, suffixes=("", "_main"))
    assert len(both) == len(ours[~ours["predictor"].str.contains("_tg")]), "rows missing from main's table"
    diff = sum(int((both[c] != both[f"{c}_main"]).sum()) for c in num)
    print(f"check: the {len(both)} rows shared with results/test_table.csv match it ({len(both) * len(num)} values, "
          f"{diff} differences)", flush=True)
    assert diff == 0

    labels = dict(target=lambda d: d["target"].map(TARGETS), predictor=lambda d: d["predictor"].map(PREDICTORS),
                  period=lambda d: d["period"].map(PERIODS))
    all_tab = res[res["period"] == "all"].drop(columns="period").assign(**{k: v for k, v in labels.items() if k != "period"})
    note = (f"Telegram experiment (branch telegram). Test origins: last {TEST_DAYS} days of official data from "
            f"{test_start:%Y-%m-%d} UTC, minus rows whose [t-24h, t+H] touches the 2026-08-29..09-02 outage: 24 days "
            "(Aug 7-28, Sep 4-5), the same rows as main. All 2026 models train on the same 2026 rows; '+ Telegram' adds "
            "seven per-oblast columns from the Air Force channel posts (src/telegram_features.py): posts strictly before t, "
            "or before t-15min. Every row without '+ Telegram' reproduces results/test_table.csv exactly. "
            "auc_within_oblast = mean of per-oblast AUCs (main number). Thresholds: max F1 on the last train week; 0/1 "
            "baselines as is. By period: test_table_by_period.md.\n\n")
    (OUT / "test_table.md").write_text(note + md_table(all_tab) + "\n")
    wrote(OUT / "test_table.md")
    by_period = res.assign(**labels)[["target", "H", "predictor", "period", "n_test", "base_rate", "auc_within_oblast",
                                      "n_oblasts_auc", "brier", "precision", "recall", "f1"]]
    (OUT / "test_table_by_period.md").write_text(
        "Every predictor on all 24 test days, on Aug 7-28 only and on Sep 4-5 only (same thresholds). On Sep 4-5 the "
        "7-day alert features are computed over the observed part of their window; the Telegram features have no gap there. "
        "Sep 4-5 is 48 origins per oblast: within-oblast AUC there is very noisy.\n\n" + md_table(by_period) + "\n")
    wrote(OUT / "test_table_by_period.md")

    tab = lambda lag: pd.DataFrame({h: [f"{n} ({100 * v:.1f}%)" for n, v in importance[(h, lag)].items()] for h in HORIZONS})
    imp_md = ""
    for lag in LAGS:
        imp = tab(lag).rename(columns=lambda h: f"H={h}")
        imp.insert(0, "rank", range(1, len(imp) + 1))
        tg_imp = pd.DataFrame([{"H": h, "feature": f, "rank by gain": int(list(importance[(h, lag)].index).index(f)) + 1,
                                "share of gain": importance[(h, lag)][f], "share of splits": splits[(h, lag)][f]}
                               for h in HORIZONS for f in TG_FEATURES])
        imp_md += f"\n### lag {lag[2:]} ({'posts < t' if lag == 'tg0' else 'posts < t-15min'})\n\n" + md_table(imp) + \
                  "\n\nThe seven Telegram features:\n\n" + md_table(tg_imp) + "\n"
    (OUT / "feature_importance.md").write_text(
        f"LightGBM from 2026-01-01 + Telegram, test fit, all {len(FEATURES) + len(TG_FEATURES)} features by share of total gain, per H.\n" + imp_md)
    wrote(OUT / "feature_importance.md")
    wins, boot = pd.DataFrame(wins), pd.DataFrame(boot)
    (OUT / "telegram_vs_no_telegram.md").write_text(
        "Target (b). In how many oblasts the model with Telegram has the higher within-oblast AUC than the same model without:\n\n"
        + md_table(wins) + "\n\nDay-block bootstrap on all 24 test days (1000 resamples of whole days, seed 0): difference with Telegram "
        "minus without, within-oblast AUC (higher is better) and Brier (lower is better), point value and 95% percentile interval; "
        "share_auc_diff_gt_0 = share of resamples where Telegram has the higher AUC.\n\n" + md_table(boot, "{:.4f}") + "\n\n"
        "Number of trees chosen by early stopping on the last train week (validation fit, 100 rounds patience); the test fit uses "
        "the same number:\n\n" + md_table(pd.DataFrame(tree_counts)) + "\n")
    wrote(OUT / "telegram_vs_no_telegram.md")

    # do the new columns drift over the months (a calendar proxy would)? 2026 rows, mean per month
    m6 = split(rows, first, end, test_start, 6, EVAL_LOOKBACK)
    sel = (m6["train"] & from_2026) | m6["test"]
    drift = pd.concat([tg["tg0"][sel], rows.loc[sel, "t"].dt.strftime("%Y-%m").rename("month")], axis=1).groupby("month").mean()
    drift.insert(0, "posts_per_day", posts.assign(month=posts["time"].dt.strftime("%Y-%m")).groupby("month").size()
                 / posts.assign(month=posts["time"].dt.strftime("%Y-%m"), d=posts["time"].dt.floor("D")).groupby("month")["d"].nunique())
    (OUT / "feature_drift_by_month.md").write_text(
        "Mean of each Telegram column (lag 0) over the 2026 training and test rows, by month, next to the channel's posts per day. "
        "The post rate rises over 2026; the per-oblast columns are bounded or relative, so they should not follow it.\n\n"
        + md_table(drift.reset_index(), "{:.3f}") + "\n")
    wrote(OUT / "feature_drift_by_month.md")

    # how often each column is 1 / what it looks like: per post, and per (oblast, hour) over the 2026 rows used
    flags = ["tg_ballistic", "tg_missile", "tg_kab"]
    prev = pd.DataFrame({
        "share of posts": [posts[c].mean() for c in flags],
        "share of oblast-hours, lag 0": [tg["tg0"].loc[sel, c].mean() for c in flags],
        "share of oblast-hours, lag 15min": [tg["tg15"].loc[sel, c].mean() for c in flags]}, index=flags)
    other = pd.DataFrame({lag: tg[lag].loc[sel, ["tg_m1h", "tg_m3h", "tg_share6h", "tg_min_since"]].mean() for lag in LAGS})
    (OUT / "flag_prevalence.md").write_text(
        "How often each national flag is 1 (2026 training and test rows; posts: all 2026 posts incl. the last days of 2025):\n\n"
        + md_table(prev.reset_index().rename(columns={"index": "flag"}), "{:.3f}") + "\n\n"
        f"Posts naming at least one oblast: {(posts['units'].map(len) > 0).mean():.1%} of {len(posts)}. Mean of the oblast columns "
        "over the same rows:\n\n" + md_table(other.reset_index().rename(columns={"index": "column"}), "{:.3f}") + "\n")
    wrote(OUT / "flag_prevalence.md")

    summary(res)
    if not args.verbose:
        return
    print()
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 300):
        print(all_tab.drop(columns=["n_oblasts_auc", "target"]).round(3).to_string(index=False))
        print(wins.to_string(index=False)); print(boot.round(4).to_string(index=False)); print(drift.round(3).to_string())


if __name__ == "__main__":
    main()
