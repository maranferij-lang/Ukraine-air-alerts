"""Score the live forecasts in data/predictions/log.csv against what the API archive says happened (offline, no token, no network).

    python scripts/score_predictions.py                 print the report
    python scripts/score_predictions.py --write         also write results/live_forecast_scores.md

Same target and metrics as the forward test (scripts/forward_test.py): target (b), a new alert starts in (t, t+H]; within-oblast AUC, Brier, calibration in
the large, precision / recall / F1 at the threshold that was logged with each forecast (the frozen one); next to the three baselines on the same rows (same as
now, same hour yesterday, train frequency from the frozen table; 0/1 baselines raw). Outcomes come from the day files in data/api_archive/, built exactly as
in the forward test (AUC only, hromada rows dropped, 5-minute restarts joined, half of the raions).

A forecast is scored only when its horizon has fully passed AND the archive was fetched after that: both day files that the window (t, t+H] touches must have
been fetched (data/api_archive/log.csv) at least 5 minutes after t+H. Forecasts that are not scoreable yet are counted, not guessed. If one origin/oblast/H was
logged more than once (the script was run twice in the same hour), the first run is the one scored. The log is only read, never changed.
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts.api_check import day_files, load_api, to_official_rows
from scripts.forward_test import NAMES, day_bootstrap, load_frozen
from scripts.live_api import PRED_COLUMNS, PRED_LOG, inputs
from src.baselines import same_hour_yesterday, train_frequency
from src.dataset import HORIZONS, build_rows
from src.metrics import brier, precision_recall_f1, summarize

ARCHIVE_DIR = ROOT / "data" / "api_archive"
MARGIN = pd.Timedelta(minutes=5)
TOO_SMALL_DAYS, WIDE_DAYS = 3, 14   # fewer than 3 scored days: no interval at all; 3-13: very wide; 14+: a start (the forward test had 41)
OUT = ROOT / "results" / "live_forecast_scores.md"


def read_log(path):
    with open(path, newline="") as fh:
        header = next(csv.reader(fh), None)
    if header != PRED_COLUMNS:
        sys.exit(f"{path} does not have the expected header {PRED_COLUMNS}")
    df = pd.read_csv(path, float_precision="round_trip", dtype={"model_version": str})
    df["origin"] = pd.to_datetime(df["origin_utc"], utc=True)
    df["run_time"] = pd.to_datetime(df["run_time_utc"], utc=True)
    n_all = len(df)
    df = df.sort_values("run_time", kind="stable").drop_duplicates(["origin", "oblast", "h"], keep="first")
    return df, n_all


def fetch_times(archive_dir):
    """{UTC day: when its newest saved file was fetched}, from the archive's own fetch log (successful dateHistory calls only)."""
    path = archive_dir / "log.csv"
    if not path.exists():
        sys.exit(f"{path} is missing: without the fetch times there is no way to know how far the archive can be trusted.")
    lg = pd.read_csv(path)
    lg = lg[(lg["endpoint"] == "dateHistory") & (lg["http_status"] == 200)]
    lg["day"] = pd.to_datetime(lg["date"], utc=True)
    lg["fetched"] = pd.to_datetime(lg["fetched_at_utc"], utc=True)
    return lg.groupby("day")["fetched"].max().to_dict()


def spans(dates):
    """'2026-10-19 to 10-23, 10-25' from a sorted list of dates."""
    out, start, prev = [], None, None
    for d in dates:
        if start is None:
            start = prev = d
        elif (d - prev).days == 1:
            prev = d
        else:
            out.append((start, prev)); start = prev = d
    if start is not None:
        out.append((start, prev))
    return ", ".join(f"{a:%Y-%m-%d}" if a == b else f"{a:%Y-%m-%d} to {b:%m-%d}" for a, b in out)


