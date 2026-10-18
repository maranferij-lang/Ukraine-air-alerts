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
from src.i18n import T, short_name
from src.panel import official_episodes
from src.targets import make_rows

ARCHIVE = ROOT / "data" / "api_archive" / "date_history"
MODEL_DIRS = {"v1": ROOT / "models", "v2": ROOT / "models" / "v2"}
DECISION = ROOT / "results" / "v2" / "decision.json"
PRED_LOG = ROOT / "data" / "predictions" / "log.csv"
LAST_FORECAST = ROOT / "output" / "last_forecast.json"   # the hand-off to scripts/alert_bot.py: the whole forecast of the last --now run (no secrets in it)
PRED_COLUMNS = ["origin_utc", "oblast", "h", "probability", "above_threshold", "threshold", "model_version", "run_time_utc"]
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


def default_model():
    """The model `predict.py --now` uses unless --model says otherwise: what the v2 decision rule chose (results/v2/decision.json); v1 if there is no decision."""
    try:
        return json.loads(DECISION.read_text())["use"]
    except Exception:
        return "v1"


def model_version(model="v1"):
    """A short fingerprint of the frozen models a forecast came from: SHA-256 of the three LightGBM files and frozen.json of that model."""
    import hashlib
    d = MODEL_DIRS[model]
    h = hashlib.sha256()
    for name in [f"lgbm_b_start_h{H}.txt" for H in HORIZONS] + ["frozen.json"]:
        h.update((d / name).read_bytes())
    return ("frozen-r13-" if model == "v1" else "frozen-v2-") + h.hexdigest()[:12]


