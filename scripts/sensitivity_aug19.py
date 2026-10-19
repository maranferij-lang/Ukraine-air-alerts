"""Side note on the old test: how much do its numbers move if the Aug 19-20 wave the official feed lacks is put back?

    python scripts/sensitivity_aug19.py        (about 2 minutes; needs data/api_archive/ and pip install translitua)

results/api_check.md found that from about 20:52 UTC on Aug 19 the API has an alert in Chernihivska and Kyivska oblast (about 10-13 hours) that
our official data does not have. This script makes a PATCHED COPY of the official rows in a temporary folder (data/raw in the repo is never
touched): the API's raion rows of those two oblasts for alerts starting in the window are added, so those oblast-hours become "alert". It then
runs the unmodified scripts/evaluate.py on the copy (same code, same training rows, so the same fitted models; only the test rows' alerts, targets
and features change) and compares results/test_table.csv. Writes results/aug19_sensitivity.md.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.api_check import day_files, load_api, to_official_rows
from src.dataset import load_inputs
from src.panel import hourly_panel, official_episodes

OBLASTS = ["Chernihivska oblast", "Kyivska oblast"]
WIN_A, WIN_B = pd.Timestamp("2026-08-19 19:00", tz="UTC"), pd.Timestamp("2026-08-20 12:00", tz="UTC")
NAMES = {"lgbm": "LightGBM", "logit": "logistic", "persistence": "same as now", "yesterday": "same hour yesterday", "frequency": "train frequency"}


def md(df, fmt="{:.4f}"):
    cells = df.map(lambda v: fmt.format(v) if isinstance(v, float) else str(v))
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
                     + ["| " + " | ".join(r) + " |" for r in cells.itertuples(index=False)])


def main():
    official, raions = load_inputs()
    api_rows, _, _ = to_official_rows(load_api(day_files(ROOT / "data" / "api_archive" / "date_history")), raions)
    add = api_rows[(api_rows["level"] == "raion") & api_rows["oblast"].isin(OBLASTS) & (api_rows["start"] >= WIN_A) & (api_rows["start"] < WIN_B)]
    # how many oblast-hours change
    pad = lambda df: df[(df["start"] >= WIN_A - pd.Timedelta(days=3)) & (df["start"] < WIN_B + pd.Timedelta(days=3))]
    before = hourly_panel(official_episodes(pad(official), raions=raions)[0], pd.Timestamp("2026-08-19", tz="UTC"), pd.Timestamp("2026-08-21", tz="UTC"), sorted(official["oblast"].unique()))
    after = hourly_panel(official_episodes(pad(pd.concat([official, add.assign(hromada="")[official.columns]])), raions=raions)[0],
                         pd.Timestamp("2026-08-19", tz="UTC"), pd.Timestamp("2026-08-21", tz="UTC"), sorted(official["oblast"].unique()))
    changed = (before["active"].to_numpy() != after["active"].to_numpy())
    n_changed = int(changed.sum())
    by_ob = before[changed].groupby("oblast").size().to_dict()

    raw = pd.read_csv(ROOT / "data" / "raw" / "official_data_en.csv", keep_default_na=False)
    fmt = lambda s: s.dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
    new = pd.DataFrame({"oblast": add["oblast"], "raion": add["raion"], "hromada": "", "level": "raion",
                        "started_at": fmt(add["start"]), "finished_at": fmt(add["end"]), "source": "official"})
    patched = pd.concat([raw, new], ignore_index=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for d in ("src", "scripts"):
            shutil.copytree(ROOT / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
        (tmp / "data" / "raw").mkdir(parents=True)
        shutil.copy(ROOT / "data" / "neighbours.csv", tmp / "data" / "neighbours.csv")
        patched.to_csv(tmp / "data" / "raw" / "official_data_en.csv", index=False)
        shutil.copy(ROOT / "data" / "raw" / "volunteer_data_en.csv", tmp / "data" / "raw" / "volunteer_data_en.csv")
        (tmp / "results").mkdir()
        (tmp / "figures").mkdir()
        subprocess.run([sys.executable, str(tmp / "scripts" / "evaluate.py")], cwd=tmp, check=True, capture_output=True)
        new_t = pd.read_csv(tmp / "results" / "test_table.csv")
    old_t = pd.read_csv(ROOT / "results" / "test_table.csv")

    key = ["target", "H", "predictor", "period"]
    j = old_t.merge(new_t, on=key, suffixes=("_old", "_new"))
    j = j[(j["target"] == "b_start") & (j["period"] == "all") & j["predictor"].isin(NAMES)]
    rows = []
    for r in j.itertuples():
        rows.append({"H": r.H, "predictor": NAMES[r.predictor],
                     "AUC old": r.auc_within_oblast_old, "AUC patched": r.auc_within_oblast_new, "AUC change": r.auc_within_oblast_new - r.auc_within_oblast_old,
                     "Brier old": r.brier_old, "Brier patched": r.brier_new, "Brier change": r.brier_new - r.brier_old})
    t = pd.DataFrame(rows)
    base = j.drop_duplicates("H")[["H", "base_rate_old", "base_rate_new"]]
    b = old_t[(old_t["target"] == "b_start") & (old_t["period"] == "all") & (old_t["predictor"] == "lgbm")][["H", "n_test"]]
    lines = [
        "# Side note: the old test with the Aug 19-20 wave put back",
        "",
        "`results/api_check.md` found a wave on Aug 19-20 (from about 20:52 UTC) that the Ukraine Alarm API has and our official data does not: "
        "alerts in all raions of Chernihivska oblast and in 7 raions of Kyivska oblast for about 10-13 hours. This is a sensitivity check, not a correction: "
        "`data/raw` and the old test (`results/test_table.md`) are unchanged.",
        "",
        "## What was done",
        f"- A patched copy of the official rows, in a temporary folder only: the API's {len(add)} raion rows of {', '.join(OBLASTS)} starting between {WIN_A:%Y-%m-%d %H:%M} and {WIN_B:%Y-%m-%d %H:%M} UTC added. "
        f"That changes {n_changed} oblast-hours from quiet to under alert ({', '.join(f'{k}: {v}' for k, v in by_ob.items())}).",
        "- The unmodified `scripts/evaluate.py` was run on the copy: the same training rows (all before 2026-08-07, so the same fitted models and thresholds), "
        "the same 24 test days and rows; only alerts, targets (b) and the features that depend on them change on the test rows (and on the same-as-now and same-hour-yesterday baselines).",
        "",
        "## Target (b), all 24 test days: within-oblast AUC and Brier, old test against the patched copy",
        "",
        md(t),
        "",
        "Base rate of a new alert starting in (t, t+H]: " + "; ".join(f"H={int(r.H)}: {r.base_rate_old:.4f} -> {r.base_rate_new:.4f}" for r in base.itertuples()) + ".",
        "",
        "Reading it: the table is the whole effect; no conclusion beyond the numbers is drawn here. Source of the added alerts: the API (one source; the official feed is the "
        "one being patched), so the patched copy is a mix of the two.",
    ]
    (ROOT / "results" / "aug19_sensitivity.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
