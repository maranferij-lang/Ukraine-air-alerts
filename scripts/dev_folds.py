"""Round 22 development: rolling-origin folds, feature-group ablations, three model families, the selection rules. Design and rules: PROCESS_LOG.md, "Round 22 ... PROTOCOL",
committed before any number existed; nothing here may deviate from it (a deviation is logged as one).

    python scripts/dev_folds.py run --configs lgb:L1:base,lgb:L1:A,lgb:L1:B [--horizons 1,3,6] [--threads 4]
    python scripts/dev_folds.py report-stage1             tables, the group rule, results/round22/stage1_decision.json
    python scripts/dev_folds.py report-stage2             the grids at H=3, the winners (after they were run at H=1 and 6), v3 eligibility, results/round22/selection.json

A config is family:name:featureset, e.g. lgb:L1:A+B. Feature sets: base (the 14 of v2), A, B, C, unions with '+', and the descriptive sub-blocks Aown, Anat, Awave.
The six folds are the 2-week blocks before 2026-09-28; the window 2026-09-28 .. 10-17 is never read for any choice. Out-of-fold predictions are cached in output/round22/oof/ (git-ignored).
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb
import numpy as np
import pandas as pd

from scripts.build_combined import CUT, load_combined
from scripts.evaluate import MAX_TREES, PARAMS
from scripts.forward_test import fast_auc
from src.candidates import CAT, GRIDS, LGB, XGB
from src.baselines import frequency_table, same_hour_yesterday, train_frequency
from src.dataset import EVAL_LOOKBACK, HORIZONS, build_rows, load_inputs, split
from src.features import FEATURES, build_features, load_neighbours
from src.features_extra import (A_FEATURES, A_NAT, A_OWN, A_WAVE, B_FEATURES, C_FEATURES, build_extra, load_weather, raion_episodes, weather_features)

OUT = ROOT / "results" / "round22"
CACHE = ROOT / "output" / "round22" / "oof"
DEV_END = pd.Timestamp("2026-09-28", tz="UTC")
FOLDS = [(pd.Timestamp("2026-07-06", tz="UTC") + pd.Timedelta(days=14 * i), pd.Timestamp("2026-07-06", tz="UTC") + pd.Timedelta(days=14 * (i + 1))) for i in range(6)]
assert FOLDS[-1][1] == DEV_END
N_BOOT, MIN_GAIN = 1000, 0.003
EARLY = 100

PREFERENCE = ["lgb", "xgb", "cat"]       # ties in the v3 rule


# ---------------------------------------------------------------------------------------------------------------- data
_DATA = {}


def data():
    if _DATA:
        return _DATA
    comb = load_combined()
    official, raions = load_inputs()
    oblasts = sorted(official["oblast"].unique())
    cr = comb[["oblast", "raion", "hromada", "level", "start", "end"]]
    rows, episodes, raw, first, end = build_rows(cr, raions, first=official["start"].min().ceil("D"), end=CUT)
    neighbours = load_neighbours()
    feats = build_features(rows, episodes, raw, neighbours, HORIZONS, oblasts, outages=[])
    extra = build_extra(rows, episodes, raw, raion_episodes(cr, raions), raions, neighbours, oblasts)
    weather = load_weather()
    if weather is not None:
        wf = weather_features(rows, weather)
        extra = pd.concat([extra, wf], axis=1)
    _DATA.update(rows=rows, feats=feats, extra=extra, first=first, end=end, oblasts=oblasts, day=rows["t"].dt.strftime("%Y-%m-%d"))
    return _DATA


def feature_columns(fset):
    d = {"base": [], "A": A_FEATURES, "B": B_FEATURES, "C": [c for c in C_FEATURES if c in data()["extra"].columns], "Aown": A_OWN, "Anat": A_NAT, "Awave": A_WAVE}
    cols = []
    for part in fset.split("+"):
        assert part in d, f"unknown feature set {part}"
        cols += [c for c in d[part] if c not in cols]
    if "C" in fset.split("+"):
        assert d["C"], "group C needs data/weather/ (scripts/fetch_weather.py)"
    return cols


def frame(H, fset):
    D = data()
    cols = feature_columns(fset)
    return pd.concat([D["feats"][H], D["extra"][cols]], axis=1) if cols else D["feats"][H]


def fold_masks(H, k):
    D = data()
    rows = D["rows"]
    a, b = FOLDS[k]
    m = split(rows, D["first"], D["end"], a, H, EVAL_LOOKBACK, outages=())
    h = pd.Timedelta(hours=H)
    assert (rows.loc[m["train"], "t"] + h).max() <= a and (rows.loc[m["before_last_week"], "t"] + h).max() <= a - pd.Timedelta(days=7), "a training window reaches into the validation week or the fold"
    m["test"] = m["test"] & (rows["t"] < b)
    assert (rows.loc[m["test"], "t"] + h).max() <= DEV_END + h and rows.loc[m["test"], "t"].max() < DEV_END
    return m


# ---------------------------------------------------------------------------------------------------------------- models
def fit_lgb(name, X, y, m, threads):
    params = {**PARAMS, "num_threads": threads, **LGB[name]}
    fit, week = m["before_last_week"], m["last_week"]
    dtrain = lgb.Dataset(X[fit], y[fit])
    val = lgb.train(params, dtrain, num_boost_round=MAX_TREES, valid_sets=[lgb.Dataset(X[week], y[week], reference=dtrain)], callbacks=[lgb.early_stopping(EARLY, verbose=False)])
    n = val.best_iteration
    final = lgb.train(params, lgb.Dataset(X[m["train"]], y[m["train"]]), num_boost_round=n)
    return n, final.predict(X[m["test"]])


def fit_xgb(name, X, y, m, threads):
    import xgboost as xgb
    params = {"objective": "binary:logistic", "eval_metric": "logloss", "tree_method": "hist", "eta": 0.05, "nthread": threads, "seed": 0, **XGB[name]}
    fit, week = m["before_last_week"], m["last_week"]
    val = xgb.train(params, xgb.DMatrix(X[fit], label=y[fit], enable_categorical=True), num_boost_round=MAX_TREES,
                    evals=[(xgb.DMatrix(X[week], label=y[week], enable_categorical=True), "week")], early_stopping_rounds=EARLY, verbose_eval=False)
    n = val.best_iteration + 1
    final = xgb.train(params, xgb.DMatrix(X[m["train"]], label=y[m["train"]], enable_categorical=True), num_boost_round=n)
    return n, final.predict(xgb.DMatrix(X[m["test"]], enable_categorical=True))


def fit_cat(name, X, y, m, threads):
    from catboost import CatBoostClassifier, Pool
    X = X.copy()
    X["oblast"] = X["oblast"].astype(str)
    cat = [list(X.columns).index("oblast")]
    base = {"learning_rate": 0.1, "loss_function": "Logloss", "random_seed": 0, "thread_count": threads, "verbose": 0, "allow_writing_files": False, **CAT[name]}
    fit, week = m["before_last_week"], m["last_week"]
    val = CatBoostClassifier(iterations=1500, eval_metric="Logloss", early_stopping_rounds=EARLY, use_best_model=True, **base)
    val.fit(Pool(X[fit], y[fit], cat_features=cat), eval_set=Pool(X[week], y[week], cat_features=cat))
    n = int(val.get_best_iteration()) + 1
    final = CatBoostClassifier(iterations=n, **base)
    final.fit(Pool(X[m["train"]], y[m["train"]], cat_features=cat))
    return n, final.predict_proba(Pool(X[m["test"]], cat_features=cat))[:, 1]


FITTERS = {"lgb": fit_lgb, "xgb": fit_xgb, "cat": fit_cat}


def cache_path(cfg, H):
    return CACHE / f"{cfg.replace(':', '_').replace('+', '-')}__H{H}.pkl"


def run_config(cfg, H, threads):
    fam, name, fset = cfg.split(":")
    path = cache_path(cfg, H)
    done = pickle.loads(path.read_bytes()) if path.exists() else {}
    D = data()
    X, y = frame(H, fset), D["rows"][f"b_start_{H}"].astype(int)
    for k in range(len(FOLDS)):
        if k in done:
            continue
        m = fold_masks(H, k)
        t0 = time.time()
        n, pred = FITTERS[fam](name, X, y, m, threads)
        done[k] = {"pos": np.flatnonzero(m["test"].to_numpy()), "pred": pred, "trees": int(n), "seconds": round(time.time() - t0, 1)}
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps(done))
        print(f"{cfg} H={H} fold {k + 1}: {n} trees, {len(pred)} rows, {done[k]['seconds']}s", flush=True)
    return done


def run_baselines():
    D = data()
    for H in HORIZONS:
        path = CACHE / f"baselines__H{H}.pkl"
        if path.exists():
            continue
        out = {}
        target = f"b_start_{H}"
        yest = same_hour_yesterday(D["rows"], target)
        for k in range(len(FOLDS)):
            m = fold_masks(H, k)
            freq = train_frequency(D["rows"], frequency_table(D["rows"][m["train"]], target))
            sel = m["test"]
            out[k] = {"pos": np.flatnonzero(sel.to_numpy()), "persistence": D["rows"].loc[sel, "now"].astype(float).to_numpy(), "yesterday": yest[sel].to_numpy(), "frequency": freq[sel].to_numpy()}
            assert not np.isnan(out[k]["frequency"]).any() and not np.isnan(out[k]["yesterday"]).any()
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps(out))
        print(f"baselines H={H} done", flush=True)


# ---------------------------------------------------------------------------------------------------------------- metrics
def load_oof(cfg, H):
    d = pickle.loads(cache_path(cfg, H).read_bytes())
    assert sorted(d) == list(range(len(FOLDS))), f"{cfg} H={H}: folds {sorted(d)} are not all there"
    return d


def load_base(H):
    return pickle.loads((CACHE / f"baselines__H{H}.pkl").read_bytes())


def oblast_auc(y, p, ob):
    vals = []
    for o in np.unique(ob):
        i = ob == o
        vals.append(fast_auc(y[i], p[i]))
    return float(np.nanmean(vals))


def fold_metrics(preds, H):
    """{k: (auc, brier)} for a {k: {pos, pred}} dict."""
    D = data()
    y_all = D["rows"][f"b_start_{H}"].to_numpy().astype(bool)
    ob_all = D["rows"]["oblast"].to_numpy()
    out = {}
    for k, v in preds.items():
        pos = v["pos"]
        p = v["pred"]
        y, ob = y_all[pos], ob_all[pos]
        out[k] = (oblast_auc(y, p, ob), float(np.mean((p - y) ** 2)))
    return out


def pooled(preds_by_cfg, H):
    """Pooled out-of-fold arrays for several predictors on the same rows: y, oblast, day, {name: p}."""
    D = data()
    first = next(iter(preds_by_cfg.values()))
    pos = np.concatenate([first[k]["pos"] for k in range(len(FOLDS))])
    for d in preds_by_cfg.values():
        assert all(np.array_equal(d[k]["pos"], first[k]["pos"]) for k in range(len(FOLDS))), "predictors are not on the same rows"
    y = D["rows"][f"b_start_{H}"].to_numpy().astype(bool)[pos]
    return y, D["rows"]["oblast"].to_numpy()[pos], D["day"].to_numpy()[pos], {n: np.concatenate([d[k]["pred"] for k in range(len(FOLDS))]) for n, d in preds_by_cfg.items()}


def bootstrap_diff(cand, ref, n=N_BOOT, seed=0):
    """cand, ref: {H: (y, oblast, day, p)} on the same rows. Resamples the development days; returns the mean over H of the AUC and Brier differences (cand minus ref)
    with 95% intervals, the same per H, and the point values on the pooled rows."""
    Hs = sorted(cand)
    days = np.unique(cand[Hs[0]][2])
    obs = np.unique(cand[Hs[0]][1])
    idx = {H: {(o, d): np.flatnonzero((cand[H][1] == o) & (cand[H][2] == d)) for o in obs for d in days} for H in Hs}
    rng = np.random.default_rng(seed)

    def one(drawn):
        da, db = {}, {}
        for H in Hs:
            y, ob, _, pc = cand[H]
            pr = ref[H][3]
            ac, ar = [], []
            for o in obs:
                i = np.concatenate([idx[H][(o, d)] for d in drawn])
                ac.append(fast_auc(y[i], pc[i]))
                ar.append(fast_auc(y[i], pr[i]))
            i = np.concatenate([idx[H][(o, d)] for o in obs for d in drawn])
            da[H] = np.nanmean(ac) - np.nanmean(ar)
            db[H] = float(np.mean((pc[i] - y[i]) ** 2) - np.mean((pr[i] - y[i]) ** 2))
        return da, db

    pt = one(days)
    draws = [one(rng.choice(days, len(days))) for _ in range(n)]
    out = {"point": {"auc": {H: pt[0][H] for H in Hs}, "brier": {H: pt[1][H] for H in Hs}}}
    out["point"]["auc_mean"] = float(np.mean([pt[0][H] for H in Hs]))
    out["point"]["brier_mean"] = float(np.mean([pt[1][H] for H in Hs]))
    am = np.array([np.mean([d[0][H] for H in Hs]) for d in draws])
    bm = np.array([np.mean([d[1][H] for H in Hs]) for d in draws])
    out["auc_mean_ci"] = (float(np.percentile(am, 2.5)), float(np.percentile(am, 97.5)))
    out["brier_mean_ci"] = (float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5)))
    out["auc_ci"] = {H: (float(np.percentile([d[0][H] for d in draws], 2.5)), float(np.percentile([d[0][H] for d in draws], 97.5))) for H in Hs}
    out["brier_ci"] = {H: (float(np.percentile([d[1][H] for d in draws], 2.5)), float(np.percentile([d[1][H] for d in draws], 97.5))) for H in Hs}
    return out


def md(df, fmt="{:.3f}"):
    cells = df.map(lambda v: fmt.format(v) if isinstance(v, (float, np.floating)) else str(v))
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)] + ["| " + " | ".join(r) + " |" for r in cells.itertuples(index=False)])


def fold_table(cfgs, H):
    """One row per predictor, one AUC / Brier cell per fold plus the mean over folds."""
    base = load_base(H)
    rows = []
    def add(name, per_fold):
        cells = {f"F{k + 1}": f"{a:.3f} / {b:.3f}" for k, (a, b) in per_fold.items()}
        cells["mean of folds"] = f"{np.mean([a for a, _ in per_fold.values()]):.3f} / {np.mean([b for _, b in per_fold.values()]):.3f}"
        rows.append({"predictor": name, **cells})
    for cfg in cfgs:
        add(cfg, fold_metrics(load_oof(cfg, H), H))
    for nm, label in [("frequency", "train frequency"), ("yesterday", "same hour yesterday"), ("persistence", "same as now")]:
        add(label, fold_metrics({k: {"pos": v["pos"], "pred": v[nm]} for k, v in base.items()}, H))
    return pd.DataFrame(rows)


def fold_means(cfg):
    """{k: (mean over H of auc, mean over H of brier)}"""
    per = {H: fold_metrics(load_oof(cfg, H), H) for H in HORIZONS}
    return {k: (float(np.mean([per[H][k][0] for H in HORIZONS])), float(np.mean([per[H][k][1] for H in HORIZONS]))) for k in range(len(FOLDS))}


def compare(cand_cfg, ref_cfg):
    """The three conditions of the rules for cand against ref, with the day bootstrap."""
    c = {H: pooled({"c": load_oof(cand_cfg, H), "r": load_oof(ref_cfg, H)}, H) for H in HORIZONS}
    cand = {H: (v[0], v[1], v[2], v[3]["c"]) for H, v in c.items()}
    ref = {H: (v[0], v[1], v[2], v[3]["r"]) for H, v in c.items()}
    b = bootstrap_diff(cand, ref)
    fc, fr = fold_means(cand_cfg), fold_means(ref_cfg)
    ahead = sum(fc[k][0] > fr[k][0] for k in range(len(FOLDS)))
    return {"boot": b, "folds_ahead": int(ahead), "fold_diff": {k: fc[k][0] - fr[k][0] for k in range(len(FOLDS))}}


# ---------------------------------------------------------------------------------------------------------------- reports
def adopted(res):
    b = res["boot"]
    return bool(b["point"]["auc_mean"] > 0 and b["auc_mean_ci"][0] > 0), bool(b["point"]["brier_mean"] <= 0), bool(res["folds_ahead"] >= 4)


def report_stage1():
    OUT.mkdir(parents=True, exist_ok=True)
    run_baselines()
    ref = "lgb:L1:base"
    groups = [g for g in ["A", "B", "C"] if cache_path(f"lgb:L1:{g}", 3).exists()]
    extra = [f"lgb:L1:{s}" for s in ["Aown", "Anat", "Awave"] if cache_path(f"lgb:L1:{s}", 3).exists()]
    lines = ["# Round 22, stage 1: feature groups added to the base (LightGBM, v2's settings, six rolling-origin folds before 2026-09-28)", "",
             "Protocol and rules: `PROCESS_LOG.md`, Round 22 (written and committed before any number). Cells are within-oblast AUC / Brier on the fold's origins; each fold's model is trained on everything whose window closed "
             "before the fold; the three simple rules are scored on the same rows (train frequency fitted on each fold's training rows). F1 2026-07-06..07-19, F2 07-20..08-02, F3 08-03..08-16, F4 08-17..08-30, F5 08-31..09-13, F6 09-14..09-27.", ""]
    verdict = {}
    rows = []
    for g in groups:
        res = compare(f"lgb:L1:{g}", ref)
        i, ii, iii = adopted(res)
        b = res["boot"]
        verdict[g] = {"adopted": bool(i and ii and iii), "auc_mean_diff": b["point"]["auc_mean"], "auc_mean_ci": b["auc_mean_ci"], "brier_mean_diff": b["point"]["brier_mean"], "brier_mean_ci": b["brier_mean_ci"],
                      "folds_ahead": res["folds_ahead"], "conditions": {"i_auc_ci_above_zero": i, "ii_brier_not_worse": ii, "iii_four_of_six_folds": iii},
                      "per_H_auc_diff": {str(H): b["point"]["auc"][H] for H in HORIZONS}, "per_H_auc_ci": {str(H): b["auc_ci"][H] for H in HORIZONS},
                      "per_H_brier_diff": {str(H): b["point"]["brier"][H] for H in HORIZONS}, "fold_auc_diff": {f"F{k + 1}": res["fold_diff"][k] for k in res["fold_diff"]}}
        rows.append({"group": g, "AUC diff (mean of H)": b["point"]["auc_mean"], "95% day-bootstrap": f"[{b['auc_mean_ci'][0]:+.4f}, {b['auc_mean_ci'][1]:+.4f}]", "Brier diff (mean of H)": b["point"]["brier_mean"],
                     "folds ahead (of 6)": res["folds_ahead"], "(i) CI above 0": "yes" if i else "no", "(ii) Brier not worse": "yes" if ii else "no", "(iii) 4+ folds": "yes" if iii else "no", "ADOPTED": "yes" if verdict[g]["adopted"] else "no"})
    lines += ["## The rule, applied (group added to base, minus base; mean over H = 1, 3, 6; pooled out-of-fold rows of the 84 days; day bootstrap 1,000 resamples, seed 0)", "",
              md(pd.DataFrame(rows), "{:+.4f}") if rows else "(no groups run)", ""]
    if extra:
        lines += ["## Descriptive only: the sub-blocks of A added alone (no rule uses these)", ""]
        sub = []
        for e in extra:
            res = compare(e, ref)
            b = res["boot"]
            sub.append({"block": e.split(":")[2], "AUC diff (mean of H)": b["point"]["auc_mean"], "95% day-bootstrap": f"[{b['auc_mean_ci'][0]:+.4f}, {b['auc_mean_ci'][1]:+.4f}]", "Brier diff (mean of H)": b["point"]["brier_mean"], "folds ahead (of 6)": res["folds_ahead"]})
        lines += [md(pd.DataFrame(sub), "{:+.4f}"), ""]
    ad = [g for g in groups if verdict[g]["adopted"]]
    # union rule
    union = "+".join(ad) if ad else "base"
    choice = {"adopted_groups": ad, "feature_set": union}
    if len(ad) >= 2:
        ucfg = f"lgb:L1:{union}"
        if all(cache_path(ucfg, H).exists() for H in HORIZONS):
            ures = compare(ucfg, ref)
            best_single = max(ad, key=lambda g: verdict[g]["auc_mean_diff"])
            if ures["boot"]["point"]["auc_mean"] < verdict[best_single]["auc_mean_diff"]:
                choice["feature_set"] = best_single
                choice["note"] = f"the union {union} (AUC diff {ures['boot']['point']['auc_mean']:+.4f}) is below the best single group {best_single} ({verdict[best_single]['auc_mean_diff']:+.4f}); the single group is used"
            else:
                choice["note"] = f"the union {union} (AUC diff {ures['boot']['point']['auc_mean']:+.4f}) is not below the best single group {best_single} ({verdict[best_single]['auc_mean_diff']:+.4f}); the union is used"
            choice["union_auc_mean_diff"] = ures["boot"]["point"]["auc_mean"]
            lines += [f"## Union of the adopted groups ({union}) against base: AUC diff {ures['boot']['point']['auc_mean']:+.4f}, 95% {ures['boot']['auc_mean_ci']}, Brier diff {ures['boot']['point']['brier_mean']:+.5f}, folds ahead {ures['folds_ahead']}", "", choice["note"], ""]
        else:
            choice["pending"] = f"run lgb:L1:{union} at H = 1, 3, 6, then report again"
    ucfg = f"lgb:L1:{union}" if len(ad) >= 2 and cache_path(f"lgb:L1:{union}", 3).exists() else None
    fold_lines = []
    for H in HORIZONS:
        cfgs = [ref] + [f"lgb:L1:{g}" for g in groups] + extra + ([ucfg] if ucfg else [])
        fold_lines += [f"## H = {H}: fold by fold", "", md(fold_table(cfgs, H)), ""]
    lines = lines[:4] + fold_lines + lines[4:]
    lines += [f"## Best feature set for stage 2: **{choice['feature_set']}**" + (" (none of the groups was adopted: base)" if not ad else ""), ""]
    (OUT / "stage1_groups.md").write_text("\n".join(lines) + "\n")
    (OUT / "stage1_decision.json").write_text(json.dumps({"verdict": verdict, "choice": choice}, indent=1, default=float) + "\n")
    print("\n".join(lines))


def report_stage2():
    OUT.mkdir(parents=True, exist_ok=True)
    run_baselines()
    st1 = json.loads((OUT / "stage1_decision.json").read_text())
    fset = st1["choice"]["feature_set"]
    ref = "lgb:L1:base"
    lines = [f"# Round 22, stage 2: three model families on the feature set **{fset}**", "",
             "Tuning: 4 fixed configurations per family, run at H = 3 on the six folds; the winner of a family has the highest mean over folds of the within-oblast AUC at H = 3 (ties: lower Brier) and is then run unchanged at H = 1 and 6. "
             "Cells: within-oblast AUC / Brier; the v2-reference is LightGBM L1 on the 14 base features.", ""]
    winners = {}
    grid = []
    for fam in PREFERENCE:
        res = []
        for name in GRIDS[fam]:
            cfg = f"{fam}:{name}:{fset}"
            if not cache_path(cfg, 3).exists():
                continue
            fm = fold_metrics(load_oof(cfg, 3), 3)
            res.append((np.mean([a for a, _ in fm.values()]), -np.mean([b for _, b in fm.values()]), name, cfg))
            grid.append({"family": fam, "config": name, "mean AUC at H=3": res[-1][0], "mean Brier at H=3": -res[-1][1]})
        if res:
            best = max(res)
            winners[fam] = {"name": best[2], "cfg": best[3]}
    lines += ["## The grids at H = 3 (mean over the six folds)", "", md(pd.DataFrame(grid), "{:.4f}"), "", "Winners: " + ", ".join(f"{f}: {w['name']}" for f, w in winners.items()), ""]
    for H in HORIZONS:
        cfgs = [ref] + [w["cfg"] for w in winners.values() if cache_path(w["cfg"], H).exists()]
        lines += [f"## H = {H}: fold by fold", "", md(fold_table(cfgs, H)), ""]
    sel_rows, eligible = [], []
    for fam, w in winners.items():
        cfg = w["cfg"]
        if not all(cache_path(cfg, H).exists() for H in HORIZONS):
            continue
        is_ref = (cfg == ref)
        res = compare(cfg, ref) if not is_ref else None
        row = {"family": fam, "config": w["name"], "features": fset}
        if is_ref:
            row.update({"AUC diff (mean of H)": 0.0, "95% day-bootstrap": "-", "Brier diff": 0.0, "folds ahead": 0, "eligible": "no (it is the v2-reference)"})
        else:
            b = res["boot"]
            e1 = bool(b["point"]["auc_mean"] >= MIN_GAIN and b["auc_mean_ci"][0] > 0)
            e2 = bool(b["point"]["brier_mean"] <= 0)
            e3 = bool(res["folds_ahead"] >= 4)
            ok = e1 and e2 and e3
            row.update({"AUC diff (mean of H)": b["point"]["auc_mean"], "95% day-bootstrap": f"[{b['auc_mean_ci'][0]:+.4f}, {b['auc_mean_ci'][1]:+.4f}]", "Brier diff": b["point"]["brier_mean"],
                        "folds ahead": res["folds_ahead"], "eligible": "yes" if ok else f"no ((i) {'ok' if e1 else 'fails'}, (ii) {'ok' if e2 else 'fails'}, (iii) {'ok' if e3 else 'fails'})"})
            if ok:
                eligible.append((b["point"]["auc_mean"], -PREFERENCE.index(fam), fam, w, res))
            row["per_H_auc_diff"] = " / ".join(f"{b['point']['auc'][H]:+.4f}" for H in HORIZONS)
        sel_rows.append(row)
    lines += ["## Eligibility against the v2-reference (rule: AUC diff >= 0.003 with the 95% day-bootstrap lower end above 0; Brier diff <= 0; ahead in at least 4 of 6 folds; mean over H = 1, 3, 6)", "",
              md(pd.DataFrame(sel_rows), "{:+.4f}") if sel_rows else "(winners not yet run at all horizons)", ""]
    selection = {"feature_set": fset, "v3": None}
    if sel_rows and len(sel_rows) == len(winners):
        if eligible:
            eligible.sort(reverse=True)
            auc_diff, _, fam, w, res = eligible[0]
            trees = {}
            for H in HORIZONS:
                trees[str(H)] = int(np.median([v["trees"] for v in load_oof(w["cfg"], H).values()]))
            selection["v3"] = {"family": fam, "config": w["name"], "features": fset, "feature_columns": feature_columns(fset), "trees": trees, "auc_mean_diff_vs_v2_reference": auc_diff,
                               "folds_ahead": res["folds_ahead"], "auc_mean_ci": res["boot"]["auc_mean_ci"]}
            lines += [f"## v3 = {fam}:{w['name']} on {fset}; trees (median over the six folds of the early-stopped count) {trees}", ""]
        else:
            lines += ["## No v3: no candidate is eligible. **Nothing beats v2 beyond noise on these folds.** v2 stays.", ""]
    (OUT / "stage2_models.md").write_text("\n".join(lines) + "\n")
    (OUT / "selection.json").write_text(json.dumps(selection, indent=1, default=float) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--configs", required=True)
    r.add_argument("--horizons", default="1,3,6")
    r.add_argument("--threads", type=int, default=4)
    sub.add_parser("report-stage1")
    sub.add_parser("report-stage2")
    a = ap.parse_args()
    if a.cmd == "run":
        for cfg in a.configs.split(","):
            for H in map(int, a.horizons.split(",")):
                run_config(cfg, H, a.threads)
    elif a.cmd == "report-stage1":
        report_stage1()
    else:
        report_stage2()


if __name__ == "__main__":
    main()
