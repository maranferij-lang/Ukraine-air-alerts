"""Leakage check for the two news columns (src/news.py), same 40 test origins as check_no_peeking.py.

For each origin t, keep only the GDELT hourly buckets whose records were all added before t-1h (the
leakage rule), recompute news_24h and news_yesterday twice, with src/news.py and with a direct sum
over the kept buckets, and require exact equality with the full-data columns the model uses. Also
checks the columns are the same for every oblast at a given t (national).
Negative control: the 24h window ending at t instead of t-1h (one hour too late), by direct sum on
the kept buckets vs on the full data. It must disagree wherever the hour [t-1h, t) had events.

    python scripts/check_no_peeking_news.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.check_no_peeking import N_ORIGINS, same
from src.dataset import TEST_DAYS, build_rows, split
from src.news import LAG, NEWS_FEATURES, load_news, news_features


def direct(kept, lo, hi):
    """Conflict events in buckets [lo, hi) among the kept buckets."""
    s = kept["events_conflict"]
    return float(s[(s.index >= lo) & (s.index < hi)].sum())


def main():
    rows, _, _, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    hourly = load_news()
    full = news_features(rows["t"], hourly)
    per_t = full.assign(t=rows["t"]).groupby("t")[NEWS_FEATURES].nunique(dropna=False)
    assert (per_t <= 1).all().all(), "news columns differ between oblasts at the same t"

    test_r2 = split(rows, first, end, test_start, 6, pd.Timedelta(hours=24))["test"]
    origins = rows.loc[test_r2, "t"].drop_duplicates().sample(N_ORIGINS, random_state=0).sort_values()
    mism = mism_direct = ctrl = ctrl_possible = 0
    for t in origins:
        cutoff = t - LAG
        kept = hourly[hourly.index + pd.Timedelta(hours=1) <= cutoff]   # every record added before t-1h
        model_cols = full[rows["t"] == t].iloc[0]
        trunc = news_features(pd.Series([t]), kept).iloc[0]
        mism += int((~same(trunc[NEWS_FEATURES], model_cols[NEWS_FEATURES])).sum())
        day_end = cutoff.floor("D")
        by_hand = [direct(kept, cutoff - pd.Timedelta(hours=24), cutoff),
                   direct(kept, day_end - pd.Timedelta(days=1), day_end)]
        mism_direct += int((~same(by_hand, model_cols[NEWS_FEATURES])).sum())
        # negative control: window [t-24h, t), one hour past the rule
        ctrl += int(direct(kept, t - pd.Timedelta(hours=24), t) != direct(hourly, t - pd.Timedelta(hours=24), t))
        ctrl_possible += int(hourly.loc[cutoff, "events_conflict"] > 0)
    n = N_ORIGINS * len(NEWS_FEATURES)
    print(f"origins: {N_ORIGINS} from {origins.min()} to {origins.max()} (same as check_no_peeking.py)")
    print(f"news columns from GDELT records added before t-1h, src/news.py: {n} values, mismatches {mism}")
    print(f"news columns from GDELT records added before t-1h, direct sum: {n} values, mismatches {mism_direct}")
    print(f"news columns identical across oblasts at every t: yes ({len(per_t)} hours)")
    print(f"negative control, 24h window ending at t: {ctrl} mismatches of {N_ORIGINS} origins "
          f"({ctrl_possible} origins had events in [t-1h, t))")
    assert mism == 0 and mism_direct == 0
    assert ctrl > 0 and ctrl == ctrl_possible


if __name__ == "__main__":
    main()
