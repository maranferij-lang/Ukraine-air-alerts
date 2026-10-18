"""Consistency check: does the Ukraine Alarm API history agree with our official data? (same idea as source_check.py)

    python scripts/api_check.py                                  reads data/api_archive/date_history/*.json
    python scripts/api_check.py --dir data/api_raw               reads date_history_YYYYMMDD.json files from another folder

Offline: it only reads the saved API answers (scripts/archive_api.py or scripts/api_probe.py write them) and our csv. Needs
`pip install translitua` (the upstream parser's package, used to turn the API's Ukrainian district names into our English raion names).

The API's `dateHistory` for a UTC day holds every alert that was active on that day (also those that started the day before), so the
union of the saved days is complete for the days that have a file. Mapping, by name: "... район" -> raion (transliterated, must be one of
our 118 raions), "м. Київ" and "... область" -> oblast level, "... територіальна громада" and other "м. ..." -> hromada (dropped, as in
src/panel.py), only alertType AIR is kept. Then the same rules as for the official data: raion rows -> oblast under alert when at least
half of its raions are -> restarts within 5 minutes joined (src/panel.py), the same fixed raion list. Compared on the days that have a file,
outside the official feed's outage and before its trusted end. Writes results/api_check.md.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.load import OFFICIAL_OUTAGES, PERMANENT_ALERT_OBLASTS, data_end, load_official
from src.panel import hourly_panel, official_episodes, raion_list
from src.ukrainealarm import RAION_ALIASES, our_name

DEFAULT_DIR = ROOT / "data" / "api_archive" / "date_history"
OUT = ROOT / "results" / "api_check.md"
PAD = pd.Timedelta(days=3)  # rows around the compared days, so alerts running across the edges are whole


def day_files(folder):
    out = {}
    for f in sorted(folder.glob("*.json")):
        m = re.search(r"(\d{8})\.json$", f.name)
        if m:
            out[pd.Timestamp(m.group(1), tz="UTC")] = f
    return out


def load_api(files):
    rows = []
    for day, f in files.items():
        for a in json.loads(f.read_text(encoding="utf-8")):
            rows.append({"regionId": a.get("regionId"), "name": a.get("regionName") or "", "start": a.get("startDate"),
                         "end": a.get("endDate"), "type": a.get("alertType"), "open": bool(a.get("isContinue"))})
    df = pd.DataFrame(rows)
    df["start"] = pd.to_datetime(df["start"], utc=True, format="ISO8601", errors="coerce")
    df["end"] = pd.to_datetime(df["end"], utc=True, format="ISO8601", errors="coerce")
    return df


def to_official_rows(api, raions):
    """API alerts -> our official-row schema, plus a count of what was dropped and why."""
    from translitua import UkrainianKMU, translit
    raion_oblast = raions.set_index("raion")["oblast"]
    oblast_names = set(raions["oblast"]) | {"Kyiv City"}
    n = {"api rows": len(api)}
    api = api.drop_duplicates(["regionId", "start", "end", "type"]).sort_values("end")
    api = api.drop_duplicates(["regionId", "start", "type"], keep="last")  # the same alert in two days' files: keep the later end
    n["after joining the days' files"] = len(api)
    air = api[api["type"] == "AIR"]
    n["not AIR (dropped)"] = len(api) - len(air)
    closed = air[air["end"].notna() & (air["end"].dt.year > 2000) & ~air["open"]]
    n["still open or without an end (dropped)"] = len(air) - len(closed)
    rows, dropped = [], {"hromada level (not used by the rule)": 0, "district not in our raion list": {}, "other name": {},
                         "oblast not in our data (Crimea, Sevastopol, Luhansk)": 0}
    for r in closed.itertuples():
        name = " ".join(r.name.split())
        if name.endswith("район"):
            raion = translit(name, UkrainianKMU)
            raion = RAION_ALIASES.get(raion, raion)
            if raion in raion_oblast.index:
                rows.append((raion_oblast[raion], raion, "", "raion", r.start, r.end))
            else:
                dropped["district not in our raion list"][name] = dropped["district not in our raion list"].get(name, 0) + 1
        elif "територіальна громада" in name or (name.startswith("м. ") and name != "м. Київ"):
            dropped["hromada level (not used by the rule)"] += 1
        elif name == "м. Київ" or name.endswith("область") or name.endswith("Республіка Крим"):
            ob = our_name(name)
            if ob in oblast_names:
                rows.append((ob, "", "", "oblast", r.start, r.end))
            else:
                dropped["oblast not in our data (Crimea, Sevastopol, Luhansk)"] += 1
        else:
            dropped["other name"][name] = dropped["other name"].get(name, 0) + 1
    out = pd.DataFrame(rows, columns=["oblast", "raion", "hromada", "level", "start", "end"])
    n["raion rows"] = int((out["level"] == "raion").sum())
    n["oblast-level rows"] = int((out["level"] == "oblast").sum())
    return out.sort_values("start", kind="stable").reset_index(drop=True), n, dropped


def match(a, b, key, tol):
    """How many rows of a have a row of b with the same key and a start within tol (nearest)."""
    a = a.sort_values("start").reset_index(drop=True)
    b = b.sort_values("start")[[key, "start", "end"]].rename(columns={"start": "start_b", "end": "end_b"})
    m = pd.merge_asof(a[[key, "start", "end"]], b.assign(start=b["start_b"]).sort_values("start"), on="start", by=key,
                      direction="nearest", tolerance=tol)
    return m


def main():
    ap = argparse.ArgumentParser(description="Compare the saved Ukraine Alarm API days with our official data.")
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="folder with the saved dateHistory files")
    ap.add_argument("--out", type=Path, default=OUT, help="where to write the report (default results/api_check.md)")
    args = ap.parse_args()
    try:
        import translitua  # noqa: F401
    except ImportError:
        sys.exit("needs one package: pip install translitua")
    files = day_files(args.dir)
    if not files:
        sys.exit(f"no dateHistory files in {args.dir}")

    official_all = load_official()
    keep = official_all[~official_all["oblast"].isin(PERMANENT_ALERT_OBLASTS)]
    raions, oblasts = raion_list(keep), sorted(keep["oblast"].unique())
    end_ok = data_end(keep)

    days = sorted(files)
    first_day, last_day = days[0], days[-1] + pd.Timedelta(days=1)
    gaps = [d for d in pd.date_range(days[0], days[-1], freq="D") if d not in files]
    api_rows, n_api, dropped = to_official_rows(load_api(files), raions)
    lo, hi = first_day - PAD, last_day + PAD
    around = lambda df: df[(df["start"] >= lo) & (df["start"] < hi)]

    ep_o, _ = official_episodes(around(keep), raions=raions)
    ep_a, _ = official_episodes(around(api_rows[api_rows["oblast"].isin(oblasts)]), raions=raions)

    # hours compared: UTC days with a file, outside the official outage, before the official trusted end
    h = pd.date_range(first_day, last_day, freq="h", inclusive="left")
    in_file = pd.Series(h.floor("D").isin(days), index=h)
    outage = pd.Series(False, index=h)
    for a, b in OFFICIAL_OUTAGES:
        outage |= (h >= pd.Timestamp(a, tz="UTC")) & (h < pd.Timestamp(b, tz="UTC"))
    ok_hours = set(h[in_file.to_numpy() & ~outage.to_numpy() & (h < end_ok)])
    po = hourly_panel(ep_o, first_day, last_day, oblasts)
    pa = hourly_panel(ep_a, first_day, last_day, oblasts)
    j = po.merge(pa, on=["oblast", "hour"], suffixes=("_off", "_api"))
    j = j[j["hour"].isin(ok_hours)]
    N = len(j)
    act_dis = j["active_off"] != j["active_api"]
    st_off, st_api = j["n_starts_off"] > 0, j["n_starts_api"] > 0
    st_dis = st_off != st_api
    per = j.assign(act_dis=act_dis, st_dis=st_dis, off_only=act_dis & j["active_off"], api_only=act_dis & j["active_api"]).groupby("oblast").agg(
        hours=("hour", "size"), active_disagree=("act_dis", "sum"), official_only=("off_only", "sum"), api_only=("api_only", "sum"),
        start_disagree=("st_dis", "sum"))

    dd = j.assign(day=j["hour"].dt.strftime("%Y-%m-%d"), a=act_dis, s=st_dis)
    dd = dd[dd["a"] | dd["s"]]
    by_day = (dd.groupby("day").agg(a=("a", "sum"), s=("s", "sum"), o=("oblast", "nunique"))
              .sort_values(["a", "s"], ascending=False).head(5)) if len(dd) else pd.DataFrame(columns=["a", "s", "o"])

    # alert rows (raion level) and oblast episodes, for alerts that start on compared days
    def in_scope(df):
        s = df["start"]
        return df[(s >= first_day) & (s < last_day) & s.dt.floor("h").isin(ok_hours)]

    ro = in_scope(keep[keep["level"] == "raion"])
    ra = in_scope(api_rows[(api_rows["level"] == "raion") & api_rows["oblast"].isin(oblasts)])
    mo = {t: match(ro, ra, "raion", pd.Timedelta(seconds=t)) for t in (5, 60)}
    mb = {t: match(ra, ro, "raion", pd.Timedelta(seconds=t)) for t in (5, 60)}
    both60 = mo[60].dropna(subset=["start_b"])
    end_close = int(((both60["end"] - both60["end_b"]).abs() <= pd.Timedelta(seconds=60)).sum())
    eo, ea = in_scope(ep_o), in_scope(ep_a)
    em = {t: match(eo, ea, "oblast", pd.Timedelta(seconds=t)) for t in (60, 300, 3600)}
    emb = {t: match(ea, eo, "oblast", pd.Timedelta(seconds=t)) for t in (60, 300, 3600)}
    cnt = lambda m: int(m["start_b"].notna().sum())

    outage_ep = [(a, b) for a, b in OFFICIAL_OUTAGES]
    api_in_outage = {}
    for a, b in outage_ep:
        w = ep_a[(ep_a["start"] >= pd.Timestamp(a, tz="UTC")) & (ep_a["start"] < pd.Timestamp(b, tz="UTC"))]
        if any(d in files for d in pd.date_range(a, pd.Timestamp(b) - pd.Timedelta(days=1), freq="D", tz="UTC")):
            api_in_outage[(a, b)] = (len(w), w["oblast"].nunique())

    sha = hashlib.sha256(b"".join(files[d].read_bytes() for d in days)).hexdigest()[:16]
    pct = lambda x, y: f"{100 * x / y:.1f}%" if y else "n/a"
    L = ["# API check: does the Ukraine Alarm API history agree with our official data?", "",
         "Source compared against our official data: **the Ukraine Alarm API** (`api.ukrainealarm.com`, `GET /api/v3/alerts/dateHistory`, a different "
         "source from the official Telegram channel behind our csv). Produced by `scripts/api_check.py`, offline, from the saved API answers.", "",
         "## What was compared",
         f"- API days saved: {len(days)} ({days[0]:%Y-%m-%d} to {days[-1]:%Y-%m-%d} UTC), {len(gaps)} missing in between"
         + (f" ({', '.join(f'{g:%m-%d}' for g in gaps[:10])}{'...' if len(gaps) > 10 else ''})" if gaps else "")
         + f"; SHA-256 prefix of the files in date order: `{sha}`.",
         "- Hours compared: the UTC days with a file, minus the official feed's outage "
         + ", ".join(f"[{a}, {b})" for a, b in OFFICIAL_OUTAGES) + f" and everything from {end_ok:%Y-%m-%d %H:%M} UTC (the official data's trusted end): "
         f"{len(ok_hours)} hours x {len(oblasts)} oblasts = {N} oblast-hours.",
         "- Rules applied to the API alerts: only alertType `AIR`; district (`... район`) -> raion row (name transliterated, must be one of our "
         f"{len(raions)} raions; one known rename: Sheptytskyi = our Chervonohradskyi); `м. Київ` and `... область` -> oblast-level row; hromada-level rows are dropped, as `src/panel.py` does; "
         "oblast under alert when at least half of its raions are (the same fixed raion list); restarts within 5 minutes joined. "
         "The official side goes through the same code.", "",
         "## What the API rows were turned into",
         *[f"- {k}: {v}" for k, v in n_api.items()],
         f"- hromada-level rows dropped: {dropped['hromada level (not used by the rule)']}",
         f"- oblast-level rows for oblasts not in our data: {dropped['oblast not in our data (Crimea, Sevastopol, Luhansk)']}",
         f"- districts not in our raion list (dropped): {sum(dropped['district not in our raion list'].values())} rows, "
         f"{len(dropped['district not in our raion list'])} names" + (f": {', '.join(sorted(dropped['district not in our raion list']))}" if dropped["district not in our raion list"] else ""),
         f"- other names (dropped): {sum(dropped['other name'].values())} rows" + (f": {', '.join(sorted(dropped['other name']))}" if dropped["other name"] else ""), "",
         "## Oblast-hours (the series the model uses)", "",
         "| | oblast-hours |", "|---|---|",
         f"| compared | {N} |",
         f"| same \"under alert\" in both | {N - int(act_dis.sum())} of {N} ({pct(N - int(act_dis.sum()), N)}) |",
         f"| under alert only in the official data | {int((act_dis & j['active_off']).sum())} |",
         f"| under alert only in the API | {int((act_dis & j['active_api']).sum())} |",
         f"| same \"a new alert starts in this hour\" in both | {N - int(st_dis.sum())} of {N} ({pct(N - int(st_dis.sum()), N)}) |",
         f"| a start in the official data only / in the API only / in both | {int((st_off & ~st_api).sum())} / {int((~st_off & st_api).sum())} / {int((st_off & st_api).sum())} |", "",
         "Per oblast:", "",
         "| oblast | hours | \"under alert\" differs | official only | API only | \"new alert starts\" differs |", "|---|---|---|---|---|---|",
         *[f"| {o} | {int(r.hours)} | {int(r.active_disagree)} | {int(r.official_only)} | {int(r.api_only)} | {int(r.start_disagree)} |" for o, r in per.iterrows()], "",
         "Days with the most disagreeing oblast-hours (top 5):", "",
         "| day (UTC) | \"under alert\" differs | \"new alert starts\" differs | oblasts involved |", "|---|---|---|---|",
         *[f"| {d} | {int(r.a)} | {int(r.s)} | {int(r.o)} |" for d, r in by_day.iterrows()], "",
         "## Oblast episodes (alerts after the half-of-raions rule and the 5-minute join)", "",
         "| | official episodes | API episodes |", "|---|---|---|",
         f"| starting on the compared hours | {len(eo)} | {len(ea)} |",
         *[f"| with a start of the other source within {lab} | {cnt(em[t])} of {len(eo)} | {cnt(emb[t])} of {len(ea)} |"
           for t, lab in ((60, "1 minute"), (300, "5 minutes"), (3600, "1 hour"))], "",
         "## Raion alert rows", "",
         "| | official | API |", "|---|---|---|",
         f"| raion-level rows starting on the compared hours | {len(ro)} | {len(ra)} |",
         *[f"| with a row of the other source, same raion, start within {t} s | {cnt(mo[t])} of {len(ro)} | {cnt(mb[t])} of {len(ra)} |" for t in (5, 60)],
         f"| of the official rows matched within 60 s, end also within 60 s | {end_close} of {len(both60)} | |", ""]
    if api_in_outage:
        L += ["## The official feed's outage", ""]
        for (a, b), (ne, no) in api_in_outage.items():
            L.append(f"- The official data has nothing in [{a}, {b}). The API days saved for that window give {ne} oblast episodes starting in it, in {no} oblasts. "
                     "They are not compared with anything here.")
        L.append("")
    args.out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:6]))
    print(f"oblast-hours compared {N}: same under-alert {N - int(act_dis.sum())}, same start-in-hour {N - int(st_dis.sum())}")
    print(f"raion rows official {len(ro)}: matched within 5 s {cnt(mo[5])}, within 60 s {cnt(mo[60])}; API rows {len(ra)}: within 60 s {cnt(mb[60])}")
    print(f"oblast episodes official {len(eo)} / API {len(ea)}; official matched within 1 min {cnt(em[60])}, 5 min {cnt(em[300])}, 1 h {cnt(em[3600])}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
