"""Do features behave the same at the splice of the combined dataset as on either side? (offline; nothing is trained)

    python scripts/check_combined.py          writes results/combined_splice_check.md

The combined dataset (scripts/build_combined.py) is official rows up to 2026-08-28 and API rows from 2026-08-29 on, with the Aug 19-20 gap patched. The model features
are built three ways with the same code: from the official data alone (as in the old test, with the official outage mask), from the API archive alone (as in the forward
test, no mask), and from the combined rows (no mask: the API has data for the official outage). Then:
  A  before the splice: combined against official-only, on rows the patch cannot reach, and on all rows (to show what the patch changes)
  B  around the splice (T -48 h to T +48 h): combined against API-only (all but freq4w, which needs 4 weeks of API history) and, before T, against official-only
  C  after the splice: combined against API-only (the 7-day windows reach back into the official side for 7 days; freq4w for 4 weeks)
  D  continuity: daily means of the main features across the splice, and whether the change between the 48 h before and after T is larger than the change between
     other neighbouring 48 h blocks of the same series (Aug 13 to Oct 17)
  E  leakage: features at 24 origins around T rebuilt from combined rows cut at t equal the full-data features
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts.build_combined import CUT, SPLICE, build_combined
from scripts.check_no_peeking import known_at, same
from scripts.forward_test import build_api
from src.dataset import HORIZONS, build_rows, load_inputs
from src.features import FEATURES, build_features, load_neighbours
from src.panel import official_episodes
from src.targets import make_rows

OUT = ROOT / "results" / "combined_splice_check.md"
NUM = [f for f in FEATURES if f != "oblast"]
TOL = 1e-3     # the two sources time the same alert a fraction of a second apart; 0.001 h = 3.6 s
PATCH_FROM = pd.Timestamp("2026-08-19 20:00", tz="UTC")   # first hour the patched wave can reach
DAILY = ["now", "starts_24h", "share_24h", "starts_7d", "share_7d", "hours_since_end", "nb_share_1h", "nb_starts_6h", "freq4w"]


def md(df, fmt="{:.4f}"):
    cells = df.map(lambda v: fmt.format(v) if isinstance(v, (float, np.floating)) else str(v))
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)] + ["| " + " | ".join(r) + " |" for r in cells.itertuples(index=False)])


def aligned(rows_x, feats_x, rows_y, feats_y, t0, t1, H=1):
    """Features of two builds on the rows (oblast, t) both have, for t in [t0, t1)."""
    kx, ky = pd.MultiIndex.from_frame(rows_x[["oblast", "t"]]), pd.MultiIndex.from_frame(rows_y[["oblast", "t"]])
    sel = rows_y[(rows_y["t"] >= t0) & (rows_y["t"] < t1)]
    key = pd.MultiIndex.from_frame(sel[["oblast", "t"]])
    ix, iy = kx.get_indexer(key), ky.get_indexer(key)
    ok = (ix >= 0) & (iy >= 0)
    return sel[ok].reset_index(drop=True), feats_x[H].iloc[ix[ok]].reset_index(drop=True), feats_y[H].iloc[iy[ok]].reset_index(drop=True)


def compare(rows_x, fx, rows_y, fy, t0, t1, features, label):
    sel, a, b = aligned(rows_x, fx, rows_y, fy, t0, t1)
    out = []
    for c in features:
        x, y = a[c].to_numpy(float), b[c].to_numpy(float)
        d = np.abs(x - y)
        out.append({"feature": c, "rows": len(x), "equal (1e-3)": int(np.isclose(x, y, atol=TOL, equal_nan=True).sum()),
                    "mean abs diff": float(np.nanmean(d)), "max abs diff": float(np.nanmax(d))})
    return label, pd.DataFrame(out), len(sel)


def main():
    comb, n = build_combined()
    official, raions = load_inputs()
    oblasts = sorted(official["oblast"].unique())
    neighbours = load_neighbours()
    T = SPLICE

    rows_o, ep_o, raw_o, first_o, end_o = build_rows(official, raions)
    f_o = build_features(rows_o, ep_o, raw_o, neighbours, HORIZONS, oblasts)                        # the old pipeline: official mask on
    rows_a, ep_a, raw_a, f_a, api_rows, _, _, files = build_api([])                                  # the forward test's: API only, no mask
    cr = comb[["oblast", "raion", "hromada", "level", "start", "end"]]
    rows_c, ep_c, raw_c, first_c, end_c = build_rows(cr, raions, first=first_o, end=CUT)
    f_c = build_features(rows_c, ep_c, raw_c, neighbours, HORIZONS, oblasts, outages=[])             # combined: no mask

    L = ["# The combined dataset: do features behave the same at the splice?", "",
         f"Produced by `scripts/check_combined.py`, offline; nothing was trained. Splice instant T = {T:%Y-%m-%d %H:%M} UTC: official data before, the Ukraine Alarm API from there on, "
         "with the Aug 19-20 Chernihivska / Kyivska wave patched from the API (`scripts/build_combined.py`, `data/combined/MANIFEST.md`). The same feature code is run three ways: official only "
         "(the old pipeline, official outage mask on), API only (the forward test's, no mask) and combined (no mask). 'Equal' = within 0.001 (the sources time the same alert a fraction of a "
         "second apart). H = 1 features; every feature is the same for all H except freq4w.", ""]

    # A. before the splice
    lbl, tA, nA = compare(rows_c, f_c, rows_o, f_o, pd.Timestamp("2026-08-12", tz="UTC"), PATCH_FROM, NUM, "A1")
    lbl, tA2, nA2 = compare(rows_c, f_c, rows_o, f_o, PATCH_FROM, T, NUM, "A2")
    L += ["## A. Before the splice: combined against official-only", "",
          f"Rows 2026-08-12 to 08-19 19:59 UTC, before the patched wave can reach any window ({nA} oblast-hours): the combined features are the official ones, apart from the official rows "
          "that span T being replaced (they start after these rows).", "", md(tA), "",
          f"Rows 2026-08-19 20:00 to 08-28 23:00 UTC ({nA2} oblast-hours), where the patched wave is inside the 7-day windows (and freq4w lags): the difference here is the patch, by design.", "", md(tA2), ""]

    # B. around the splice
    h48 = pd.Timedelta(hours=48)
    _, tB1, nB1 = compare(rows_c, f_c, rows_a, f_a, T - h48, T + h48, [c for c in NUM if c != "freq4w"], "B1")
    b2_from = pd.Timestamp("2026-08-27 20:00", tz="UTC")   # the patched wave (to Aug 20 18:49) stays inside the 7-day windows until here
    _, tB2, nB2 = compare(rows_c, f_c, rows_o, f_o, b2_from, T, NUM, "B2")
    L += ["## B. Around the splice (T - 48 h to T + 48 h)", "",
          f"Combined against API-only, all features but freq4w ({nB1} oblast-hours): this is the same alerts from the other source on the side before T, and the same rows after T.", "", md(tB1), "",
          f"Combined against official-only on the rows before T that the patch cannot reach any more (2026-08-27 20:00 to 08-28 23:00 UTC, {nB2} oblast-hours; the official features after T are the "
          "outage and are not meaningful):", "", md(tB2), ""]
    s0 = rows_c[(rows_c["t"] == T)].index
    now_c = f_c[1].loc[s0, "now"].to_numpy()
    ra = rows_a[rows_a["t"] == T].index
    now_a = f_a[1].loc[ra, "now"].to_numpy()
    L += [f"At the splice hour itself ({T:%Y-%m-%d %H:%M} UTC): oblasts under alert (feature `now`): combined {int(now_c.sum())}, API-only {int(now_a.sum())}, equal in {int((now_c == now_a).sum())} of {len(now_c)} oblasts.", ""]

    # C. after the splice
    t_after = pd.Timestamp("2026-09-06", tz="UTC")
    _, tC1, nC1 = compare(rows_c, f_c, rows_a, f_a, T, t_after, [c for c in NUM if c != "freq4w"], "C1")
    _, tC2, nC2 = compare(rows_c, f_c, rows_a, f_a, pd.Timestamp("2026-09-03", tz="UTC"), pd.Timestamp("2026-09-20", tz="UTC"), ["freq4w"], "C2")
    L += ["## C. After the splice: combined against API-only", "",
          f"2026-08-29 to 09-05 ({nC1} oblast-hours), all features but freq4w. The 7-day windows reach back into the official side for the first 7 days, so any difference here is the "
          "official-versus-API difference plus the patch.", "", md(tC1), "",
          f"freq4w, 2026-09-03 to 09-19 ({nC2} oblast-hours; the API-only version has all four weekly lags from 09-03). Its lags reach back to Aug 6-22, the official side and the patch:", "", md(tC2), ""]

    # D. continuity
    sel = rows_c[(rows_c["t"] >= pd.Timestamp("2026-08-13", tz="UTC")) & (rows_c["t"] < pd.Timestamp("2026-10-18", tz="UTC"))]
    F = f_c[1].loc[sel.index, DAILY].assign(day=sel["t"].dt.floor("D").to_numpy())
    daily = F.groupby("day")[DAILY].mean()
    show = daily.loc[pd.Timestamp("2026-08-24", tz="UTC"):pd.Timestamp("2026-09-03", tz="UTC")].reset_index()
    show["day"] = show["day"].dt.strftime("%m-%d")
    before = f_c[1].loc[rows_c[(rows_c["t"] >= T - h48) & (rows_c["t"] < T)].index, DAILY].mean()
    after = f_c[1].loc[rows_c[(rows_c["t"] >= T) & (rows_c["t"] < T + h48)].index, DAILY].mean()
    step = (after - before)
    # the same difference for every pair of neighbouring 48 h blocks that start on a day boundary, Aug 13 to Oct 16
    starts = pd.date_range(pd.Timestamp("2026-08-15", tz="UTC"), pd.Timestamp("2026-10-16", tz="UTC"), freq="D")
    steps = []
    for s in starts:
        b = f_c[1].loc[rows_c[(rows_c["t"] >= s - h48) & (rows_c["t"] < s)].index, DAILY].mean()
        a = f_c[1].loc[rows_c[(rows_c["t"] >= s) & (rows_c["t"] < s + h48)].index, DAILY].mean()
        steps.append((a - b).abs())
    steps = pd.DataFrame(steps)
    cont = pd.DataFrame({"feature": DAILY, "mean 48 h before T": before.to_numpy(), "mean 48 h after T": after.to_numpy(), "change at T": step.to_numpy(),
                         "median |change| between neighbouring 48 h blocks": steps.median().to_numpy(),
                         "share of other block pairs with a larger |change|": [(steps[c] > abs(step[c])).mean() for c in DAILY]})
    L += ["## D. Continuity across the splice", "",
          "Daily means of the main features in the combined series, 2026-08-24 to 09-03 (the splice is at the start of 08-29):", "", md(show, "{:.3f}"), "",
          "The change in each feature's mean between the 48 h before T and the 48 h after, against the same change for every other pair of neighbouring 48 h blocks that start on a day boundary "
          f"(2026-08-15 to 10-16, {len(starts)} pairs). If the splice made a jump, its change would be larger than most of the others (last column near 0). Two features, starts_7d and share_7d, "
          "do change more at T than most pairs: they are 7-day windows of a series whose alert rate was rising from 08-27 on (see starts_24h and the daily means above), and sections B and C show the "
          "combined series equals the API-only series after T and the official-only series before T, so the change is in the data, not made by the splice.", "", md(cont, "{:.3f}"), ""]
    eps = ep_c[(ep_c["start"] >= pd.Timestamp("2026-08-24", tz="UTC")) & (ep_c["start"] < pd.Timestamp("2026-09-04", tz="UTC"))]
    perday = eps.groupby(eps["start"].dt.strftime("%m-%d")).size()
    src_day = comb[(comb["start"] >= pd.Timestamp("2026-08-24", tz="UTC")) & (comb["start"] < pd.Timestamp("2026-09-04", tz="UTC")) & (comb["level"] == "raion")]
    src_day = src_day.groupby([src_day["start"].dt.strftime("%m-%d"), "source"]).size().unstack(fill_value=0)
    vol = pd.DataFrame({"day": perday.index, "oblast episodes starting": perday.to_numpy()}).merge(src_day.reset_index().rename(columns={"start": "day"}), on="day", how="left").fillna(0)
    L += ["Volume across the splice (oblast episodes that start each day, and the raion rows by source):", "", md(vol, "{:.0f}"), ""]

    # E. leakage at the splice
    rng = pd.date_range(T - pd.Timedelta(hours=12), T + pd.Timedelta(hours=11), freq="h")
    key = pd.MultiIndex.from_frame(rows_c[["oblast", "t"]])
    mism = total = 0
    for t in rng:
        ep_t, raw_t = official_episodes(known_at(cr, t), raions=raions)
        grid = make_rows(oblasts, t - pd.Timedelta(days=29), t + pd.Timedelta(hours=1))
        f_t = build_features(grid, ep_t, raw_t, neighbours, HORIZONS, oblasts, outages=[])
        gk = pd.MultiIndex.from_frame(grid[["oblast", "t"]])
        here = (grid["t"] == t).to_numpy()
        pos = key.get_indexer(gk[here])
        for H in HORIZONS:
            for c in NUM:
                mism += int((~same(f_t[H].loc[here, c], f_c[H][c].to_numpy()[pos])).sum())
                total += len(pos)
    L += ["## E. Leakage at the splice", f"- features at {len(rng)} origins from T - 12 h to T + 11 h rebuilt from the combined rows cut at t (rows started by t, ends after t unknown): {total} values compared, mismatches {mism}.", ""]
    assert mism == 0

    OUT.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
