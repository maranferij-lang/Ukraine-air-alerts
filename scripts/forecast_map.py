"""The forecast map: one self-contained HTML page (output/forecast_map.html, git-ignored) written after every `predict.py --now` and `predict.py --at`.

A dark, map-first page: top bar (what it shows in one sentence, how old the data is, which model, how to read it), the map of the oblasts on the left with a 1 h / 3 h / 6 h
switch, a side panel on the right (the five most probable oblasts; click an oblast for its big number, the three horizons with the threshold, the alert state and how its
forecast changed over the last runs of data/predictions/log.csv), a bottom sheet instead of the panel on a phone, and a footer line that always says what this is.
The page has inline script and style and nothing else: no request of any kind when it is opened. The template is scripts/forecast_map_page.html; this module fills it.

Oblast outlines: data/geo/ukraine_oblasts.geojson (Natural Earth, public domain; source and licence in data/geo/README.md), matched to our 24 units by ISO 3166-2 code (OURS
below; scripts/check_forecast_map.py checks that match). Crimea (with Sevastopol) and Luhansk are not modelled: grey, hatched, "no data".
Colour is never the only carrier: percentages in text, a triangle for at or above the frozen threshold, a "!" badge for an alert at the origin hour.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.i18n import S, T, full_name, map_unit_name, short_name, sort_key, unit_full_name

GEO = ROOT / "data" / "geo" / "ukraine_oblasts.geojson"
OUT = ROOT / "output" / "forecast_map.html"
HORIZONS = (1, 3, 6)

# our unit name -> (ISO 3166-2 code of the Natural Earth feature, a name that feature must carry in name / name_en / name_alt)
OURS = {
    "Cherkaska oblast": ("UA-71", "Cherkasy"), "Chernihivska oblast": ("UA-74", "Chernihiv"), "Chernivetska oblast": ("UA-77", "Chernivtsi"),
    "Dnipropetrovska oblast": ("UA-12", "Dnipropetrovsk"), "Donetska oblast": ("UA-14", "Donetsk"), "Ivano-Frankivska oblast": ("UA-26", "Ivano-Frankivsk"),
    "Kharkivska oblast": ("UA-63", "Kharkiv"), "Khersonska oblast": ("UA-65", "Kherson"), "Khmelnytska oblast": ("UA-68", "Khmelnytskyi"),
    "Kirovohradska oblast": ("UA-35", "Kirovohrad"), "Kyiv City": ("UA-30", "Kiev City"), "Kyivska oblast": ("UA-32", "Kyyivs'ka Oblast'"),
    "Lvivska oblast": ("UA-46", "Lviv"), "Mykolaivska oblast": ("UA-48", "Mykolaiv"), "Odeska oblast": ("UA-51", "Odesa"), "Poltavska oblast": ("UA-53", "Poltava"),
    "Rivnenska oblast": ("UA-56", "Rivne"), "Sumska oblast": ("UA-59", "Sumy"), "Ternopilska oblast": ("UA-61", "Ternopil"), "Vinnytska oblast": ("UA-05", "Vinnytsia"),
    "Volynska oblast": ("UA-07", "Volyn"), "Zakarpatska oblast": ("UA-21", "Zakarpattia"), "Zaporizka oblast": ("UA-23", "Zaporizhzhia"),
    "Zhytomyrska oblast": ("UA-18", "Zhytomyr"),
}
NOT_MODELLED = {"UA-09": "Luhansk", "UA-43": "Crimea", "UA-40": "Sevastopol"}  # Luhansk: permanent alert, left out of the model; Crimea and Sevastopol: not in the data
NO_LABEL = {"UA-40"}                                                           # too small to carry a label (drawn grey, in the tooltip)

EDGES = [0.10, 0.25, 0.50, 0.75]
BIN_NAMES = T("pg_bins", "en")
RAMP = ["#374991", "#5173bc", "#6ea0e8", "#a0cdff", "#edf6ff"]  # more probable = lighter; hue 270 to 245 degrees; neighbours at least 13 apart (OKLab x100), also with red-green colour blindness; the darkest is 2:1 on the map colour
TOKENS = dict(  # the one dark theme: surfaces, text, accents, status colours, the map's own greys
    bg="#0b0e13", map="#0e131a", surface="#141a23", surface_2="#1b2330", line="#273141", line_2="#364458",
    text="#eef2f7", text_2="#b4bdca", text_3="#8793a3", accent="#8ec5ff", focus="#ffd166", alert="#d03b3b", ok="#3ecf8e", warn="#f5a524", bad="#ff6b6b",
    nd="#2a313c", nd_line="#5b6676", edge="#0e131a", white="#ffffff", hover="#202a39", info_line="#3d5c8f", on_warn="#1a1200",
    warn_bg="#3a2a05", warn_line="#6b4e0a", warn_text="#ffd98a", alert_bg="#3b1416", alert_line="#7a2a2d", alert_text="#ffb3b3")
WIDTH, MARGIN, TOP_PAD = 900, 14, 64
COS_LAT = 0.66
TEMPLATE = Path(__file__).resolve().with_name("forecast_map_page.html")
JS_TEXTS = ["ui_ago", "ui_fresh_live", "ui_stale", "ui_top_title", "ui_top_sub", "ui_all", "ui_back", "ui_big_cap", "ui_thr_above", "ui_thr_below", "ui_bars", "ui_bars_legend",
            "ui_alert_yes", "ui_alert_no", "ui_hist_title", "ui_hist_n", "ui_hist_none", "ui_hist_replay", "ui_hist_thr", "ui_nodata_detail", "ui_rank", "ui_seg_item",
            "ui_rel_above", "ui_rel_below"]  # the texts the page's script needs, in the page's language


def bin_of(p):
    return sum(p >= e for e in EDGES)


def luminance(hex_):
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_on(fill):
    """Black or white, whichever reads better on `fill`."""
    return max(("#0b0b0b", "#ffffff"), key=lambda c: contrast(c, fill))


def load_geo(path=None):
    return json.loads(Path(path or GEO).read_text(encoding="utf-8"))["features"]


def short(name):
    return short_name(name)


def _project(features):
    xs = [c[0] for f in features for poly in f["geometry"]["coordinates"] for r in poly for c in r]
    ys = [c[1] for f in features for poly in f["geometry"]["coordinates"] for r in poly for c in r]
    lon0, lon1, lat0, lat1 = min(xs), max(xs), min(ys), max(ys)
    k = (WIDTH - 2 * MARGIN) / ((lon1 - lon0) * COS_LAT)
    height = int((lat1 - lat0) * k + 2 * MARGIN + TOP_PAD)
    return (lambda lon, lat: ((lon - lon0) * COS_LAT * k + MARGIN, (lat1 - lat) * k + MARGIN + TOP_PAD)), height


def _path(poly, proj):
    parts = []
    for ring in poly:
        pts = [proj(*c) for c in ring[:-1]]
        parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(parts)


def tokens_css():
    css = "".join(f"--{k.replace('_', '-')}:{v};" for k, v in TOKENS.items())
    return css + "".join(f"--c{k}:{c};--t{k}:{text_on(c)};" for k, c in enumerate(RAMP))


def map_css():
    css = []
    for h in HORIZONS:
        css.append(f'body[data-h="{h}"] .l{h}{{display:inline}}')
        css += [f'body[data-h="{h}"] .p{h}-{k}{{fill:var(--c{k})}}' for k in range(len(RAMP))]
    css += [f".q{k} text{{fill:var(--t{k})}}.q{k} rect{{fill:var(--c{k})}}.sw-{k}{{background:var(--c{k})}}" for k in range(len(RAMP))]
    return "\n".join(css)


def history_from_log(path, version, limit=24):
    """The last `limit` forecasts of one model version from the prediction log (data/predictions/log.csv), one per origin hour (the latest run of that hour), oldest first:
    {"runs": [{"o": origin as ISO, "lbl": "10-10 15:00" in Kyiv time, "p": {ISO code: {"1": p, "3": p, "6": p}}}]}. An empty list of runs if the log is not there."""
    import csv
    path = Path(path)
    iso_of = {n: iso for n, (iso, _) in OURS.items()}
    by_origin = {}
    if path.exists() and path.stat().st_size:
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["model_version"] != version or r["oblast"] not in iso_of:
                    continue
                run = by_origin.setdefault(r["origin_utc"], {}).setdefault(r["run_time_utc"], {})
                run.setdefault(iso_of[r["oblast"]], {})[r["h"]] = float(r["probability"])
    runs = []
    for origin in sorted(by_origin):
        latest = by_origin[origin][max(by_origin[origin])]
        if len(latest) == len(OURS) and all(len(v) == len(HORIZONS) for v in latest.values()):
            t = pd.Timestamp(origin)
            runs.append({"o": origin, "lbl": f"{t.tz_convert('Europe/Kyiv'):%m-%d %H:%M}", "p": latest})
    return {"runs": runs[-limit:]}


def render(payload, features=None):
    """The whole page as a string. `payload`: origin, made (Timestamps), mode ("live" or "replay"), model, version, model_text, thresholds {H: threshold}, notes [str],
    rows [{oblast, now, p: {H: probability}}], history (history_from_log or None), lang ("uk" default, or "en")."""
    features = features or load_geo()
    lang = payload.get("lang", "uk")
    mode = payload.get("mode", "live")
    proj, height = _project(features)
    rows = {r["oblast"]: r for r in payload["rows"]}
    thr = {int(h): v for h, v in payload["thresholds"].items()}
    origin = pd.Timestamp(payload["origin"])
    kyiv = origin.tz_convert("Europe/Kyiv")
    made = pd.Timestamp(payload["made"])
    esc = html.escape

    def pct(p):
        return f"{100 * p:.0f}%"

    def tri(p, h):
        return "\u25b2" if p >= thr[h] else "\u25bd"

    units, data_units, units_html = [], [], []
    kyiv_city = None
    ordered = sorted(features, key=lambda f: (f["properties"]["ours"] == "Kyiv City", f["properties"]["iso"]))  # the city last, so it is on top of its oblast
    for f in ordered:
        pr = f["properties"]
        ours, iso = pr["ours"], pr["iso"]
        r = rows.get(ours) if ours else None
        if ours and r is None:
            raise ValueError(f"no forecast row for {ours}")
        name = ours or NOT_MODELLED[iso]
        d = "".join(_path(poly, proj) for poly in f["geometry"]["coordinates"])
        lx, ly = proj(*pr["label"])
        if r is None:
            shown = map_unit_name(name, lang)
            data_units.append(dict(iso=iso, name=shown, full=unit_full_name(name, lang), modelled=False, now=False, p={}, pc={}))
            lab = "" if iso in NO_LABEL else (f'<text class="nodata" x="{lx:.1f}" y="{ly - 3:.1f}">{esc(shown)}</text>'
                                              f'<text class="nodata" x="{lx:.1f}" y="{ly + 9:.1f}">{T("pg_nodata", lang)}</text>')
            units_html.append(f'<g class="u nd" data-iso="{iso}" role="button" tabindex="0" aria-pressed="false" aria-label="{esc(shown)}"><path id="p-{iso}" d="{d}"/>{lab}</g>')
            continue
        shown = short_name(ours, lang)
        data_units.append(dict(iso=iso, name=shown, full=full_name(ours, lang), modelled=True, now=bool(r["now"]),
                               p={str(h): r["p"][h] for h in HORIZONS}, pc={str(h): pct(r["p"][h]) for h in HORIZONS}))
        classes = " ".join(f"p{h}-{bin_of(r['p'][h])}" for h in HORIZONS)
        labs = []
        for h in HORIZONS:
            if ours == "Kyiv City":
                continue
            two = shown.split("-", 1)
            lines = [two[0] + "-", two[1]] if len(shown) > 11 and len(two) == 2 else [shown]
            tspans = "".join(f'<text class="nm" x="{lx:.1f}" y="{ly - 8 + 9 * i - 9 * (len(lines) - 1):.1f}">{esc(t)}</text>' for i, t in enumerate(lines))
            labs.append(f'<g class="lab l{h} q{bin_of(r["p"][h])}">{tspans}<text class="pc" x="{lx:.1f}" y="{ly + 6:.1f}">{pct(r["p"][h])} {tri(r["p"][h], h)}</text></g>')
        badge = ""
        if r["now"] and ours != "Kyiv City":
            widest = max(len(t) for t in (shown.split("-", 1) if len(shown) > 11 and "-" in shown else [shown]))
            bx_ = lx - max(20, widest * 2.7) - 11  # left of the wider of the name and the percentage line, so the badge never sits on a letter
            badge = f'<g class="badge"><circle cx="{bx_:.1f}" cy="{ly + 2:.1f}" r="8"/><text x="{bx_:.1f}" y="{ly + 6:.1f}">!</text></g>'
        units_html.append(f'<g class="u" data-oblast="{esc(ours)}" data-iso="{iso}" role="button" tabindex="0" aria-pressed="false" aria-label="{esc(shown)}: {pct(r["p"][1])}">'
                          f'<path id="p-{iso}" class="{classes}" d="{d}"/>{"".join(labs)}{badge}</g>')
        if ours == "Kyiv City":
            kyiv_city = (r, proj(*pr["label"]))

    # Kyiv City: the outline itself is small, so a call-out in the empty corner above the north-west of the country repeats its numbers (it can be clicked, like the outline)
    callout = ""
    if kyiv_city:
        r, (cx, cy) = kyiv_city
        bx, by, bw, bh = 150, 6, 190, 50
        labs = []
        for h in HORIZONS:
            labs.append(f'<g class="lab l{h} q{bin_of(r["p"][h])}"><rect x="{bx + 6}" y="{by + 24}" width="{bw - 12}" height="22" rx="4"/>'
                        f'<text class="pc kv" x="{bx + 12}" y="{by + 40}">{pct(r["p"][h])} {tri(r["p"][h], h)}</text></g>')
        bad = f'<g class="badge"><circle cx="{bx + bw - 14}" cy="{by + 14}" r="8"/><text x="{bx + bw - 14}" y="{by + 18}">!</text></g>' if r["now"] else ""
        callout = (f'<g class="callout" data-iso="UA-30" role="button" tabindex="0" aria-label="{esc(short_name("Kyiv City", lang))}"><path class="leader" d="M{cx:.1f},{cy:.1f}L{bx + bw / 2:.1f},{by + bh:.1f}"/>'
                   f'<rect class="box" x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6"/>'
                   f'<text class="kv" x="{bx + 10}" y="{by + 17}" style="font-size:12px;font-weight:700">{esc(short_name("Kyiv City", lang))}</text>{bad}'
                   f'{"".join(labs)}<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" style="fill:var(--text)"/></g>')

    data_units.sort(key=lambda u: (not u["modelled"], sort_key(u["name"], lang)))
    bins = T("pg_bins", lang)
    legend = ('<span class="scale">' + "".join(f'<span class="chip"><i class="sw-{k}"></i>{esc(bins[k])}</span>' for k in range(len(RAMP))) + "</span>"
              f'<span class="chip"><i style="background:var(--nd)"></i>{T("pg_lg_nd", lang)}</span>'
              f'<span class="chip"><b>\u25b2</b> {T("pg_lg_above", lang)}</span><span class="chip"><b>\u25bd</b> {T("pg_lg_below", lang)}</span>'
              f'<span class="chip"><b class="bd">!</b> {T("pg_lg_alert", lang)}</span>')
    seg = "".join(f'<button type="button" role="radio" data-h="{h}" aria-checked="{"true" if h == 1 else "false"}" tabindex="{0 if h == 1 else -1}">{T("ui_seg_item", lang, H=h)}</button>' for h in HORIZONS)
    thr_txt = T("pg_thr", lang, thr=", ".join(T("pg_thr_item", lang, h=h, v=thr[h]) for h in HORIZONS))
    warn = tuple(T("pg_warn_prefixes", lang)) + ("!",)
    notes = list(payload["notes"])
    banner = "".join(f"<p>{esc(n.lstrip('!'))}</p>" for n in notes if n.startswith(warn))
    banner = f'<div class="banner" role="status">{banner}</div>' if banner else ""
    model_pill = "<span>" + esc(T("ui_model", lang, model=payload["model"])) + f'<span class="fp"> \u00b7 {esc(payload["version"])}</span></span>'
    model_full = T("ui_model", lang, model=f"{payload['model']} \u00b7 {payload['version']}")
    how = "".join(f"<div><dt>{esc(h)}</dt><dd>{esc(t)}</dd></div>" for h, t in T("ui_how_items", lang))
    about = "".join(f"<p>{esc(n.lstrip('!'))}</p>" for n in [model_full, payload["model_text"]] + notes + [thr_txt])
    th = T("pg_th", lang)
    tr = []
    for name in sorted(rows, key=lambda n: sort_key(short_name(n, lang), lang)):
        r = rows[name]
        cells = "".join(f'<td>{r["p"][h]:.3f} {T("pg_above" if r["p"][h] >= thr[h] else "pg_below", lang)}</td>' for h in HORIZONS)
        tr.append(f"<tr><td>{esc(short_name(name, lang))}</td><td>{T('pg_alert_yes' if r['now'] else 'pg_alert_no', lang)}</td>{cells}</tr>")
    table = (f"<h2>{T('pg_h2', lang)}</h2><table><thead><tr>{''.join(f'<th>{esc(c)}</th>' for c in th)}</tr></thead><tbody>{''.join(tr)}</tbody></table>")
    history = payload.get("history")
    data = dict(lang=lang, h=1, mode=mode, made=f"{made.tz_convert('UTC'):%Y-%m-%dT%H:%M:%SZ}", origin=f"{origin.tz_convert('UTC'):%Y-%m-%dT%H:%M:%SZ}",
                thr={str(h): thr[h] for h in HORIZONS}, edges=EDGES, units=data_units, history=history, thrText=thr_txt,
                S={k: S[k][lang] for k in JS_TEXTS})
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8")
    fills = {"{{TOKENS_CSS}}": tokens_css(), "{{MAP_CSS}}": map_css(), "{{LANG}}": lang, "{{H0}}": "1",
             "{{FRESH_CLASS}}": "", "{{FRESH_STATIC}}": esc(T("ui_replay_pill", lang) if mode == "replay" else T("ui_fresh_static", lang, made=made)),
             "{{MODEL_TITLE}}": esc(payload["model_text"]), "{{MODEL_PILL}}": model_pill, "{{ORIGIN_PILL}}": esc(T("ui_origin", lang, hm=f"{kyiv:%H:%M}", t=origin)),
             "{{BANNER}}": banner, "{{SEG}}": seg, "{{W}}": str(WIDTH), "{{HT}}": str(height), "{{UNITS}}": "\n".join(units_html), "{{CALLOUT}}": callout,
             "{{LEGEND}}": legend, "{{HOW}}": how, "{{ABOUT}}": about, "{{NOSCRIPT_TABLE}}": table}
    for k, v in fills.items():
        page = page.replace(k, v)
    page = re.sub(r"\[\[(\w+)\]\]", lambda m: esc(T(m.group(1), lang)), page)
    page = page.replace("{{DATA_JSON}}", data_json)  # last: the data must not be searched for placeholders
    return page


def write(payload, path=None):
    """Writes the page; returns the path."""
    path = Path(path or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(payload), encoding="utf-8")
    return path


def write_or_warn(payload, path=None):
    """For predict.py: a map that cannot be written must not take the forecast down with it. Prints one line either way."""
    try:
        p = write(payload, path)
        shown = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
        print(T("map_written", payload.get("lang", "uk"), path=shown))
        return p
    except Exception as e:  # noqa: BLE001
        print(T("map_not_written", payload.get("lang", "uk"), err=f"{type(e).__name__}: {e}"), file=sys.stderr)
        return None
