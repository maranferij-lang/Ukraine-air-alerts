"""Leakage check for the seven Telegram columns (src/telegram_features.py), same 40 test origins as check_no_peeking.py.

For each origin t and each lag (0, 15 min): keep only the posts published strictly before t - lag (a plain
pandas filter on the post time), rebuild the features for that origin from the kept posts alone, and
require exact equality with the columns the model uses (built from all posts). A second, slow and
independent implementation (loops over oblasts and plain boolean masks) must agree with the vectorized one.
Negative controls: a window ending 15 minutes AFTER t, and the lag-0 features against the lag-15 ones. Both
must disagree wherever a post fell in the extra minutes. Last, how many features change if the posts marked
"edited" are left out (the text of an edited post is the text at pull time, see the README).

    python scripts/check_no_peeking_telegram.py

Prints the result and writes the same lines to results/telegram/no_peeking.txt.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts.check_no_peeking import N_ORIGINS, same
from src.dataset import EVAL_LOOKBACK, TEST_DAYS, build_rows, split
from src.telegram_features import CAP_MIN, TG_FEATURES, THREATS, load_posts, tg_features

LAGS = {"lag 0": pd.Timedelta(0), "lag 15min": pd.Timedelta(minutes=15)}
H = pd.Timedelta(hours=1)


def slow_features(oblasts, t, posts, lag):
    """The seven features for one origin by plain masks. Independent of tg_features()."""
    e = t - lag
    p = posts[posts["time"] < e]  # strictly before
    rows = []
    for ob in oblasts:
        mine = p[p["units"].map(lambda s: ob in s)]
        last6 = p[p["time"] >= e - 6 * H]
        in6 = mine[mine["time"] >= e - 6 * H]
        since = (t - mine["time"].max()) / pd.Timedelta(minutes=1) if len(mine) else CAP_MIN
        r = {"tg_m1h": float((mine["time"] >= e - H).any()), "tg_m3h": float((mine["time"] >= e - 3 * H).any()),
             "tg_share6h": len(in6) / len(last6) if len(last6) else np.nan, "tg_min_since": min(since, CAP_MIN)}
        for name in THREATS:
            r[name] = float(p.loc[p["time"] >= e - 3 * H, name].any())
        rows.append(r)
    return pd.DataFrame(rows, index=oblasts)[TG_FEATURES]


def main(verbose=True):
    rows, _, _, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    oblasts = sorted(rows["oblast"].unique())
    posts = load_posts()
    full = {name: tg_features(rows, posts, lag) for name, lag in LAGS.items()}
    key = pd.MultiIndex.from_frame(rows[["oblast", "t"]])

    test6 = split(rows, first, end, test_start, 6, pd.Timedelta(hours=24))["test"]
    origins = rows.loc[test6, "t"].drop_duplicates().sample(N_ORIGINS, random_state=0).sort_values()
    mism_trunc = mism_slow = ctrl_future = ctrl_future_possible = ctrl_lag = ctrl_lag_possible = checked = 0
    for t in origins:
        grid = rows[rows["t"] == t].reset_index(drop=True)
        pos = key.get_indexer(pd.MultiIndex.from_frame(grid[["oblast", "t"]]))
        for name, lag in LAGS.items():
            kept = posts[posts["time"] < t - lag].reset_index(drop=True)
            trunc = tg_features(grid, kept, lag)
            want = full[name].to_numpy()[pos]
            mism_trunc += int((~same(trunc.to_numpy(), want)).sum())
            slow = slow_features(grid["oblast"].tolist(), t, posts, lag)
            mism_slow += int((~same(slow.to_numpy(), want)).sum())
            checked += want.size
        # negative control 1: the lag-0 window moved to end 15 minutes AFTER t (posts from the future)
        future = tg_features(grid, posts, pd.Timedelta(minutes=-15)).to_numpy()
        base = full["lag 0"].to_numpy()[pos]
        new_posts = int(((posts["time"] >= t) & (posts["time"] < t + pd.Timedelta(minutes=15))).sum())
        ctrl_future_possible += new_posts > 0
        ctrl_future += int((~same(future, base)).any())
        # negative control 2: lag 0 against lag 15 must differ when a post fell in [t-15min, t)
        gap_posts = int(((posts["time"] >= t - pd.Timedelta(minutes=15)) & (posts["time"] < t)).sum())
        ctrl_lag_possible += gap_posts > 0
        ctrl_lag += int((~same(full["lag 15min"].to_numpy()[pos], base)).any())

    # sensitivity to edited posts: features of the lag-0 model without them, over all rows of 2026
    edited = posts["edited"].astype(str).str.lower().eq("true")
    sel = (rows["t"] >= pd.Timestamp("2026-01-01", tz="UTC")).to_numpy()
    no_edit = tg_features(rows[sel].reset_index(drop=True), posts[~edited].reset_index(drop=True), pd.Timedelta(0))
    ref = full["lag 0"][sel].reset_index(drop=True)
    changed = (~same(no_edit.to_numpy(), ref.to_numpy())).mean(axis=0)
    test_posts = posts[(posts["time"] >= test_start)]
    n = N_ORIGINS * len(oblasts) * len(TG_FEATURES) * len(LAGS)
    lines = [
        f"origins: {N_ORIGINS} from {origins.min()} to {origins.max()} (same as check_no_peeking.py)",
        f"features rebuilt from posts published before t - lag only: {n} values, mismatches {mism_trunc}",
        f"independent slow implementation vs vectorized features: {n} values, mismatches {mism_slow}",
        f"negative control, window ending 15 minutes after t: differs at {ctrl_future} of {N_ORIGINS} origins "
        f"({ctrl_future_possible} origins had a post in [t, t+15min))",
        f"negative control, lag 0 vs lag 15 min features: differ at {ctrl_lag} of {N_ORIGINS} origins "
        f"({ctrl_lag_possible} origins had a post in [t-15min, t))",
        f"posts marked edited: {int(edited.sum())} of {len(posts)} ({edited.mean():.1%}); in the test window "
        f"{int(test_posts['edited'].astype(str).str.lower().eq('true').sum())} of {len(test_posts)}",
        "share of 2026 rows whose value changes if edited posts are dropped (lag 0): "
        + ", ".join(f"{c} {v:.2%}" for c, v in zip(TG_FEATURES, changed)),
    ]
    if verbose:
        print("\n".join(lines))
    assert mism_trunc == 0 and mism_slow == 0
    assert ctrl_future > 0 and ctrl_future == ctrl_future_possible and ctrl_lag > 0
    out = ROOT / "results" / "telegram" / "no_peeking.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out.relative_to(ROOT)} (Telegram leakage check: {mism_trunc + mism_slow} mismatches, negative controls fired "
          f"at {ctrl_future} and {ctrl_lag} of {N_ORIGINS} origins)", flush=True)


if __name__ == "__main__":
    main()
