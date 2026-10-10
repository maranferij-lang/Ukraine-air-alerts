"""Forecast rows and targets, computed exactly from episode start/end times.

A row is (oblast, t) where t is a forecast origin: an instant on the hour, UTC.
Episodes are [start, end) intervals, disjoint and sorted within an oblast (merge_episodes output).

  active_now(t)      some episode has start <= t < end              (known at t)
  y_active(t, H)     some episode overlaps (t, t+H]: start <= t+H and end > t
  y_start(t, H)      some episode starts in (t, t+H]: t < start <= t+H

Note y_active = active_now OR y_start: an alert running at t keeps running just after t, and if
nothing runs at t, anything overlapping (t, t+H] must start inside it.
"""
import numpy as np
import pandas as pd


def _per_oblast(episodes):
    out = {}
    for ob, g in episodes.sort_values(["oblast", "start"]).groupby("oblast"):
        out[ob] = (g["start"].dt.tz_convert(None).to_numpy("datetime64[ns]"),
                   g["end"].dt.tz_convert(None).to_numpy("datetime64[ns]"))
    return out


def _eval(rows, episodes, fn):
    """Apply fn(starts, ends, t) oblast by oblast; t is a numpy datetime64[ns] array."""
    result = np.zeros(len(rows), dtype=bool)
    eps = _per_oblast(episodes)
    t_all = rows["t"].dt.tz_convert(None).to_numpy("datetime64[ns]")
    for ob, idx in rows.groupby("oblast").indices.items():
        if ob in eps:
            result[idx] = fn(*eps[ob], t_all[idx])
    return result


def active_now(rows, episodes):
    def fn(starts, ends, t):
        k = np.searchsorted(starts, t, side="right") - 1  # last episode with start <= t
        return (k >= 0) & (ends[np.maximum(k, 0)] > t)
    return _eval(rows, episodes, fn)


def y_active(rows, episodes, H):
    h = np.timedelta64(H, "h")
    def fn(starts, ends, t):
        k = np.searchsorted(starts, t + h, side="right") - 1  # last episode with start <= t+H
        return (k >= 0) & (ends[np.maximum(k, 0)] > t)
    return _eval(rows, episodes, fn)


def y_start(rows, episodes, H):
    h = np.timedelta64(H, "h")
    def fn(starts, ends, t):
        return np.searchsorted(starts, t + h, side="right") > np.searchsorted(starts, t, side="right")
    return _eval(rows, episodes, fn)


def make_rows(oblasts, first, last):
    """Every (oblast, t) for hourly t in [first, last], sorted by oblast then t."""
    t = pd.date_range(first, last, freq="h")
    rows = pd.MultiIndex.from_product([sorted(oblasts), t], names=["oblast", "t"]).to_frame(index=False)
    return rows


def touches(rows, intervals, before, after):
    """True where [t - before, t + after] overlaps any [a, b) in intervals (UTC strings)."""
    hit = np.zeros(len(rows), dtype=bool)
    for a, b in intervals:
        a, b = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
        hit |= ((rows["t"] - before) < b).to_numpy() & ((rows["t"] + after) > a).to_numpy()
    return hit
