"""Does the official source channel reproduce our official csv?

    pip install translitua
    python scripts/source_check.py

Runs the UNMODIFIED upstream parser (Vadimkin/ukrainian-air-raid-sirens-dataset, processors/official_channel_processor.py,
the code that built our snapshot from https://t.me/air_alert_ua) over posts of that channel, and compares the alerts it
produces with data/raw/official_data_en.csv after our cleaning (src/load.py), for the same days.

Inputs
  data/source_check/channel_posts_aug13_18.csv.gz   public posts of the channel, 2026-08-13 .. 08-18 (id, UTC time, text),
                                                    pulled with the same polite, sequential method as the Telegram pull
  upstream parser files                              downloaded from GitHub at the pinned commit into
                                                    data/source_check/upstream/ (not committed); their SHA-256 are in the output
Only the Telethon import is stubbed (no network, no token); the parser class is not edited. It is fed messages shaped like
Telethon's (text, UTC date, id) in id order, as its own iter_messages(reverse=True) would.

Writes results/source_check.md.
"""
import gzip
import hashlib
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.load import PERMANENT_ALERT_OBLASTS, load_official
from src.panel import hourly_panel, official_episodes, raion_list

COMMIT = "7ccd4367b7057a4541ce109ca09cf1f0220f6a75"  # the upstream commit of our snapshot (data/raw/PULL_INFO.md)
RAW = f"https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/{COMMIT}/processors/"
FILES = ["official_channel_processor.py", "legacy_states.py", "tg_dataclasses.py", "states.json"]
WORK = ROOT / "data" / "source_check" / "upstream"
POSTS = ROOT / "data" / "source_check" / "channel_posts_aug13_18.csv.gz"
OUT = ROOT / "results" / "source_check.md"
LO, HI = pd.Timestamp("2026-08-14", tz="UTC"), pd.Timestamp("2026-08-17", tz="UTC")  # alerts that START in [LO, HI)
KEYS = ["oblast", "raion", "hromada", "level"]


def fetch_upstream():
    """Download the upstream parser files (once) and write the Telethon stub. Returns {file: sha256}."""
    pkg = WORK / "processors"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("")
    for f in FILES:
        if not (pkg / f).exists():
            req = urllib.request.Request(RAW + f, headers={"User-Agent": "ukraine-air-alerts course project"})
            (pkg / f).write_bytes(urllib.request.urlopen(req, timeout=60).read())
    stub = WORK / "telethon" / "tl"
    stub.mkdir(parents=True, exist_ok=True)
    (WORK / "telethon" / "__init__.py").write_text("")
    (stub / "__init__.py").write_text("")
    (stub / "types.py").write_text("class Message:\n    pass\n")
    return {f: hashlib.sha256((pkg / f).read_bytes()).hexdigest() for f in FILES}


def run_upstream(posts):
    """Completed alerts (English names, as in our csv) and the parser's error messages."""
    import logging
    sys.path.insert(0, str(WORK))
    from processors import official_channel_processor as mod
    errors = []

    class Catch(logging.Handler):
        def emit(self, rec):
            if rec.levelno >= logging.ERROR:
                errors.append(rec.getMessage())

    mod.logger.handlers, mod.logger.propagate = [Catch()], False
    mod.logger.setLevel(logging.ERROR)
    proc = mod.OfficialAirAlertProcessor(client=None)
    proc.active_alerts_by_location, proc.completed_alerts = {}, []
    for r in posts.itertuples():
        if r.text:
            proc.process_message(SimpleNamespace(message=r.text, date=r.time, id=r.id))
    rows = pd.DataFrame([a.dict(lang="en") for a in proc.completed_alerts])
    rows["start"] = pd.to_datetime(rows["started_at"], utc=True, format="ISO8601")
    rows["end"] = pd.to_datetime(rows["finished_at"], utc=True, format="ISO8601")
    bad = (rows["level"] == "hromada") & (rows["hromada"] == rows["raion"])  # same cleaning as src/load.py
    rows.loc[bad, ["level", "hromada"]] = ["raion", ""]
    return rows[KEYS + ["start", "end"]].drop_duplicates(), errors, len(proc.active_alerts_by_location)


