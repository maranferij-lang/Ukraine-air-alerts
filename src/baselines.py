"""The three dumb baselines. Each returns a score per row (higher = more likely an alert).

rows must be a complete hourly grid per oblast (output of targets.make_rows, before any
filtering), with columns oblast, t, now and the target column.
"""
import pandas as pd

KYIV = "Europe/Kyiv"


def persistence(rows):
    """Same as now: 1 if an alert is active at t (0/1 score, same for every target and H)."""
    return rows["now"].astype(float)


def same_hour_yesterday(rows, target):
    """The target's own outcome for the origin 24h earlier, i.e. the window (t-24h, t-24h+H].
    That window closed at t-24h+H <= t-18h, so it is known at t. NaN for the first 24h."""
    return rows.groupby("oblast")[target].shift(24).astype(float)


def local_hour_weekday(t):
    local = t.dt.tz_convert(KYIV)
    return local.dt.hour, local.dt.dayofweek


def frequency_table(train_rows, target):
    """Share of training rows with target = 1, by oblast x Kyiv-local hour x weekday."""
    hour, weekday = local_hour_weekday(train_rows["t"])
    return train_rows.groupby([train_rows["oblast"], hour.rename("hour"), weekday.rename("weekday")])[target].mean()


def train_frequency(rows, table):
    hour, weekday = local_hour_weekday(rows["t"])
    keys = pd.MultiIndex.from_arrays([rows["oblast"], hour, weekday])
    return pd.Series(table.reindex(keys).to_numpy(), index=rows.index)
