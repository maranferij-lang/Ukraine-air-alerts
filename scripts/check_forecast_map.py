"""Checks for the forecast map (scripts/forecast_map.py, scripts/forecast_map_page.html, data/geo/ukraine_oblasts.geojson). Offline, a few seconds.

    python scripts/check_forecast_map.py

1. names: our 24 units are matched to the boundary file by ISO 3166-2 code, and each match is checked against the feature's own names; the file has exactly those 24
   plus Luhansk, Crimea and Sevastopol (not modelled), nothing twice, nothing left over; our 24 are the 24 units of the data. The Ukrainian names are checked against the
   API's own spelling (UK_TO_OURS and the saved API files); every text has both languages with the same placeholders
2. geometry: rings closed, inside Ukraine's bounding box, small file, shared borders simplified identically (no slivers between neighbours)
3. page, in both languages: self-contained (no address of any kind, no external script, style, font or image, no network function in the script, only the two inline scripts),
   the data block equals the forecast it was made from, every oblast once on the map with the right colour class for each horizon, the right triangle, the alert badge exactly
   where an alert is running, the top bar (one sentence, freshness pill, model version, how-to popover), the footer sentence, the Kyiv City call-out, the fallback table;
   the script is syntax-checked by node if node is there; the design system is linted (type scale, no colour outside the tokens)
4. colours: the dark ramp is monotone in lightness, neighbours clearly apart under normal, protan and deutan vision, text readable on every fill; the page tokens read well
5. predict.py --at writes the page for a past hour in both languages (if models/ is there)
6. in a headless browser (if node and playwright are there): scripts/check_forecast_map_browser.js: no request at all, top 5, selection, bars, history chart, keyboard,
   popover, freshness pill, phone bottom sheet
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
from src.i18n import T, full_name, short_name, sort_key

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


def uk_names():
    import json
    from src.i18n import NOT_MODELLED_UK, OBLAST_UK
    from src.ukrainealarm import UK_TO_OURS, our_name
    check(set(OBLAST_UK) == set(fm.OURS), "the Ukrainian name list has exactly our 24 units")
    bad = [(en, uk, our_name(uk)) for en, uk in OBLAST_UK.items() if our_name(uk) != en]
    check(not bad, "every Ukrainian name maps back to its own unit through UK_TO_OURS, the table the data pipeline maps the API's state names with" + (f": {bad}" if bad else ""))
    check({our_name(uk) for uk in OBLAST_UK.values()} | {"Luhanska oblast"} == set(UK_TO_OURS.values()), "UK_TO_OURS has nothing else (our 24 plus Luhansk) and the list leaves nothing out")
    seen = set()
    for f in sorted((ROOT / "data" / "api_archive" / "date_history").glob("*.json")):
        for a in json.loads(f.read_text(encoding="utf-8")):
            n = a.get("regionName") or ""
            if n.endswith(" область") or n == "м. Київ":
                seen.add(n)
    check(len(seen) >= 2 and seen <= set(OBLAST_UK.values()), f"state-level names found in the saved API files are spelled exactly as in the list (found {sorted(seen)})")
    allowed = set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя -.’'")
    odd = [n for n in list(OBLAST_UK.values()) + list(NOT_MODELLED_UK.values()) if set(n.lower()) - allowed or (n[3:] if n.startswith("м. ") else n)[0] != (n[3:] if n.startswith("м. ") else n)[0].upper()]
    check(not odd and len(set(OBLAST_UK.values())) == 24, f"names are Ukrainian letters only, capitalised (after the API's \"м. \" for cities), all different{'' if not odd else ': ' + str(odd)}")
    check(len({short_name(n, 'uk') for n in OBLAST_UK}) == 24, "the short forms shown on the map are all different")
    check(our_name(NOT_MODELLED_UK["Luhansk"]) == "Luhanska oblast" and NOT_MODELLED_UK["Crimea"].endswith("Республіка Крим"),
          "Luhansk is the API's spelling (UK_TO_OURS); Crimea ends in the \"Республіка Крим\" that scripts/api_check.py looks for")
    print("note  Sevastopol (\"м. Севастополь\") is in none of our data and could not be checked against anything in the repo; it is only in the side panel when selected, not labelled on the map")


def i18n_checks():
    import string
    from src.i18n import S
    bad = []
    for k, v in S.items():
        if set(v) != {"en", "uk"}:
            bad.append((k, "languages"))
            continue
        en, uk = v["en"], v["uk"]
        if isinstance(en, str):
            fields = lambda t: {f for _, f, _, _ in string.Formatter().parse(t) if f}
            if fields(en) != fields(uk):
                bad.append((k, "placeholders", fields(en), fields(uk)))
            if re.search("[а-яіїєґА-ЯІЇЄҐ]", en) or (re.search("[A-Za-z]", en) and not re.search("[а-яіїєґА-ЯІЇЄҐ]", uk)):
                bad.append((k, "script"))
        elif len(en) != len(uk):
            bad.append((k, "length"))
    check(not bad, f"every text has an English and a Ukrainian version with the same placeholders, English without Cyrillic, Ukrainian with it ({len(S)} texts)" + (f": {bad}" if bad else ""))


def freshness_checks():
    from scripts.live_api import ago
    now = pd.Timestamp("2026-10-10 12:37:00", tz="UTC")
    cases = {-125: "just now", -1: "just now", 0: "just now", 30: "just now", 59: "just now", 60: "1 min before now", 61: "1 min before now", 150: "2 min before now",
             3599: "60 min before now", 3 * 3600 - 1: "180 min before now", 3 * 3600: "3.0 h before now", 5 * 3600: "5.0 h before now"}
    bad = [(d, ago(now, now - pd.Timedelta(seconds=d)), want) for d, want in cases.items() if ago(now, now - pd.Timedelta(seconds=d)) != want]
    check(not bad, f"freshness wording in English: under 1 minute or ahead of our clock is 'just now', then minutes, then hours (checked at {len(cases)} gaps from -125 s to 5 h)" + (f": {bad}" if bad else ""))
    ukbad = [d for d in (-125, 0, 59) if ago(now, now - pd.Timedelta(seconds=d), "uk") != "щойно"] + [d for d in (60, 150) if "хв тому" not in ago(now, now - pd.Timedelta(seconds=d), "uk")]
    check(not ukbad and "год тому" in ago(now, now - pd.Timedelta(hours=5), "uk"), "freshness wording in Ukrainian: щойно / N хв тому / N.N год тому")
    check(all("-" not in ago(now, now - pd.Timedelta(seconds=d), lg) for d in (-125, -1) for lg in ("en", "uk")), "no negative number ever appears in the freshness text")


def extract_data(page):
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


def page_checks(lang="uk"):
    rng = np.random.default_rng(0)
    for origin, offset, mode in ((pd.Timestamp("2026-10-10 12:00", tz="UTC"), "15:00", "live"), (pd.Timestamp("2026-12-10 12:00", tz="UTC"), "14:00", "replay")):
        payload = synthetic(origin, rng)
        payload["lang"], payload["mode"] = lang, mode
        if mode == "live":
            names = sorted(fm.OURS)
            payload["history"] = {"runs": [{"o": f"2026-10-10T{h:02d}:00:00Z", "lbl": f"10-10 {h + 3:02d}:00", "p": {fm.OURS[n][0]: {str(H): round(rng.uniform(0, 1), 3) for H in fm.HORIZONS} for n in names}} for h in (6, 9, 12)]}
        else:
            payload["history"] = None
            payload["notes"] = payload["notes"] + [T("st_train", lang, cutoff="2026-08-07 00:00 UTC")]
        page = fm.render(payload)
        tag = f"[{lang} {mode} {origin:%Y-%m-%d}]"
        thr = payload["thresholds"]
        by = {r["oblast"]: r for r in payload["rows"]}
        scripts_ = re.findall(r"<script\b([^>]*)>", page)
        checks_banned = ["http", "<link", "src=", "@import", "fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "importScripts", "import(", "new Image", "<img", "<iframe", "<object", "<embed", "<form", "//cdn", "eval(", "document.write"]
        found = [b for b in checks_banned if b in page]
        urls = re.findall(r"url\(([^)]*)\)", page)
        check(not found and set(urls) <= {"#hatch"} and len(scripts_) == 2 and all("src" not in a for a in scripts_),
              f"{tag} self-contained: none of {checks_banned} anywhere, url() only for the in-page pattern, exactly two inline scripts (the data and the code)" + (f" (found {found})" if found else ""))
        data = extract_data(page)
        dbad = []
        if data["lang"] != lang or data["mode"] != mode or data["thr"] != {str(h): thr[h] for h in fm.HORIZONS} or data["edges"] != fm.EDGES:
            dbad.append("header fields")
        iso_of = {n: iso for n, (iso, _) in fm.OURS.items()}
        mod = {u["iso"]: u for u in data["units"] if u["modelled"]}
        if len(data["units"]) != 27 or len(mod) != 24:
            dbad.append("unit count")
        for n, r in by.items():
            u = mod.get(iso_of[n])
            if not u or u["name"] != short_name(n, lang) or u["full"] != full_name(n, lang) or u["now"] != r["now"]:
                dbad.append((n, "name/full/now")); continue
            for h in fm.HORIZONS:
                if u["p"][str(h)] != r["p"][h] or u["pc"][str(h)] != f"{100 * r['p'][h]:.0f}%":
                    dbad.append((n, h))
        nd = {u["iso"]: u for u in data["units"] if not u["modelled"]}
        if set(nd) != set(fm.NOT_MODELLED) or any(u["p"] or u["pc"] for u in nd.values()):
            dbad.append("not modelled units")
        order = [u["name"] for u in data["units"] if u["modelled"]]
        if order != sorted(order, key=lambda n: sort_key(n, lang)):
            dbad.append("order")
        if data["history"] != payload["history"]:
            dbad.append("history")
        check(not dbad, f"{tag} the data block equals the forecast it was made from (24 oblasts x 3 horizons, names in the page language, alert flags, thresholds, bins, history)" + (f": {dbad[:4]}" if dbad else ""))
        jsk = [k for k in fm.JS_TEXTS if k not in data["S"]]
        check(not jsk and data["S"]["ui_seg_item"] == T("ui_seg_item", lang, H="{H}"), f"{tag} the texts the script needs are in the page, in the page language")
        # the map
        i0 = page.index('<svg id="map"')
        svg = page[i0:page.index("</svg>", i0)]
        callout_at = svg.index('<g class="callout"')
        groups = [(re.match(r'<g class="u" data-oblast="([^"]+)" data-iso="([^"]+)"', c).group(1), c) for c in re.split(r'(?=<g class="u[ "])', svg[:callout_at]) if c.startswith('<g class="u" data-oblast=')]
        check(sorted(g[0] for g in groups) == sorted(fm.OURS), f"{tag} every one of our 24 units is on the map exactly once ({len(groups)} groups)")
        bad = []
        for name, body in groups:
            r = by[name]
            iso = iso_of[name]
            if f'id="p-{iso}"' not in body or 'role="button"' not in body or 'tabindex="0"' not in body or 'aria-pressed="false"' not in body:
                bad.append((name, "path id / button role"))
            cls = re.search(r'<path id="p-[^"]+" class="([^"]+)"', body).group(1).split()
            shown = short_name(name, lang)
            for h in fm.HORIZONS:
                if f"p{h}-{fm.bin_of(r['p'][h])}" not in cls:
                    bad.append((name, h, "colour class"))
                if name == "Kyiv City":
                    continue
                m = re.search(rf'<g class="lab l{h} q(\d)">(.*?)</g>', body, re.S)
                if int(m.group(1)) != fm.bin_of(r["p"][h]):
                    bad.append((name, h, "text class"))
                txt = re.search(r'<text class="pc"[^>]*>([^<]*)<', m.group(2)).group(1)
                want = f"{100 * r['p'][h]:.0f}% " + ("▲" if r["p"][h] >= thr[h] else "▽")
                if txt != want:
                    bad.append((name, h, txt, want))
                label = "".join(re.findall(r'<text class="nm"[^>]*>([^<]*)<', m.group(2)))
                if label.replace("-", "") != shown.replace("-", ""):
                    bad.append((name, "name", label, shown))
            if (name != "Kyiv City") and (('class="badge"' in body) != r["now"]):
                bad.append((name, "badge"))
        check(not bad, f"{tag} colour class, name, percentage, triangle (at or above the threshold) and alert badge right for every unit and horizon" + (f": {bad[:4]}" if bad else ""))
        call = svg[callout_at:]
        kc = by["Kyiv City"]
        ok = all(f'class="lab l{h} q{fm.bin_of(kc["p"][h])}"' in call and f"{100 * kc['p'][h]:.0f}% " + ("▲" if kc["p"][h] >= thr[h] else "▽") in call for h in fm.HORIZONS)
        check(ok and (('class="badge"' in call) == kc["now"]) and short_name("Kyiv City", lang) in call and 'data-iso="UA-30"' in call and 'role="button"' in call,
              f"{tag} the Kyiv City call-out repeats its three probabilities, triangles and alert state, and can be selected")
        check(svg.count('class="u nd"') == 3 and svg.count(T("pg_nodata", lang)) >= 2 and '<path id="hl-hover"' in svg and '<path id="hl-sel"' in svg,
              f"{tag} Crimea, Sevastopol and Luhansk are grey, hatched; Crimea and Luhansk say \"{T('pg_nodata', lang)}\"; hover and selection outlines exist")
        check("<title>" not in svg, f"{tag} no tooltip text inside the map")
        # the page around the map
        topbar = page[page.index('<header class="topbar">'):page.index("</header>")]
        needs = {"sentence": T("ui_sentence", lang), "brand": T("ui_brand", lang), "fresh pill": 'id="fresh"', "model": T("ui_model", lang, model=payload["model"]), "version": payload["version"],
                 "origin": T("ui_origin", lang, hm=offset, t=origin), "how button": f'id="how"', "how label": T("ui_how", lang)}
        miss = [k for k, v in needs.items() if v not in topbar]
        check(not miss, f"{tag} the top bar has the sentence, the freshness pill, the model and its version, the origin hour in Kyiv time and UTC, and the how-to button" + (f" (missing {miss})" if miss else ""))
        fresh_txt = re.search(r'<span id="fresh-text">(.*?)</span>', page).group(1)
        check(fresh_txt == (T("ui_replay_pill", lang) if mode == "replay" else T("ui_fresh_static", lang, made=pd.Timestamp(payload["made"]))), f"{tag} the freshness pill has a text before any script runs ({fresh_txt})")
        import html as _html
        pop = _html.unescape(page[page.index('id="howpop"'):page.index('<div class="sr"')])
        items = T("ui_how_items", lang)
        check(all(h in pop and t in pop for h, t in items) and len(items) == 6 and T("ui_how_title", lang) in pop and 'role="dialog"' in pop and ' hidden>' in page[page.index('id="howpop"') - 5:page.index('id="howpop"') + 200],
              f"{tag} the how-to popover has its six explanations and the about section, and starts closed")
        about_miss = [n for n in [payload["model_text"]] + payload["notes"] if n.lstrip("!") not in pop]
        check(not about_miss, f"{tag} every note (freshness, calibration, status lines) is in the popover's about section" + (f": {about_miss[:2]}" if about_miss else ""))
        warn = T("pg_warn_prefixes", lang) + ("!",)
        has_warn = any(n.startswith(warn) for n in payload["notes"])
        check(('class="banner"' in page) == has_warn, f"{tag} the warning banner is there exactly when a note is a warning ({'training-period note' if has_warn else 'none'})")
        footer = page[page.index('<footer class="strip">'):page.index("</footer>")]
        check(T("pg_footer", lang) in footer and page.count("<footer") == 1, f"{tag} the footer line says it is a study model, follow the official alerts")
        seg = page[page.index('id="seg"'):page.index('class="readout"')]
        check(seg.count('role="radio"') == 3 and 'role="radiogroup"' in seg and all(T("ui_seg_item", lang, H=h) in seg for h in fm.HORIZONS), f"{tag} the 1 / 3 / 6 h control is a radio group with three radios")
        legend = page[page.index('<div class="legend">'):page.index("</section>")]
        check(all(b in legend for b in T("pg_bins", lang)) and T("pg_lg_alert", lang) in legend and T("pg_lg_above", lang) in legend, f"{tag} the legend names the five bins, the triangles, the badge and the grey")
        nos = page[page.index("<noscript>"):page.index("</noscript>")]
        rows_html = re.findall(r"<tr><td>([^<]+)</td><td>([^<]+)</td>(.*?)</tr>", nos)
        tbl_ok = len(rows_html) == 24 and [r[0] for r in rows_html] == sorted([r[0] for r in rows_html], key=lambda n: sort_key(n, lang))
        for name, now, cells in rows_html:
            r = next(v for k, v in by.items() if short_name(k, lang) == name)
            vals = re.findall(rf">(\d\.\d{{3}}) ({T('pg_above', lang)}|{T('pg_below', lang)})<", cells)
            tbl_ok &= [v[0] for v in vals] == [f"{r['p'][h]:.3f}" for h in fm.HORIZONS]
            tbl_ok &= [v[1] for v in vals] == [T("pg_above" if r["p"][h] >= thr[h] else "pg_below", lang) for h in fm.HORIZONS]
            tbl_ok &= (now == T("pg_alert_yes", lang)) == r["now"]
        check(tbl_ok and T("ui_noscript", lang) in nos, f"{tag} the fallback table (no script) has all 24 rows, in alphabetical order of the language, with the same numbers")
        check(f'<html lang="{lang}">' in page and "color-scheme:dark" in page and 'name="viewport"' in page, f"{tag} page language, one dark colour scheme, viewport")
        css = page[page.index("<style>"):page.index("</style>")]
        raw_hex = re.findall(r"[:(,\s]#[0-9a-fA-F]{3,8}\b", re.sub(r":root\{.*?\n  --sp-1", ":root{ --sp-1", css, count=1, flags=re.S))
        raw_px = [m for m in re.findall(r"([^{}]*)\{[^}]*font-size:(\d+)px", css) if not re.search(r"\.nm|\.pc|\.nodata|\.badge text|\.hist svg text|\.mini|\.chip b\.bd|\.strip b|\.bignum", m[0])]
        tokens_ok = all(f"--sp-{i}:" in css for i in range(1, 7)) and all(f"--fs-{k}:" in css for k in ("xs", "sm", "md", "lg", "xl", "2xl", "hero")) and all(f"--r-{k}:" in css for k in ("sm", "md", "lg", "pill"))
        check(tokens_ok and not raw_hex and not raw_px,
              f"{tag} one design system: spacing, type and radius scales defined; no colour outside the tokens and no font size outside the scale (except the map's own labels)" + (f" (raw colours {raw_hex[:3]}, raw sizes {raw_px[:3]})" if raw_hex or raw_px else ""))
        if lang == "uk" and mode == "live":
            body_text = re.sub(r"<style>.*?</style>|<script.*?</script>", "", page, flags=re.S)
            visible = re.sub(r"<[^>]+>", " ", body_text)
            english = [w for w in ("Origin hour", "within ", "Chance that", "Alert at", "under alert", " above", " below", "Kyiv time", "page made", "A study model", "Hover", "All oblasts", "Frozen thresholds", "Kharkivska", "Crimea", "Luhansk", "How to read", "Highest probability")
                       if w in visible]
            check(not english, f"{tag} nothing of the page chrome is left in English" + (f": {english}" if english else ""))
            js = re.findall(r"<script>(.*?)</script>", page, re.S)[0]
            leftovers = [w for w in ("Highest", "All oblasts", "How the forecast", "Three horizons") if w in js]
            check(not leftovers, f"{tag} no English text hard-coded in the script")
            import shutil, subprocess
            if shutil.which("node"):
                tmp = Path(tempfile.mkdtemp()) / "page.js"
                tmp.write_text(js)
                r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
                check(r.returncode == 0, f"{tag} the script is valid JavaScript (node --check)" + (f": {r.stderr[:200]}" if r.returncode else ""))
            else:
                print("skip  the script's syntax check: node is not installed")
    # a missing row is an error, not a silently empty oblast
    p1 = synthetic(pd.Timestamp("2026-10-10 12:00", tz="UTC"), rng)
    p1["lang"] = lang
    p1["rows"] = p1["rows"][1:]
    try:
        fm.render(p1)
        check(False, "a missing oblast row stops the render")
    except ValueError:
        check(True, f"[{lang}] a missing oblast row stops the render (ValueError), it is not drawn empty")
    with contextlib.redirect_stderr(io.StringIO()) as err:
        res = fm.write_or_warn(dict(p1), Path(tempfile.mkdtemp()) / "x.html")
    check(res is None and T("map_not_written", lang, err="")[:12] in err.getvalue(), f"[{lang}] write_or_warn turns a failure into one line on stderr and returns None")
    # a payload with a script-closing string in a note cannot break out of the data block
    p2 = synthetic(pd.Timestamp("2026-10-10 12:00", tz="UTC"), rng)
    p2["lang"] = lang
    p2["notes"] = ["</script><script>alert(1)</script>"]
    pg2 = fm.render(p2)
    check(pg2.count("<script") == 2 and "<script>alert" not in pg2, f"[{lang}] text from a note cannot close the script or add one")


def history_checks():
    import csv
    tmp = Path(tempfile.mkdtemp()) / "log.csv"
    names = sorted(fm.OURS)
    with open(tmp, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["origin_utc", "oblast", "h", "probability", "above_threshold", "threshold", "model_version", "run_time_utc"])
        for origin, run, ver, val in (("2026-10-10T10:00:00Z", "2026-10-10T10:20:00Z", "frozen-v2-aaa", 0.30), ("2026-10-10T11:00:00Z", "2026-10-10T11:20:00Z", "frozen-v2-aaa", 0.40),
                                      ("2026-10-10T11:00:00Z", "2026-10-10T11:50:00Z", "frozen-v2-aaa", 0.45),   # the same origin hour run again: the later run counts
                                      ("2026-10-10T12:00:00Z", "2026-10-10T12:20:00Z", "frozen-r13-bbb", 0.99),  # another model: not in this chart
                                      ("2026-10-10T13:00:00Z", "2026-10-10T13:20:00Z", "frozen-v2-aaa", 0.50)):
            for n in names:
                for H in fm.HORIZONS:
                    w.writerow([origin, n, H, f"{val + H / 100:.8f}", 0, "0.25", ver, run])
        for H in fm.HORIZONS:  # a run that is cut off (one oblast missing) is not used
            for n in names[1:]:
                w.writerow(["2026-10-10T14:00:00Z", n, H, "0.1", 0, "0.25", "frozen-v2-aaa", "2026-10-10T14:20:00Z"])
    h = fm.history_from_log(tmp, "frozen-v2-aaa")
    runs = h["runs"]
    kharkiv = fm.OURS["Kharkivska oblast"][0]
    ok = (len(runs) == 3 and [r["o"] for r in runs] == ["2026-10-10T10:00:00Z", "2026-10-10T11:00:00Z", "2026-10-10T13:00:00Z"]
          and abs(runs[1]["p"][kharkiv]["3"] - 0.48) < 1e-9 and runs[0]["lbl"] == "10-10 13:00" and set(runs[0]["p"][kharkiv]) == {"1", "3", "6"})
    check(ok, "history from the prediction log: this model's runs only, one per origin hour (the latest run), a cut-off run skipped, oldest first, labels in Kyiv time")
    check(fm.history_from_log(tmp, "frozen-v2-aaa", limit=2)["runs"][0]["o"] == "2026-10-10T11:00:00Z" and fm.history_from_log(Path(tempfile.mkdtemp()) / "none.csv", "x") == {"runs": []},
          "history keeps the last N runs, and an absent log gives no runs")


MACHADO = {"protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],   # Machado, Oliveira and Fernandes (2009), severity 1.0, linear RGB
           "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]}


def oklab(hex_, kind=None):
    c = np.array([int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    if kind:
        c = np.clip(np.array(MACHADO[kind]) @ c, 0, 1)
    l, m, s = np.cbrt(np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]]) @ c)
    return np.array([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s])


def delta_e(a, b, kind=None):
    return float(100 * np.linalg.norm(oklab(a, kind) - oklab(b, kind)))


def colour_checks():
    ramp, tk = fm.RAMP, fm.TOKENS
    Ls = [float(oklab(c)[0]) for c in ramp]
    d = np.diff(Ls)
    check((d > 0).all() and np.abs(d).min() >= 0.06, f"ramp is monotone in lightness (lighter = more probable), smallest step {np.abs(d).min():.3f} (>= 0.06)")
    de = {k: min(delta_e(a, b, k) for a, b in zip(ramp[:-1], ramp[1:])) for k in (None, "protan", "deutan")}
    check(min(de.values()) >= 12, f"neighbouring bins are clearly apart: smallest OKLab x100 difference {de[None]:.1f} (normal), {de['protan']:.1f} (protanopia), {de['deutan']:.1f} (deuteranopia); at least 12")
    hues = [np.degrees(np.arctan2(oklab(c)[2], oklab(c)[1])) % 360 for c in ramp]
    check(max(hues) - min(hues) <= 40, f"one blue family: hue spread {max(hues) - min(hues):.0f} degrees (validator limit 40)")
    worst = min(fm.contrast(fm.text_on(c), c) for c in ramp)
    check(worst >= 4.5, f"text on every fill reads at {worst:.1f}:1 (>= 4.5)")
    check(fm.contrast(ramp[0], tk["map"]) >= 2.0, f"darkest fill against the map colour {fm.contrast(ramp[0], tk['map']):.2f}:1 (2:1 floor of the ordinal ramp rule)")
    gap = min(fm.contrast(tk["edge"], c) for c in ramp)
    check(gap >= 2.0, f"the thin line between oblasts stands out from every fill: {gap:.2f}:1 (>= 2)")
    check(fm.contrast(tk["alert"], tk["map"]) >= 3 and fm.contrast(tk["white"], tk["alert"]) >= 4.5, f"alert badge {fm.contrast(tk['alert'], tk['map']):.1f}:1 on the map, its ! {fm.contrast(tk['white'], tk['alert']):.1f}:1 on it")
    surfaces = [tk["bg"], tk["map"], tk["surface"], tk["surface_2"]]
    check(all(fm.contrast(tk["text"], s_) >= 7 and fm.contrast(tk["text_2"], s_) >= 4.5 and fm.contrast(tk["text_3"], s_) >= 4.5 for s_ in surfaces),
          f"page text readable on every surface (text >= 7, text-2 and text-3 >= 4.5; the faintest is {min(fm.contrast(tk['text_3'], s_) for s_ in surfaces):.1f}:1)")
    check(all(fm.contrast(tk[k], tk["surface"]) >= 3 for k in ("accent", "focus", "warn", "ok", "bad")) and fm.contrast(tk["accent"], tk["surface"]) >= 4.5,
          "accent, focus ring and status colours are at least 3:1 on the panel (accent 4.5:1)")
    check(fm.contrast(tk["warn_text"], tk["warn_bg"]) >= 4.5 and fm.contrast(tk["alert_text"], tk["alert_bg"]) >= 4.5 and fm.contrast(tk["on_warn"], tk["warn"]) >= 4.5,
          "banner, alert-status and warning-icon text read at 4.5:1 or more")
    check(fm.contrast(tk["nd_line"], tk["nd"]) >= 1.5 and fm.contrast(tk["nd"], tk["map"]) >= 1.1, "the grey hatched 'no data' area is visible against the map and not mistaken for a probability bin (neutral grey, hatched)")
    check(len(fm.RAMP) == len(fm.BIN_NAMES) == len(fm.EDGES) + 1 == 5, "5 bins, 4 edges, 5 names, 5 colours")


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
        for lang in ("uk", "en", None):  # None: no --lang at all, which must be Ukrainian
            for argv in (["--at", "2026-08-20 12:00", "--all"], ["--at", "2026-08-20 12:00", "--oblast", "Kyivska"]):
                tmp.unlink(missing_ok=True)
                sys.argv = ["predict.py", *argv, *(["--lang", lang] if lang else [])]
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    predict.main()
                page = tmp.read_text(encoding="utf-8")
                out = buf.getvalue()
                lg = lang or "uk"
                tag = f"predict.py {' '.join(argv)}{' --lang ' + lang if lang else ''}"
                data = extract_data(page)
                check(len(data["units"]) == 27 and "frozen-r13-" in page and "2026-08-20 12:00 UTC" in page and "15:00" in page and f'<html lang="{lg}">' in page and data["mode"] == "replay" and data["history"] is None,
                      f"{tag}: page written for all oblasts, replay mode without history, round-13 model fingerprint, origin hour in UTC and Kyiv time, page language {lg}")
                check(T("map_written", lg, path="")[:10] in out, "  and says so on stdout, in the same language")
                check(T("map_replay", lg) in page and T("ui_hist_replay", lg) in page.replace("&#x27;", "'") + json.dumps(data["S"], ensure_ascii=False), "  and carries the replay text")
                has_cyr = bool(re.search("[а-яіїєґ]", out.lower()))
                check(has_cyr == (lg == "uk"), f"  terminal output {'is' if lg == 'uk' else 'has no'} Ukrainian")
                if lg == "uk":
                    left = [w for w in ("oblast", "Kyivska", "Kyiv City", "chance", "alert", "yesterday", "Inputs", "Under alert", "Next new") if w in out]
                    check(not left, "  and nothing of the terminal text is left in English" + (f": {left}" if left else ""))
                    if "--all" in argv:
                        lines = out.split("\n")
                        first_col = [ln.split()[0] for ln in lines[lines.index(next(l for l in lines if l.strip().startswith("область"))) + 1:] if ln.strip() and not ln.startswith(("Карту", "[", "н/д"))]
                        check(len(first_col) == 24 and first_col == sorted(first_col, key=lambda n: sort_key(n, "uk")), "  and the table is in Ukrainian alphabetical order")
    finally:
        fm.OUT, sys.argv = old_out, old_argv


def browser_check():
    import shutil, subprocess
    js = ROOT / "scripts" / "check_forecast_map_browser.js"
    probe = ["/opt/node-tools/node_modules/playwright", "playwright"]
    if not shutil.which("node"):
        print("skip  browser checks: node is not installed")
        return
    tmp = Path(tempfile.mkdtemp())
    rng = np.random.default_rng(5)
    names = sorted(fm.OURS)
    pages = {}
    for lang, mode, runs in (("uk", "live", 4), ("en", "live", 4), ("uk", "live", 1), ("uk", "replay", 0)):
        payload = synthetic(pd.Timestamp("2026-10-10 12:00", tz="UTC"), rng)
        payload["lang"], payload["mode"] = lang, mode
        hist = [{"o": f"2026-10-10T{6 + 2 * k:02d}:00:00Z", "lbl": f"10-10 {9 + 2 * k:02d}:00", "p": {fm.OURS[n][0]: {str(H): round(float(rng.uniform(0, 1)), 3) for H in fm.HORIZONS} for n in names}} for k in range(runs)]
        payload["history"] = {"runs": hist} if mode == "live" else None
        f = tmp / f"{lang}_{mode}_{runs}.html"
        f.write_text(fm.render(payload), encoding="utf-8")
        pages[f.name] = str(f)
    env = {**__import__("os").environ, "NODE_PATH": "/opt/node-tools/node_modules"}
    r = subprocess.run(["node", str(js), str(tmp)], capture_output=True, text=True, env=env)
    out = r.stdout + r.stderr
    if "Cannot find module" in out and "playwright" in out:
        print("skip  browser checks: the playwright package for node is not installed (npm i playwright)")
        return
    for line in out.strip().split("\n"):
        if line.startswith("ok    ") or line.startswith("FAIL  "):
            check(line.startswith("ok    "), line[6:])
        elif line.strip():
            print("      " + line)
    if r.returncode not in (0, 1):
        check(False, f"the browser check crashed: {out[-300:]}")


if __name__ == "__main__":
    names_and_geometry()
    uk_names()
    i18n_checks()
    freshness_checks()
    history_checks()
    page_checks("uk")
    page_checks("en")
    colour_checks()
    at_check()
    browser_check()
    print()
    print("forecast map checks: " + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
    sys.exit(1 if FAILS else 0)
