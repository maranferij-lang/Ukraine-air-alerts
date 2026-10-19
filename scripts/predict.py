"""What the model would have said at a past hour, from the data known at that hour only.

    python scripts/predict.py --at "2026-09-05 14:00" --oblast Kyivska
    python scripts/predict.py --at "2026-09-05 17:00+03:00" --all
    python scripts/predict.py --now                      (live, from the Ukraine Alarm API; needs UA_ALARM_TOKEN)
    python scripts/predict.py --now --oblast Kharkivska
    python scripts/predict.py --now --lang en            (the output and the map in English; Ukrainian is the default)

For origin t (a whole hour, UTC unless the time carries an offset) prints the probability that a new
alert starts in (t, t+H] for H = 1, 3, 6 (target (b)), from the LightGBM models scripts/evaluate.py
saved in models/, next to the three baselines and to what actually happened.

--now forecasts the last completed hour from the Ukraine Alarm API instead (scripts/live_api.py): it tops up data/api_archive/ (the days not saved yet and the last
three), refuses and names the missing days if it cannot get a complete history (no scaling, no filling), and prints every oblast's probability for H = 1, 3, 6 and whether
it is at or above the frozen threshold, sorted by H = 1. Needs your token in the environment variable UA_ALARM_TOKEN and the network; the models are the frozen ones.

Both --at and --now also write output/forecast_map.html (git-ignored): a self-contained map of all oblasts for the three horizons (scripts/forecast_map.py).

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
from src.i18n import MONTHS_UK, T, full_name, short_name, sort_key
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


def parse_origin(text, lang="en"):
    bad = f'Cannot read --at "{text}". Use e.g. "2026-09-05 14:00" (UTC) or "2026-09-05 17:00+03:00".'
    try:
        ts = pd.to_datetime(text, format="ISO8601")  # ISO only: "05.09.2026" would be read as 9 May
    except (ValueError, TypeError):
        fail(bad)
    if pd.isna(ts):
        fail(bad)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    t = ts.floor("h")
    note = None if t == ts else T("round_note", lang, t=t, ts=ts)
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


def status_lines(t, first, end, test_start, oblast_any, lang="en"):
    """Is t a forecast or a training hour, and is anything about its data unusual?"""
    one = make_rows([oblast_any], t, t)
    in_test = {H: bool(split(one, first, end, test_start, H, EVAL_LOOKBACK)["test"].iloc[0]) for H in HORIZONS}
    cutoff = f"{test_start:%Y-%m-%d %H:%M} UTC"
    tested = [H for H in HORIZONS if in_test[H]]
    if t < test_start:
        lines = [T("st_train", lang, cutoff=cutoff)]
    elif len(tested) == len(HORIZONS):
        lines = [T("st_after_all", lang, cutoff=cutoff)]
    elif tested:
        rest = [H for H in HORIZONS if not in_test[H]]
        lines = [T("st_after_some", lang, cutoff=cutoff, tested=", ".join(map(str, tested)), rest=", ".join(map(str, rest)))]
    else:
        lines = [T("st_after_none", lang, cutoff=cutoff)]
    if t - first < FEATURE_HISTORY:
        lines.append(T("st_short", lang))
    if touches(one, OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=pd.Timedelta(0)).any():
        lines.append(T("st_out_in", lang, outages=OUTAGES))
    elif touches(one, OFFICIAL_OUTAGES, before=EVAL_LOOKBACK, after=pd.Timedelta(0)).any():
        lines.append(T("st_out_24", lang, outages=OUTAGES))
    elif touches(one, OFFICIAL_OUTAGES, before=pd.Timedelta(days=7), after=pd.Timedelta(0)).any():
        lines.append(T("st_out_7", lang, outages=OUTAGES))
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


def span(gap, lang="en"):
    """'22 minutes', '1 h 20 min'"""
    mins = int(round(gap.total_seconds() / 60))
    if mins < 60:
        return T("span_min", lang, n=mins)
    if mins < 48 * 60:
        return T("span_hm", lang, h=mins // 60, m=mins % 60)
    return T("span_dh", lang, d=mins // 1440, h=mins % 1440 // 60)


def when_text(local, lang="en"):
    """'15:00 Kyiv time on 5 Sep' / '15:00 за київським часом, 5 вересня'"""
    month = MONTHS_UK[local.month - 1] if lang == "uk" else f"{local:%b}"
    return T("when", lang, hm=f"{local:%H:%M}", day=local.day, month=month)


def plain_one(r, when, t, nxt, lang="en"):
    """One plain sentence for one oblast: the three probabilities and what happened."""
    pct = lambda v: f"{100 * v:.0f}%"
    name = short_name(r["oblast"], lang)
    head = T("one_head", lang, name=name, when=when, p1=pct(r["model_1"]), p3=pct(r["model_3"]), p6=pct(r["model_6"]))
    gap = None if nxt is None else nxt - t
    down = touches(make_rows([r["oblast"]], t, t), OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=pd.Timedelta(hours=6)).any()
    if gap is not None and gap <= pd.Timedelta(hours=6):
        tail = T("one_started", lang, gap=span(gap, lang)) + (T("one_started_down", lang) if down else ".")
    elif r["happened_6"] >= 0:
        tail = T("one_none", lang) + (T("one_next", lang, gap=span(gap, lang)) if gap is not None else ".")
    else:
        tail = T("one_unknown", lang)
    return f"{head} {tail}"


def plain_all(table, when, lang="en"):
    """One plain sentence for every oblast: who is highest within 1 hour, and how many alerts did start."""
    pct = lambda v: f"{100 * v:.0f}%"
    top = table.sort_values("model_1", ascending=False).head(3)
    names = ", ".join(f"{short_name(o, lang)} {pct(v)}" for o, v in zip(top["oblast"], top["model_1"]))
    known = (table["happened_1"] >= 0).all()
    outcome = T("all_outcome", lang, k=int((table["happened_1"] == 1).sum()), n=len(table)) if known else ""
    return T("all_text", lang, n=len(table), when=when, names=names, outcome=outcome)


def write_replay_map(t, round_note, status, map_rows, lang="uk"):
    """output/forecast_map.html for a past hour: the round-13 model (models/), the status lines of this script, the forward-test calibration note."""
    from scripts import forecast_map
    from scripts.live_api import calibration_note, model_version, now_utc
    thr = {H: json.loads((MODELS / "frozen.json").read_text())["thresholds"][str(H)]["lgbm"] for H in HORIZONS}
    note = calibration_note("v1", lang, percent=True)  # the page shows probabilities as percent only
    notes = ([round_note] if round_note else []) + status + ([note] if note else [])
    forecast_map.write_or_warn(dict(origin=t, made=now_utc(), mode="replay", history=None, model="v1", version=model_version("v1"), thresholds=thr, notes=notes, rows=map_rows, lang=lang,
                                    model_text=T("map_replay", lang)))


def main():
    ap = argparse.ArgumentParser(description="Probability of a new alert in the next 1, 3 and 6 hours, as the "
                                             "model would have said at a past hour, next to the baselines and "
                                             "what actually happened. Needs models/ from scripts/evaluate.py.")
    when = ap.add_mutually_exclusive_group(required=True)
    when.add_argument("--at", help='forecast origin, e.g. "2026-09-05 14:00" (UTC) or '
                                   '"2026-09-05 17:00+03:00"; rounded down to the hour')
    when.add_argument("--now", action="store_true", help="live forecast for the last completed hour from the Ukraine Alarm API (needs UA_ALARM_TOKEN in "
                                                          "the environment); every oblast unless --oblast is given")
    ap.add_argument("--lang", choices=["en", "uk"], default="uk", help="language of the output and of the map: uk (Ukrainian, the default) or en (English); error messages stay English")
    ap.add_argument("--token-from-keychain", action="store_true", help="with --now: read the Ukraine Alarm token from the macOS keychain (item ukraine-air-alerts.ukrainealarm-token) instead of the environment variable; "
                                                                      "this is how the hourly job runs")
    ap.add_argument("--model", choices=["v1", "v2"], help="with --now: which model to use (default: the one the v2 decision rule chose, results/v2/decision.json)")
    who = ap.add_mutually_exclusive_group()
    who.add_argument("--oblast", help='oblast name or a unique start of it, e.g. "Kyivska", "Kyiv City", "Lviv"')
    who.add_argument("--all", action="store_true", help="every oblast, one row each")
    args = ap.parse_args()
    if args.at and not (args.oblast or args.all):
        ap.error("--at needs --oblast or --all")
    if args.token_from_keychain and not args.now:
        ap.error("--token-from-keychain only applies to --now")
    if args.model and not args.now:
        ap.error("--model only applies to --now (--at uses the round-13 model on the official data)")
    if args.now:
        load_models()  # the frozen models must be there (scripts/evaluate.py writes them)
        from scripts.live_api import live_forecast
        token = None
        if args.token_from_keychain:
            from src import keychain
            token = keychain.get("alarm_token")
            if not token:
                fail(f"Cannot read the Ukraine Alarm token from the keychain (item {keychain.SERVICES['alarm_token']}). Put it there first, see docs/DETAILS.md, section \"The alert bot\".")
        sys.exit(live_forecast(args.oblast, lambda name, names: resolve_oblast(name, sorted(names)), args.model, args.lang, token))

    info, boosters, freq = load_models()
    lang = args.lang
    t, round_note = parse_origin(args.at, lang)
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
    map_rows = [{"oblast": r.oblast, "now": bool(r.now), "p": {H: float(getattr(r, f"model_{H}")) for H in HORIZONS}} for r in table.itertuples()]  # all 24, whatever is chosen
    table = table[table["oblast"].isin(chosen)].reset_index(drop=True)
    if lang == "uk":  # the table is in alphabetical order of the names shown, which is not the English order
        table = table.iloc[sorted(range(len(table)), key=lambda i: sort_key(short_name(table["oblast"][i], "uk"), "uk"))].reset_index(drop=True)

    local = t.tz_convert(KYIV)
    when = when_text(local, lang)
    hm = f"{local:%H:%M}"
    yn = lambda v: {1: T("yes", lang), 0: T("no", lang), -1: T("na", lang)}[int(v)]
    status = status_lines(t, first, end, test_start, oblasts[0], lang)
    if args.all:
        print(textwrap.fill(plain_all(table, when, lang), 100))
    else:
        r = table.iloc[0]
        starts = episodes.loc[(episodes["oblast"] == r["oblast"]) & (episodes["start"] > t), "start"].sort_values()
        nxt = starts.iloc[0] if len(starts) and starts.iloc[0] < end else None
        print(textwrap.fill(plain_one(r, when, t, nxt, lang), 100))
    if t < test_start:
        print(T("training_note", lang))
    print()
    print(T("at_header", lang, who=T("all_oblasts", lang) if args.all else full_name(chosen[0], lang), t=t, hm=hm))
    for line in ([round_note] if round_note else []) + status:
        print(line)
    print(T("inputs", lang, t=t))
    if args.all:
        print(T("columns_help", lang))
        out = pd.DataFrame({T("col_oblast", lang): table["oblast"].map(lambda o: short_name(o, lang)), T("col_now", lang): table["now"]})
        for H in HORIZONS:
            out[T("col_model", lang, H=H)] = table[f"model_{H}"].map("{:.3f}".format)
            out[T("col_yday", lang, H=H)] = table[f"yday_{H}"].map(lambda v: T("na", lang) if v < 0 else str(int(v)))
            out[T("col_freq", lang, H=H)] = table[f"freq_{H}"].map("{:.3f}".format)
            out[T("col_happened", lang, H=H)] = table[f"happened_{H}"].map(yn)
        print(out.to_string(index=False))
        write_replay_map(t, round_note, status, map_rows, lang)
        return

    print(T("under_alert_at", lang, t=t, yn=yn(r["now"])))
    c = T("one_cols", lang)
    rows = [{c[0]: T("one_h", lang, H=H), c[1]: f"{r[f'model_{H}']:.3f}", c[2]: int(r["now"]),
             c[3]: T("na", lang) if r[f"yday_{H}"] < 0 else int(r[f"yday_{H}"]),
             c[4]: f"{r[f'freq_{H}']:.3f}", c[5]: yn(r[f"happened_{H}"])} for H in HORIZONS]
    print(pd.DataFrame(rows).to_string(index=False))
    if any(r[f"happened_{H}"] < 0 or r[f"yday_{H}"] < 0 for H in HORIZONS):
        print(T("na_note", lang))
    if nxt is not None:
        gap = nxt - t
        after = f"{int(gap.total_seconds() // 3600)}:{int(gap.total_seconds() % 3600 // 60):02d}"
        caveat = (T("next_caveat", lang, outages=OUTAGES)
                  if touches(make_rows([r["oblast"]], t, t), OFFICIAL_OUTAGES, before=pd.Timedelta(0), after=gap).any() else "")
        print(T("next_alert", lang, t=t, nxt=nxt, after=after, caveat=caveat))
    else:
        print(T("no_next", lang))
    write_replay_map(t, round_note, status, map_rows, lang)

if __name__ == "__main__":
    if hasattr(signal, "SIGPIPE"):  # `predict.py ... | head` exits quietly instead of a BrokenPipeError
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
