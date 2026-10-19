"""v2: LightGBM trained on the combined official + API dataset, compared with frozen v1 on a held-out test window. The design is in PROCESS_LOG.md (Round 16),
committed before this script existed; nothing here may deviate from it.

    python scripts/build_combined.py      first (makes data/combined/alerts_combined.csv, or this script builds the rows in memory)
    python scripts/train_v2.py            fits, scores, applies the decision rule, writes results/v2/ (and models/v2/ if the rule says v2)
    python scripts/train_v2.py --refit    also writes the production refit to models/v2/ when the rule says v1 (to try `predict.py --now --model v2`)

Data: the combined dataset cut at 2026-10-18 00:00 UTC, no outage mask. Split per H as v1's `split()` with test_start = 2026-09-28: train = windows closing by 09-28, validation fit =
windows closing by 09-21, validation week 09-21..09-27 (early stopping, F1 thresholds, Platt), final fit on all train with the early-stopped tree count (thresholds from the validation fit:
the same known approximation as v1), test = 09-28 .. 10-17 (windows closing by the cut). Same features, same PARAMS, MAX_TREES and early stopping as scripts/evaluate.py: no tuning.
Predictors on the same test rows: v2, v2 + Platt (secondary), frozen v1 (models/), logistic (refit on the v2 rows), same as now, same hour yesterday, train frequency (fitted on the v2
train rows), rolling 4-week frequency. Within-oblast AUC, Brier + decomposition, calibration in the large, precision/recall/F1 at the validation-week threshold, day-block bootstrap
(1,000 resamples of whole test days, seed 0). v1 was already scored on these days in the forward test.
Decision rule (fixed in advance): v2 becomes the default of `predict.py --now` only if AUC_v2 >= AUC_v1 at H = 1, 3 and 6 AND Brier_v2 < Brier_v1 at H = 1 (point values, plain v2, the same rows).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb
import numpy as np
import pandas as pd

from scripts.build_combined import CUT, build_combined, to_csv_bytes
from scripts.evaluate import MAX_TREES, PARAMS, fit_predict, fit_predict_logit
from scripts.forward_test import day_bootstrap, load_frozen
from src import logit
from src.baselines import frequency_table, same_hour_yesterday, train_frequency
from src.dataset import EVAL_LOOKBACK, HORIZONS, build_rows, load_inputs, split
from src.features import FEATURES, build_features, load_neighbours
from src.metrics import best_f1_threshold, brier, brier_decomposition, precision_recall_f1, reliability_table, summarize

TEST_START = pd.Timestamp("2026-09-28", tz="UTC")
OUT = ROOT / "results" / "v2"
MODELS_V2 = ROOT / "models" / "v2"
NAMES = {"lgbm": "v2 LightGBM", "platt": "v2 + Platt (secondary)", "v1": "frozen v1 LightGBM", "logit": "logistic (refit on the v2 rows)",
         "persistence": "same as now", "yesterday": "same hour yesterday", "frequency": "train frequency", "freq4w": "rolling 4-week frequency"}
N_BOOT = 1000


def md(df, fmt="{:.3f}"):
    cells = df.map(lambda v: fmt.format(v) if isinstance(v, (float, np.floating)) else str(v))
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)] + ["| " + " | ".join(r) + " |" for r in cells.itertuples(index=False)])


def platt_fit(p, y):
    """Platt scaling: logistic regression of the outcome on the logit of the score (intercept and slope), by the same IRLS as the logistic model."""
    z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    w, _ = logit.fit(np.column_stack([z, np.ones_like(z)]), y)
    return w


def platt_apply(p, w):
    z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    return 1 / (1 + np.exp(-(w[0] * z + w[1])))


def rounded(obj, ndigits):
    """Every float in a nested dict/list rounded (round() is correctly rounded, so the same value gives the same text on every machine)."""
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: rounded(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [rounded(v, ndigits) for v in obj]
    return obj


def main():
    ap = argparse.ArgumentParser(description="Train v2 on the combined dataset and compare it with frozen v1 (design: PROCESS_LOG.md, Round 16).")
    ap.add_argument("--refit", action="store_true", help="write the production refit to models/v2/ even if the decision rule keeps v1")
    args = ap.parse_args()

    comb, _ = build_combined()
    official, raions = load_inputs()
    oblasts = sorted(official["oblast"].unique())
    cr = comb[["oblast", "raion", "hromada", "level", "start", "end"]]
    first = official["start"].min().ceil("D")
    rows, episodes, raw, first, end = build_rows(cr, raions, first=first, end=CUT)
    assert end == CUT
    feats = build_features(rows, episodes, raw, load_neighbours(), HORIZONS, oblasts, outages=[])      # no outage mask
    info1, frozen1, boosters1, _ = load_frozen()
    day = rows["t"].dt.strftime("%Y-%m-%d")
    print(f"rows: {rows['oblast'].nunique()} oblasts x {rows['t'].nunique()} hours, {first:%Y-%m-%d} to {end:%Y-%m-%d %H:%M} UTC; test from {TEST_START:%Y-%m-%d}", flush=True)

    table, cal, boot_rows, decomp, rel, platt_info, train_info = [], [], [], [], [], [], []
    auc, br, trees_by_h, thr_v2, models_v2 = {}, {}, {}, {}, {}
    for H in HORIZONS:
        m = split(rows, first, end, TEST_START, H, EVAL_LOOKBACK, outages=())
        h = pd.Timedelta(hours=H)
        train_close, val_close = (rows.loc[m["train"], "t"] + h).max(), (rows.loc[m["before_last_week"], "t"] + h).max()
        assert train_close <= TEST_START and val_close <= TEST_START - pd.Timedelta(days=7), "a training window reaches into the validation week or the test window"
        test, wk = m["test"], m["last_week"]
        y = rows[f"b_start_{H}"]
        yt = y[test].to_numpy().astype(bool)

        s_v2, trees, final = fit_predict(feats[H], y, m)                    # scores: validation week from the validation fit, test from the final fit
        s_lg, it, w_lg = fit_predict_logit(feats[H], y, m, oblasts)
        trees_by_h[H], models_v2[H] = int(trees), final
        thr_v2[H] = best_f1_threshold(y[wk], s_v2[wk])
        thr_lg = best_f1_threshold(y[wk], s_lg[wk])
        w_pl = platt_fit(s_v2[wk].to_numpy(), y[wk].to_numpy())
        s_pl = pd.Series(platt_apply(s_v2.to_numpy(), w_pl), index=s_v2.index)
        thr_pl = best_f1_threshold(y[wk], s_pl[wk])
        p_v1 = pd.Series(boosters1[H].predict(feats[H][FEATURES]), index=rows.index)
        f_tab = frequency_table(rows[m["train"]], f"b_start_{H}")
        s_fq = train_frequency(rows, f_tab)
        s_fq_wk = train_frequency(rows, frequency_table(rows[m["before_last_week"]], f"b_start_{H}"))
        f4 = feats[H]["freq4w"].astype(float)
        thr_f4 = best_f1_threshold(y[wk & f4.notna()], f4[wk & f4.notna()])
        S_all = {"lgbm": s_v2, "platt": s_pl, "v1": p_v1, "logit": s_lg, "persistence": rows["now"].astype(float),
                 "yesterday": same_hour_yesterday(rows, f"b_start_{H}"), "frequency": s_fq, "freq4w": f4}
        thr = {"lgbm": thr_v2[H], "platt": thr_pl, "v1": frozen1["thresholds"][str(H)]["lgbm"], "logit": thr_lg, "persistence": None, "yesterday": None,
               "frequency": best_f1_threshold(y[wk], s_fq_wk[wk]), "freq4w": thr_f4}
        S = {k: v[test].to_numpy() for k, v in S_all.items()}
        assert all(not np.isnan(v).any() for v in S.values()), "a predictor has missing scores on the test rows"
        ob = rows.loc[test, "oblast"]
        for name, s in S.items():
            r = summarize(yt, s, ob, thr[name])
            table.append({"H": H, "predictor": NAMES[name], "n": len(yt), "base_rate": float(yt.mean()), "auc_within_oblast": r["auc_within_oblast"], "oblasts_with_both_outcomes": r["n_oblasts_auc"],
                          "brier": r["brier"], "threshold": r["threshold"], "precision": r["precision"], "recall": r["recall"], "f1": r["f1"]})
            if name == "lgbm":
                auc[(H, "v2")], br[(H, "v2")] = r["auc_within_oblast"], r["brier"]
            if name == "v1":
                auc[(H, "v1")], br[(H, "v1")] = r["auc_within_oblast"], r["brier"]
            if name in ("lgbm", "platt", "v1", "logit", "frequency", "freq4w"):
                d = brier_decomposition(yt, s)
                bias = float(s.mean() - yt.mean())
                cal.append({"H": H, "predictor": NAMES[name], "mean_predicted": float(s.mean()), "observed": float(yt.mean()), "bias": bias, "bias^2": bias ** 2,
                            "brier": d["brier"], "reliability": d["reliability"], "resolution": d["resolution"], "uncertainty": d["uncertainty"], "residual": d["residual"]})
            if name in ("lgbm", "platt"):
                rel.append(reliability_table(yt, s).reset_index().rename(columns={"index": "bin"}).assign(H=H, predictor=NAMES[name]))
        b = day_bootstrap(yt, S, ob, day[test].to_numpy(), n=N_BOOT)
        for name, v in b.items():
            boot_rows.append({"H": H, "predictor": NAMES[name], **v})
        platt_info.append({"H": H, "intercept": float(w_pl[1]), "slope on logit(p)": float(w_pl[0]), "validation-week rows": int(wk.sum()), "threshold plain v2": thr_v2[H], "threshold Platt": thr_pl})
        train_info.append({"H": H, "train rows": int(m["train"].sum()), "validation-fit rows": int(m["before_last_week"].sum()), "validation-week rows": int(wk.sum()), "test rows": int(test.sum()),
                           "trees (early stopping on the validation week)": int(trees), "logistic iterations": int(it), "train windows close by": f"{train_close:%Y-%m-%d %H:%M}",
                           "validation-fit windows close by": f"{val_close:%Y-%m-%d %H:%M}", "frozen v1 threshold": thr["v1"], "v2 threshold": thr_v2[H]})
        print(f"H={H}: v2 {trees} trees; train {int(m['train'].sum())}, test {int(test.sum())} rows; bootstrap done", flush=True)

    # ------- the decision rule, applied exactly as written in the design
    rule_auc = {H: bool(auc[(H, "v2")] >= auc[(H, "v1")]) for H in HORIZONS}
    rule_brier = bool(br[(1, "v2")] < br[(1, "v1")])
    use = "v2" if all(rule_auc.values()) and rule_brier else "v1"
    decision = {"use": use, "rule": "v2 only if AUC_v2 >= AUC_v1 at H = 1, 3 and 6 AND Brier_v2 < Brier_v1 at H = 1 (plain v2 against frozen v1, point values, the same test rows)",
                "auc_v2": {str(H): auc[(H, "v2")] for H in HORIZONS}, "auc_v1": {str(H): auc[(H, "v1")] for H in HORIZONS}, "auc_not_worse": {str(H): rule_auc[H] for H in HORIZONS},
                "brier_v2": {str(H): br[(H, "v2")] for H in HORIZONS}, "brier_v1": {str(H): br[(H, "v1")] for H in HORIZONS}, "brier_better_at_h1": rule_brier,
                "tree_counts": {str(H): trees_by_h[H] for H in HORIZONS}, "thresholds": {str(H): thr_v2[H] for H in HORIZONS}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "decision.json").write_text(json.dumps(rounded(decision, 10), indent=1) + "\n")  # the rule above ran on the full-precision values; the file keeps 10 decimals so it is the same on arm and x86

    T, C, B, R = pd.DataFrame(table), pd.DataFrame(cal), pd.DataFrame(boot_rows), pd.concat(rel)
    T.to_csv(OUT / "test_table.csv", index=False, float_format="%.4f")
    head = ("# v2 against frozen v1 on the held-out window (2026-09-28 to 2026-10-17)\n\n"
            "v2 = LightGBM trained on the combined official + API dataset (cut at 2026-10-18 00:00 UTC, no outage mask) with v1's features and hyperparameters, nothing tuned; split as in `PROCESS_LOG.md` (Round 16, written before any of these numbers existed): "
            "train to 2026-09-27 (windows closing by 09-28), validation fit to 09-20, validation week 09-21 to 09-27, test 09-28 to 10-17, **20 days**. **Frozen v1 was already scored on these days in the forward test** "
            "(`results/forward_api/`): its number here is not new information about v1. One period, one source (the API for these days): the intervals are wide. Target (b): a new alert starts in (t, t+H].\n\n")
    (OUT / "test_table.md").write_text(head + md(T) + "\n\nThresholds: max F1 on the validation week (v2, Platt, logistic, rolling 4-week frequency: from the validation fit; train frequency: from the table fitted without the validation week); frozen v1: its own frozen threshold; 'raw 0/1': the baseline as is.\n")
    cols = ["H", "predictor", "auc", "auc_lo", "auc_hi", "brier", "brier_lo", "brier_hi"]
    diff = B[B["predictor"] != NAMES["lgbm"]][["H", "predictor", "d_auc", "d_auc_lo", "d_auc_hi", "share_auc_ahead", "d_brier", "d_brier_lo", "d_brier_hi", "share_brier_ahead"]]
    (OUT / "bootstrap.md").write_text(f"v2 test window (20 days). Day-block bootstrap: whole test days resampled with replacement, {N_BOOT} resamples, seed 0, 95% percentile intervals.\n\nEach predictor:\n\n" + md(B[cols])
                                      + "\n\nv2 minus each other predictor (AUC: positive = v2 ahead; Brier: negative = v2 ahead; `share_*_ahead` = share of resamples in which v2 is ahead). 'v2 + Platt' has the same within-oblast AUC by construction, so its AUC difference is 0:\n\n" + md(diff) + "\n")
    (OUT / "calibration.md").write_text("v2 test window (20 days), target (b). Calibration in the large (mean predicted against observed; Brier = bias^2 + Var(p - y) exactly) and the Murphy decomposition "
                                        "(Brier = reliability - resolution + uncertainty + residual).\n\n" + md(C, "{:.4f}") + "\n\n## Platt scaling (secondary variant)\n\nFitted only on the validation week, on the validation-fit model's scores, "
                                        "then applied to the final model's test scores (the same approximation as the thresholds):\n\n" + md(pd.DataFrame(platt_info), "{:.4f}")
                                        + "\n\nReliability table, plain v2 and v2 + Platt (10 bins):\n\n" + md(R[["H", "predictor", "bin", "mean_predicted", "observed", "n"]]) + "\n")
    inf = pd.DataFrame(train_info)
    verdict = [f"- H={H}: AUC v2 {auc[(H, 'v2')]:.4f} against v1 {auc[(H, 'v1')]:.4f}: " + ("not worse" if rule_auc[H] else "WORSE") for H in HORIZONS]
    verdict.append(f"- Brier at H=1: v2 {br[(1, 'v2')]:.4f} against v1 {br[(1, 'v1')]:.4f}: " + ("better" if rule_brier else "NOT better"))
    (OUT / "decision.md").write_text("# The decision rule, applied\n\nFixed in advance (`PROCESS_LOG.md`, Round 16): `predict.py --now` switches to v2 only if the within-oblast AUC of plain v2 is not worse than frozen v1's at all three horizons "
                                     "and its Brier is better at least at H = 1 (point values at full precision, the same test rows; intervals and the Platt variant play no part).\n\n" + "\n".join(verdict)
                                     + f"\n\n**Result: `predict.py --now` uses {use} by default.**\n\n## Training record\n\n" + md(inf, "{:.4f}") + "\n")
    print("\n".join(verdict)); print(f"DECISION: {use}")
    print(md(T)); print(md(B[cols])); print(md(diff)); print(md(C, "{:.4f}"))

    # ------- the production refit (only if the rule says v2, or on request): all origins whose window closes by the cut, the same tree counts
    if use == "v2" or args.refit:
        MODELS_V2.mkdir(parents=True, exist_ok=True)
        for H in HORIZONS:
            m_all = split(rows, first, end, end, H, EVAL_LOOKBACK, outages=())["train"]      # test_start = the cut: every usable origin
            prod = lgb.train(PARAMS, lgb.Dataset(feats[H][m_all], rows.loc[m_all, f"b_start_{H}"].astype(int)), num_boost_round=trees_by_h[H])
            prod.save_model(str(MODELS_V2 / f"lgbm_b_start_h{H}.txt"))
            print(f"H={H}: production refit on {int(m_all.sum())} rows, {trees_by_h[H]} trees", flush=True)
        (MODELS_V2 / "info.json").write_text(json.dumps({"features": FEATURES, "horizons": HORIZONS, "trees": {str(H): trees_by_h[H] for H in HORIZONS}, "cut": CUT.isoformat(),
                                                         "test_start": TEST_START.isoformat(), "combined_sha256": hashlib.sha256(to_csv_bytes(comb)).hexdigest(), "decision": use}, indent=1) + "\n")
        (MODELS_V2 / "frozen.json").write_text(json.dumps({"oblasts": oblasts, "thresholds": {str(H): {"lgbm": thr_v2[H]} for H in HORIZONS}}, indent=1) + "\n")
        print(f"wrote {MODELS_V2.relative_to(ROOT)}/ (production refit; not committed)")
    print(f"wrote {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
