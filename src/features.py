"""Model features for forecast origin t. Every feature uses only what is known at t.

Own oblast. State and coverage come from raw episodes (before restarts are joined), because at t
nobody knows yet whether a restart will follow. Start counts use joined episodes; whether a start
joins the previous alert is decided at the start itself, so starts up to t are known.
  now               alert active at t
  hours_since_start hours since the current alert started (0 if quiet)
  hours_since_end   hours since the last alert ended (capped at 720 = 30 days)
  share_6h/24h/7d   share of time under alert in [t-w, t]
  starts_24h/7d     alert starts in (t-w, t]
  Windows that overlap a known outage (OFFICIAL_OUTAGES) are computed over the observed part
  only: shares over the observed time, counts scaled up to the full window length.
Neighbours, last completed hour only ("lagged one hour"):
  nb_share_1h       share of neighbouring oblasts under alert at some point in [t-1h, t)
  nb_starts_6h      alert starts in neighbouring oblasts in [t-6h, t)
Calendar: hour, weekday (Europe/Kyiv).
Recent rate:
  freq4w            target (b) for the same H at the same oblast and hour 1, 2, 3 and 4 weeks
                    earlier, averaged (windows that touch a known outage are skipped).
                    Those windows closed by t-7d+H, so they are known at t.
Oblast: categorical.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .baselines import local_hour_weekday
from .load import OFFICIAL_OUTAGES
from .targets import _per_oblast, touches, y_start

NEIGHBOURS_CSV = Path(__file__).resolve().parents[1] / "data" / "neighbours.csv"
HOURS_SINCE_CAP = 720.0
NS_PER_HOUR = 3600 * 10**9
MASKS = [(pd.Timestamp(a, tz="UTC").value, pd.Timestamp(b, tz="UTC").value) for a, b in OFFICIAL_OUTAGES]


def load_neighbours(path=NEIGHBOURS_CSV):
    """Hand-written oblast adjacency (land borders), one row per pair, both directions."""
    pairs = pd.read_csv(path)
    both = pd.concat([pairs, pairs.rename(columns={"oblast": "neighbour", "neighbour": "oblast"})])
    return both.drop_duplicates().groupby("oblast")["neighbour"].apply(sorted).to_dict()


def _ns(a):
    return a.astype("datetime64[ns]").astype(np.int64)


def _own(starts, ends, joined_starts, t):
    """Own-oblast features for one oblast; all inputs int64 ns, t sorted or not."""
    out = {}
    k = np.searchsorted(starts, t, side="right") - 1          # last raw start <= t
    kk = np.maximum(k, 0)
    running = (k >= 0) & (ends[kk] > t)
    out["now"] = running.astype(float)
    out["hours_since_start"] = np.where(running, (t - starts[kk]) / NS_PER_HOUR, 0.0)
    j = np.searchsorted(ends, t, side="right") - 1            # last raw end <= t
    since_end = np.where(j >= 0, (t - ends[np.maximum(j, 0)]) / NS_PER_HOUR, np.inf)
    out["hours_since_end"] = np.minimum(since_end, HOURS_SINCE_CAP)

    cum = np.concatenate([[0], np.cumsum(ends - starts)])   # covered time before episode i
    def covered_until(x):
        i = np.searchsorted(starts, x, side="right") - 1
        ii = np.maximum(i, 0)
        partial = np.where(i >= 0, np.minimum(x, ends[ii]) - starts[ii], 0)
        return cum[ii] * (i >= 0) + partial
    def n_starts(lo, hi):  # joined starts in (lo, hi]
        return (np.searchsorted(joined_starts, hi, side="right")
                - np.searchsorted(joined_starts, lo, side="right"))

    for hours in [6, 24, 168]:
        w = hours * NS_PER_HOUR
        masked, covered_masked, starts_masked = np.zeros_like(t), np.zeros_like(t), np.zeros_like(t)
        for m0, m1 in MASKS:  # the part of [t-w, t] inside each outage
            lo, hi = np.maximum(t - w, m0), np.minimum(t, m1)
            inside = hi > lo
            hi = np.where(inside, hi, lo)
            masked = masked + (hi - lo)
            covered_masked = covered_masked + (covered_until(hi) - covered_until(lo))
            starts_masked = starts_masked + n_starts(lo, hi)
        observed = (w - masked).astype(float)
        observed[observed <= 0] = np.nan
        suffix = "7d" if hours == 168 else f"{hours}h"
        out[f"share_{suffix}"] = (covered_until(t) - covered_until(t - w) - covered_masked) / observed
        if hours != 6:
            out[f"starts_{suffix}"] = (n_starts(t - w, t) - starts_masked) * (w / observed)
    return out


def _neighbour_inputs(starts, ends, joined_starts, t):
    k = np.searchsorted(starts, t, side="left") - 1           # last raw start < t
    alert_last_hour = (k >= 0) & (ends[np.maximum(k, 0)] > t - NS_PER_HOUR)
    starts_6h = (np.searchsorted(joined_starts, t, side="left")
                 - np.searchsorted(joined_starts, t - 6 * NS_PER_HOUR, side="left"))
    return alert_last_hour.astype(float), starts_6h.astype(float)


def build_features(rows, episodes, raw, neighbours, horizons, oblasts):
    """rows: complete hourly grid per oblast with the same t values for every oblast, sorted by
    oblast then t (targets.make_rows). Returns {H: DataFrame aligned with rows}; the frames
    differ only in freq4w."""
    groups = rows.groupby("oblast").indices
    t_all = _ns(rows["t"].dt.tz_convert(None).to_numpy("datetime64[ns]"))
    grids = [t_all[idx] for idx in groups.values()]
    assert all(np.array_equal(g, grids[0]) for g in grids), "rows must be the same t grid per oblast"
    assert np.all(np.diff(grids[0]) == NS_PER_HOUR), "rows must be hourly with no gaps"

    raw_eps = {ob: tuple(map(_ns, se)) for ob, se in _per_oblast(raw).items()}
    joined = {ob: _ns(se[0]) for ob, se in _per_oblast(episodes).items()}
    empty = np.array([], dtype=np.int64)

    cols = {}
    nb_alert, nb_starts = {}, {}
    for ob, idx in groups.items():
        s, e = raw_eps.get(ob, (empty, empty))
        js = joined.get(ob, empty)
        for name, values in _own(s, e, js, t_all[idx]).items():
            cols.setdefault(name, np.full(len(rows), np.nan))[idx] = values
        nb_alert[ob], nb_starts[ob] = _neighbour_inputs(s, e, js, t_all[idx])
    cols["nb_share_1h"] = np.full(len(rows), np.nan)
    cols["nb_starts_6h"] = np.full(len(rows), np.nan)
    for ob, idx in groups.items():
        nbs = [n for n in neighbours[ob] if n in nb_alert]
        cols["nb_share_1h"][idx] = np.mean([nb_alert[n] for n in nbs], axis=0)
        cols["nb_starts_6h"][idx] = np.sum([nb_starts[n] for n in nbs], axis=0)

    base = pd.DataFrame(cols, index=rows.index)
    hour, weekday = local_hour_weekday(rows["t"])
    base["hour"] = hour.to_numpy()
    base["weekday"] = weekday.to_numpy()
    base["oblast"] = pd.Categorical(rows["oblast"], categories=sorted(oblasts))

    out = {}
    for H in horizons:
        target = pd.Series(y_start(rows, episodes, H), index=rows.index, dtype=float)
        target[touches(rows, OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=pd.Timedelta(hours=H))] = np.nan
        by_oblast = target.groupby(rows["oblast"])
        lagged = pd.concat([by_oblast.shift(168 * k) for k in range(1, 5)], axis=1)
        f = base.copy()
        f["freq4w"] = lagged.mean(axis=1, skipna=True)
        out[H] = f[FEATURES]
    return out


FEATURES = ["now", "hours_since_start", "hours_since_end", "share_6h", "share_24h", "share_7d",
            "starts_24h", "starts_7d", "nb_share_1h", "nb_starts_6h", "hour", "weekday", "freq4w",
            "oblast"]
