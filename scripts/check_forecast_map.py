"""Checks for the forecast map (scripts/forecast_map.py, data/geo/ukraine_oblasts.geojson). Offline, a few seconds.

    python scripts/check_forecast_map.py

1. names: our 24 units are matched to the boundary file by ISO 3166-2 code, and each match is checked against the feature's own names; the file has exactly those 24
   plus Luhansk, Crimea and Sevastopol (not modelled), nothing twice, nothing left over; our 24 are the 24 units of the data
2. geometry: rings closed, inside Ukraine's bounding box, small file, shared borders simplified identically (no slivers between neighbours)
3. page: self-contained (no script, no link, no external address of any kind), every oblast once with the right colour class for each horizon, the right triangle
   (at or above the threshold), the alert badge exactly where an alert is running, the header facts, the footer sentence; light and dark colours defined
4. colours: the ramp is monotone in lightness in both modes, steps far enough apart, text readable on every fill, outlines visible on the page colour
5. predict.py --at writes the page for a past hour (if models/ is there)
"""
import contextlib
import io
import json
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts import forecast_map as fm

FAILS = []


def check(ok, msg):
    print(("ok    " if ok else "FAIL  ") + msg)
    if not ok:
        FAILS.append(msg)


def stem(s):
    return re.sub(r"[^a-z]", "", s.lower())[:3]


def names_and_geometry():
    feats = fm.load_geo()
    by_iso = defaultdict(list)
    for f in feats:
        by_iso[f["properties"]["iso"]].append(f)
    check(all(len(v) == 1 for v in by_iso.values()), f"no ISO code twice ({len(feats)} features)")
    check(set(by_iso) == {iso for iso, _ in fm.OURS.values()} | set(fm.NOT_MODELLED), "the file has exactly our 24 units plus Luhansk, Crimea and Sevastopol")
    check(len({iso for iso, _ in fm.OURS.values()}) == len(fm.OURS) == 24, "our 24 names map to 24 different codes")
    from scripts.live_api import inputs
    _, data_oblasts = inputs()
    check(sorted(data_oblasts) == sorted(fm.OURS), "the 24 names in the alert data are exactly the keys of OURS")
    bad = []
    for ours, (iso, alias) in fm.OURS.items():
        p = by_iso[iso][0]["properties"]
        names = [p["ne_name"], p["ne_name_en"], p["ne_name_alt"] or ""]
        if p["ours"] != ours:
            bad.append(f"{ours}: file says {p['ours']}")
        if not any(alias in n for n in names):
            bad.append(f"{ours}: {alias!r} not in {names}")
        if ours != "Kyiv City" and ours != "Kyivska oblast" and stem(ours) != stem(p["ne_name_en"]):
            bad.append(f"{ours}: first three letters differ from {p['ne_name_en']!r}")
    check(not bad, "each of our 24 matches its feature by code, by a required alias and by the first three letters of the name" + ("" if not bad else f": {bad}"))
    check({by_iso[i][0]["properties"]["ours"] for i in fm.NOT_MODELLED} == {None}, "Luhansk, Crimea, Sevastopol carry no model unit")
    from src.load import PERMANENT_ALERT_OBLASTS
    check(any("Luhansk" in o for o in PERMANENT_ALERT_OBLASTS) and "Luhansk" in fm.NOT_MODELLED.values(), "Luhansk is the permanent-alert oblast the model leaves out")

    ok_ring, outside, n_vert = True, 0, 0
    for f in feats:
        for poly in f["geometry"]["coordinates"]:
            for r in poly:
                ok_ring &= len(r) >= 4 and r[0] == r[-1]
                for x, y in r:
                    n_vert += 1
                    outside += not (22 <= x <= 41 and 44 <= y <= 53)
    check(ok_ring and outside == 0, f"rings closed with 4+ points, all {n_vert} vertices inside Ukraine's bounding box")
    size = fm.GEO.stat().st_size
    check(size < 200_000, f"boundary file is small ({size} bytes)")
    owners, edges = defaultdict(set), {}
    for i, f in enumerate(feats):
        es = set()
        for poly in f["geometry"]["coordinates"]:
            for r in poly:
                for a, b in zip(r[:-1], r[1:]):
                    owners[tuple(a)].add(i)
                    es.add(frozenset((tuple(a), tuple(b))))
        edges[i] = es
    mism = n = 0
    for i, es in edges.items():
        for e in es:
            a, b = tuple(e)
            for j in owners[a] & owners[b]:
                if j != i:
                    n += 1
                    mism += e not in edges[j]
    check(n > 0 and mism == 0, f"shared borders are the same line in both neighbours: {n} edges shared by two units, {mism} not in the other unit")
    kc = next(i for i, f in enumerate(feats) if f["properties"]["ours"] == "Kyiv City")
    check(any(len(o) > 1 for o in owners.values()) and sum(1 for o in owners.values() if kc in o and len(o) > 1) >= 3, "Kyiv City shares its outline with Kyivska oblast")


