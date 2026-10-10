"""Alert intervals -> one row per oblast per UTC hour.

Steps:
  1. expand_to_raions: official rows -> raion-level alerts (an oblast-wide alert counts
     for every raion of the oblast; hromada-only alerts are dropped).
  2. oblast_episodes: oblast "under alert" while at least min_share of its raions are.
  3. hourly_panel: lay episodes onto an hourly grid. Hour h is the bucket [h, h+1h).
merge_episodes is the generic "union of overlapping intervals per unit" used throughout.
official_episodes chains steps 1-2 and joins restarts within RESTART_GAP (re-issued messages).
"""
import numpy as np
import pandas as pd

HOUR = pd.Timedelta(hours=1)
# a new oblast episode starting within this long after the previous one ended is the same
# alert re-issued, not a new alert (decision 2026-10-10, round 2)
RESTART_GAP = pd.Timedelta(minutes=5)


def official_episodes(official, min_share=0.5, restart_gap=RESTART_GAP, raions=None):
    """Oblast episodes from cleaned official rows (permanent-alert oblasts already removed).

    Returns (episodes, raw_episodes): raw_episodes are before joining restarts. Use raw ones
    for "what is the state at t" (at t nobody knows yet whether a restart will follow) and
    the joined ones for targets.
    """
    if raions is None:
        raions = raion_list(official)
    n_raions = raions.groupby("oblast")["raion"].size()
    raw = oblast_episodes(expand_to_raions(official, raions), min_share, n_raions)
    return merge_episodes(raw, max_gap=restart_gap), raw


def raion_list(official):
    """Raions of each oblast: every raion name seen in a raion-level row. These are the 2020
    administrative raions, i.e. a fixed list known in advance, not something learnt from data."""
    raion_rows = official[official["level"] == "raion"]
    return raion_rows.groupby("oblast")["raion"].unique().explode().reset_index()


def expand_to_raions(official, raions=None):
    """Official alerts as one row per raion.

    raions: DataFrame oblast, raion (default: raion_list(official)).
    Kyiv City never has raion-level rows, so it is its own single "raion".
    """
    raion_rows = official[official["level"] == "raion"]
    if raions is None:
        raions = raion_list(official)
    oblast_rows = official[official["level"] == "oblast"].drop(columns="raion")
    oblast_rows = oblast_rows.merge(raions, on="oblast", how="left")
    oblast_rows["raion"] = oblast_rows["raion"].fillna(oblast_rows["oblast"])
    return pd.concat([raion_rows, oblast_rows])[["oblast", "raion", "start", "end"]]


def oblast_episodes(raion_alerts, min_share=0.5, n_raions=None):
    """Intervals during which at least min_share of an oblast's raions are under alert.

    min_share=0 means "any raion"; 0.5 means "at least half"; 1 means "all raions".
    n_raions: Series oblast -> number of raions (default: raions seen in raion_alerts;
    oblasts missing from it, i.e. Kyiv City, count as 1).
    Works by sweeping over raion episode starts (+1) and ends (-1) in time order.
    """
    if n_raions is None:
        n_raions = raion_alerts.groupby("oblast")["raion"].nunique()
    per_raion = merge_episodes(raion_alerts.assign(oblast=raion_alerts["oblast"] + "|" + raion_alerts["raion"]))
    per_raion["oblast"] = per_raion["oblast"].str.split("|").str[0]
    per_raion = per_raion[per_raion["end"] > per_raion["start"]]

    events = pd.concat([
        per_raion[["oblast", "start"]].rename(columns={"start": "t"}).assign(step=1),
        per_raion[["oblast", "end"]].rename(columns={"end": "t"}).assign(step=-1),
    ])
    events = events.sort_values(["oblast", "t", "step"]).reset_index(drop=True)  # ends first at ties
    n_active = events.groupby("oblast")["step"].cumsum()
    needed = np.maximum(1, np.ceil(min_share * events["oblast"].map(n_raions).fillna(1) - 1e-9))
    on = n_active >= needed
    was_on = on.groupby(events["oblast"]).shift(fill_value=False)

    starts = events.loc[on & ~was_on, ["oblast", "t"]].reset_index(drop=True)
    ends = events.loc[~on & was_on, "t"].reset_index(drop=True)
    out = pd.DataFrame({"oblast": starts["oblast"], "start": starts["t"], "end": ends})
    return merge_episodes(out[out["end"] > out["start"]])