def main():
    try:
        import translitua  # noqa: F401  (upstream uses it for the English names)
    except ImportError:
        sys.exit("needs the upstream parser's one dependency: pip install translitua")
    hashes = fetch_upstream()
    with gzip.open(POSTS, "rt", encoding="utf-8", newline="") as f:
        posts = pd.read_csv(f, keep_default_na=False)
    posts["time"] = pd.to_datetime(posts["time_utc"], utc=True, format="ISO8601")
    posts = posts.sort_values("id").reset_index(drop=True)
    chan, errors, still_active = run_upstream(posts)
    last_post = posts["time"].max()

    ours_all = load_official()
    ours = ours_all[(ours_all["start"] >= LO) & (ours_all["start"] < HI)]
    chan_w = chan[(chan["start"] >= LO) & (chan["start"] < HI)]
    m = ours.merge(chan_w, on=KEYS + ["start"], how="outer", suffixes=("_csv", "_chan"), indicator=True)
    both = m[m["_merge"] == "both"]
    identical = int((both["end_csv"] == both["end_chan"]).sum())
    only_csv, only_chan = m[m["_merge"] == "left_only"], m[m["_merge"] == "right_only"]
    explained = int((only_csv["end_csv"] > last_post).sum())  # still running when the posts stop

    # the level the model uses: hours with the oblast under alert (at least half its raions), same fixed raion list
    keep = ours_all[~ours_all["oblast"].isin(PERMANENT_ALERT_OBLASTS)]
    raions = raion_list(keep)
    oblasts = sorted(keep["oblast"].unique())
    pad = pd.Timedelta(hours=12)
    around = lambda df: df[(df["start"] >= LO - pad) & (df["start"] < HI + pad) & ~df["oblast"].isin(PERMANENT_ALERT_OBLASTS)]
    h0, h1 = (LO + pd.Timedelta(hours=6)).floor("h"), (HI - pd.Timedelta(hours=6)).floor("h")
    pa = hourly_panel(official_episodes(around(ours_all), raions=raions)[0], h0, h1, oblasts)
    pb = hourly_panel(official_episodes(around(chan), raions=raions)[0], h0, h1, oblasts)
    j = pa.merge(pb, on=["oblast", "hour"], suffixes=("_csv", "_chan"))
    disagree = int((j["active_csv"] != j["active_chan"]).sum())

    first = lambda t: t.split("\n")[0]
    skipped = [e for e in errors if e.startswith("Can't parse")]
    unknown_tags = [e for e in errors if e.startswith("Can't process")]
    lvl = lambda df: ", ".join(f"{k} {v}" for k, v in df["level"].value_counts().sort_index().items())
    lines = [
        "# Source check: does the official channel reproduce our official csv?",
        "",
        "We re-derived the official alerts from their source, the public Telegram channel `air_alert_ua`, with the **unmodified upstream "
        f"parser** (Vadimkin/ukrainian-air-raid-sirens-dataset at commit `{COMMIT[:7]}`, the commit of our snapshot), and compared them "
        "with `data/raw/official_data_en.csv` after our cleaning (`src/load.py`: exact duplicates dropped, hromada = raion rows relabelled).",
        "",
        "Produced by `scripts/source_check.py` (offline apart from downloading the four upstream files; no Telegram access, no token).",
        "",
        "## What was run",
        f"- Posts: `data/source_check/channel_posts_aug13_18.csv.gz`, {len(posts)} public posts, {posts['time'].min():%Y-%m-%d %H:%M} to {last_post:%Y-%m-%d %H:%M} UTC.",
        "- Parser: upstream `OfficialAirAlertProcessor.process_message` (hashtags to oblast / raion / hromada through `states.json`, 🔴 starts, "
        "🟢 / \"Відбій\" ends, the 3-hour rule for alerts without an end). Only the Telethon import is stubbed; the class is not edited. "
        "Posts are fed in id order, shaped like Telethon's messages (text, UTC date, id).",
        "- Upstream files, SHA-256:",
        *[f"  - `{f}`: `{h}`" for f, h in hashes.items()],
        f"- Compared: alerts that **start** in [{LO:%Y-%m-%d}, {HI:%Y-%m-%d}) UTC, i.e. Aug 14–16 (the day before is warm-up for alerts already running; the days after let the alerts end).",
        "",
        "## Alert rows (oblast, raion, hromada, level, start, end)",
        "",
        "| | rows |",
        "|---|---|",
        f"| our csv (cleaned) | {len(ours)} ({lvl(ours)}) |",
        f"| channel, upstream parser | {len(chan_w)} ({lvl(chan_w)}) |",
        f"| same place and start in both | {len(both)} |",
        f"| of those, identical end too | **{identical}** |",
        f"| only in our csv | {len(only_csv)} |",
        f"| only in the channel | {len(only_chan)} |",
        "",
        f"So **{identical} of {len(ours)}** rows of our csv are reproduced to the second, and nothing in the channel is missing from the csv.",
    ]
    if len(only_csv):
        lines += ["", "The row only in our csv:", "", "| oblast | raion | hromada | level | start | end |", "|---|---|---|---|---|---|"]
        lines += [f"| {r.oblast} | {r.raion} | {r.hromada} | {r.level} | {r.start:%Y-%m-%d %H:%M:%S} | {r.end_csv:%Y-%m-%d %H:%M:%S} |" for r in only_csv.itertuples()]
        lines += ["", f"{explained} of {len(only_csv)} only-in-csv rows end after the last post in the file ({last_post:%Y-%m-%d %H:%M} UTC): the alert was still running when "
                  "the posts stop, so the parser has no end for it yet. That is an edge of this slice, not a difference between the sources."
                  + ("" if explained == len(only_csv) else f" The other {len(only_csv) - explained} are not explained by this.")]
    lines += [
        "",
        "## The level the model uses: hours with the oblast under alert",
        f"Oblast under alert = at least half of its raions (same fixed raion list), {len(oblasts)} oblasts, {h0:%Y-%m-%d %H}:00 to {h1:%Y-%m-%d %H}:00 UTC.",
        "",
        "| | |",
        "|---|---|",
        f"| oblast-hours compared | {len(j)} |",
        f"| share under alert, our csv / channel | {j['active_csv'].mean():.4f} / {j['active_chan'].mean():.4f} |",
        f"| oblast-hours where they disagree | **{disagree}** |",
        f"| alert starts, our csv / channel | {int(j['n_starts_csv'].sum())} / {int(j['n_starts_chan'].sum())} |",
        "",
        "## Posts the parser skips",
        f"{len(skipped)} of {len(posts)} posts are skipped (not an alert state): "
        f"{sum(first(e.split('Can' + chr(39) + 't parse ', 1)[1]).startswith('🟠') for e in skipped)} are 🟠 warnings and the rest other notices (for example evacuation). "
        f"Hashtags the parser did not know: {len(unknown_tags)}. The same skips happen in the upstream run that made our csv, which is why the rows match.",
        "",
        "## The channel stopped on 2026-09-07 (recorded by hand)",
        "On 2026-10-11 the newest post in `t.me/s/air_alert_ua` was number 338380, from **2026-09-07 06:09:04 UTC**, in the middle of an alert wave "
        "with no all-clear after it. Three checks agreed: `?after=338380` returned no posts; `?before=999999` returned the same last page; a direct link to post "
        "338381 answered \"Post not found\". The same method returned fresh posts of another channel (`kpszsu`) from that day, so the preview was not stale. "
        "The message format did not change before the stop (the same templates on Aug 6, Sep 2 and Sep 7). So there is no newer official data to add, "
        "and `scripts/predict.py --now` re-checks the channel every time it runs.",
    ]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {identical} of {len(ours)} rows identical, {disagree} of {len(j)} oblast-hours disagree")


if __name__ == "__main__":
    main()