def synthetic(origin, rng, now_every=4):
    rows = []
    for i, n in enumerate(sorted(fm.OURS)):
        b = rng.uniform(0.0, 1.0)
        rows.append({"oblast": n, "now": bool(i % now_every == 0), "p": {1: round(b * 0.5, 3), 3: round(b * 0.8, 3), 6: round(b, 3)}})
    # values at and next to the thresholds and the bin edges
    thr = {1: 0.252, 3: 0.427, 6: 0.427}
    for h, (a, b_) in {1: ("Cherkaska oblast", "Sumska oblast"), 3: ("Odeska oblast", "Poltavska oblast"), 6: ("Lvivska oblast", "Volynska oblast")}.items():
        next(r for r in rows if r["oblast"] == a)["p"][h] = thr[h]
        next(r for r in rows if r["oblast"] == b_)["p"][h] = thr[h] - 0.001
    for k, e in enumerate(fm.EDGES):
        rows[k]["p"][3] = e
        rows[k + 7]["p"][3] = e - 0.0004
    return dict(origin=origin, made=origin + pd.Timedelta(minutes=37), model="v2", version="frozen-v2-0123456789ab", thresholds=thr, rows=rows,
                model_text="Live forecast from the Ukraine Alarm API. Model: LightGBM v2.",
                notes=["Freshness: the newest alert start in the API is 5 min before now.", "Note: in the v2 test window the model predicted a bit low."])


