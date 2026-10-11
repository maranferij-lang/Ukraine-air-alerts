"""Per-oblast Telegram features from the Air Force channel (data/telegram/kpszsu_posts.csv).

Leakage rule: a post counts at origin t only if its post time is strictly before e = t - lag, with
lag = 0 ("posts published before t") or 15 minutes. Windows end at e and are half open [e - w, e).
The text of an edited post is the text at pull time (edits keep the original time), see the README.

  tg_m1h, tg_m3h   0/1: this oblast is mentioned in any post in the last 1h / 3h before e
  tg_share6h       share of ALL posts in the last 6h before e that mention this oblast (NaN if no post)
  tg_min_since     minutes from the oblast's latest mention before e to t, capped at 1440 (24h)
  tg_ballistic, tg_cruise, tg_drone
                   0/1, national: a post of that threat type in the last 3h before e. These say what
                   kind of night it is, not which oblast. No raw national counts are used.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .telegram_oblasts import mentioned

POSTS_CSV = Path(__file__).resolve().parents[1] / "data" / "telegram" / "kpszsu_posts.csv"
TG_FEATURES = ["tg_m1h", "tg_m3h", "tg_share6h", "tg_min_since", "tg_ballistic", "tg_cruise", "tg_drone"]
THREATS = {
    "tg_ballistic": re.compile(r"балісти|іскандер|кинджал|циркон"),
    "tg_cruise": re.compile(r"крилат|калібр|(?<!\w)х-?\d{2,3}(?!\w)|(?<!\w)ту-?\d{2,3}(?!\w)|стратегіч|ракетоносі"),
    "tg_drone": re.compile(r"бпла|(?<!\w)дрон|шахед|шахід|герань|реактивн"),
}
SUMMARY_LEN = 300  # month-end tallies ("знищено понад ...") are long; they are not threat reports
HOUR = np.int64(3600 * 10**9)
CAP_MIN = 1440.0


def load_posts(path=POSTS_CSV):
    """Posts with time (ns, UTC), the set of units mentioned and the threat flags."""
    df = pd.read_csv(path, keep_default_na=False)
    df["text"] = df["text"].astype(str)
    df["time"] = pd.to_datetime(df["time_utc"], utc=True, format="ISO8601")
    df = df.sort_values(["time", "id"], kind="stable").reset_index(drop=True)
    df["units"] = [mentioned(t) for t in df["text"]]
    low = df["text"].str.lower()
    report = df["text"].str.len() <= SUMMARY_LEN
    for name, rx in THREATS.items():
        df[name] = low.map(lambda t: bool(rx.search(t))) & report
    return df


def _ns(ts):
    return ts.dt.tz_convert(None).to_numpy("datetime64[ns]").astype(np.int64)


def _count(times, lo, hi):
    """Number of times in [lo, hi) (times sorted)."""
    return np.searchsorted(times, hi, side="left") - np.searchsorted(times, lo, side="left")


def tg_features(rows, posts, lag=pd.Timedelta(0)):
    """DataFrame of TG_FEATURES aligned with rows (columns oblast, t)."""
    p_time = _ns(posts["time"])
    by_unit = {u: p_time[posts["units"].map(lambda s, u=u: u in s).to_numpy()] for u in set().union(*posts["units"])}
    flag_times = {name: p_time[posts[name].to_numpy()] for name in THREATS}
    t_ns = _ns(rows["t"])
    e = t_ns - np.int64(lag.value)
    out = {c: np.full(len(rows), np.nan) for c in TG_FEATURES}
    empty = np.array([], dtype=np.int64)
    for unit, idx in rows.groupby("oblast").indices.items():
        times, ee = by_unit.get(unit, empty), e[idx]
        out["tg_m1h"][idx] = _count(times, ee - HOUR, ee) > 0
        out["tg_m3h"][idx] = _count(times, ee - 3 * HOUR, ee) > 0
        m6, n6 = _count(times, ee - 6 * HOUR, ee), _count(p_time, ee - 6 * HOUR, ee)
        out["tg_share6h"][idx] = np.where(n6 > 0, m6 / np.maximum(n6, 1), np.nan)
        i = np.searchsorted(times, ee, side="left") - 1
        last = times[np.maximum(i, 0)] if len(times) else np.zeros(len(idx), dtype=np.int64)
        minutes = np.where(i >= 0, (t_ns[idx] - last) / 60e9, CAP_MIN) if len(times) else np.full(len(idx), CAP_MIN)
        out["tg_min_since"][idx] = np.minimum(minutes, CAP_MIN)
    for name, times in flag_times.items():
        out[name] = (_count(times, e - 3 * HOUR, e) > 0).astype(float)
    return pd.DataFrame(out, index=rows.index)[TG_FEATURES]
