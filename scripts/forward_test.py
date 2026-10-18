"""Forward test: the frozen round-13 models scored on Ukraine Alarm API data they never saw (2026-09-07 .. 2026-10-17).

    python scripts/forward_test.py --diagnose    does the feature pipeline behave the same on API data? (no outcome is scored)
    python scripts/forward_test.py --selftest    the scoring code applied to the OLD test rows must give results/test_table.csv back
    python scripts/forward_test.py --score       the forward test itself -> results/forward_api/

Needs models/ (scripts/evaluate.py writes the LightGBM fits, the train-frequency tables, frozen.json with the thresholds and the logistic
weights) and data/api_archive/date_history/ (scripts/archive_api.py). Nothing is refitted and nothing is retuned: LightGBM trees, logistic
weights, the frequency table and every F1 threshold are exactly what evaluate.py produced from the official data (train to 2026-08-07,
thresholds from the last train week). Every feature comes from the API archive only (one source), from 2026-08-06 on.

Rows: origins t from 2026-09-07 00:00 to 2026-10-17 23:00 UTC (41 days; targets end by 2026-10-18 06:00). Target (b): a new alert starts in
(t, t+H]. Predictors: LightGBM, logistic, the three baselines (same as now, same hour yesterday, train frequency) and, as an extra, the rolling
4-week frequency (the model's freq4w feature used as a score). Metrics as in the old test (within-oblast AUC, Brier + decomposition,
calibration, precision/recall/F1 at the frozen threshold; 0/1 baselines raw) plus a day-block bootstrap (whole days, 1000 resamples, seed 0).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import rankdata

from scripts.api_check import day_files, load_api, to_official_rows
from scripts.check_no_peeking import known_at, same
from src import logit
from src.baselines import local_hour_weekday, same_hour_yesterday, train_frequency
from src.dataset import EVAL_LOOKBACK, HORIZONS, build_rows, load_inputs, split
from src.features import FEATURES, build_features, load_neighbours
from src.load import OFFICIAL_OUTAGES
from src.metrics import brier, brier_decomposition, reliability_table, summarize
from src.panel import official_episodes
from src.targets import make_rows

MODELS = ROOT / "models"
ARCHIVE = ROOT / "data" / "api_archive" / "date_history"
OUT = ROOT / "results" / "forward_api"
FIRST = pd.Timestamp("2026-08-06", tz="UTC")           # first API day saved
END = pd.Timestamp("2026-10-18 06:00", tz="UTC")       # targets must close by here (the archive covers it)
SCORE_FROM, SCORE_TO = pd.Timestamp("2026-09-07", tz="UTC"), pd.Timestamp("2026-10-18", tz="UTC")
NAMES = {"lgbm": "LightGBM", "logit": "logistic", "persistence": "same as now", "yesterday": "same hour yesterday",
         "frequency": "train frequency", "freq4w": "rolling 4-week frequency"}
BASELINES = ["persistence", "yesterday", "frequency"]
N_BOOT = 1000


def load_frozen():
    info = json.loads((MODELS / "info.json").read_text())
    frozen = json.loads((MODELS / "frozen.json").read_text())
    boosters = {H: lgb.Booster(model_file=str(MODELS / f"lgbm_b_start_h{H}.txt")) for H in HORIZONS}
    freq = {H: pd.read_csv(MODELS / f"frequency_b_start_h{H}.csv", float_precision="round_trip").set_index(["oblast", "hour", "weekday"])["rate"] for H in HORIZONS}
    assert info["features"] == FEATURES and info["horizons"] == HORIZONS
    return info, frozen, boosters, freq


def build_api(outages, official_for_raions=None):
    """API archive -> rows, episodes, features (same code as the old pipeline; `outages` = what the source did not observe)."""
    official, raions = load_inputs()
    files = day_files(ARCHIVE)
    api_rows, _, _ = to_official_rows(load_api(files), raions)
    oblasts = sorted(official["oblast"].unique())
    api_rows = api_rows[api_rows["oblast"].isin(oblasts)]
    rows, episodes, raw, first, end = build_rows(api_rows, raions, first=FIRST, end=END)
    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, oblasts, outages=outages)
    return rows, episodes, raw, feats, api_rows, raions, oblasts, files


def scores(rows, F, H, frozen, boosters, freq, oblasts):
    w = np.array(frozen["logit_weights"][str(H)])
    return {
        "lgbm": pd.Series(boosters[H].predict(F[FEATURES]), index=F.index),
        "logit": pd.Series(logit.predict(logit.design(F, oblasts), w), index=F.index),
        "persistence": rows["now"].astype(float),
        "yesterday": same_hour_yesterday(rows, f"b_start_{H}"),
        "frequency": train_frequency(rows, freq[H]),
        "freq4w": F["freq4w"].astype(float),
    }


def fast_auc(y, p):
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return np.nan
    r = rankdata(p)
    return (r[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def day_bootstrap(y, S, oblast, day, n=N_BOOT, seed=0):
    """Resample whole days with replacement. Returns {name: (auc_lo, auc_hi, brier_lo, brier_hi)} and, for the LightGBM minus every
    other predictor, the 95% interval of the difference in within-oblast AUC and in Brier, and the share of resamples where LightGBM is ahead."""
    y = np.asarray(y, bool)
    S = {k: np.asarray(v, float) for k, v in S.items()}
    oblast, day = np.asarray(oblast), np.asarray(day)
    days, obs = np.unique(day), np.unique(oblast)
    pos = {(o, d): np.flatnonzero((oblast == o) & (day == d)) for o in obs for d in days}
    rng = np.random.default_rng(seed)

    def one(drawn):
        auc_, br = {k: [] for k in S}, {}
        for o in obs:
            idx = np.concatenate([pos[(o, d)] for d in drawn])
            for k, s in S.items():
                auc_[k].append(fast_auc(y[idx], s[idx]))
        idx = np.concatenate([pos[(o, d)] for o in obs for d in drawn])
        for k, s in S.items():
            br[k] = brier(y[idx], s[idx])
        return {k: np.nanmean(v) for k, v in auc_.items()}, br

    point = one(days)
    draws = [one(rng.choice(days, len(days))) for _ in range(n)]
    out = {}
    for k in S:
        a = np.array([d[0][k] for d in draws])
        b = np.array([d[1][k] for d in draws])
        out[k] = {"auc": point[0][k], "auc_lo": np.percentile(a, 2.5), "auc_hi": np.percentile(a, 97.5),
                  "brier": point[1][k], "brier_lo": np.percentile(b, 2.5), "brier_hi": np.percentile(b, 97.5)}
        if k != "lgbm":
            da = np.array([d[0]["lgbm"] - d[0][k] for d in draws])
            db = np.array([d[1]["lgbm"] - d[1][k] for d in draws])
            out[k].update({"d_auc": point[0]["lgbm"] - point[0][k], "d_auc_lo": np.percentile(da, 2.5), "d_auc_hi": np.percentile(da, 97.5),
                           "share_auc_ahead": float((da > 0).mean()),
                           "d_brier": point[1]["lgbm"] - point[1][k], "d_brier_lo": np.percentile(db, 2.5), "d_brier_hi": np.percentile(db, 97.5),
                           "share_brier_ahead": float((db < 0).mean())})
    return out


def md(df, fmt="{:.3f}"):
    cells = df.map(lambda v: fmt.format(v) if isinstance(v, (float, np.floating)) else str(v))
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
                     + ["| " + " | ".join(r) + " |" for r in cells.itertuples(index=False)])


# ----------------------------------------------------------------------------------------------------------------------------------
def selftest():
    """The scoring code on the old official test rows: must reproduce results/test_table.csv (target b, all 24 days)."""
    info, frozen, boosters, freq = load_frozen()
    official, raions = load_inputs()
    rows, episodes, raw, first, end = build_rows(official, raions)
    oblasts = sorted(rows["oblast"].unique())
    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, oblasts)
    old = pd.read_csv(ROOT / "results" / "test_table.csv")
    old = old[(old["target"] == "b_start") & (old["period"] == "all")].set_index(["H", "predictor"])
    test_start = end - pd.Timedelta(days=30)
    bad = 0
    for H in HORIZONS:
        test = split(rows, first, end, test_start, H, EVAL_LOOKBACK)["test"]
        S = scores(rows, feats[H], H, frozen, boosters, freq, oblasts)
        y = rows[f"b_start_{H}"]
        for name in ["lgbm", "logit", "persistence", "yesterday", "frequency"]:
            thr = frozen["thresholds"][str(H)][name]
            r = summarize(y[test], S[name][test], rows.loc[test, "oblast"], thr)
            o = old.loc[(H, name)]
            for col in ["auc_within_oblast", "brier", "precision", "recall", "f1"]:
                ok = np.isclose(r[col], o[col], atol=6e-5)  # the csv keeps 4 decimals
                bad += not ok
                if not ok:
                    print(f"MISMATCH H={H} {name} {col}: {r[col]:.5f} vs {o[col]:.5f}")
    print(f"selftest: scoring code vs results/test_table.csv: {'all cells equal (to the 4 decimals of the csv)' if not bad else f'{bad} cells differ'}")
    assert not bad
    return 0


def no_peeking_api(api_rows, raions, rows, feats, oblasts, outages, n=40):
    """Features for n origins in the scoring window recomputed from API rows truncated at t: must equal the full-data features."""
    neighbours = load_neighbours()
    key = pd.MultiIndex.from_frame(rows[["oblast", "t"]])
    origins = rows.loc[(rows["t"] >= SCORE_FROM) & (rows["t"] < SCORE_TO), "t"].drop_duplicates().sample(n, random_state=0).sort_values()
    mism = total = 0
    for t in origins:
        ep_t, raw_t = official_episodes(known_at(api_rows, t), raions=raions)
        grid = make_rows(oblasts, t - pd.Timedelta(days=29), t + pd.Timedelta(hours=1))
        f_t = build_features(grid, ep_t, raw_t, neighbours, HORIZONS, oblasts, outages=outages)
        grid_key = pd.MultiIndex.from_frame(grid[["oblast", "t"]])
        here = (grid["t"] == t).to_numpy()
        pos = key.get_indexer(grid_key[here])
        for H in HORIZONS:
            for f in [c for c in FEATURES if c != "oblast"]:
                m = ~same(f_t[H].loc[here, f], feats[H][f].to_numpy()[pos])
                mism += int(m.sum())
                total += len(pos)
    return total, mism


def diagnose():
    info, frozen, boosters, freq = load_frozen()
    rows, episodes, raw, f_api, api_rows, raions, oblasts, files = build_api([])
    _, _, _, f_masked, *_ = build_api(OFFICIAL_OUTAGES)
    test = ((rows["t"] >= SCORE_FROM) & (rows["t"] < SCORE_TO)).to_numpy()
    num = [c for c in FEATURES if c != "oblast"]
    L = ["# Forward test, diagnostics: does the feature pipeline behave the same on API data?", "",
         "Produced by `scripts/forward_test.py --diagnose` before anything was scored: no outcome of the forward rows is compared with any "
         "prediction here. Source of every number below: the Ukraine Alarm API archive (`data/api_archive/`), "
         f"{len(files)} days, {min(files):%Y-%m-%d} to {max(files):%Y-%m-%d}.", ""]

    # 1. coverage
    n_days = rows.loc[test, "t"].dt.floor("D").nunique()
    L += ["## 1. Rows", f"- origins {SCORE_FROM:%Y-%m-%d} 00:00 to {(SCORE_TO - pd.Timedelta(hours=1)):%Y-%m-%d %H:%M} UTC: {n_days} days x {len(oblasts)} oblasts = {int(test.sum())} rows; "
          f"history before the first origin: {(SCORE_FROM - FIRST).days} days (7-day windows and the 4 lags of freq4w are complete from {(FIRST + pd.Timedelta(days=29)):%Y-%m-%d}).",
          f"- features with a missing value on those rows (H=1): " + (", ".join(f"{c} {int(f_api[1].loc[test, c].isna().sum())}" for c in FEATURES if f_api[1].loc[test, c].isna().any()) or "none"), ""]

    # 2. the outage masks
    L += ["## 2. The official feed's outage masks (the one thing that behaves differently)",
          "`src/features.py` treats the official feed's outage (" + ", ".join(f"[{a}, {b})" for a, b in OFFICIAL_OUTAGES) + ") as unobserved: "
          "7-day windows that overlap it are computed over the observed part and scaled, and a freq4w lag that touches it is skipped. "
          "On API data those hours are observed (the API has alerts there), so the right setting is no mask. The two versions on the forward rows:", ""]
    r = []
    for H in HORIZONS:
        for c in [c for c in num if (f_masked[H].loc[test, c].to_numpy() != f_api[H].loc[test, c].to_numpy()).any() and not
                  np.allclose(f_masked[H].loc[test, c].to_numpy(float), f_api[H].loc[test, c].to_numpy(float), equal_nan=True, atol=1e-9)]:
            a, b = f_masked[H].loc[test, c].to_numpy(float), f_api[H].loc[test, c].to_numpy(float)
            d = ~np.isclose(a, b, equal_nan=True, atol=1e-9)
            when = rows.loc[test, "t"][d]
            r.append({"H": H, "feature": c, "rows differing": int(d.sum()), "of": int(test.sum()), "from": f"{when.min():%m-%d}", "to": f"{when.max():%m-%d}",
                      "mean abs diff": float(np.nanmean(np.abs(a - b)[d]))})
    L += [md(pd.DataFrame(r), "{:.3f}") if r else "no feature differs", ""]
    diffs = []
    for H in HORIZONS:
        pm = boosters[H].predict(f_masked[H].loc[test, FEATURES])
        pa = boosters[H].predict(f_api[H].loc[test, FEATURES])
        diffs.append({"H": H, "rows where the frozen model's probability differs by > 0.001": int((np.abs(pm - pa) > 1e-3).sum()),
                      "largest difference": float(np.abs(pm - pa).max()), "mean abs difference": float(np.abs(pm - pa).mean())})
    L += ["The frozen LightGBM's probabilities with the masked and the unmasked features (a feature-pipeline effect only; no outcome used):", "", md(pd.DataFrame(diffs), "{:.4f}"), ""]

    # 3. API vs official features on the overlap where both are complete and unmasked
    official, oraions = load_inputs()
    o_rows, o_ep, o_raw, o_first, o_end = build_rows(official, oraions)
    o_feats = build_features(o_rows, o_ep, o_raw, load_neighbours(), HORIZONS, oblasts)
    ok_a = pd.Timestamp("2026-08-13", tz="UTC")  # API history starts Aug 6: 7-day windows complete from here
    ok_b = pd.Timestamp("2026-08-29", tz="UTC")  # official outage starts
    ko = pd.MultiIndex.from_frame(o_rows[["oblast", "t"]])
    ka = pd.MultiIndex.from_frame(rows[["oblast", "t"]])
    sel = rows[(rows["t"] >= ok_a) & (rows["t"] < ok_b)]
    pa_, po_ = ka.get_indexer(pd.MultiIndex.from_frame(sel[["oblast", "t"]])), ko.get_indexer(pd.MultiIndex.from_frame(sel[["oblast", "t"]]))
    r = []
    event = ((sel["t"] >= pd.Timestamp("2026-08-19 20:00", tz="UTC")) & (sel["t"] < pd.Timestamp("2026-08-21", tz="UTC"))).to_numpy()
    for c in [c for c in num if c != "freq4w"]:
        a, b = f_api[1][c].to_numpy(float)[pa_], o_feats[1][c].to_numpy(float)[po_]
        eq = np.isclose(a, b, atol=1e-3, equal_nan=True)
        r.append({"feature": c, "rows": len(a), "equal (1e-3)": int(eq.sum()), "equal outside Aug 19-20": f"{int(eq[~event].sum())} of {int((~event).sum())}",
                  "mean abs diff": float(np.nanmean(np.abs(a - b))), "max abs diff": float(np.nanmax(np.abs(a - b))),
                  "correlation": float(np.corrcoef(a[~np.isnan(a) & ~np.isnan(b)], b[~np.isnan(a) & ~np.isnan(b)])[0, 1])})
    L += ["## 3. The same features built from the official data and from the API, on the same rows",
          f"Rows {ok_a:%m-%d} to {(ok_b - pd.Timedelta(hours=1)):%m-%d %H:%M} UTC (API 7-day history complete, before the official outage): {len(sel)} rows. "
          "Equal = within 0.001 (the two sources time the same alert a fraction of a second apart; 0.001 h is 3.6 s). The Aug 19-20 column leaves out the wave "
          "the official feed does not have (see results/api_check.md). "
          "`freq4w` cannot be compared one to one: it needs four weeks of API history and the archive starts on Aug 6.", "", md(pd.DataFrame(r), "{:.4f}"), ""]

    # 4. no peeking on the API rows
    total, mism = no_peeking_api(api_rows, raions, rows, f_api, oblasts, [])
    L += ["## 4. Leakage check on API rows", f"- features for 40 origins in the forward window recomputed from API rows cut at t (alerts started by t, ends after t unknown): "
          f"{total} values compared, mismatches {mism}.", ""]

    # 5. distribution against the old test
    test_old = split(o_rows, o_first, o_end, o_end - pd.Timedelta(days=30), 1, EVAL_LOOKBACK)["test"].to_numpy()
    r = []
    for c in ["now", "hours_since_end", "share_24h", "share_7d", "starts_24h", "starts_7d", "nb_share_1h", "nb_starts_6h", "freq4w"]:
        r.append({"feature (mean)": c, "old test (official, 24 days)": float(np.nanmean(o_feats[1].loc[test_old, c].astype(float))),
                  "forward (API, 41 days)": float(np.nanmean(f_api[1].loc[test, c].astype(float)))})
    L += ["## 5. How the forward rows look next to the old test rows (features and the share of origins with a new alert; no model output)", "",
          md(pd.DataFrame(r), "{:.3f}"), ""]
    trn = split(o_rows, o_first, o_end, o_end - pd.Timedelta(days=30), 1, EVAL_LOOKBACK)["train"].to_numpy()
    rng_rows = []
    for c in [c for c in num if c not in ("hour", "weekday")]:
        tr_v, fw = o_feats[1].loc[trn, c].astype(float).dropna(), f_api[1].loc[test, c].astype(float)
        rng_rows.append({"feature": c, "training min": float(tr_v.min()), "training 99th pct": float(tr_v.quantile(0.99)), "training max": float(tr_v.max()),
                         "forward max": float(fw.max()), "forward rows above training 99th pct": f"{100 * float((fw > tr_v.quantile(0.99)).mean()):.1f}%",
                         "forward rows above training max": int((fw > tr_v.max()).sum())})
    L += ["Where the forward features sit against the range the models were trained on (official data to 2026-08-07, H=1 train rows):", "", md(pd.DataFrame(rng_rows), "{:.3f}"), ""]
    br = [{"H": H, "old test": float(o_rows.loc[test_old, f"b_start_{H}"].mean()), "forward": float(rows.loc[test, f"b_start_{H}"].mean())} for H in HORIZONS]
    L += ["Share of origins where a new alert starts in (t, t+H]:", "", md(pd.DataFrame(br), "{:.3f}"), ""]

    # 6. gaps in the API
    eps = episodes[(episodes["start"] >= SCORE_FROM) & (episodes["start"] < SCORE_TO)]
    per_day = eps.groupby(eps["start"].dt.floor("D")).size()
    zero = [o for o in oblasts if o not in set(eps["oblast"])]
    L += ["## 6. Gaps in the API data",
          f"- oblast episodes starting per day in the forward window: min {per_day.min()}, median {int(per_day.median())}, max {per_day.max()}; days with fewer than half the median: "
          + (", ".join(f"{d:%m-%d} ({n})" for d, n in per_day[per_day < per_day.median() / 2].items()) or "none"),
          "- oblasts with no episode at all in the window: " + (", ".join(zero) or "none"),
          "- API rows left out for having no end (`isContinue` true, end 0001-01-01): 2 hromada rows from Sep 17 (hromadas are not used by the rule) and 78 rows from "
          "Oct 18 09:51 on (after the scoring window); none inside the window affects an oblast.", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diagnostics.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"wrote {OUT.relative_to(ROOT)}/diagnostics.md")
    return 0


def forward_scores(masked):
    """Score every predictor on the forward rows. masked=True switches the official outage mask on (secondary run only)."""
    info, frozen, boosters, freq = load_frozen()
    rows, episodes, raw, feats, api_rows, raions, oblasts, files = build_api(OFFICIAL_OUTAGES if masked else [])
    test = ((rows["t"] >= SCORE_FROM) & (rows["t"] < SCORE_TO)).to_numpy()
    out = {}
    for H in HORIZONS:
        y = rows[f"b_start_{H}"].to_numpy()[test]
        S = {k: v.to_numpy()[test] for k, v in scores(rows, feats[H], H, frozen, boosters, freq, oblasts).items()}
        assert all(not np.isnan(v).any() for v in S.values()), "a predictor has missing scores on the forward rows"
        out[H] = (y, S)
    return rows[test].reset_index(drop=True), out, frozen


def old_scores():
    """The same frozen artifacts on the OLD official test rows (reproduces results/test_table.csv and results/calibration.md)."""
    info, frozen, boosters, freq = load_frozen()
    official, raions = load_inputs()
    rows, episodes, raw, first, end = build_rows(official, raions)
    oblasts = sorted(rows["oblast"].unique())
    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, oblasts)
    out = {}
    for H in HORIZONS:
        test = split(rows, first, end, end - pd.Timedelta(days=30), H, EVAL_LOOKBACK)["test"].to_numpy()
        S = {k: v.to_numpy()[test] for k, v in scores(rows, feats[H], H, frozen, boosters, freq, oblasts).items()}
        out[H] = (rows[f"b_start_{H}"].to_numpy()[test], S)
    return out


def summary_table(tr, res, frozen):
    t = []
    for H, (y, S) in res.items():
        for name, s in S.items():
            r = summarize(y, s, tr["oblast"], frozen["thresholds"][str(H)][name])
            t.append({"H": H, "predictor": NAMES[name], "n": len(y), "base_rate": float(y.mean()), "auc_within_oblast": r["auc_within_oblast"],
                      "brier": r["brier"], "threshold": r["threshold"], "precision": r["precision"], "recall": r["recall"], "f1": r["f1"]})
    return pd.DataFrame(t)


def in_the_large(res, names=("lgbm", "logit", "frequency", "freq4w")):
    """Mean predicted vs observed; Brier = bias^2 + Var(p - y) exactly, so bias^2 is the calibration-in-the-large part of the Brier score."""
    r = []
    for H, (y, S) in res.items():
        for k in names:
            p = S[k]
            bias = float(p.mean() - y.mean())
            br = brier(y, p)
            r.append({"H": H, "predictor": NAMES[k], "mean_predicted": float(p.mean()), "observed": float(y.mean()), "bias": bias,
                      "bias^2": bias ** 2, "brier": br, "bias^2 share of Brier": bias ** 2 / br})
    return pd.DataFrame(r)


def brier_change(old, new, names=("lgbm", "frequency")):
    """Old test -> forward test: the change in Brier and in its Murphy terms, and in the squared bias."""
    r = []
    for H in HORIZONS:
        for k in names:
            row = {"H": H, "predictor": NAMES[k]}
            terms = {}
            for lab, (y, S) in (("old", old[H]), ("fwd", new[H])):
                d = brier_decomposition(y, S[k])
                bias = float(S[k].mean() - y.mean())
                terms[lab] = {**d, "bias2": bias ** 2, "mean_pred": float(S[k].mean()), "observed": float(y.mean())}
            for key, label in [("brier", "Brier"), ("uncertainty", "uncertainty (base rate x (1 - base rate))"), ("reliability", "reliability"),
                               ("resolution", "resolution"), ("residual", "residual"), ("bias2", "bias^2")]:
                row[f"{label} old"] = terms["old"][key]
                row[f"{label} fwd"] = terms["fwd"][key]
                row[f"{label} change"] = terms["fwd"][key] - terms["old"][key]
            r.append(row)
    return pd.DataFrame(r)


def brier_words(CH):
    """The Brier change in plain words, generated from the numbers of brier_change()."""
    out = []
    for _, r in CH.iterrows():
        unc, ch = r["uncertainty (base rate x (1 - base rate)) change"], r["Brier change"]
        out.append(
            f"- H={int(r['H'])}, {r['predictor']}: Brier {r['Brier old']:.4f} -> {r['Brier fwd']:.4f} ({ch:+.4f}). The higher base rate alone changes the uncertainty term by {unc:+.4f}"
            f" ({100 * unc / ch:.0f}% of the change); resolution changes by {r['resolution change']:+.4f} (a rise lowers the Brier), reliability by {r['reliability change']:+.4f}, "
            f"residual by {r['residual change']:+.4f}. Calibration in the large: squared bias {r['bias^2 old']:.4f} -> {r['bias^2 fwd']:.4f} "
            f"({r['bias^2 change']:+.4f}, {100 * r['bias^2 change'] / ch:.0f}% of the Brier change).")
    return "\n".join(out)


def score():
    tr, res, frozen = forward_scores(False)
    old = old_scores()
    day = tr["t"].dt.strftime("%Y-%m-%d").to_numpy()
    n_rows = len(tr)
    OUT.mkdir(parents=True, exist_ok=True)
    T = summary_table(tr, res, frozen)
    cal, rel, boot_rows = [], [], []
    for H, (y, S) in res.items():
        for name in ("lgbm", "logit", "frequency", "freq4w"):
            d = brier_decomposition(y, S[name])
            cal.append({"H": H, "predictor": NAMES[name], "mean_predicted": float(S[name].mean()), "observed": float(y.mean()),
                        **{k: float(v) for k, v in d.items()}})
        for name in ("lgbm", "frequency"):
            rel.append(reliability_table(y, S[name]).reset_index().rename(columns={"index": "bin"}).assign(H=H, predictor=NAMES[name]))
        b = day_bootstrap(y, S, tr["oblast"], day)
        for name, v in b.items():
            boot_rows.append({"H": H, "predictor": NAMES[name], **v})
        print(f"H={H} bootstrap done ({len(y)} rows)", flush=True)
    C, B, R = pd.DataFrame(cal), pd.DataFrame(boot_rows), pd.concat(rel)
    L, CH = in_the_large(res), brier_change(old, res)
    T.to_csv(OUT / "forward_table.csv", index=False, float_format="%.4f")
    head = ("# Forward test on the Ukraine Alarm API (2026-09-07 to 2026-10-17)\n\n"
            "**Source: the Ukraine Alarm API (`api.ukrainealarm.com`), one source for every feature and every outcome; no outage mask.** The models are the frozen round-13 fits "
            "(trained on official data to 2026-08-07; every threshold from the last train week; nothing refitted, nothing retuned). "
            f"**41 days, {n_rows} oblast-hours per horizon: a short test, so the intervals in `bootstrap.md` are wide.** This is separate from the old test "
            "(official data, 24 days, `results/test_table.md`); the two are not pooled. Target (b): a new alert starts in (t, t+H]. "
            "The forward period is busier than the old test (share of origins with a new alert at H=1: 0.180 against 0.121), so read the Brier scores with `calibration.md` next to them.\n\n")
    (OUT / "forward_table.md").write_text(head + md(T) + "\n\nThresholds are the frozen max-F1 thresholds from the last train week; 'raw 0/1' means the baseline is taken as is.\n")
    cols = ["H", "predictor", "auc", "auc_lo", "auc_hi", "brier", "brier_lo", "brier_hi"]
    diff = B[B["predictor"] != NAMES["lgbm"]][["H", "predictor", "d_auc", "d_auc_lo", "d_auc_hi", "share_auc_ahead", "d_brier", "d_brier_lo", "d_brier_hi", "share_brier_ahead"]]
    (OUT / "bootstrap.md").write_text(f"Forward test (API, 41 days). Day-block bootstrap, whole days resampled with replacement, {N_BOOT} resamples, seed 0, 95% percentile intervals.\n\n"
                                      "Each predictor (within-oblast AUC, Brier):\n\n" + md(B[cols]) + "\n\nLightGBM minus each other predictor "
                                      "(AUC: positive = LightGBM ahead; Brier: negative = LightGBM ahead):\n\n" + md(diff) + "\n")
    (OUT / "calibration.md").write_text(
        "Forward test (API, 41 days), target (b), frozen models.\n\n"
        "## Calibration in the large: mean predicted against observed\n\n"
        "Brier = (mean predicted - observed)^2 + Var(p - y), exactly, so `bias^2` is the part of the Brier score that is calibration-in-the-large.\n\n"
        + md(L, "{:.4f}") + "\n\n"
        "## How the Brier score changed from the old test to the forward test\n\n"
        "Old test = the same frozen artifacts on the old official test rows (24 days; reproduces `results/calibration.md`). Murphy terms as in `results/calibration.md`: "
        "Brier = reliability - resolution + uncertainty + residual. `uncertainty` is base rate x (1 - base rate): a higher base rate raises it for any forecaster.\n\n"
        + md(CH, "{:.4f}") + "\n\nIn words (generated from the table above; percentages can exceed 100 or be negative because the terms offset each other):\n\n" + brier_words(CH) + "\n\n"
        "## Brier decomposition, forward test\n\n" + md(C, "{:.4f}") + "\n\nReliability table (10 bins):\n\n"
        + md(R[["H", "predictor", "bin", "mean_predicted", "observed", "n"]]) + "\n")
    print(md(T)); print(md(B[cols])); print(md(diff)); print(md(L, "{:.4f}"))
    print(f"wrote {OUT.relative_to(ROOT)}/ (main, no mask)")

    # secondary: the official outage mask switched on for the API features
    tr2, res2, _ = forward_scores(True)
    T2 = summary_table(tr2, res2, frozen)
    cmp_ = T.merge(T2, on=["H", "predictor"], suffixes=("", "_masked"))
    cmp_ = cmp_[["H", "predictor", "auc_within_oblast", "auc_within_oblast_masked", "brier", "brier_masked", "f1", "f1_masked"]]
    cmp_.insert(4, "AUC change", cmp_["auc_within_oblast_masked"] - cmp_["auc_within_oblast"])
    cmp_.insert(7, "Brier change", cmp_["brier_masked"] - cmp_["brier"])
    L2 = in_the_large(res2, ("lgbm", "logit", "freq4w"))
    (OUT / "secondary_mask_on.md").write_text(
        "# SECONDARY, not the result: the forward test with the official outage mask switched on for the API features\n\n"
        "The main result (`forward_table.md`) uses no mask, because the API observed 2026-08-29..09-02. This run applies the official feed's mask anyway "
        "(7-day windows that overlap the outage computed over the observed part and scaled, freq4w lags that touch it skipped), to show what the choice changes. "
        "Same frozen models and thresholds, same rows. Only the LightGBM, the logistic model and the rolling 4-week frequency use these features; the other predictors are identical in both runs. "
        "Point estimates only (no bootstrap).\n\n" + md(cmp_, "{:.4f}") + "\n\nCalibration in the large, masked features:\n\n" + md(L2, "{:.4f}") + "\n")
    print(md(cmp_, "{:.4f}"))
    print(f"wrote {OUT.relative_to(ROOT)}/secondary_mask_on.md")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Forward test of the frozen models on the API archive.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--diagnose", action="store_true")
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--score", action="store_true")
    a = ap.parse_args()
    return diagnose() if a.diagnose else selftest() if a.selftest else score()


if __name__ == "__main__":
    sys.exit(main())
