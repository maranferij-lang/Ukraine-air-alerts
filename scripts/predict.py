"""What the model would have said at a past hour, from the data known at that hour only.

    python scripts/predict.py --at "2026-09-05 14:00" --oblast Kyivska
    python scripts/predict.py --at "2026-09-05 17:00+03:00" --all
    python scripts/predict.py --now                      (live, from the Ukraine Alarm API; needs UA_ALARM_TOKEN)
    python scripts/predict.py --now --oblast Kharkivska

For origin t (a whole hour, UTC unless the time carries an offset) prints the probability that a new
alert starts in (t, t+H] for H = 1, 3, 6 (target (b)), from the LightGBM models scripts/evaluate.py
saved in models/, next to the three baselines and to what actually happened.

--now forecasts the last completed hour from the Ukraine Alarm API instead (scripts/live_api.py): it tops up data/api_archive/ (the days not saved yet and the last
three), refuses and names the missing days if it cannot get a complete history (no scaling, no filling), and prints every oblast's probability for H = 1, 3, 6 and whether
it is at or above the frozen threshold, sorted by H = 1. Needs your token in the environment variable UA_ALARM_TOKEN and the network; the models are the frozen ones.

The inputs are recomputed from the alert rows as they looked at t: only alerts that had started by
t, with the end of any alert still running at t unknown (the same cut scripts/check_no_peeking.py
checks against the full-data features). Times before the end of training (models/info.json) were
part of the training rows: the output says so, because the model has seen what happened next.
"""
import argparse
import json
import signal
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb
import numpy as np
import pandas as pd

from scripts.check_no_peeking import known_at
from src.baselines import KYIV, local_hour_weekday
from src.dataset import EVAL_LOOKBACK, FEATURE_HISTORY, HORIZONS, load_inputs, split
from src.features import FEATURES, build_features, load_neighbours
from src.load import OFFICIAL_OUTAGES, PERMANENT_ALERT_OBLASTS, data_end
from src.panel import official_episodes
from src.targets import make_rows, touches, y_start

MODELS = ROOT / "models"
GRID = pd.Timedelta(days=29)  # freq4w looks 1-4 weeks back; the grid must reach that far
OUTAGES = ", ".join(f"{a}..{pd.Timestamp(b) - pd.Timedelta(days=1):%m-%d}" for a, b in OFFICIAL_OUTAGES)


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_models():
    files = ([MODELS / "info.json"] + [MODELS / f"lgbm_b_start_h{H}.txt" for H in HORIZONS]
             + [MODELS / f"frequency_b_start_h{H}.csv" for H in HORIZONS])
    missing = [str(f.relative_to(ROOT)) for f in files if not f.exists()]
    if missing:
        which = "No saved models in models/" if len(missing) == len(files) else f"Missing {', '.join(missing)}"
        fail(f"{which}. Run `python scripts/evaluate.py` first (about 1.5 min): it fits the models and saves "
             "them to models/.")
    info = json.loads((MODELS / "info.json").read_text())
    if info.get("horizons") != HORIZONS or info.get("features") != FEATURES:
        fail("models/ was written by a different version of the code. Run `python scripts/evaluate.py` again.")
    boosters = {H: lgb.Booster(model_file=str(MODELS / f"lgbm_b_start_h{H}.txt")) for H in HORIZONS}
    freq = {H: pd.read_csv(MODELS / f"frequency_b_start_h{H}.csv").set_index(["oblast", "hour", "weekday"])["rate"]
            for H in HORIZONS}
    return info, boosters, freq


def parse_origin(text):
    bad = f'Cannot read --at "{text}". Use e.g. "2026-09-05 14:00" (UTC) or "2026-09-05 17:00+03:00".'
    try:
        ts = pd.to_datetime(text, format="ISO8601")  # ISO only: "05.09.2026" would be read as 9 May
    except (ValueError, TypeError):
        fail(bad)
    if pd.isna(ts):
        fail(bad)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    t = ts.floor("h")
    note = None if t == ts else (f"Forecasts are made on the hour: using {t:%H:%M} UTC, the last whole hour "
                                 f"before {ts:%H:%M:%S} UTC.")
    return t, note