def append_prediction_log(origin, oblasts, prob, thr, version, run_time, path=None):
    """Append this run's forecast (every oblast, every H) to the prediction log. Append only: the file is opened for appending, never rewritten,
    and nothing is written if an existing file has a different header. Returns the number of rows appended."""
    import csv
    path = Path(path or PRED_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        with open(path, newline="") as fh:
            header = next(csv.reader(fh), None)
        if header != PRED_COLUMNS:
            raise SystemExit(f"{path} has an unexpected header; nothing was appended.")
    rows = [[f"{origin:%Y-%m-%dT%H:%M:%SZ}", ob, H, f"{prob[H][i]:.8f}", int(prob[H][i] >= thr[H]), f"{thr[H]:.8f}", version, f"{run_time:%Y-%m-%dT%H:%M:%SZ}"]
            for i, ob in enumerate(oblasts) for H in HORIZONS]
    new = not (path.exists() and path.stat().st_size)
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        if new:
            w.writerow(PRED_COLUMNS)
        w.writerows(rows)
    return len(rows)


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


def calibration_note(model="v1", lang="en", percent=False):
    """One line about calibration from the model's own evaluation table: v1: the forward test; v2: its held-out test window. None if the table is not there."""
    path, label, name = ((ROOT / "results" / "forward_api" / "calibration.md", T("cal_v1", lang), "LightGBM") if model == "v1"
                         else (ROOT / "results" / "v2" / "calibration.md", T("cal_v2", lang), "v2 LightGBM"))
    try:
        text = path.read_text(encoding="utf-8")
        rows = {}
        section = text.split("## Calibration in the large")[1].split("\n## ")[0] if model == "v1" else text.split("\n## ")[0]  # the first table only
        for line in section.split("\n"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[1] == name and cells[0] in ("1", "3", "6"):
                rows[int(cells[0])] = (float(cells[2]), float(cells[3]))
        assert len(rows) == 3
    except Exception:
        return None
    low = all(rows[H][0] < rows[H][1] for H in HORIZONS)
    high = all(rows[H][0] > rows[H][1] for H in HORIZONS)
    word = T("cal_low", lang) if low else T("cal_high", lang) if high else T("cal_mid", lang)
    return T("cal_note", lang, label=label, word=word, items=", ".join(T("cal_item_pct", lang, p=100 * rows[H][0], o=100 * rows[H][1], H=H) if percent else T("cal_item", lang, p=rows[H][0], o=rows[H][1], H=H) for H in HORIZONS),
             tail=T("cal_tail_low", lang) if low else T("cal_tail", lang))


def ago(now, ts, lang="en", whole_hours=False):
    """How long before `now` an API timestamp is: 'just now' for anything under a minute, and also for a timestamp ahead of our clock (the API's clock may run ahead of ours)."""
    d = (now - ts).total_seconds()
    if d < 60:
        return T("ago_now", lang)
    return T("ago_min", lang, n=d / 60) if d < 3 * 3600 else T("ago_h_whole" if whole_hours else "ago_h", lang, n=d / 3600)


def forward_test_note(lang="en"):
    return calibration_note("v1", lang)


def write_last_forecast(origin, made, model, version, thresholds, rows, path=None):
    """Write the last --now forecast as JSON (atomically): origin and make time (UTC), model and fingerprint, the frozen thresholds and, per oblast, the probability for 1, 3, 6 h
    and whether an alert is running at the origin hour. scripts/alert_bot.py reads this file; it is git-ignored and holds no secret."""
    import os
    path = Path(path or LAST_FORECAST)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"origin": f"{pd.Timestamp(origin).tz_convert('UTC'):%Y-%m-%dT%H:%M:%SZ}", "made": f"{pd.Timestamp(made).tz_convert('UTC'):%Y-%m-%dT%H:%M:%SZ}", "model": model, "version": version,
           "thresholds": {str(H): float(thresholds[H]) for H in HORIZONS},
           "rows": [{"oblast": r["oblast"], "now": bool(r["now"]), "p": {str(H): float(r["p"][H]) for H in HORIZONS}} for r in rows]}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def refuse(lines):
    print("\n".join(lines))
    return 1


def live_forecast(oblast=None, resolve=None, model=None, lang="uk", token=None):
    """Forecast for the last completed hour from the API. Returns the exit code (0 = forecast printed, 1 = refused). `oblast`: show one oblast only
    (resolve turns the typed name into one of ours). `token`: the Ukraine Alarm token if the caller has it (the hourly job: from the keychain); else the environment variable."""
    import textwrap
    from datetime import timedelta
    from scripts import archive_api
    from scripts.forward_test import load_frozen
    from src.ukrainealarm import Client

    model = model or default_model()
    if not (MODEL_DIRS[model] / "info.json").exists():
        return refuse([f"Cannot forecast now: the {model} model files are missing ({MODEL_DIRS[model].relative_to(ROOT)}/).",
                       "Make them with: python scripts/evaluate.py" if model == "v1" else "Make them with: python scripts/build_combined.py, then python scripts/train_v2.py"])
    info, frozen, boosters, freq = load_frozen(MODEL_DIRS[model])
    raions, oblasts = inputs()
    want = resolve(oblast, oblasts).replace(" oblast", "") if oblast else None  # a bad name stops here, before any request
    now = now_utc()
    t = origin_for(now)
    days = needed_days(t)
    today = now.date()
    refetch_from = today - timedelta(days=REFETCH_DAYS - 1)
    c = Client(token=token)

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
    table = pd.DataFrame({"oblast": rows_t["oblast"].str.replace(" oblast", "", regex=False), "now": feats[1]["now"].to_numpy() > 0, "full": rows_t["oblast"]})
    for H in HORIZONS:
        table[f"p{H}"] = prob[H]
        table[f"o{H}"] = prob[H] >= thr[H]
    map_rows = [{"oblast": ob, "now": bool(nw), "p": {H: float(prob[H][i]) for H in HORIZONS}}
                for i, (ob, nw) in enumerate(zip(rows_t["oblast"], feats[1]["now"].to_numpy() > 0))]  # all 24, whatever --oblast shows
    n_logged = append_prediction_log(t, list(rows_t["oblast"]), prob, thr, model_version(model), now)  # the whole forecast, whatever is shown below
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
    def fresh_text(whole_hours):
        return (T("fresh_head", lang, now=now, start=newest_start, ago=ago(now, newest_start, lang, whole_hours))
                + (T("fresh_end", lang, end=newest_end) if newest_end is not None else "")
                + (T("fresh_upd", lang, upd=max(upd), ago=ago(now, max(upd), lang, whole_hours)) if upd else "")
                + T("fresh_tail", lang))
    fresh = fresh_text(False)
    fresh_page = fresh_text(True)  # the page shows no decimal numbers anywhere, so "3 h" and not "3.0 h"
    local = t.tz_convert(KYIV)
    model_text = T("model_v1" if model == "v1" else "model_v2", lang)
    print(textwrap.fill(T("live_head", lang, t=t, hm=f"{local:%H:%M}", model_text=model_text), 100))
    print()
    print(textwrap.fill(fresh, 100))
    left_out = ""
    if dropped["district not in our raion list"]:
        left_out = T("left_out", lang, names=", ".join(sorted(dropped["district not in our raion list"])))
        print(textwrap.fill(left_out, 100))
    note = calibration_note(model, lang)
    if note:
        print()
        print(textwrap.fill(note, 100))
    print()
    print(T("above_help", lang, thr=", ".join(T("thr_item", lang, H=H, v=thr[H]) for H in HORIZONS)))
    yn = lambda v: T("yes", lang) if v else T("no", lang)
    rows_out = []
    for _, r in table.iterrows():
        row = [short_name(r["full"], lang), yn(r["now"])]
        for H in HORIZONS:
            row += [f"{r[f'p{H}']:.3f}", yn(r[f"o{H}"])]
        rows_out.append(row)
    print(pd.DataFrame(rows_out, columns=T("live_cols", lang)).to_string(index=False))
    print(T("logged", lang, n=n_logged, path=PRED_LOG.relative_to(ROOT) if PRED_LOG.is_relative_to(ROOT) else PRED_LOG))
    from scripts import forecast_map
    note_page = calibration_note(model, lang, percent=True)  # the page shows probabilities as percent only
    notes = [fresh_page] + ([left_out] if left_out else []) + ([note_page] if note_page else [])
    forecast_map.write_or_warn(dict(origin=t, made=now, mode="live", model=model, version=model_version(model), model_text=T("map_live", lang) + model_text,
                                    thresholds=thr, notes=notes, rows=map_rows, lang=lang,
                                    history=forecast_map.history_from_log(PRED_LOG, model_version(model))))  # the log already has this run
    try:
        write_last_forecast(t, now, model, model_version(model), thr, map_rows)
    except OSError as e:  # the forecast is already printed and logged; the bot just has nothing new to read
        print(f"last_forecast.json not written: {type(e).__name__}", file=sys.stderr)
    return 0
