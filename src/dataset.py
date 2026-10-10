"""Forecast rows, targets and the chronological split, shared by the evaluation scripts."""
import pandas as pd

from .load import OFFICIAL_OUTAGES, PERMANENT_ALERT_OBLASTS, data_end, load_official
from .panel import official_episodes, raion_list
from .targets import active_now, make_rows, touches, y_active, y_start

HORIZONS = [1, 3, 6]
TEST_DAYS = 30       # test = last 30 full days of official data
THRESHOLD_DAYS = 7   # thresholds (and early stopping) are chosen on the last week of train


def load_inputs():
    """Cleaned official rows without permanent-alert oblasts, and the fixed raion list."""
    official = load_official()
    official = official[~official["oblast"].isin(PERMANENT_ALERT_OBLASTS)]
    return official, raion_list(official)


def build_rows(official=None, raions=None):
    """Complete hourly grid of (oblast, t) with "now" and both targets for every H.

    "now" comes from raw episodes (before joining restarts): at t nobody knows yet whether a
    restart will follow. Targets come from the joined episodes.
    """
    if official is None:
        official, raions = load_inputs()
    episodes, raw = official_episodes(official, raions=raions)
    first = official["start"].min().ceil("D")
    end = data_end(official)
    rows = make_rows(official["oblast"].unique(), first, end - pd.Timedelta(hours=1))
    rows["now"] = active_now(rows, raw)
    for H in HORIZONS:
        rows[f"a_active_{H}"] = y_active(rows, episodes, H)
        rows[f"b_start_{H}"] = y_start(rows, episodes, H)
    return rows, episodes, raw, first, end


def split(rows, first, end, test_start, H, lookback):
    """Boolean masks for horizon H.

    usable:           lookback [t - lookback, t] and target window (t, t+H] inside the data and
                      away from known outages
    test:             usable, t >= test_start
    train:            usable, target window closes by test_start
    last_week:        the last THRESHOLD_DAYS of train (thresholds, early stopping)
    before_last_week: train whose target window closes before last_week starts (validation fit)
    """
    h = pd.Timedelta(hours=H)
    week_start = test_start - pd.Timedelta(days=THRESHOLD_DAYS)
    usable = ((rows["t"] - lookback >= first) & (rows["t"] + h <= end)
              & ~touches(rows, OFFICIAL_OUTAGES, before=lookback, after=h))
    test = usable & (rows["t"] >= test_start)
    train = usable & (rows["t"] + h <= test_start)
    last_week = train & (rows["t"] >= week_start)
    before_last_week = train & (rows["t"] + h <= week_start)
    return {"test": test, "train": train, "last_week": last_week, "before_last_week": before_last_week}
