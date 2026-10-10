"""Leakage check: recompute everything a forecast at t uses from data truncated at t.

For the same 40 test origins as round 2: keep only alert rows that started by t, and mark every
end after t as unknown (far future). Rebuild the episodes and recompute
  - "now" and the same-hour-yesterday outcomes (baseline inputs)
  - the full model feature matrix, every feature, every H
and require exact equality with the full-data pipeline. Two negative controls show the check would
catch peeking: the future target itself, and a deliberately leaky feature (time under alert in a
window reaching one hour past t). Also checks that every training row's target window closes
before the data it must not see.

    python scripts/check_no_peeking.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.dataset import EVAL_LOOKBACK, HORIZONS, TEST_DAYS, build_rows, load_inputs, split
from src.features import FEATURES, build_features, load_neighbours
from src.panel import official_episodes
from src.targets import active_now, make_rows, y_active, y_start

N_ORIGINS = 40
UNKNOWN_END = pd.Timestamp("2100-01-01", tz="UTC")
HISTORY = pd.Timedelta(days=32)  # longest lookback: freq4w (28d + H), hours_since_end cap (30d)
NUMERIC = [f for f in FEATURES if f != "oblast"]


def known_at(official, t):
    """Alert rows as they looked at instant t. Rows that ended more than HISTORY before t cannot
    change any input at t, so they are skipped to keep this fast."""
    known = official[(official["start"] <= t) & (official["end"] > t - HISTORY)].copy()
    known.loc[known["end"] > t, "end"] = UNKNOWN_END
    return known


def same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return (np.isclose(a, b, rtol=0, atol=1e-9) | (np.isnan(a) & np.isnan(b)))


def main():
    official, raions = load_inputs()
    rows, episodes, raw, first, end = build_rows(official, raions)
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    oblasts = rows["oblast"].unique()
    neighbours = load_neighbours()
    feats = build_features(rows, episodes, raw, neighbours, HORIZONS, oblasts)
    key = pd.MultiIndex.from_frame(rows[["oblast", "t"]])

    # same origins as round 2: H=6 test rows under the 24h-lookback split, seed 0
    test_r2 = split(rows, first, end, test_start, 6, pd.Timedelta(hours=24))["test"]
    origins = rows.loc[test_r2, "t"].drop_duplicates().sample(N_ORIGINS, random_state=0).sort_values()
    print(f"origins: {N_ORIGINS} from {origins.min()} to {origins.max()}; "
          f"{(origins >= pd.Timestamp('2026-09-03', tz='UTC')).sum()} of them after the outage, where the "
          f"7-day features are computed over the observed part of their window")

    checked = mism_base = mism_feat = 0
    ctrl_target = ctrl_feature = ctrl_target_pos = 0
    for t in origins:
        ep_t, raw_t = official_episodes(known_at(official, t), raions=raions)
        at_t = rows[rows["t"] == t]
        yday = rows[rows["t"] == t - pd.Timedelta(hours=24)]
        mism_base += (~same(active_now(at_t, raw_t), at_t["now"])).sum()
        for H in HORIZONS:
            mism_base += (~same(y_active(yday, ep_t, H), yday[f"a_active_{H}"])).sum()
            mism_base += (~same(y_start(yday, ep_t, H), yday[f"b_start_{H}"])).sum()
        checked += len(at_t) * (1 + 2 * len(HORIZONS))

        grid = make_rows(oblasts, t - pd.Timedelta(days=29), t + pd.Timedelta(hours=1))
        f_t = build_features(grid, ep_t, raw_t, neighbours, HORIZONS, oblasts)
        grid_key = pd.MultiIndex.from_frame(grid[["oblast", "t"]])
        here = grid["t"] == t
        full_pos = key.get_indexer(grid_key[here])
        for H in HORIZONS:
            for f in NUMERIC:
                mism_feat += (~same(f_t[H].loc[here, f], feats[H][f].to_numpy()[full_pos])).sum()

        # negative control 1: the future target, (b) H=6 at t
        ctrl_target += (~same(y_start(at_t, ep_t, 6), at_t["b_start_6"])).sum()
        ctrl_target_pos += at_t["b_start_6"].sum()
        # negative control 2: share_6h one hour past t, i.e. a window that reaches beyond t
        later = grid["t"] == t + pd.Timedelta(hours=1)
        later_pos = key.get_indexer(grid_key[later])
        ctrl_feature += (~same(f_t[6].loc[later, "share_6h"], feats[6]["share_6h"].to_numpy()[later_pos])).sum()

    n_feat = N_ORIGINS * len(oblasts) * len(NUMERIC) * len(HORIZONS)
    print(f"baseline inputs from data known at t: {checked} values, mismatches {mism_base}")
    print(f"model features from data known at t: {n_feat} values "
          f"({len(NUMERIC)} features x {len(HORIZONS)} H x {len(oblasts)} oblasts x {N_ORIGINS} origins), "
          f"mismatches {mism_feat}")
    print(f"negative control, future target (b) H=6: {ctrl_target} mismatches "
          f"(true positives in full data: {ctrl_target_pos})")
    print(f"negative control, share_6h evaluated at t+1h: {ctrl_feature} mismatches of {N_ORIGINS * len(oblasts)}")

    for H in HORIZONS:
        m = split(rows, first, end, test_start, H, EVAL_LOOKBACK)
        h = pd.Timedelta(hours=H)
        week_start = test_start - pd.Timedelta(days=7)
        train_close = (rows.loc[m["train"], "t"] + h).max()
        val_close = (rows.loc[m["before_last_week"], "t"] + h).max()
        ok = train_close <= test_start and val_close <= week_start
        print(f"H={H}: training windows close by {train_close}, validation-fit windows by {val_close}: "
              f"{'ok' if ok else 'LEAK'}")
        assert ok
    assert mism_base == 0 and mism_feat == 0
    assert ctrl_target > 0 and ctrl_feature > 0


if __name__ == "__main__":
    main()
