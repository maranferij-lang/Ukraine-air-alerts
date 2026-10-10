"""Leakage check for the baselines: recompute their inputs from data truncated at t.

For random test origins t: drop every alert row that starts after t, and mark every end after t
as unknown (far future). Rebuild the episodes from that and recompute "now" and the
same-hour-yesterday outcomes. They must equal what the full-data pipeline produced.
Also checks that the frequency table only uses rows whose target window closed before the test month.

    python scripts/check_no_peeking.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import pandas as pd

from evaluate_baselines import HORIZONS, TEST_DAYS, build_rows, split
from src.load import PERMANENT_ALERT_OBLASTS, load_official
from src.panel import official_episodes, raion_list
from src.targets import active_now, y_active, y_start

N_ORIGINS = 40
UNKNOWN_END = pd.Timestamp("2100-01-01", tz="UTC")


def known_at(official, t):
    """Alert rows as they looked at instant t. Rows that ended long before t cannot change
    anything from t-24h on, so they are skipped to keep this fast."""
    known = official[(official["start"] <= t) & (official["end"] > t - pd.Timedelta(hours=26))].copy()
    known.loc[known["end"] > t, "end"] = UNKNOWN_END
    return known


def main():
    rows, episodes, raw, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    official = load_official()
    official = official[~official["oblast"].isin(PERMANENT_ALERT_OBLASTS)]
    raions = raion_list(official)  # fixed administrative list

    test_any, *_ = split(rows, first, end, test_start, max(HORIZONS))
    origins = rows.loc[test_any, "t"].drop_duplicates().sample(N_ORIGINS, random_state=0).sort_values()
    mismatches = 0
    for t in origins:
        ep_t, raw_t = official_episodes(known_at(official, t), raions=raions)
        now_rows = rows[rows["t"] == t]
        mismatches += (active_now(now_rows, raw_t) != now_rows["now"].to_numpy()).sum()
        yday_rows = rows[rows["t"] == t - pd.Timedelta(hours=24)]
        for H in HORIZONS:
            mismatches += (y_active(yday_rows, ep_t, H) != yday_rows[f"a_active_{H}"].to_numpy()).sum()
            mismatches += (y_start(yday_rows, ep_t, H) != yday_rows[f"b_start_{H}"].to_numpy()).sum()
    n_checked = N_ORIGINS * rows["oblast"].nunique() * (1 + 2 * len(HORIZONS))
    print(f"persistence + yesterday inputs recomputed from data known at t: {n_checked} values at "
          f"{N_ORIGINS} test origins, mismatches: {mismatches}")

    for H in HORIZONS:
        _, train, last_week = split(rows, first, end, test_start, H)
        latest = (rows.loc[train, "t"] + pd.Timedelta(hours=H)).max()
        print(f"H={H}: latest training target window closes {latest}, test starts {test_start}: "
              f"{'ok' if latest <= test_start else 'LEAK'}")
    assert mismatches == 0


if __name__ == "__main__":
    main()