def resolve_oblast(name, oblasts):
    """Exact name (without " oblast", any case) first, then a unique prefix."""
    norm = lambda s: s.lower().replace(" oblast", "").strip()
    q = norm(name)
    if not q:
        fail(f'--oblast is empty. Choose from: {", ".join(oblasts)}.')
    exact = [o for o in oblasts if norm(o) == q]
    if exact:
        return exact[0]
    prefix = [o for o in oblasts if norm(o).startswith(q)]
    if len(prefix) == 1:
        return prefix[0]
    if not prefix and any(norm(o).startswith(q) for o in PERMANENT_ALERT_OBLASTS):
        fail(f'--oblast "{name}": Luhansk oblast is excluded from the model (under permanent alert since 2022).')
    what = f"matches more than one: {', '.join(prefix)}" if prefix else "matches none"
    fail(f'--oblast "{name}" {what}. Choose from: {", ".join(oblasts)}.')


def status_lines(t, first, end, test_start, oblast_any):
    """Is t a forecast or a training hour, and is anything about its data unusual?"""
    one = make_rows([oblast_any], t, t)
    in_test = {H: bool(split(one, first, end, test_start, H, EVAL_LOOKBACK)["test"].iloc[0]) for H in HORIZONS}
    cutoff = f"{test_start:%Y-%m-%d %H:%M} UTC"
    tested = [H for H in HORIZONS if in_test[H]]
    if t < test_start:
        lines = [f"TRAINING PERIOD: the models were fitted on data up to {cutoff}, which includes this hour and "
                 "what followed it. These numbers are not forecasts."]
    elif len(tested) == len(HORIZONS):
        lines = [f"After the end of training ({cutoff}): the models never saw this hour, so this is a real "
                 "forecast, inside the 24-day test window."]
    elif tested:
        rest = [H for H in HORIZONS if not in_test[H]]
        lines = [f"After the end of training ({cutoff}): the models never saw this hour, so this is a real "
                 f"forecast. It is a test row for H = {', '.join(map(str, tested))}; for H = "
                 f"{', '.join(map(str, rest))} the window touches the feed outage or passes the end of the data, "
                 "so it is not scored."]
    else:
        lines = [f"After the end of training ({cutoff}): the models never saw this hour, but it is outside the "
                 "24-day test window (its window or the 24h before it touches the feed outage, or the data ends)."]
    if t - first < FEATURE_HISTORY:
        lines.append("Less than 7 days of data before this hour: the history features are incomplete.")
    if touches(one, OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=pd.Timedelta(0)).any():
        lines.append(f"This hour is inside the masked official feed outage ({OUTAGES}): alert data are missing or "
                     "incomplete, so the inputs and the outcome are not reliable.")
    elif touches(one, OFFICIAL_OUTAGES, before=EVAL_LOOKBACK, after=pd.Timedelta(0)).any():
        lines.append(f"The last 24 hours overlap the feed outage ({OUTAGES}): the 6h/24h features and the time "
                     "since the last alert come from partial data, and no training or test row has inputs like "
                     "these. Treat the numbers with care.")
    elif touches(one, OFFICIAL_OUTAGES, before=pd.Timedelta(days=7), after=pd.Timedelta(0)).any():
        lines.append(f"The 7-day lookback overlaps the feed outage ({OUTAGES}): those features are computed "
                     "over the observed hours only, as on Sep 4-5 in the test window.")
    return lines


def forecast(t, official, raions, episodes, first, end, boosters, freq):
    """One row per oblast at origin t: "now", and per H the model probability, the same-hour-yesterday
    and train-frequency baselines (-1 = not available) and what happened (-1 = unknown). Inputs come
    from known_at(official, t) only; "happened" comes from the full-data episodes."""
    oblasts = sorted(official["oblast"].unique())
    ep_t, raw_t = official_episodes(known_at(official, t), raions=raions)
    grid = make_rows(oblasts, max(t - GRID, first), t)
    feats = build_features(grid, ep_t, raw_t, load_neighbours(), HORIZONS, oblasts)
    here = (grid["t"] == t).to_numpy()
    at_t = grid[here].reset_index(drop=True)
    yday = grid[(grid["t"] == t - pd.Timedelta(hours=24)).to_numpy()].reset_index(drop=True)
    hour, weekday = local_hour_weekday(at_t["t"])
    keys = pd.MultiIndex.from_arrays([at_t["oblast"], hour, weekday])
    table = pd.DataFrame({"oblast": at_t["oblast"], "now": feats[HORIZONS[0]].loc[here, "now"].to_numpy().astype(int)})
    for H in HORIZONS:
        h = pd.Timedelta(hours=H)
        table[f"model_{H}"] = boosters[H].predict(feats[H].loc[here, FEATURES])
        yday_known = (t - pd.Timedelta(hours=24) >= first
                      and not touches(yday, OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=h).any())
        table[f"yday_{H}"] = y_start(yday, ep_t, H).astype(int) if yday_known else -1
        table[f"freq_{H}"] = freq[H].reindex(keys).to_numpy()
        known = t + h <= end and not touches(at_t, OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=h).any()
        table[f"happened_{H}"] = y_start(at_t, episodes, H).astype(int) if known else -1
    return table