def merge_episodes(alerts, max_gap=pd.Timedelta(0)):
    """Union of alert intervals per oblast.

    alerts: DataFrame with columns oblast, start, end.
    max_gap: intervals separated by a gap <= max_gap are joined into one episode.
             With the default 0, intervals that overlap or touch are joined.
    Returns DataFrame oblast, start, end, n_rows (alert rows merged into the episode).
    """
    df = alerts[["oblast", "start", "end"]].sort_values(["oblast", "start"])
    if df.empty:
        return df.assign(n_rows=0).reset_index(drop=True)
    # running max of end within oblast; a new episode starts when start > previous max end + gap
    prev_end = df.groupby("oblast")["end"].transform(lambda s: s.cummax().shift())
    new_episode = prev_end.isna() | (df["start"] > prev_end + max_gap)
    episode_id = new_episode.cumsum()
    out = df.groupby(episode_id).agg(
        oblast=("oblast", "first"),
        start=("start", "min"),
        end=("end", "max"),
        n_rows=("start", "size"),
    )
    return out.reset_index(drop=True)


def hourly_panel(episodes, start, end, oblasts=None):
    """One row per oblast per hour in [start, end).

    Columns:
      active          alert active at any moment inside [h, h+1)
      active_at_start alert already running at the instant h (started strictly before h);
                      this is the "same as now" state for a forecast made at h
      minutes_active  minutes of [h, h+1) covered by an alert (0..60)
      n_starts        episodes whose start falls in [h, h+1)
    episodes must be disjoint within an oblast (output of merge_episodes).
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if oblasts is None:
        oblasts = sorted(episodes["oblast"].unique())
    hours = pd.date_range(start, end, freq="h", inclusive="left")
    grid = pd.MultiIndex.from_product([oblasts, hours], names=["oblast", "hour"])

    ep = episodes[(episodes["end"] > start) & (episodes["start"] < end) & episodes["oblast"].isin(oblasts)]
    ep = ep[ep["end"] > ep["start"]]  # zero-length alerts never cover any time

    # expand each episode into the hour buckets it touches
    first_h = ep["start"].dt.floor("h").clip(lower=start)
    last_h = (ep["end"] - pd.Timedelta(microseconds=1)).dt.floor("h").clip(upper=end - HOUR)
    n_h = ((last_h - first_h) // HOUR + 1).to_numpy()
    rep = ep.loc[ep.index.repeat(n_h)].reset_index(drop=True)
    offset = np.concatenate([np.arange(k) for k in n_h]) if len(n_h) else np.array([], dtype=int)
    rep["hour"] = first_h.repeat(n_h).reset_index(drop=True) + pd.to_timedelta(offset, unit="h")

    overlap = rep["end"].clip(upper=rep["hour"] + HOUR) - rep["start"].clip(lower=rep["hour"])
    rep["minutes_active"] = overlap.dt.total_seconds() / 60
    rep["active_at_start"] = rep["start"] < rep["hour"]
    cover = rep.groupby(["oblast", "hour"]).agg(
        minutes_active=("minutes_active", "sum"),
        active_at_start=("active_at_start", "any"),
    )

    starts = ep[ep["start"] >= start].assign(hour=lambda d: d["start"].dt.floor("h"))
    n_starts = starts.groupby(["oblast", "hour"]).size().rename("n_starts")

    panel = pd.DataFrame(index=grid).join(cover).join(n_starts)
    panel["minutes_active"] = panel["minutes_active"].fillna(0.0)
    panel["active_at_start"] = panel["active_at_start"].astype("boolean").fillna(False).astype(bool)
    panel["n_starts"] = panel["n_starts"].fillna(0).astype(int)
    panel["active"] = panel["minutes_active"] > 0
    cols = ["active", "active_at_start", "minutes_active", "n_starts"]
    return panel[cols].reset_index()
