"""Candidate feature groups of round 22 (design and rules: PROCESS_LOG.md, Round 22 protocol). Nothing here is used by v1, v2 or `predict.py --now`.

Every feature uses only what is known at the origin t. Other oblasts are only looked at before t, never at the instant t (CLAUDE.md: neighbours = the last completed hour).
A "bin" is a 10-minute bin [T0 + 10k min, T0 + 10(k+1) min) on a grid anchored at an hour boundary, so every origin t is a bin boundary and "the last bin" is [t-10 min, t).
A unit "is in a bin" when one of its raw oblast episodes (before restarts are joined, as the state `now`) overlaps the bin.

A, finer timing (14):
  own_cover_10m, own_cover_30m, own_cover_1h   share of the last 1, 3, 6 bins the oblast is in
  raion_frac_now                               share of the oblast's raions under alert at the instant t (own state, like `now`)
  raion_frac_max_1h                            maximum of that share over the instants t-60, -50, ..., t minutes
  raion_starts_30m                             raion alerts that started in (t-30 min, t]
  nat_now                                      units in the last bin (all 24 units)
  nat_max_1h, nat_max_3h                       maximum of the per-bin unit count over the last 6 and 18 bins
  nat_starts_1h, nat_starts_3h                 oblast alert starts (joined episodes) in [t-1h, t) and [t-3h, t)
  up_any_30m, up_any_60m                       share of the upwind neighbours (east or south of the oblast, src/geo_centres.py) in at least one of the last 3 / 6 bins
  up_new_60m                                   number of upwind neighbours in the last 6 bins and in none of the 6 bins before
B, massive events (3): a massive moment is a bin with at least MASSIVE_UNITS units in it; a run that starts less than MASSIVE_GAP_BINS bins' time (3 h) after the
  previous run's last massive moment is the same event, so an event's start is known when it starts.
  hours_since_massive                          hours from the start of the last event that began before t (720 if none within 30 days)
  massive_14d                                  events that began in [t-14 d, t)
  massive_now                                  1 if the last bin is a massive moment
C, weather (4 or 6, from src/features_extra.weather_features): stamps up to and including t only. Visibility is used only if the download has values for it (the archive API returns all null).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .geo_centres import CENTRES, upwind_neighbours
from .panel import expand_to_raions, merge_episodes

BIN_NS = 10 * 60 * 10**9
HOUR_NS = 3600 * 10**9
BINS_PER_HOUR = 6
MASSIVE_UNITS = 15
MASSIVE_GAP_BINS = 18          # 3 hours
HOURS_CAP = 720.0
WEATHER_DIR = Path(__file__).resolve().parents[1] / "data" / "weather"

A_FEATURES = ["own_cover_10m", "own_cover_30m", "own_cover_1h", "raion_frac_now", "raion_frac_max_1h", "raion_starts_30m",
              "nat_now", "nat_max_1h", "nat_max_3h", "nat_starts_1h", "nat_starts_3h", "up_any_30m", "up_any_60m", "up_new_60m"]
A_OWN, A_NAT, A_WAVE = A_FEATURES[:6], A_FEATURES[6:11], A_FEATURES[11:]
B_FEATURES = ["hours_since_massive", "massive_14d", "massive_now"]
C_FEATURES = ["wind_t", "cloud_t", "precip_1h", "precip_3h", "vis_t", "vis_min_6h"]
WEATHER_VARS = ["wind_speed_10m", "cloud_cover", "precipitation", "visibility"]


def _ns(a):
    return a.astype("datetime64[ns]").astype(np.int64)


def raion_episodes(rows, raions):
    """Per-raion merged alert intervals (oblast, raion, start, end) from alert rows in the official schema (an oblast-wide row counts for every raion of the oblast)."""
    ra = expand_to_raions(rows, raions)
    per = merge_episodes(ra.assign(oblast=ra["oblast"] + "|" + ra["raion"]))
    per["raion"] = per["oblast"].str.split("|").str[1]
    per["oblast"] = per["oblast"].str.split("|").str[0]
    return per[per["end"] > per["start"]]


def _coverage(starts, ends, t0, n_bins):
    """Boolean per bin: some interval overlaps the bin. starts/ends int64 ns, disjoint or not."""
    first = np.clip((starts - t0) // BIN_NS, 0, n_bins)
    last = np.clip((ends - 1 - t0) // BIN_NS, -1, n_bins - 1)
    ok = (ends > starts) & (last >= first) & (last >= 0)
    diff = np.zeros(n_bins + 1, dtype=np.int64)
    np.add.at(diff, first[ok], 1)
    np.add.at(diff, last[ok] + 1, -1)
    return np.cumsum(diff[:-1]) > 0


def _rolling_max(a, k):
    """out[j] = max(a[j-k+1..j]) (the first k-1 values use what exists)."""
    return pd.Series(a).rolling(k, min_periods=1).max().to_numpy()


def massive_event_starts(nat, units=MASSIVE_UNITS, gap_bins=MASSIVE_GAP_BINS):
    """Start bins of massive events from the per-bin unit count (see the module docstring)."""
    moments = np.flatnonzero(nat >= units)
    if len(moments) == 0:
        return np.array([], dtype=np.int64)
    new = np.r_[True, np.diff(moments) - 1 >= gap_bins]
    return moments[new]


def build_extra(rows, episodes, raw, raion_eps, raions, neighbours, oblasts):
    """DataFrame aligned with `rows` (the hourly grid of build_features): A_FEATURES + B_FEATURES.
    episodes: joined oblast episodes; raw: oblast episodes before joining restarts; raion_eps: raion_episodes(...); raions: DataFrame oblast, raion."""
    groups = rows.groupby("oblast").indices
    t_all = _ns(rows["t"].dt.tz_convert(None).to_numpy("datetime64[ns]"))
    t_unique = t_all[next(iter(groups.values()))]
    t0 = t_unique[0] - 2 * 24 * HOUR_NS                       # room for the longest look-back before the first origin
    n_bins = int((t_unique[-1] - t0) // BIN_NS) + 1
    n_raions = raions.groupby("oblast").size()

    cov = {}
    for ob in oblasts:
        g = raw[raw["oblast"] == ob]
        cov[ob] = _coverage(_ns(g["start"].dt.tz_convert(None).to_numpy("datetime64[ns]")), _ns(g["end"].dt.tz_convert(None).to_numpy("datetime64[ns]")), t0, n_bins)
    nat = np.sum([cov[ob] for ob in oblasts], axis=0).astype(np.int64)
    nat_max_1h, nat_max_3h = _rolling_max(nat, BINS_PER_HOUR), _rolling_max(nat, 3 * BINS_PER_HOUR)
    cs = {ob: np.r_[0, np.cumsum(cov[ob])] for ob in oblasts}
    joined_starts_all = np.sort(_ns(episodes["start"].dt.tz_convert(None).to_numpy("datetime64[ns]")))
    ev = massive_event_starts(nat)

    up = upwind_neighbours({ob: [n for n in neighbours[ob] if n in cov] for ob in oblasts})
    cols = {name: np.full(len(rows), np.nan) for name in A_FEATURES + B_FEATURES}

    def window_any(ob, b, k, shift=0):
        """1 where the unit is in at least one of the k bins ending `shift` bins before b."""
        return ((cs[ob][b - shift] - cs[ob][b - shift - k]) > 0).astype(float)

    for ob, idx in groups.items():
        t = t_all[idx]
        b = ((t - t0) // BIN_NS).astype(np.int64)
        assert np.all(t0 + b * BIN_NS == t), "origins must sit on a bin boundary"
        c = cs[ob]
        cols["own_cover_10m"][idx] = (c[b] - c[b - 1]) / 1.0
        cols["own_cover_30m"][idx] = (c[b] - c[b - 3]) / 3.0
        cols["own_cover_1h"][idx] = (c[b] - c[b - 6]) / 6.0
        r = raion_eps[raion_eps["oblast"] == ob]
        rs, re_ = np.sort(_ns(r["start"].dt.tz_convert(None).to_numpy("datetime64[ns]"))), np.sort(_ns(r["end"].dt.tz_convert(None).to_numpy("datetime64[ns]")))
        n_r = float(n_raions.get(ob, 1))
        def active(x):
            return (np.searchsorted(rs, x, side="right") - np.searchsorted(re_, x, side="right")) / n_r
        cols["raion_frac_now"][idx] = active(t)
        cols["raion_frac_max_1h"][idx] = np.max([active(t - m * BIN_NS) for m in range(0, 7)], axis=0)
        cols["raion_starts_30m"][idx] = np.searchsorted(rs, t, side="right") - np.searchsorted(rs, t - 3 * BIN_NS, side="right")
        cols["nat_now"][idx] = nat[b - 1]
        cols["nat_max_1h"][idx] = nat_max_1h[b - 1]
        cols["nat_max_3h"][idx] = nat_max_3h[b - 1]
        cols["nat_starts_1h"][idx] = np.searchsorted(joined_starts_all, t, side="left") - np.searchsorted(joined_starts_all, t - HOUR_NS, side="left")
        cols["nat_starts_3h"][idx] = np.searchsorted(joined_starts_all, t, side="left") - np.searchsorted(joined_starts_all, t - 3 * HOUR_NS, side="left")
        if up[ob]:
            cols["up_any_30m"][idx] = np.mean([window_any(u, b, 3) for u in up[ob]], axis=0)
            cols["up_any_60m"][idx] = np.mean([window_any(u, b, 6) for u in up[ob]], axis=0)
            cols["up_new_60m"][idx] = np.sum([window_any(u, b, 6) * (1 - window_any(u, b, 6, shift=6)) for u in up[ob]], axis=0)
        j = np.searchsorted(ev, b, side="left") - 1                                 # last event that began before t
        since = np.where(j >= 0, (b - (ev[np.maximum(j, 0)] if len(ev) else 0)) / BINS_PER_HOUR, np.inf)
        cols["hours_since_massive"][idx] = np.minimum(since, HOURS_CAP)
        cols["massive_14d"][idx] = np.searchsorted(ev, b, side="left") - np.searchsorted(ev, b - 14 * 24 * BINS_PER_HOUR, side="left")
        cols["massive_now"][idx] = (nat[b - 1] >= MASSIVE_UNITS).astype(float)
    return pd.DataFrame(cols, index=rows.index)[A_FEATURES + B_FEATURES]


def load_weather(directory=WEATHER_DIR):
    """{oblast: DataFrame indexed by UTC hour with the WEATHER_VARS that exist}, or None if the download is not there or not complete (all 24 units)."""
    files = sorted(Path(directory).glob("*.csv"))
    if len(files) < len(CENTRES):
        return None
    out = {}
    for f in files:
        d = pd.read_csv(f, parse_dates=["time"]).set_index("time")
        d.index = d.index.tz_localize("UTC") if d.index.tz is None else d.index
        out[f.stem.replace("_", " ")] = d
    return out


def weather_features(rows, weather):
    """C_FEATURES aligned with `rows`, from stamps at or before the origin. Features of a variable the download does not have stay NaN-free by being absent (columns are dropped)."""
    cols = {}
    for ob, idx in rows.groupby("oblast").indices.items():
        w = weather[ob]
        t = pd.DatetimeIndex(rows["t"].to_numpy()[idx])
        r = w.reindex(t)
        def roll(col, fn, n):
            s = w[col].rolling(n, min_periods=n)
            return getattr(s, fn)().reindex(t).to_numpy()
        part = {"wind_t": r["wind_speed_10m"].to_numpy(), "cloud_t": r["cloud_cover"].to_numpy(), "precip_1h": r["precipitation"].to_numpy(),
                "precip_3h": roll("precipitation", "sum", 3)}
        if "visibility" in w.columns and w["visibility"].notna().any():          # the archive API accepts the variable but delivers nothing (all null): then it is not used
            part["vis_t"] = r["visibility"].to_numpy()
            part["vis_min_6h"] = roll("visibility", "min", 6)
        for k, v in part.items():
            cols.setdefault(k, np.full(len(rows), np.nan))[idx] = v
    return pd.DataFrame(cols, index=rows.index)
