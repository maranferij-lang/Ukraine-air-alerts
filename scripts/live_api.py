"""Live forecast from the Ukraine Alarm API: the day files in data/api_archive/ -> features at the last completed hour -> the frozen models.

Used by scripts/predict.py --now and tested offline by scripts/check_live_replay.py. Nothing here talks to the network; scripts/archive_api.py
(fetch_days) does that. Same pipeline as the forward test (scripts/forward_test.py): the same feature code with no outage mask, the same frozen LightGBM
and thresholds. Alerts that are still running when the data was fetched have no end in the API (isContinue true, end year 0001): they are kept as running
with an unknown end, exactly how a forecast at t treats every alert that has not ended by t (scripts/check_no_peeking.known_at).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts.api_check import day_files, rows_from_items, to_official_rows
from scripts.check_no_peeking import known_at
from src.baselines import KYIV
from src.dataset import HORIZONS, load_inputs
from src.features import FEATURES, build_features, load_neighbours
from src.panel import official_episodes
from src.targets import make_rows

ARCHIVE = ROOT / "data" / "api_archive" / "date_history"
GRID = pd.Timedelta(days=29)         # freq4w looks 1-4 weeks back
HISTORY = pd.Timedelta(days=32)      # known_at keeps alerts that ended up to 32 days before t (hours_since_end is capped at 30 days)
REFETCH_DAYS = 3                     # today and the two days before are always fetched again


def origin_for(now):
    """The last completed hour: the instant on the hour just before `now`. Everything the forecast uses is cut at that instant."""
    return pd.Timestamp(now).tz_convert("UTC").floor("h")


def needed_days(t):
    """UTC days whose files the features at t need: the day of t - 32 days up to the day of t (an alert is in the file of every day it was active)."""
    return list(pd.date_range((t - HISTORY).floor("D"), t.floor("D"), freq="D"))


def read_days(days, folder=None):
    """Items of the saved day files for `days`; also returns the days that have no (readable) file."""
    files = day_files(folder or ARCHIVE)
    items, missing = [], []
    for d in days:
        f = files.get(d)
        try:
            items.extend(json.loads(f.read_text(encoding="utf-8")) if f else [])
            if not f:
                missing.append(d)
        except ValueError:
            missing.append(d)
    return items, missing


def live_rows(items, raions, oblasts, keep_open=True):
    """API items -> alert rows in our schema (running alerts kept with an unknown end), only our oblasts."""
    rows, n, dropped = to_official_rows(rows_from_items(items), raions, keep_open=keep_open)
    return rows[rows["oblast"].isin(oblasts)].reset_index(drop=True), n, dropped


def features_at(api_rows, raions, oblasts, t):
    """Features at origin t for every H, from the rows as they looked at t. Returns (rows at t, {H: features aligned with them})."""
    ep_t, raw_t = official_episodes(known_at(api_rows, t), raions=raions)
    grid = make_rows(oblasts, t - GRID, t)
    feats = build_features(grid, ep_t, raw_t, load_neighbours(), HORIZONS, oblasts, outages=[])  # no mask: the API observes every hour
    here = (grid["t"] == t).to_numpy()
    return grid[here].reset_index(drop=True), {H: feats[H][here].reset_index(drop=True) for H in HORIZONS}


def stale_open(api_rows, active_ids, refetch_from):
    """Running alerts (no end) older than `refetch_from` (the days refreshed on this run) whose day files may be out of date: a region can have only one
    running alert, so an older running row of a region that has a newer running row is stale, and so is one whose region is not in the API's active list now."""
    running = api_rows[(api_rows["end"] == pd.Timestamp("2100-01-01", tz="UTC")) & api_rows["level"].isin(["raion", "oblast"])]
    newest = running.groupby("regionId")["start"].transform("max")
    old = (running["start"] < refetch_from)
    return running[old & ((running["start"] < newest) | ~running["regionId"].isin(set(active_ids)))]


def probabilities(feats, boosters):
    return {H: boosters[H].predict(feats[H][FEATURES]) for H in HORIZONS}