def page_checks():
    rng = np.random.default_rng(0)
    for origin, offset in ((pd.Timestamp("2026-10-10 12:00", tz="UTC"), "15:00"), (pd.Timestamp("2026-12-10 12:00", tz="UTC"), "14:00")):
        payload = synthetic(origin, rng)
        page = fm.render(payload)
        tag = f"[{origin:%Y-%m-%d}]"
        banned = ["http", "<script", "<link", "@import", "src=", "href=", "<img", "<iframe", "fetch(", "XMLHttpRequest", "<object", "<embed", "<form"]
        found = [b for b in banned if b in page]
        urls = re.findall(r"url\(([^)]*)\)", page)
        check(not found and set(urls) <= {"#hatch"}, f"{tag} self-contained: nothing from {banned} in the page, url() only for the in-page pattern" + (f" (found {found})" if found else ""))
        thr = payload["thresholds"]
        by = {r["oblast"]: r for r in payload["rows"]}
        svg = page[page.index("<svg"):page.index('<g class="callout">')]
        groups = [(re.match(r'<g class="u" data-oblast="([^"]+)"', c).group(1), c) for c in re.split(r'(?=<g class="u[ "])', svg) if c.startswith('<g class="u" data-oblast=')]
        check(sorted(g[0] for g in groups) == sorted(fm.OURS), f"{tag} every one of our 24 units is on the map exactly once ({len(groups)} groups)")
        bad = []
        for name, body in groups:
            r = by[name]
            cls = re.search(r'<path class="([^"]+)"', body).group(1).split()
            for h in fm.HORIZONS:
                if f"p{h}-{fm.bin_of(r['p'][h])}" not in cls:
                    bad.append((name, h, "colour class"))
                m = re.search(rf'<g class="lab l{h} q(\d)">(.*?)</g>', body, re.S)
                if name == "Kyiv City":
                    continue
                if int(m.group(1)) != fm.bin_of(r["p"][h]):
                    bad.append((name, h, "text class"))
                txt = re.search(r'<text class="pc"[^>]*>([^<]*)<', m.group(2)).group(1)
                want = f"{100 * r['p'][h]:.0f}% " + ("▲" if r["p"][h] >= thr[h] else "▽")
                if txt != want:
                    bad.append((name, h, txt, want))
            if (name != "Kyiv City") and (('class="badge"' in body) != r["now"]):
                bad.append((name, "badge"))
        check(not bad, f"{tag} colour class, percentage, triangle (at or above the threshold) and alert badge right for every unit and horizon" + (f": {bad[:4]}" if bad else ""))
        call = page[page.index('<g class="callout">'):page.index("</svg>")]
        kc = by["Kyiv City"]
        ok = all(f'class="lab l{h} q{fm.bin_of(kc["p"][h])}"' in call and f"{100 * kc['p'][h]:.0f}% " + ("▲" if kc["p"][h] >= thr[h] else "▽") in call for h in fm.HORIZONS)
        check(ok and (('class="badge"' in call) == kc["now"]), f"{tag} the Kyiv City call-out repeats its three probabilities, triangles and alert state")
        check(page.count('class="u nd"') == 3 and page.count("no data") >= 2 + 1, f"{tag} Crimea, Sevastopol and Luhansk are grey, hatched; Crimea and Luhansk say \"no data\"")
        edge_cases = {(a, h): (by[a]["p"][h], fm.bin_of(by[a]["p"][h])) for a, h in (("Cherkaska oblast", 1), ("Sumska oblast", 1))}
        check(edge_cases[("Cherkaska oblast", 1)][0] >= thr[1] > edge_cases[("Sumska oblast", 1)][0], f"{tag} (test data really sit on both sides of the threshold)")
        rows_html = re.findall(r"<tr><td>([^<]+)</td><td>([^<]+)</td>(.*?)</tr>", page)
        tbl_ok = len(rows_html) == 24
        for name, now, cells in rows_html:
            r = next(v for k, v in by.items() if fm.short(k) == name)
            vals = re.findall(r">(\d\.\d{3}) (above|below)<", cells)
            tbl_ok &= [v[0] for v in vals] == [f"{r['p'][h]:.3f}" for h in fm.HORIZONS]
            tbl_ok &= [v[1] for v in vals] == ["above" if r["p"][h] >= thr[h] else "below" for h in fm.HORIZONS]
            tbl_ok &= (now == "under alert") == r["now"]
        check(tbl_ok, f"{tag} the table under the map has all 24 rows with the same probabilities, above/below and alert state")
        head = [f"{origin:%Y-%m-%d %H:%M} UTC", f"({offset} Kyiv time)", "frozen-v2-0123456789ab", "<b>v2</b>", "Freshness: the newest alert start", "predicted a bit low",
                "A study model, not for safety decisions: follow the official alerts.", f"within 1 hour", "within 3 hours", "within 6 hours",
                f"1 h: {thr[1]:.3f}, 3 h: {thr[3]:.3f}, 6 h: {thr[6]:.3f}"]
        miss = [h for h in head if h not in page]
        check(not miss, f"{tag} header, notes, switch, thresholds and the footer sentence are there" + (f" (missing {miss})" if miss else ""))
        check(page.count('<input type="radio"') == 3 and page.count("<footer>") == 1 and "prefers-color-scheme:dark" in page and "color-scheme:light dark" in page,
              f"{tag} three radio buttons (CSS-only switch), one footer, light and dark colour sets")
    # the page without any alert running has no badge at all
    p0 = synthetic(pd.Timestamp("2026-10-10 12:00", tz="UTC"), rng)
    for r in p0["rows"]:
        r["now"] = False
    check('class="badge"' not in re.sub(r"\.badge[^}]*\}", "", fm.render(p0)), "no alert running anywhere: no badge anywhere")
    # a missing row is an error, not a silently empty oblast
    p1 = synthetic(pd.Timestamp("2026-10-10 12:00", tz="UTC"), rng)
    p1["rows"] = p1["rows"][1:]
    try:
        fm.render(p1)
        check(False, "a missing oblast row stops the render")
    except ValueError:
        check(True, "a missing oblast row stops the render (ValueError), it is not drawn empty")
    # warn_or_write must not raise
    with contextlib.redirect_stderr(io.StringIO()) as err:
        res = fm.write_or_warn(dict(p1), Path(tempfile.mkdtemp()) / "x.html")
    check(res is None and "Map not written" in err.getvalue(), "write_or_warn turns a failure into one line on stderr and returns None")