def score(log_path=PRED_LOG, archive_dir=ARCHIVE_DIR, n_boot=1000):
    """Returns (report lines, table DataFrame or None)."""
    df, n_all = read_log(log_path)
    lines = []
    if df.empty:
        return ["The prediction log is empty: nothing to score."], None
    fetched = fetch_times(archive_dir)
    files = day_files(archive_dir / "date_history")

    def ok(t, H):
        end = t + pd.Timedelta(hours=H)
        days = {t.floor("D"), end.floor("D")}
        return all(d in files and d in fetched and fetched[d] >= end + MARGIN for d in days)

    df["scoreable"] = [ok(t, H) for t, H in zip(df["origin"], df["h"])]
    raions, oblasts = inputs()
    info, frozen, boosters, freq = load_frozen()
    api_rows, _, _ = to_official_rows(load_api(files), raions, keep_open=True)
    api_rows = api_rows[api_rows["oblast"].isin(oblasts)]
    first = min(files)
    end = max(fetched.values()).floor("h")
    rows, episodes, raw, first, end = build_rows(api_rows, raions, first=first, end=end)
    key = pd.MultiIndex.from_frame(rows[["oblast", "t"]])

    runs = df["run_time"].nunique()
    versions = sorted(df["model_version"].unique())
    mixed = len(versions) > 1
    lines += [f"Logged forecasts: {n_all} rows ({len(df)} distinct origin/oblast/horizon; {runs} runs), origins {df['origin'].min():%Y-%m-%d %H:%M} to {df['origin'].max():%Y-%m-%d %H:%M} UTC, "
              f"{df['origin'].nunique()} distinct hours on {df['origin'].dt.floor('D').nunique()} dates; model version(s): {', '.join(versions)}."]
    per_h = df.groupby("h")["scoreable"].agg(["sum", "size"])
    lines.append("Scoreable now (horizon passed and the archive fetched after it): " + "; ".join(f"H={h}: {int(r['sum'])} of {int(r['size'])}" for h, r in per_h.iterrows())
                 + f". Not scoreable yet: {int((~df['scoreable']).sum())}" + (" (their horizon has not passed, or the archive has not been refreshed since)." if (~df["scoreable"]).any() else "."))
    sc = df[df["scoreable"]]
    if sc.empty:
        lines.append("Nothing can be scored yet. Run scripts/archive_api.py on a later day, then this again.")
        return lines, None
    days_scored = sorted(sc["origin"].dt.floor("D").unique())
    lines.append(f"Scored: {len(sc)} forecasts ({sc['origin'].nunique()} origin hours) on {len(days_scored)} dates: {spans([pd.Timestamp(d) for d in days_scored])}.")

    table, boots = [], []
    for H in HORIZONS:
        s = sc[sc["h"] == H]
        if s.empty:
            continue
        idx = key.get_indexer(pd.MultiIndex.from_arrays([s["oblast"], s["origin"]]))
        assert (idx >= 0).all(), "a scored forecast is outside the rows built from the archive"
        r = rows.iloc[idx].reset_index(drop=True)
        y = r[f"b_start_{H}"].to_numpy().astype(bool)
        yday = same_hour_yesterday(rows, f"b_start_{H}").to_numpy()[idx]
        table_f = pd.read_csv(ROOT / "models" / f"frequency_b_start_h{H}.csv", float_precision="round_trip").set_index(["oblast", "hour", "weekday"])["rate"]
        fq = train_frequency(rows, table_f).to_numpy()[idx]
        preds = {"lgbm": s["probability"].to_numpy(), "persistence": r["now"].to_numpy().astype(float), "yesterday": yday, "frequency": fq}
        thr = {"lgbm": float(s["threshold"].median()), "persistence": None, "yesterday": None, "frequency": frozen["thresholds"][str(H)]["frequency"]}
        flags = s["above_threshold"].to_numpy().astype(float)  # the decision logged with each forecast, not recomputed
        for name, p in preds.items():
            keep = ~np.isnan(p)
            res = summarize(y[keep], p[keep], r["oblast"][keep], thr[name])
            if name == "lgbm":
                res["precision"], res["recall"], res["f1"] = precision_recall_f1(y[keep], flags[keep], 0.5)
                uniq = sorted(s["threshold"].round(6).unique())
                res["threshold"] = f"{uniq[0]:.3f}" if len(uniq) == 1 else "mixed: " + "/".join(f"{u:.3f}" for u in uniq)
            table.append({"H": H, "predictor": NAMES[name], "n": int(keep.sum()), "base_rate": float(y[keep].mean()), "mean_predicted": float(p[keep].mean()),
                          "auc_within_oblast": res["auc_within_oblast"], "oblasts_with_both_outcomes": res["n_oblasts_auc"], "brier": res["brier"],
                          "threshold": res["threshold"], "precision": res["precision"], "recall": res["recall"], "f1": res["f1"]})
        if len(days_scored) >= TOO_SMALL_DAYS:
            ok_all = ~np.isnan(preds["yesterday"])
            bs = day_bootstrap(y[ok_all], {k: v[ok_all] for k, v in preds.items()}, r["oblast"].to_numpy()[ok_all],
                               s["origin"].dt.strftime("%Y-%m-%d").to_numpy()[ok_all], n=n_boot)
            boots.append({"H": H, **{f"{NAMES[k]} AUC": f"{v['auc']:.3f} ({v['auc_lo']:.3f}-{v['auc_hi']:.3f})" for k, v in bs.items()},
                          "LightGBM minus train frequency, AUC": f"{bs['frequency']['d_auc']:+.3f} ({bs['frequency']['d_auc_lo']:+.3f} to {bs['frequency']['d_auc_hi']:+.3f})"})
    T = pd.DataFrame(table)

    def md(d, fmt="{:.3f}"):
        cells = d.map(lambda v: fmt.format(v) if isinstance(v, (float, np.floating)) else str(v))
        return "\n".join(["| " + " | ".join(map(str, d.columns)) + " |", "|" + "---|" * len(d.columns)] + ["| " + " | ".join(c) + " |" for c in cells.itertuples(index=False)])

    n_days = len(days_scored)
    if n_days < TOO_SMALL_DAYS:
        verdict = (f"**FAR TOO SMALL TO MEAN ANYTHING.** {n_days} scored date(s) is a very small sample: the numbers below are anecdotes, no interval is computed, and one alert "
                   "more or less moves them. Do not read the model against the baselines from this.")
    elif n_days < WIDE_DAYS:
        verdict = (f"**TOO SMALL TO MEAN ANYTHING YET.** {n_days} scored dates. The day-resampling intervals below are very wide; the forward test had 41 days and its interval for the "
                   "H=1 AUC was still about +-0.03. Do not read the model against the baselines from this.")
    else:
        verdict = (f"{n_days} scored dates: a start, not yet the 41 days of the forward test. Read the intervals, not the point values, and do not pool this with the forward test.")
    ref = ROOT / "results" / "forward_api" / "forward_table.csv"
    refline = ""
    if ref.exists():
        f = pd.read_csv(ref)
        f = f[f["predictor"] == "LightGBM"].set_index("H")
        refline = ("For reference only (not pooled): the forward test, 41 days, LightGBM within-oblast AUC " + ", ".join(f"{f.loc[H, 'auc_within_oblast']:.3f} at H={H}" for H in HORIZONS) + ".")
    if mixed:
        verdict += (f" **The scored forecasts come from {len(versions)} model versions ({', '.join(versions)}); their thresholds differ, so the thresholded columns mix them. "
                    "Score them separately before reading anything.**")
    lines += ["", verdict, "", "Within-oblast AUC, Brier, calibration in the large (mean predicted against observed rate) and precision/recall/F1 at the logged frozen threshold, "
              "next to the baselines on the same rows. `oblasts_with_both_outcomes` is how many oblasts the AUC average covers (an oblast needs both outcomes).", "", md(T)]
    if boots:
        lines += ["", f"Day-block bootstrap ({n_boot} resamples of whole origin dates, seed 0), within-oblast AUC with 95% interval:", "", md(pd.DataFrame(boots))]
    if refline:
        lines += ["", refline]
    return lines, T


def main():
    ap = argparse.ArgumentParser(description="Score the logged live forecasts against the API archive.")
    ap.add_argument("--log", type=Path, default=PRED_LOG)
    ap.add_argument("--write", action="store_true", help="also write results/live_forecast_scores.md")
    a = ap.parse_args()
    if not a.log.exists():
        sys.exit(f"{a.log} does not exist yet: run scripts/predict.py --now first (every run appends to it).")
    lines, _ = score(a.log)
    print("\n".join(lines))
    if a.write:
        OUT.write_text("# Live forecasts scored against the API archive\n\nProduced by `scripts/score_predictions.py`.\n\n" + "\n".join(lines) + "\n")
        print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
