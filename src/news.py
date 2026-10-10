"""National news-intensity features from GDELT (data/news/gdelt_events_ukraine_hourly.csv).

Leakage rule: a GDELT record is known at origin t only if it was added to GDELT (DATEADDED) before
t-1h, the same one-hour lag as the neighbour features. The event date is never used. Hourly bucket h
holds the records added in [h, h+1h).
  news_24h        conflict events (CAMEO root 18/19/20) located in Ukraine, added in [t-25h, t-1h)
  news_yesterday  the same events added during the last full UTC day that ended by t-1h
NaN where the window starts before the pulled range (the first day of 2026).
"""
from pathlib import Path

import numpy as np
import pandas as pd

NEWS_CSV = Path(__file__).resolve().parents[1] / "data" / "news" / "gdelt_events_ukraine_hourly.csv"
NEWS_FEATURES = ["news_24h", "news_yesterday"]
LAG = pd.Timedelta(hours=1)


def load_news(path=NEWS_CSV):
    """Hourly counts indexed by the UTC hour bucket; checks the grid is complete."""
    g = pd.read_csv(path)
    g["hour"] = pd.to_datetime(g["hour"], utc=True)
    g = g.set_index("hour")
    assert (g.index[1:] - g.index[:-1] == pd.Timedelta(hours=1)).all(), "hourly grid must have no gaps"
    return g


def added_before(hourly, x, col="events_conflict"):
    """Records added before instant x (on the hour), counted from the start of the pulled range."""
    s = hourly[col]
    bounds = s.index.append(pd.DatetimeIndex([s.index[-1] + pd.Timedelta(hours=1)]))
    cum = pd.Series(np.concatenate([[0], s.cumsum().to_numpy()]), index=bounds, dtype=float)
    return cum.reindex(pd.DatetimeIndex(x)).to_numpy()


def news_features(t, hourly):
    """DataFrame of NEWS_FEATURES for origins t (Series of UTC timestamps on the hour)."""
    cutoff = t - LAG
    day_end = cutoff.dt.floor("D")  # the last full UTC day before the cutoff ends here
    return pd.DataFrame({
        "news_24h": added_before(hourly, cutoff) - added_before(hourly, cutoff - pd.Timedelta(hours=24)),
        "news_yesterday": added_before(hourly, day_end) - added_before(hourly, day_end - pd.Timedelta(days=1)),
    }, index=t.index)