def oklab_L(hex_):
    c = np.array([int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    l, m, s = (np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]]) @ c)
    return float(0.2104542553 * np.cbrt(l) + 0.7936177850 * np.cbrt(m) - 0.0040720468 * np.cbrt(s))


def colour_checks():
    for mode, v in fm.MODES.items():
        Ls = [oklab_L(c) for c in v["ramp"]]
        d = np.diff(Ls)
        mono = (d < 0).all() if mode == "light" else (d > 0).all()
        check(mono and np.abs(d).min() >= 0.06, f"[{mode}] ramp is monotone in lightness ({'dark' if mode == 'light' else 'light'} = more probable), smallest step {np.abs(d).min():.3f} (>= 0.06)")
        worst = min(fm.contrast(fm.text_on(c), c) for c in v["ramp"])
        check(worst >= 4.5, f"[{mode}] text on every fill reads at {worst:.1f}:1 (>= 4.5)")
        check(fm.contrast(v["edge"], v["surface"]) >= 3, f"[{mode}] outlines are {fm.contrast(v['edge'], v['surface']):.1f}:1 on the page colour (>= 3)")
        check(fm.contrast(v["alert"], v["surface"]) >= 3 and fm.contrast("#ffffff", v["alert"]) >= 4.5,
              f"[{mode}] alert badge {fm.contrast(v['alert'], v['surface']):.1f}:1 on the page, its ! {fm.contrast('#ffffff', v['alert']):.1f}:1 on it")
        check(fm.contrast(v["ramp"][0], v["surface"]) >= 2.0, f"[{mode}] lowest fill against the page colour {fm.contrast(v['ramp'][0], v['surface']):.2f}:1 (2:1 floor of the ordinal ramp rule)")
        check(fm.contrast(v["ink"], v["surface"]) >= 7 and fm.contrast(v["ink2"], v["surface"]) >= 4.5, f"[{mode}] page text is readable")
    check(len(fm.RAMP) == len(fm.RAMP_DARK) == len(fm.BIN_NAMES) == len(fm.EDGES) + 1 == 5, "5 bins, 4 edges, 5 names, 5 colours in each mode")


def at_check():
    if not (ROOT / "models" / "info.json").exists():
        print("skip  predict.py --at: models/ is not there (python scripts/evaluate.py makes it)")
        return
    import scripts.predict as predict
    tmp = Path(tempfile.mkdtemp()) / "m.html"
    old_out, old_argv = fm.OUT, sys.argv
    fm.OUT = tmp
    try:
        assert tmp.is_relative_to(tempfile.gettempdir())
        for argv in (["--at", "2026-08-20 12:00", "--all"], ["--at", "2026-08-20 12:00", "--oblast", "Kyivska"]):
            tmp.unlink(missing_ok=True)
            sys.argv = ["predict.py", *argv]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                predict.main()
            page = tmp.read_text(encoding="utf-8")
            check(page.count('data-oblast="') == 24 and "frozen-r13-" in page and "2026-08-20 12:00 UTC" in page and "(15:00 Kyiv time)" in page,
                  f"predict.py {' '.join(argv)}: page written for all 24 oblasts, round-13 model fingerprint, origin hour in UTC and Kyiv time")
            check("Map written to" in buf.getvalue(), "  and says so on stdout")
            check("Replay of a past hour" in page and "Model: LightGBM v1 (round 13)" in page, "  and carries the replay text")
    finally:
        fm.OUT, sys.argv = old_out, old_argv


if __name__ == "__main__":
    names_and_geometry()
    page_checks()
    colour_checks()
    at_check()
    print()
    print("forecast map checks: " + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
    sys.exit(1 if FAILS else 0)
