"""Replay test for the live forecast (offline): a forecast made "as of" a past moment, from an archive cut to what the API would have said then,
must give exactly the features and probabilities the forward test has for that hour.

    python scripts/check_live_replay.py

As of 2026-10-10 12:00 UTC (and as of 12:37, which must give the same answer: the origin is the last completed hour and everything is cut at it).
The archive is cut by scripts/live_api.as_of: only alerts that had started, and every alert that ended later has no end (isContinue true, end year 0001),
only the days the live path would read. The reference is the forward test's full-data features (scripts/forward_test.build_api). Two negative controls:
dropping the running alerts, and cutting the archive an hour late.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts.check_no_peeking import same
from scripts.forward_test import build_api, load_frozen
from scripts.live_api import (as_of, features_at, inputs, live_rows, needed_days, origin_for, probabilities, read_days)
from src.dataset import HORIZONS
from src.features import FEATURES

MOMENTS = [pd.Timestamp("2026-10-10 12:00", tz="UTC"), pd.Timestamp("2026-10-10 12:37", tz="UTC")]


def compare(label, got_rows, got_feats, got_p, ref_rows, ref_feats, ref_p, t):
    num = [f for f in FEATURES if f != "oblast"]
    mism_f = mism_p = total = 0
    for H in HORIZONS:
        for f in num:
            mism_f += int((~same(got_feats[H][f], ref_feats[H][f])).sum())
            total += len(got_rows)
        mism_p += int((~np.isclose(got_p[H], ref_p[H], rtol=0, atol=1e-12)).sum())
    print(f"{label}: {total} feature values compared, mismatches {mism_f}; {3 * len(got_rows)} probabilities, mismatches {mism_p}")
    return mism_f, mism_p


def main():
    raions, oblasts = inputs()
    info, frozen, boosters, freq = load_frozen()
    rows, episodes, raw, feats, api_rows_full, _, _, files = build_api([])
    ok = True
    for moment in MOMENTS:
        t = origin_for(moment)
        sel = (rows["t"] == t).to_numpy()
        ref_rows = rows[sel].reset_index(drop=True)
        ref_feats = {H: feats[H][sel].reset_index(drop=True) for H in HORIZONS}
        ref_p = probabilities(ref_feats, boosters)
        items, missing = read_days(needed_days(t))
        assert not missing, f"the archive lacks days {missing}"
        cut = as_of(items, moment)
        n_open = sum(1 for a in cut if a["isContinue"])
        api_rows, n, _ = live_rows(cut, raions, oblasts)
        got_rows, got_feats = features_at(api_rows, raions, oblasts, t)
        got_p = probabilities(got_feats, boosters)
        assert list(got_rows["oblast"]) == list(ref_rows["oblast"])
        print(f"\nas of {moment:%Y-%m-%d %H:%M} UTC, origin {t:%Y-%m-%d %H:%M}: {len(items)} items read from {len(needed_days(t))} day files, {len(cut)} after the cut "
              f"({n_open} running, no end); oblasts under alert at the origin: {int(ref_feats[1]['now'].sum())} of {len(oblasts)}")
        a, b = compare("  live path vs forward test", got_rows, got_feats, got_p, ref_rows, ref_feats, ref_p, t)
        ok &= (a == 0 and b == 0)

        # control 1: running alerts dropped (what the old loader did)
        api_drop, _, _ = live_rows(cut, raions, oblasts, keep_open=False)
        _, f_drop = features_at(api_drop, raions, oblasts, t)
        p_drop = probabilities(f_drop, boosters)
        ca, cb = compare("  control, running alerts dropped (must differ)", got_rows, f_drop, p_drop, ref_rows, ref_feats, ref_p, t)
        assert ca > 0, "the control did not change anything: the test cannot see the open-alert handling"
        # control 2: data from an hour later (alerts that started in (t, t+1h] included, and no cut at t): must differ if the cut matters
        later = as_of(items, t + pd.Timedelta(hours=1))
        api_later, _, _ = live_rows(later, raions, oblasts)
        ep_rows = api_later  # same rows, but features read as of t+1h
        _, f_later = features_at(ep_rows, raions, oblasts, t + pd.Timedelta(hours=1))
        ca, cb = compare("  control, features at the next hour (must differ)", got_rows, f_later, probabilities(f_later, boosters), ref_rows, ref_feats, ref_p, t)
        assert ca > 0
    print("\nreplay test:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