def as_of(items, moment):
    """What the API would have returned at `moment`: alerts that started by then; those that ended later are running (no end)."""
    out = []
    for a in items:
        s = pd.Timestamp(a["startDate"])
        if s > moment:
            continue
        e = pd.Timestamp(a["endDate"]) if a.get("endDate") else None
        if a.get("isContinue") or e is None or e.year <= 2000 or e > moment:
            a = {**a, "endDate": "0001-01-01T00:00:00Z", "isContinue": True}
        out.append(a)
    return out


def inputs():
    official, raions = load_inputs()
    return raions, sorted(official["oblast"].unique())


# ----------------------------------------------------------------------------------------------------------------------------------
# the live forecast (needs the network and UA_ALARM_TOKEN; scripts/predict.py --now calls it)
def now_utc():
    return pd.Timestamp.now(tz="UTC")


def forward_test_note():
    """One line from the forward test's calibration table: the model tended to predict low. None if the table is not there."""
    path = ROOT / "results" / "forward_api" / "calibration.md"
    try:
        text = path.read_text(encoding="utf-8")
        rows = {}
        section = text.split("## Calibration in the large")[1].split("\n## ")[0]  # the first table only
        for line in section.split("\n"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[1] == "LightGBM" and cells[0] in ("1", "3", "6"):
                rows[int(cells[0])] = (cells[2], cells[3])
        assert len(rows) == 3
    except Exception:
        return None
    return ("Note: in the forward test (41 days, 2026-09-07 to 10-17, same models) the model predicted a bit low: mean predicted against observed "
            + ", ".join(f"{float(rows[H][0]):.3f} against {float(rows[H][1]):.3f} at {H} h" for H in HORIZONS)
            + ". Nothing is recalibrated; read the probabilities as slightly low.")


def refuse(lines):
    print("\n".join(lines))
    return 1


def live_forecast(oblast=None, resolve=None):
    """Forecast for the last completed hour from the API. Returns the exit code (0 = forecast printed, 1 = refused). `oblast`: show one oblast only
    (resolve turns the typed name into one of ours)."""
    import textwrap
    from datetime import timedelta
    from scripts import archive_api
    from scripts.forward_test import load_frozen
    from src.ukrainealarm import Client

    info, frozen, boosters, freq = load_frozen()
    raions, oblasts = inputs()
    want = resolve(oblast, oblasts).replace(" oblast", "") if oblast else None  # a bad name stops here, before any request
    now = now_utc()
    t = origin_for(now)
    days = needed_days(t)
    today = now.date()
    refetch_from = today - timedelta(days=REFETCH_DAYS - 1)
    c = Client()

    lines = []
    res = archive_api.fetch_days(c, [d.date() for d in days], refetch_from, say=lambda m: lines.append(m) if "not saved" in m else None)
    s_act, active, fetched_at = archive_api.fetch_active(c, say=lambda m: None)
    items, missing = read_days(days)
    bad = sorted({d.date() for d in missing} | set(res["failed"]))
    if res["fatal"]:
        return refuse([f"Cannot forecast now: {res['fatal']}", "Check that UA_ALARM_TOKEN holds your token, then run this again."])
    if bad:
        why = "; ".join(lines)
        first, last = (bad[0], bad[-1]) if bad else (days[0].date(), today)
        return refuse(["Cannot forecast now: the API history is not complete."
                       + (f" Missing or not refreshed: {', '.join(d.isoformat() for d in bad)}." if bad else "")
                       + (f" ({why})" if why else ""),
                       "No scaling and no filling. Fix it first with:",
                       f"  python scripts/archive_api.py --from {first.isoformat()} --to {last.isoformat()}",
                       "and run this again."])

    api_rows, n, dropped = live_rows(items, raions, oblasts)
    ids = [a.get("regionId") for a in active] if s_act == 200 and isinstance(active, list) else None
    old = api_rows[(api_rows["end"] == pd.Timestamp("2100-01-01", tz="UTC")) & (api_rows["start"] < pd.Timestamp(refetch_from, tz="UTC"))
                   & api_rows["level"].isin(["raion", "oblast"])]
    if len(old):
        if ids is None:
            return refuse([f"Cannot forecast now: {len(old)} alerts older than 3 days are still marked as running in the saved files and the API's active list "
                           f"is not available (HTTP {s_act}) to check them. Run again later."])
        stale = stale_open(api_rows, ids, pd.Timestamp(refetch_from, tz="UTC"))
        if len(stale):
            f0 = stale["start"].min().date()
            return refuse([f"Cannot forecast now: {len(stale)} alerts that started on or after {f0.isoformat()} are marked as running in the saved files, but the API does not show "
                           "them as running now (their region has no active alert, or a newer one), so their day files are out of date. No guessing. Refresh them with:",
                           f"  python scripts/archive_api.py --from {f0.isoformat()} --to {today.isoformat()} --force",
                           "and run this again."])

    rows_t, feats = features_at(api_rows, raions, oblasts, t)
    prob = probabilities(feats, boosters)
    thr = {H: frozen["thresholds"][str(H)]["lgbm"] for H in HORIZONS}
    table = pd.DataFrame({"oblast": rows_t["oblast"].str.replace(" oblast", "", regex=False), "now": feats[1]["now"].to_numpy() > 0})
    for H in HORIZONS:
        table[f"p{H}"] = prob[H]
        table[f"o{H}"] = prob[H] >= thr[H]
    table = table.sort_values("p1", ascending=False, kind="stable").reset_index(drop=True)
    if want:
        table = table[table["oblast"] == want].reset_index(drop=True)

    # freshness
    st = rows_from_items(items)
    st = st[st["start"] <= now]
    newest_start = st["start"].max()
    ends = st["end"][(st["end"].dt.year > 2000) & (st["end"] <= now)]
    newest_end = ends.max() if len(ends) else None
    upd = [pd.Timestamp(a["lastUpdate"]) for a in (active or []) if isinstance(a, dict) and a.get("lastUpdate")]
    mins = lambda ts: f"{(now - ts).total_seconds() / 60:.0f} min before now" if (now - ts) < pd.Timedelta(hours=3) else f"{(now - ts).total_seconds() / 3600:.1f} h before now"
    fresh = (f"Freshness: now is {now:%Y-%m-%d %H:%M} UTC. The newest alert start in the API is {newest_start:%Y-%m-%d %H:%M} UTC ({mins(newest_start)})"
             + (f", the newest end {newest_end:%Y-%m-%d %H:%M} UTC" if newest_end is not None else "")
             + (f"; its active-alerts list was last updated {max(upd):%Y-%m-%d %H:%M} UTC ({mins(max(upd))})" if upd else "")
             + ". A quiet spell and an API that is behind look the same from here.")
    local = t.tz_convert(KYIV)
    print(textwrap.fill(f"Live forecast from the Ukraine Alarm API for the hour starting {t:%Y-%m-%d %H:%M} UTC ({local:%H:%M} Kyiv time), the last completed hour: "
                        "the chance that a NEW alert starts within the next 1, 3 and 6 hours. Only what the API reported by that hour is used; alerts that started later are not. "
                        "Models: LightGBM trained on official data to 2026-08-07, not retrained.", 100))
    print()
    print(textwrap.fill(fresh, 100))
    if dropped["district not in our raion list"]:
        print(textwrap.fill("Left out: alerts in districts that are not in our raion list: " + ", ".join(sorted(dropped["district not in our raion list"])) + ".", 100))
    note = forward_test_note()
    if note:
        print()
        print(textwrap.fill(note, 100))
    print()
    print("'above' = at or above the frozen threshold (max F1 on the last train week): " + ", ".join(f"{H} h {thr[H]:.3f}" for H in HORIZONS) + ". Sorted by the 1 h probability.")
    rows_out = []
    for _, r in table.iterrows():
        row = [r["oblast"], "yes" if r["now"] else "no"]
        for H in HORIZONS:
            row += [f"{r[f'p{H}']:.3f}", "yes" if r[f"o{H}"] else "no"]
        rows_out.append(row)
    print(pd.DataFrame(rows_out, columns=["oblast", "alert now", "1 h", "above", "3 h", "above ", "6 h", "above  "]).to_string(index=False))
    return 0
