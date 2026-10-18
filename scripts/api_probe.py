"""Probe the Ukraine Alarm API: what it returns and how far back the history goes (run this on your own machine).

    export UA_ALARM_TOKEN=...        (in your shell; the script reads it from there and from nowhere else)
    python scripts/api_probe.py

About 20-45 requests, at least 6 s apart and slower after any HTTP 429 (the swagger names no rate limit). It prints only status codes, counts, region
names and the earliest/latest timestamps it saw, never the token, and writes the raw answers to data/api_raw/ (git-ignored).

1. /api/v3/regions        the id tree; how many states / districts / communities; which of our 25 oblasts are matched by name
2. /api/v3/alerts/status  the "last action" counter
3. /api/v3/alerts         the alerts active now: which levels the ids are on
4. /api/v3/alerts/regionHistory?regionId=<Kharkiv>   "the last 25 alerts of a region": format and recency
5. /api/v3/alerts/dateHistory?date=YYYYMMDD   depth: a ladder of dates from 2022-02-24 to yesterday, then a bisection to the
   first date with data if the oldest ones are empty. For every date: status, items, ids by level, start times.
"""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.ukrainealarm import UK_TO_OURS, Client, our_name, region_index

RAW = ROOT / "data" / "api_raw"
LADDER = ["2022-02-24", "2023-01-01", "2024-01-01", "2025-01-01", "2025-07-01", "2026-01-01", "2026-06-01",
          "2026-08-15", "2026-08-31", "2026-09-05"]  # 08-31 is inside our official feed's outage (08-29..09-02)
OURS = 25


def save(name, raw):
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_bytes(raw)


def say(status, what):
    print(f"  HTTP {status}: {what}")


def ts(values):
    return pd.to_datetime(pd.Series(list(values), dtype="object"), utc=True, errors="coerce", format="ISO8601")


def date_stats(items, day, idx):
    """Counts for one dateHistory answer: levels of the ids, start times against the requested day."""
    n = len(items)
    lvl = Counter((idx.get(a.get("regionId")) or (None, "id not in /regions", None))[1] for a in items)
    ids = {a.get("regionId") for a in items}
    st = ts(a.get("startDate") for a in items)
    d0 = pd.Timestamp(day, tz="UTC")
    ok = st.notna()
    out = {"items": n, "distinct ids": len(ids), "by level": dict(lvl),
           "alertType": dict(Counter(a.get("alertType") for a in items)),
           "isContinue": sum(1 for a in items if a.get("isContinue")),
           "raw start strings carry a timezone": any(str(a.get("startDate", "")).endswith(("Z",)) or "+" in str(a.get("startDate", ""))[10:] for a in items)}
    if ok.any():
        out["start min / max (raw)"] = (min(a["startDate"] for a in items if a.get("startDate")),
                                        max(a["startDate"] for a in items if a.get("startDate")))
        out["starts on the day / before / after (UTC)"] = (int(((st >= d0) & (st < d0 + pd.Timedelta(days=1))).sum()),
                                                           int((st < d0).sum()), int((st >= d0 + pd.Timedelta(days=1)).sum()))
        en = ts(a.get("endDate") for a in items)
        out["end max (raw)"] = max((a["endDate"] for a in items if a.get("endDate")), default=None)
        out["ends before they start"] = int((en.notna() & ok & (en < st)).sum())
    return out