def span(gap):
    """'22 minutes', '1 h 20 min'"""
    mins = int(round(gap.total_seconds() / 60))
    if mins < 60:
        return f"{mins} minutes"
    if mins < 48 * 60:
        return f"{mins // 60} h {mins % 60:02d} min"
    return f"{mins // 1440} days {mins % 1440 // 60} h"


def plain_one(r, when, t, nxt):
    """One plain sentence for one oblast: the three probabilities and what happened."""
    pct = lambda v: f"{100 * v:.0f}%"
    name = r["oblast"].replace(" oblast", "")
    head = (f"{name}, {when}: {pct(r['model_1'])} chance a new alert starts within 1 hour, "
            f"{pct(r['model_3'])} within 3, {pct(r['model_6'])} within 6.")
    gap = None if nxt is None else nxt - t
    down = touches(make_rows([r["oblast"]], t, t), OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=pd.Timedelta(hours=6)).any()
    if gap is not None and gap <= pd.Timedelta(hours=6):
        tail = f"It did start, {span(gap)} later" + (" (the feed was down for part of this window, so the real start may be earlier)." if down else ".")
    elif r["happened_6"] >= 0:
        tail = "No new alert started within 6 hours" + (f"; the next came {span(gap)} later." if gap is not None else ".")
    else:
        tail = "What happened next is not known (the data ends or the feed was down)."
    return f"{head} {tail}"


def plain_all(table, when):
    """One plain sentence for every oblast: who is highest within 1 hour, and how many alerts did start."""
    pct = lambda v: f"{100 * v:.0f}%"
    top = table.sort_values("model_1", ascending=False).head(3)
    names = ", ".join(f"{o.replace(' oblast', '')} {pct(v)}" for o, v in zip(top["oblast"], top["model_1"]))
    known = (table["happened_1"] >= 0).all()
    outcome = (f" A new alert did start within 1 hour in {int((table['happened_1'] == 1).sum())} of {len(table)} oblasts."
               if known else "")
    return (f"All {len(table)} oblasts, {when}: chance that a new alert starts within 1, 3 and 6 hours (table below). "
            f"Highest within 1 hour: {names}.{outcome}")


