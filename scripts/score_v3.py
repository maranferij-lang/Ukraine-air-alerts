"""The final comparison of v3 and the frozen v2 on days after 2026-10-19 (round 22; protocol: PROCESS_LOG.md, section 7). Run it later, when there are 14 or more full days.

    python scripts/archive_api.py ...           first, on the Mac: refresh data/api_archive/ (needs the Ukraine Alarm token, see the README)
    python scripts/train_v3.py                  if models/v3/ is not there (rebuilds it from results/round22/selection.json)
    python scripts/score_v3.py                  scores, writes results/v3_vs_v2/, prints the verdict

What it does: rebuilds the combined dataset with a later cut (`build_combined(cut=...)`, default: the start of the date of the latest day file in data/api_archive/, so a possibly partial last day is left out),
the rows, the 14 base features and v3's extra features; scores v3 (models/v3), the frozen v2 (models/v2) and the three simple rules on the same origins t >= 2026-10-19 00:00 UTC (train frequency fitted on the
production training rows, windows closing by 2026-10-18 00:00 UTC). Within-oblast AUC and Brier per H, precision/recall/F1 at each model's own validation-week threshold (the 0/1 rules raw), a day bootstrap
of the difference (1,000 resamples, seed 0), and the verdict of the rule written in advance: v3 beats v2 only if the mean-over-H AUC difference is > 0 with the lower end of the interval > 0, the mean-over-H
Brier difference is <= 0, and v3 is ahead on mean-over-H AUC in at least two thirds (rounded up) of the full 7-day blocks. The verdict is a report; it changes nothing (the default of `--now` stays v2 unless the
owner decides otherwise). With fewer than 14 full origin days it prints "too early" and the day count and stops (--force-early scores anyway and says on every line that it is not the verdict).
--start / --cut / --out exist for the pipeline test (in-sample, never reported as a result).
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts import dev_folds
from scripts.api_check import day_files
from scripts.build_combined import ARCHIVE, CUT, build_combined
from scripts.forward_test import load_frozen
from src import candidates
from src.baselines import frequency_table, same_hour_yesterday, train_frequency
from src.dataset import EVAL_LOOKBACK, HORIZONS, build_rows, load_inputs, split
from src.features import FEATURES, build_features, load_neighbours
from src.features_extra import build_extra, load_weather, raion_episodes, weather_features
from src.metrics import best_f1_threshold, precision_recall_f1

FINAL_START = pd.Timestamp("2026-10-19", tz="UTC")
MIN_DAYS = 14
OUT = ROOT / "results" / "v3_vs_v2"


def md(df, fmt="{:.3f}"):
    return dev_folds.md(df, fmt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=str(FINAL_START.date()))
    ap.add_argument("--cut", default=None, help="UTC instant the data is cut at (default: the start of the date of the latest day file)")
    ap.add_argument("--force-early", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--v2", default=str(ROOT / "models" / "v2"))
    ap.add_argument("--v3", default=str(ROOT / "models" / "v3"))
    a = ap.parse_args()
    start = pd.Timestamp(a.start, tz="UTC")
    files = day_files(ARCHIVE)
    cut = pd.Timestamp(a.cut, tz="UTC") if a.cut else max(files)
    v3dir = Path(a.v3)
    if not (v3dir / "info.json").exists():
        print("no models/v3/: either the round-22 rule selected no v3 (results/round22/selection.json) or scripts/train_v3.py has not been run here")
        return 0
    n_full = max(0, int((cut - pd.Timedelta(hours=max(HORIZONS) - 1) - start) // pd.Timedelta(days=1)))
    print(f"archive days to {max(files):%Y-%m-%d}; cut {cut:%Y-%m-%d %H:%M} UTC; full origin days from {start:%Y-%m-%d} (all 24 origins with the H=6 window inside the data): {n_full}")
    if n_full < MIN_DAYS and not a.force_early:
        print(f"too early: {n_full} full days, the protocol waits for {MIN_DAYS}. Refresh the archive (scripts/archive_api.py) and run again later.")
        return 0

    info3 = json.loads((v3dir / "info.json").read_text())
    thr3 = json.loads((v3dir / "frozen.json").read_text())["thresholds"]
    fam, fset = info3["family"], info3["feature_set"]
    d2 = Path(a.v2)
    info2, frozen2, boosters2, _ = load_frozen(d2)

    comb, _ = build_combined(cut=cut)
    official, raions = load_inputs()
    oblasts = sorted(official["oblast"].unique())
    cr = comb[["oblast", "raion", "hromada", "level", "start", "end"]]
    rows, episodes, raw, first, end = build_rows(cr, raions, first=official["start"].min().ceil("D"), end=cut)
    neighbours = load_neighbours()
    feats = build_features(rows, episodes, raw, neighbours, HORIZONS, oblasts, outages=[])
    extra = build_extra(rows, episodes, raw, raion_episodes(cr, raions), raions, neighbours, oblasts)
    if "C" in fset.split("+"):
        weather = load_weather()
        assert weather is not None and max(w.index.max() for w in weather.values()) >= end - pd.Timedelta(hours=1), "v3 uses weather, but data/weather/ does not cover the test days (scripts/fetch_weather.py --start ...)"
        extra = pd.concat([extra, weather_features(rows, weather)], axis=1)
    day = rows["t"].dt.strftime("%Y-%m-%d")
    cols = list(info3["extra_columns"])
    tag = ""
    if start != FINAL_START:
        tag = f"  [NOT THE VERDICT: --start {start:%Y-%m-%d} is not the protocol's {FINAL_START:%Y-%m-%d}; a pipeline test]"
    elif a.force_early and n_full < MIN_DAYS:
        tag = "  [NOT THE VERDICT: --force-early]"

    table, per_H = [], {}
    S_cache = {}
    for H in HORIZONS:
        target = f"b_start_{H}"
        m_prod = split(rows, first, end, CUT, H, EVAL_LOOKBACK, outages=())           # the production training rows of v2 and v3 (windows closing by the v2/v3 cut)
        m_test = split(rows, first, end, start, H, EVAL_LOOKBACK, outages=())["test"]
        sel = m_test.to_numpy()
        y = rows.loc[m_test, target].to_numpy().astype(bool)
        ob = rows.loc[m_test, "oblast"].to_numpy()
        X3 = pd.concat([feats[H], extra[cols]], axis=1) if cols else feats[H]
        p3 = candidates.predict(fam, candidates.load(fam, v3dir / f"{fam}_b_start_h{H}.{candidates.EXT[fam]}"), X3[m_test])
        p2 = boosters2[H].predict(feats[H][FEATURES][m_test])
        freq_tab = frequency_table(rows[m_prod["train"]], target)
        pf = train_frequency(rows, freq_tab)[m_test].to_numpy()
        pf_wk = train_frequency(rows, frequency_table(rows[m_prod["before_last_week"]], target))
        thr_f = best_f1_threshold(rows.loc[m_prod["last_week"], target], pf_wk[m_prod["last_week"]])
        S = {"v3": p3, "v2": p2, "persistence": rows.loc[m_test, "now"].astype(float).to_numpy(), "yesterday": same_hour_yesterday(rows, target)[m_test].to_numpy(), "frequency": pf}
        assert all(not np.isnan(v).any() for v in S.values()), "a predictor has missing scores on the test rows"
        thr = {"v3": thr3[str(H)]["v3"], "v2": frozen2["thresholds"][str(H)]["lgbm"], "persistence": None, "yesterday": None, "frequency": thr_f}
        labels = {"v3": f"v3 ({fam}:{info3['config']} on {fset})", "v2": "frozen v2 LightGBM", "persistence": "same as now", "yesterday": "same hour yesterday", "frequency": "train frequency"}
        for k, p in S.items():
            auc_, br = dev_folds.oblast_auc(y, p, ob), float(np.mean((p - y) ** 2))
            pr, rc, f1 = precision_recall_f1(y, p, 0.5 if thr[k] is None else thr[k])
            table.append({"H": H, "predictor": labels[k], "n": int(len(y)), "base_rate": float(y.mean()), "auc_within_oblast": auc_, "brier": br, "threshold": "raw 0/1" if thr[k] is None else round(float(thr[k]), 3), "precision": pr, "recall": rc, "f1": f1})
        per_H[H] = (y, ob, day[m_test].to_numpy(), S)

    boot = dev_folds.bootstrap_diff({H: (v[0], v[1], v[2], v[3]["v3"]) for H, v in per_H.items()}, {H: (v[0], v[1], v[2], v[3]["v2"]) for H, v in per_H.items()})
    # 7-day blocks of full days
    days_all = sorted(set(per_H[6][2]))
    full_days = [d for d in days_all if pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=23 + max(HORIZONS)) <= cut]
    blocks = [full_days[i:i + 7] for i in range(0, len(full_days) - 6, 7)]
    ahead = []
    for blk in blocks:
        diffs = []
        for H, (y, ob, dy, S) in per_H.items():
            i = np.isin(dy, blk)
            diffs.append(dev_folds.oblast_auc(y[i], S["v3"][i], ob[i]) - dev_folds.oblast_auc(y[i], S["v2"][i], ob[i]))
        ahead.append(float(np.mean(diffs)))
    need = math.ceil(2 * len(blocks) / 3)
    c_i = bool(boot["point"]["auc_mean"] > 0 and boot["auc_mean_ci"][0] > 0)
    c_ii = bool(boot["point"]["brier_mean"] <= 0)
    c_iii = bool(sum(d > 0 for d in ahead) >= need)
    verdict = "v3 beats v2" if (c_i and c_ii and c_iii) else "v2 stays"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    T = pd.DataFrame(table)
    head = (f"# v3 against the frozen v2 on origins from {start:%Y-%m-%d}{tag}\n\nOrigins {start:%Y-%m-%d} to the cut {cut:%Y-%m-%d %H:%M} UTC ({n_full} full origin days; the protocol waits for {MIN_DAYS}); the same rows for every predictor; "
            "train frequency fitted on the production training rows (windows closing by 2026-10-18 00:00 UTC). Thresholds: each model's own, from the last train week; 'raw 0/1' = the baseline as is. "
            "Target (b): a new alert starts in (t, t+H]. Protocol and rule: `PROCESS_LOG.md`, Round 22, section 7.\n\n")
    txt = [head + md(T)]
    txt.append(f"\n\n## Difference v3 minus v2 (day bootstrap, 1,000 resamples of the test days, seed 0)\n\nMean over H = 1, 3, 6: AUC {boot['point']['auc_mean']:+.4f} (95% [{boot['auc_mean_ci'][0]:+.4f}, {boot['auc_mean_ci'][1]:+.4f}]), "
               f"Brier {boot['point']['brier_mean']:+.5f} (95% [{boot['brier_mean_ci'][0]:+.5f}, {boot['brier_mean_ci'][1]:+.5f}]). Per H (AUC): " + ", ".join(f"H={H} {boot['point']['auc'][H]:+.4f} [{boot['auc_ci'][H][0]:+.4f}, {boot['auc_ci'][H][1]:+.4f}]" for H in HORIZONS)
               + f". Per H (Brier): " + ", ".join(f"H={H} {boot['point']['brier'][H]:+.5f}" for H in HORIZONS) + ".")
    txt.append("\n\n## Seven-day blocks (mean over H of the within-oblast AUC difference)\n\n" + (md(pd.DataFrame({"block": [f"{b[0]}..{b[-1]}" for b in blocks], "AUC diff (v3 minus v2)": ahead}), "{:+.4f}") if blocks else "no full 7-day block yet")
               + f"\n\nv3 ahead in {sum(d > 0 for d in ahead)} of {len(blocks)} blocks; the rule needs {need}.")
    txt.append(f"\n\n## Verdict of the rule written in advance{tag}\n\n(i) AUC difference > 0 with the lower end of the interval > 0: {'yes' if c_i else 'no'}; (ii) Brier difference <= 0: {'yes' if c_ii else 'no'}; (iii) ahead in at least two thirds of the 7-day blocks: {'yes' if c_iii else 'no'}.\n\n**{verdict}.**\n")
    (out / "v3_vs_v2.md").write_text("".join(txt))
    (out / "verdict.json").write_text(json.dumps({"verdict": verdict, "full_origin_days": n_full, "cut": cut.isoformat(), "start": start.isoformat(), "conditions": {"i": c_i, "ii": c_ii, "iii": c_iii},
                                                  "auc_mean_diff": boot["point"]["auc_mean"], "auc_mean_ci": boot["auc_mean_ci"], "brier_mean_diff": boot["point"]["brier_mean"], "force_early": bool(a.force_early)}, indent=1, default=float) + "\n")
    print("".join(txt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
