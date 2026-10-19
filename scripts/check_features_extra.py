"""Checks for the round-22 candidate features (src/features_extra.py): a hand-computed example, the massive-event rule, and a leakage check.

    python scripts/check_features_extra.py            everything (the leakage check takes a few minutes)
    python scripts/check_features_extra.py --quick    only the hand-computed examples

Leakage check, as scripts/check_no_peeking.py: for N origins, keep only the alert rows that started by t and mark every end after t as unknown, rebuild the rows,
episodes and the extra features from that, and require exact equality with the full-data features at (oblast, t). A negative control (a feature that looks one hour
past t) shows the check would catch peeking. Also checks the existing 14 features are untouched: build_features on the same rows is the code in src/features.py.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts.build_combined import CUT, load_combined
from src.dataset import build_rows, load_inputs
from src.features import load_neighbours
from src.features_extra import (A_FEATURES, B_FEATURES, MASSIVE_GAP_BINS, build_extra, massive_event_starts, raion_episodes)

UNKNOWN_END = pd.Timestamp("2100-01-01", tz="UTC")
HISTORY = pd.Timedelta(days=45)       # events and hours_since_massive look back 30 days; the extra margin keeps an event from being cut in two
failed = 0


def ok(cond, msg):
    global failed
    failed += 0 if cond else 1
    print(("ok    " if cond else "FAIL  ") + msg, flush=True)


def synthetic():
    K, P, S = "Kharkivska oblast", "Poltavska oblast", "Sumska oblast"
    raions = pd.DataFrame({"oblast": [K, K, P, P, S, S], "raion": ["k1", "k2", "p1", "p2", "s1", "s2"]})
    ts = lambda s: pd.Timestamp(s, tz="UTC")
    rows_ = pd.DataFrame([
        [K, "k1", "", "raion", ts("2026-01-10 09:35"), ts("2026-01-10 09:55")],
        [K, "k2", "", "raion", ts("2026-01-10 09:35"), ts("2026-01-10 09:55")],
        [P, "p1", "", "raion", ts("2026-01-10 09:47"), ts("2026-01-10 10:05")],
        # an older alert for Sumska, to have history and to leave it out of the last hour
        [S, "s1", "", "raion", ts("2026-01-09 20:00"), ts("2026-01-09 20:40")],
    ], columns=["oblast", "raion", "hromada", "level", "start", "end"])
    neighbours = {K: [P, S], P: [K, S], S: [K, P]}
    obl = [K, P, S]
    rows, episodes, raw, first, end = build_rows(rows_, raions, first=ts("2026-01-09 00:00"), end=ts("2026-01-10 13:00"))
    rows = rows[rows["oblast"].isin(obl)].reset_index(drop=True)
    extra = build_extra(rows, episodes, raw, raion_episodes(rows_, raions), raions, neighbours, obl)
    at = lambda ob, t: extra[(rows["oblast"] == ob) & (rows["t"] == ts(t))].iloc[0]
    k, p, s = at(K, "2026-01-10 10:00"), at(P, "2026-01-10 10:00"), at(S, "2026-01-10 10:00")
    ok(k["own_cover_10m"] == 1 and k["own_cover_30m"] == 1 and k["own_cover_1h"] == 0.5, "own bins: Kharkivska 09:35-09:55 at origin 10:00 is in the last bin, in all 3 of the last 3 bins, in 3 of the last 6")
    ok(p["own_cover_10m"] == 1 and p["own_cover_30m"] == 2 / 3 and p["own_cover_1h"] == 2 / 6, "own bins: Poltavska 09:47-10:05 (the end after t is unknown at t) is in 2 of the last 3 bins")
    ok(s["own_cover_10m"] == 0 and s["own_cover_1h"] == 0, "own bins: Sumska is quiet in the last hour")
    ok(k["raion_frac_now"] == 0 and k["raion_frac_max_1h"] == 1.0 and k["raion_starts_30m"] == 2, "raions: none active at 10:00, both at 09:50 (max over the last hour), 2 starts in the last 30 min")
    ok(p["raion_frac_now"] == 0.5 and p["raion_frac_max_1h"] == 0.5 and p["raion_starts_30m"] == 1, "raions: Poltavska has 1 of 2 raions under alert now")
    ok(k["nat_now"] == 2 and k["nat_max_1h"] == 2 and k["nat_max_3h"] == 2, "nationwide: K and P in the last bin, none else")
    ok(k["nat_starts_1h"] == 2 and k["nat_starts_3h"] == 2, "nationwide starts in the last 1 h and 3 h: 2 (Sumska's alert of the evening before is outside)")
    ok(k["up_any_30m"] == 1.0 and k["up_any_60m"] == 1.0 and k["up_new_60m"] == 1, "wave: Kharkivska's only upwind neighbour (Poltavska, south and west: its latitude is lower) is in, and is new")
    ok(p["up_any_30m"] == 0.5 and p["up_new_60m"] == 1, "wave: Poltavska has two upwind neighbours (Kharkivska east, Sumska east); one is in and new")
    ok(not np.isnan(at(S, "2026-01-10 10:00")["up_any_30m"]), "wave: Sumska has upwind neighbours (Kharkivska is east of it), a number")
    ok(k["hours_since_massive"] == 720 and k["massive_14d"] == 0 and k["massive_now"] == 0, "massive: none in this tiny example")
    k11 = at(K, "2026-01-10 11:00")
    ok(k11["own_cover_10m"] == 0 and k11["nat_now"] == 0 and k11["up_new_60m"] == 0 and k11["nat_max_1h"] == 1 and k11["nat_max_3h"] == 2,
       "an hour later (11:00) everything has ended: the last bin is empty, the 1 h maximum is 1 (Poltavska until 10:05 is in the bin 10:00-10:10), the 3 h maximum (08:00-11:00) still sees the two units of 09:35-10:05")


def massive_rule():
    nat = np.zeros(400, dtype=int)
    nat[10:13] = 16                       # event 1 starts at bin 10
    nat[20] = 15                          # 7 bins later (gap 7 < 18): same event
    nat[20 + 19] = 15                     # gap of exactly 18 bins after the last massive moment: a new event
    nat[20 + 19 + 18] = 15                # gap of 17 bins: same event as the one before
    nat[300] = 30                         # far later: a new event
    nat[100] = 14                         # 14 is not massive
    ev = massive_event_starts(nat)
    ok(list(ev) == [10, 39, 300], f"massive events start at bins 10, 39 and 300 (got {list(ev)}); 14 units is not massive, a gap of 17 bins joins, 18 splits")
    ok(MASSIVE_GAP_BINS == 18, "the gap is 18 bins (3 hours)")


def weather_check():
    """Weather features use only stamps up to and including the origin: compare with a hand lookup on the CSV for random origins; a shifted-by-one-hour copy must differ."""
    from src.features_extra import load_weather, weather_features
    w = load_weather()
    if w is None:
        print("skip  weather: data/weather/ is not complete here")
        return
    ob = "Kharkivska oblast"
    rows = pd.DataFrame({"oblast": ob, "t": pd.date_range("2026-09-01", "2026-09-05", freq="h", tz="UTC")})
    f = weather_features(rows, {ob: w[ob]} | {o: w[o] for o in w})
    d = w[ob]
    rng = np.random.default_rng(0)
    bad = 0
    for i in rng.choice(len(rows), 15, replace=False):
        t = rows["t"][i]
        exp3 = d["precipitation"].loc[t - pd.Timedelta(hours=2):t].sum()
        bad += int(not (np.isclose(f["wind_t"][i], d["wind_speed_10m"][t]) and np.isclose(f["cloud_t"][i], d["cloud_cover"][t])
                        and np.isclose(f["precip_1h"][i], d["precipitation"][t]) and np.isclose(f["precip_3h"][i], exp3)))
    ok(bad == 0, f"weather: wind_t, cloud_t, precip_1h and precip_3h equal a hand lookup of the stamps t and t-2..t for 15 origins ({bad} differ)")
    ok(list(f.columns) == ["wind_t", "cloud_t", "precip_1h", "precip_3h"], f"weather: columns {list(f.columns)} (visibility is all null in the archive API, so it is not used)")
    ok(all(d.index.is_monotonic_increasing and (d.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all() for d in w.values()), "weather: every file is hourly without gaps")


def known_at(rows, t):
    known = rows[(rows["start"] <= t) & (rows["end"] > t - HISTORY)].copy()
    known.loc[known["end"] > t, "end"] = UNKNOWN_END
    return known


def leakage(n_origins):
    comb = load_combined()
    official, raions = load_inputs()
    oblasts = sorted(official["oblast"].unique())
    cr = comb[["oblast", "raion", "hromada", "level", "start", "end"]]
    rows, episodes, raw, first, end = build_rows(cr, raions, first=official["start"].min().ceil("D"), end=CUT)
    neighbours = load_neighbours()
    full = build_extra(rows, episodes, raw, raion_episodes(cr, raions), raions, neighbours, oblasts)
    key = pd.MultiIndex.from_frame(rows[["oblast", "t"]])
    rng = np.random.default_rng(0)
    cand = rows.loc[(rows["t"] >= pd.Timestamp("2026-06-01", tz="UTC")) & (rows["t"] < CUT - pd.Timedelta(hours=7)), "t"].drop_duplicates()
    origins = sorted(rng.choice(cand.to_numpy(), n_origins, replace=False))
    # make sure at least a few origins are inside or just after a busy period
    busy = full.groupby(rows["t"])["nat_max_3h"].max()
    origins = sorted(set(origins) | set(busy[busy >= 10].sample(min(5, int((busy >= 10).sum())), random_state=0).index.to_numpy()))
    bad, leaky_bad = 0, 0
    for t in map(pd.Timestamp, origins):
        t = t.tz_localize("UTC") if t.tz is None else t
        kn = known_at(cr, t)
        r2, e2, w2, _, _ = build_rows(kn, raions, first=(t - pd.Timedelta(days=44)).ceil("D"), end=t + pd.Timedelta(hours=1))
        x2 = build_extra(r2, e2, w2, raion_episodes(kn, raions), raions, neighbours, oblasts)
        sel = (r2["t"] == t).to_numpy()
        a = x2[sel].set_index(r2.loc[sel, "oblast"].to_numpy())
        idx = pd.MultiIndex.from_arrays([r2.loc[sel, "oblast"], r2.loc[sel, "t"]])
        b = full.iloc[key.get_indexer(idx)].set_index(r2.loc[sel, "oblast"].to_numpy())
        same = np.isclose(a.to_numpy(float), b.loc[a.index].to_numpy(float), rtol=0, atol=1e-9) | (np.isnan(a.to_numpy(float)) & np.isnan(b.loc[a.index].to_numpy(float)))
        bad += int((~same).sum())
        if (~same).any():
            print("  differs at", t, list(a.columns[(~same).any(axis=0)]))
    ok(bad == 0, f"leakage: {len(origins)} origins, every extra feature of every oblast equal when the data is cut at t ({bad} cells differ)")

    # negative control: "is the oblast under alert in (t, t+1h]" (a look-ahead feature) read from the cut data and from the full data must differ somewhere
    diffs = 0
    for t in map(pd.Timestamp, origins):
        t = t.tz_localize("UTC") if t.tz is None else t
        kn = known_at(cr, t)
        _, _, w2, _, _ = build_rows(kn, raions, first=(t - pd.Timedelta(days=44)).ceil("D"), end=t + pd.Timedelta(hours=1))
        for ob in oblasts:
            fa, fb = raw[raw["oblast"] == ob], w2[w2["oblast"] == ob]
            look = lambda e: bool(((e["start"] < t + pd.Timedelta(hours=1)) & (e["end"] > t)).any())
            diffs += int(look(fa) != look(fb))
    ok(diffs > 0, f"negative control: a look-ahead feature differs between full and cut data in {diffs} (origin, oblast) cells, so the check can see peeking")
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--origins", type=int, default=25)
    a = ap.parse_args()
    synthetic()
    massive_rule()
    weather_check()
    if not a.quick:
        leakage(a.origins)
    print("ALL OK" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