def main():
    ap = argparse.ArgumentParser(description="Probability of a new alert in the next 1, 3 and 6 hours, as the "
                                             "model would have said at a past hour, next to the baselines and "
                                             "what actually happened. Needs models/ from scripts/evaluate.py.")
    when = ap.add_mutually_exclusive_group(required=True)
    when.add_argument("--at", help='forecast origin, e.g. "2026-09-05 14:00" (UTC) or '
                                   '"2026-09-05 17:00+03:00"; rounded down to the hour')
    when.add_argument("--now", action="store_true", help="live forecast for the last completed hour from the Ukraine Alarm API (needs UA_ALARM_TOKEN in "
                                                          "the environment); every oblast unless --oblast is given")
    who = ap.add_mutually_exclusive_group()
    who.add_argument("--oblast", help='oblast name or a unique start of it, e.g. "Kyivska", "Kyiv City", "Lviv"')
    who.add_argument("--all", action="store_true", help="every oblast, one row each")
    args = ap.parse_args()
    if args.at and not (args.oblast or args.all):
        ap.error("--at needs --oblast or --all")
    if args.now:
        load_models()  # the frozen models must be there (scripts/evaluate.py writes them)
        from scripts.live_api import live_forecast
        sys.exit(live_forecast(args.oblast, lambda name, names: resolve_oblast(name, sorted(names))))

    info, boosters, freq = load_models()
    t, round_note = parse_origin(args.at)
    official, raions = load_inputs()
    oblasts = sorted(official["oblast"].unique())
    first, end = official["start"].min().ceil("D"), data_end(official)
    if (info["data_first"], info["data_end"]) != (first.isoformat(), end.isoformat()):
        fail("models/ was fitted on a different data snapshot. Run `python scripts/evaluate.py` again.")
    test_start = pd.Timestamp(info["test_start"])
    last = end - pd.Timedelta(hours=1)
    if not first <= t <= last:
        fail(f"--at must be between {first:%Y-%m-%d %H:%M} and {last:%Y-%m-%d %H:%M} UTC, the hours covered by "
             f"the official data in data/raw/.")
    chosen = [resolve_oblast(args.oblast, oblasts)] if args.oblast is not None else oblasts

    episodes, _ = official_episodes(official, raions=raions)
    table = forecast(t, official, raions, episodes, first, end, boosters, freq)
    table = table[table["oblast"].isin(chosen)].reset_index(drop=True)

    local = t.tz_convert(KYIV)
    when = f"{local:%H:%M} Kyiv time on {local.day} {local:%b}"
    pct = lambda v: f"{100 * v:.0f}%"
    yn = lambda v: {1: "yes", 0: "no", -1: "n/a"}[int(v)]
    if args.all:
        print(textwrap.fill(plain_all(table, when), 100))
    else:
        r = table.iloc[0]
        starts = episodes.loc[(episodes["oblast"] == r["oblast"]) & (episodes["start"] > t), "start"].sort_values()
        nxt = starts.iloc[0] if len(starts) and starts.iloc[0] < end else None
        print(textwrap.fill(plain_one(r, when, t, nxt), 100))
    if t < test_start:
        print("This hour was part of the training data, so this is not a real forecast.")
    print()
    print(f"{'All oblasts' if args.all else chosen[0]}, origin {t:%Y-%m-%d %H:%M} UTC ({local:%H:%M} Kyiv time)")
    for line in ([round_note] if round_note else []) + status_lines(t, first, end, test_start, oblasts[0]):
        print(line)
    print(f"Inputs: only alerts known at {t:%H:%M} UTC; neighbours from the hour before. Target: a new alert "
          "starts within the next H hours.")
    if args.all:
        print("Columns per H: model = LightGBM probability; yday = same hour yesterday; freq = train frequency; "
              "now = same as now (one column for all H);\nhappened = a new alert started (n/a: after the end "
              "of the data or in the feed outage).\n")
        out = pd.DataFrame({"oblast": table["oblast"].str.replace(" oblast", "", regex=False), "now": table["now"]})
        for H in HORIZONS:
            out[f"{H}h model"] = table[f"model_{H}"].map("{:.3f}".format)
            out[f"{H}h yday"] = table[f"yday_{H}"].map(lambda v: "n/a" if v < 0 else str(int(v)))
            out[f"{H}h freq"] = table[f"freq_{H}"].map("{:.3f}".format)
            out[f"{H}h happened"] = table[f"happened_{H}"].map(yn)
        print(out.to_string(index=False))
        return

    print(f"Under alert at {t:%H:%M} UTC: {yn(r['now'])}.\n")
    rows = [{"new alert within": f"{H} h", "model": f"{r[f'model_{H}']:.3f}", "same as now": int(r["now"]),
             "same hour yesterday": "n/a" if r[f"yday_{H}"] < 0 else int(r[f"yday_{H}"]),
             "train frequency": f"{r[f'freq_{H}']:.3f}", "happened": yn(r[f"happened_{H}"])} for H in HORIZONS]
    print(pd.DataFrame(rows).to_string(index=False))
    if any(r[f"happened_{H}"] < 0 or r[f"yday_{H}"] < 0 for H in HORIZONS):
        print("n/a: the window is after the end of the data or touches the feed outage.")
    if nxt is not None:
        gap = nxt - t
        after = f"{int(gap.total_seconds() // 3600)}:{int(gap.total_seconds() % 3600 // 60):02d}"
        caveat = (f" (the feed was down {OUTAGES}, so an earlier alert may be missing)"
                  if touches(make_rows([r["oblast"]], t, t), OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=gap).any() else "")
        print(f"\nNext new alert after {t:%H:%M} UTC: {nxt:%Y-%m-%d %H:%M} UTC, {after} later{caveat}.")
    else:
        print("\nNo new alert after this hour before the official data ends.")

if __name__ == "__main__":
    if hasattr(signal, "SIGPIPE"):  # `predict.py ... | head` exits quietly instead of a BrokenPipeError
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
