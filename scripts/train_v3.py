"""Train v3, the one candidate the round-22 rule selected (results/round22/selection.json), to models/v3/ (git-ignored, like every model). Design: PROCESS_LOG.md, Round 22, section 6.

    python scripts/train_v3.py                      reads results/round22/selection.json; says "no v3" and stops if the rule selected none
    python scripts/train_v3.py --selection FILE     another selection file (the scorer's pipeline test uses a throwaway one)
    python scripts/train_v3.py --out DIR            another output folder

Final fit: all origins whose target window closes by the cut (2026-10-18 00:00 UTC), the number of trees FIXED by the selection (the median over the six development folds of the early-stopped count, per H),
no early stopping on the last weeks. Thresholds: max F1 on the last train week (2026-10-11 .. 10-17) from a fit on the windows closing by 10-11 with the same fixed number of trees, as for v1 and v2.
Nothing here changes v2, models/v2 or `predict.py --now`.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts import dev_folds
from scripts.build_combined import CUT, to_csv_bytes, load_combined
from src import candidates
from src.dataset import EVAL_LOOKBACK, HORIZONS, split
from src.metrics import best_f1_threshold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection", default=str(ROOT / "results" / "round22" / "selection.json"))
    ap.add_argument("--out", default=str(ROOT / "models" / "v3"))
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    sel = json.loads(Path(a.selection).read_text())
    v3 = sel.get("v3")
    if not v3:
        print("no v3: the round-22 rule selected no candidate (v2 stays); nothing trained")
        return 0
    fam, name, fset = v3["family"], v3["config"], v3["features"]
    D = dev_folds.data()
    rows = D["rows"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    thresholds, used = {}, {}
    for H in HORIZONS:
        X, y = dev_folds.frame(H, fset), rows[f"b_start_{H}"].astype(int)
        m = split(rows, D["first"], D["end"], CUT, H, EVAL_LOOKBACK, outages=())
        trees = int(v3["trees"][str(H)])
        h = pd.Timedelta(hours=H)
        assert (rows.loc[m["train"], "t"] + h).max() <= CUT and (rows.loc[m["before_last_week"], "t"] + h).max() <= CUT - pd.Timedelta(days=7)
        val = candidates.fit_final(fam, name, X[m["before_last_week"]], y[m["before_last_week"]], trees, a.threads)
        wk = m["last_week"]
        thresholds[str(H)] = best_f1_threshold(y[wk], candidates.predict(fam, val, X[wk]))
        final = candidates.fit_final(fam, name, X[m["train"]], y[m["train"]], trees, a.threads)
        candidates.save(fam, final, out / f"{fam}_b_start_h{H}.{candidates.EXT[fam]}")
        used[str(H)] = {"train_rows": int(m["train"].sum()), "validation_fit_rows": int(m["before_last_week"].sum()), "last_week_rows": int(wk.sum()), "trees": trees}
        print(f"H={H}: {fam}:{name} on {fset}, {trees} trees, train {used[str(H)]['train_rows']} rows, threshold {thresholds[str(H)]:.4f}", flush=True)
    comb = load_combined()
    (out / "info.json").write_text(json.dumps({"family": fam, "config": name, "feature_set": fset, "extra_columns": dev_folds.feature_columns(fset), "horizons": HORIZONS, "trees": v3["trees"], "cut": CUT.isoformat(),
                                               "combined_sha256": hashlib.sha256(to_csv_bytes(comb[["oblast", "raion", "hromada", "level", "start", "end", "source"]])).hexdigest(), "rows": used}, indent=1) + "\n")
    (out / "frozen.json").write_text(json.dumps({"oblasts": D["oblasts"], "thresholds": {H: {"v3": thresholds[H]} for H in thresholds}}, indent=1) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