def main():
    c = Client()
    summary = []

    print("1. regions")
    s, regions, raw = c.get("/api/v3/regions")
    say(s, f"{len(raw)} bytes")
    if s != 200:
        print("Stopping: no valid answer from /regions (401 = token refused; 403 = blocked, for example by Cloudflare; "
              "0 = no connection).")
        return 1
    save("regions.json", raw)
    idx = region_index(regions)
    types = Counter(t for _, t, _ in idx.values())
    states = [(rid, v[0]) for rid, v in idx.items() if v[1] == "State"]
    matched = {our_name(nm): rid for rid, nm in states if our_name(nm)}
    print(f"  nodes by type: {dict(types)}; top-level states: {len(states)}")
    print(f"  our oblasts matched by name: {len(matched)} of {OURS}")
    print("  states not matched to one of ours:", [nm for _, nm in states if not our_name(nm)])
    print("  of our 25 oblasts, no state with that name:", sorted(set(UK_TO_OURS.values()) - set(matched)))
    state_ids = {rid for rid, _ in states}
    summary.append(("regions", s, f"{len(idx)} nodes, {len(states)} states, {len(matched)}/{OURS} matched"))

    print("2. status")
    s, st, raw = c.get("/api/v3/alerts/status")
    say(s, "lastActionIndex present" if isinstance(st, dict) and "lastActionIndex" in st else "no lastActionIndex")
    save("status.json", raw)

    print("3. active alerts")
    s, act, raw = c.get("/api/v3/alerts")
    if s == 200:
        save("alerts_active.json", raw)
        lv = Counter((idx.get(a.get("regionId")) or (None, "id not in /regions", None))[1] for a in act)
        say(s, f"{len(act)} regions with an alert now, by level: {dict(lv)}")
    else:
        say(s, "no data")

    print("4. regionHistory (Kharkivska)")
    rid = matched.get("Kharkivska oblast")
    if rid:
        s, rh, raw = c.get("/api/v3/alerts/regionHistory", {"regionId": rid})
        if s == 200:
            save("region_history_kharkivska.json", raw)
            al = [a for blk in rh for a in (blk.get("alarms") or [])]
            say(s, f"{len(rh)} blocks, {len(al)} alarms; start min / max: "
                   f"{min((a['startDate'] for a in al), default=None)} / {max((a['startDate'] for a in al), default=None)}")
        else:
            say(s, "no data")
    else:
        print("  skipped: Kharkivska not matched")

    print("5. dateHistory depth")
    seen = {}

    def day(dstr):
        if dstr in seen:
            return seen[dstr]
        s, items, raw = c.get("/api/v3/alerts/dateHistory", {"date": dstr.replace("-", "")})
        if s == 200:
            save(f"date_history_{dstr.replace('-', '')}.json", raw)
        info = date_stats(items, dstr, idx) if s == 200 and isinstance(items, list) else {}
        seen[dstr] = (s, info.get("items", 0) if info else 0, info)
        line = f"  {dstr}: HTTP {s}, items {seen[dstr][1]}"
        if info.get("items"):
            line += f", by level {info['by level']}, start min/max {info.get('start min / max (raw)')}"
        print(line)
        return seen[dstr]

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    ladder = LADDER + [yesterday]
    results = [(d, day(d)) for d in ladder]
    first_ok = next((i for i, (_, (s, n, _i)) in enumerate(results) if s == 200 and n > 0), None)
    earliest, exact = None, False
    if first_ok is None:
        print("  no ladder date returned any alert")
    elif first_ok == 0:
        earliest, exact = ladder[0], False
        print("  the oldest date asked (2022-02-24) already has data: history reaches back at least that far")
    else:
        lo, hi = datetime.strptime(ladder[first_ok - 1], "%Y-%m-%d"), datetime.strptime(ladder[first_ok], "%Y-%m-%d")
        while (hi - lo).days > 1:  # lo: no data, hi: data
            mid = lo + (hi - lo) // 2
            s, n, _ = day(mid.strftime("%Y-%m-%d"))
            lo, hi = (lo, mid) if (s == 200 and n > 0) else (mid, hi)
        earliest, exact = hi.strftime("%Y-%m-%d"), True
    print("\nPROBE SUMMARY (safe to paste: no token in it)")
    print(f"  requests made: {c.calls}; HTTP 429 seen: {c.n429}; Retry-After values seen (s): {sorted(set(c.retry_after_seen)) or 'none sent'}; "
          f"gap at the end: {c.gap:.1f} s")
    for name, s, text in summary:
        print(f"  {name}: HTTP {s}: {text}")
    print(f"  dateHistory: earliest date with data: {earliest}" + (" (found by bisection, exact if data is continuous)" if exact
          else " (older dates were not asked: the history reaches back at least this far)" if earliest else ""))
    print("  per date (HTTP status, items):", {d: (v[0], v[1]) for d, v in sorted(seen.items())})
    for d in ("2026-08-15", "2026-08-31", "2026-09-05", yesterday):
        if d in seen and seen[d][2]:
            print(f"  detail {d}:", json.dumps(seen[d][2], ensure_ascii=False))
    print(f"  raw answers saved in {RAW.relative_to(ROOT)}/ (git-ignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
