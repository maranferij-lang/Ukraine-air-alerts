"""The forecast map: one self-contained HTML file (output/forecast_map.html, git-ignored) written after every `predict.py --now` and `predict.py --at`.

No script, no font, no image, no request of any kind when the page is opened: the oblast outlines (data/geo/ukraine_oblasts.geojson, Natural Earth, public domain;
source and licence in data/geo/README.md) are inlined as SVG paths, the 1 h / 3 h / 6 h switch is plain CSS (radio buttons), colours are CSS variables with a light and a
dark set (prefers-color-scheme). Colour is never the only carrier: every oblast says its probability in text, a triangle for at-or-above the frozen threshold, a "!" badge for
"under alert at the origin hour"; the same numbers are in a table under the map.

The 24 units we model are matched to the file's features by ISO 3166-2 code (OURS below); scripts/check_forecast_map.py checks that match (code, name, completeness).
Crimea (with Sevastopol) and Luhansk are not modelled: grey, hatched, "no data".
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.i18n import T, map_unit_name, short_name, sort_key

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
RAMP = ["#61b9ff", "#2f8ad4", "#005da2", "#003465", "#00112b"]  # light mode, light to dark: one blue family (hue 255 to 245 degrees), lightness-monotone, adjacent bins at least 14 apart (OKLab x100), also as seen with red-green colour blindness
RAMP_DARK = ["#374991", "#5173bc", "#6ea0e8", "#a0cdff", "#edf6ff"]  # dark mode: more probable = lighter, hue 270 to 245 degrees, adjacent bins at least 13 apart; the darkest is 2:1 on the page colour
MODES = {  # light: more probable = darker
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", grid="#d9d8d3", nd="#dcdbd6", nd_line="#8a8984", ramp=RAMP, alert="#d03b3b", edge="#8a8984"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", grid="#383835", nd="#363633", nd_line="#7a7973", ramp=RAMP_DARK, alert="#d03b3b", edge="#8d8c86"),
}
WIDTH, MARGIN, TOP_PAD = 900, 14, 64
COS_LAT = 0.66


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


def _css(units=()):
    def block(m):
        v = MODES[m]
        lines = [f"--surface:{v['surface']};--ink:{v['ink']};--ink2:{v['ink2']};--grid:{v['grid']};--nd:{v['nd']};--nd-line:{v['nd_line']};--edge:{v['edge']};--alert:{v['alert']};"]
        lines += [f"--c{k}:{c};--t{k}:{text_on(c)};" for k, c in enumerate(v["ramp"])]
        return "".join(lines)
    css = [f":root{{color-scheme:light dark;{block('light')}}}",
           f"@media (prefers-color-scheme:dark){{:root{{{block('dark')}}}}}",
           "*{box-sizing:border-box}",
           "body{margin:0;background:var(--surface);color:var(--ink);font:15px/1.45 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}",
           "main{max-width:980px;margin:0 auto;padding:16px}",
           "h1{font-size:1.3rem;margin:0 0 4px}h2{font-size:1.05rem;margin:22px 0 8px}",
           ".sub{margin:0 0 6px;color:var(--ink2)}.note{margin:6px 0;color:var(--ink2);font-size:.9rem}.warn{color:var(--ink);font-weight:600}",
           ".sw input{position:absolute;opacity:0;pointer-events:none}",
           ".tabs{display:flex;gap:8px;margin:14px 0 8px;flex-wrap:wrap}",
           ".tabs label{border:2px solid var(--grid);border-radius:8px;padding:6px 14px;cursor:pointer;font-weight:600}",
           ".stage svg{width:100%;height:auto;display:block}",
           "svg text{font-family:inherit;text-anchor:middle;pointer-events:none}",
           ".nm{font-size:9px;font-weight:500}.pc{font-size:12.5px;font-weight:700}.kv{text-anchor:start}",
           ".u path{stroke:var(--edge);stroke-width:.8;stroke-linejoin:round}.u.nd path{fill:url(#hatch)}",
           ".u:hover path,.u:focus path{stroke:var(--ink);stroke-width:2.5}.u:focus,.callout:focus{outline:none}",
           ".panel{border:1px solid var(--grid);border-radius:8px;padding:8px 12px;margin:0 0 8px;min-height:4.9em;font-size:.92rem;font-variant-numeric:tabular-nums}",
           ".d{display:none}.has-no{display:none}",
           "@supports not selector(:has(a)){.has-yes{display:none}.has-no{display:inline}}",
           ".sw:has(.u:hover) .dflt,.sw:has(.u:focus) .dflt,.sw:has(.callout:hover) .dflt,.sw:has(.callout:focus) .dflt{display:none}",
           ".lab{display:none}.badge circle{fill:var(--alert);stroke:var(--surface);stroke-width:1.5}.badge text{fill:#fff;font-size:11px;font-weight:800}",
           ".nodata{fill:var(--ink2);font-size:9px}",
           ".leader{stroke:var(--ink);stroke-width:1.2;fill:none}.callout .box{fill:var(--surface);stroke:var(--ink);stroke-width:1.5}.callout text{fill:var(--ink)}",
           ".legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin:12px 0 4px;font-size:.85rem;color:var(--ink2);align-items:center}",
           ".chip{display:inline-flex;align-items:center;gap:5px}.chip i{width:22px;height:14px;border-radius:3px;display:inline-block;border:1px solid var(--ink2)}",
           ".chip b.bd{display:inline-block;background:var(--alert);color:#fff;border-radius:50%;width:16px;height:16px;text-align:center;line-height:16px;font-size:11px}",
           "table{border-collapse:collapse;width:100%;font-size:.88rem;font-variant-numeric:tabular-nums}th,td{padding:4px 8px;border-bottom:1px solid var(--grid);text-align:right}",
           "th:first-child,td:first-child{text-align:left}.hot{font-weight:700}",
           "footer{margin-top:22px;padding-top:10px;border-top:1px solid var(--grid);font-weight:600}",
           "@media (max-width:640px){.nm{display:none}.pc{font-size:22px}.badge{transform:translate(37px,-26px)}.badge text{font-size:14px}}"]
    for h in HORIZONS:
        css.append(f"#h{h}:checked~.tabs label[for=h{h}]{{background:var(--ink);color:var(--surface);border-color:var(--ink)}}")
        css.append(f"#h{h}:focus-visible~.tabs label[for=h{h}]{{outline:3px solid var(--alert);outline-offset:2px}}")
        css.append(f"#h{h}:checked~.stage .l{h}{{display:inline}}")
        for k in range(len(RAMP)):
            css.append(f"#h{h}:checked~.stage .p{h}-{k}{{fill:var(--c{k})}}")
    for iso in units:
        sel = [f".u[data-iso=\"{iso}\"]:hover", f".u[data-iso=\"{iso}\"]:focus"] + ([".callout:hover", ".callout:focus"] if iso == "UA-30" else [])
        css.append(",".join(f".sw:has({x}) #d-{iso}" for x in sel) + "{display:block}")
    for k in range(len(RAMP)):
        css.append(f".q{k} text{{fill:var(--t{k})}}.q{k} rect{{fill:var(--c{k})}}.sw-{k}{{background:var(--c{k})}}")
    return "\n".join(css)


def render(payload, features=None):
    """The whole page as a string. `payload`: origin, made, model, version, model_text, thresholds {H: threshold}, notes [str], rows [{oblast, now, p: {H: probability}}],
    and optionally lang ("en" or "uk")."""
    features = features or load_geo()
    lang = payload.get("lang", "en")
    proj, height = _project(features)
    rows = {r["oblast"]: r for r in payload["rows"]}
    thr = payload["thresholds"]
    origin = pd.Timestamp(payload["origin"])
    kyiv = origin.tz_convert("Europe/Kyiv")
    made = pd.Timestamp(payload["made"])
    esc = html.escape

    def pct(p):
        return f"{100 * p:.0f}%"

    def tri(p, h):
        return "\u25b2" if p >= thr[h] else "\u25bd"

    def detail(name, r):
        """The text of the fixed panel for one unit."""
        if r is None:
            return f"<b>{esc(name)}</b>: {T('pg_panel_nodata', lang)}"
        head = f"<b>{esc(short_name(name, lang))}</b>: " + T("pg_panel_alert" if r["now"] else "pg_panel_calm", lang)
        items = [T("pg_panel_h", lang, h=h, p=r["p"][h], rel=T("pg_panel_at" if r["p"][h] >= thr[h] else "pg_panel_under", lang), thr=thr[h]) for h in HORIZONS]
        return head + "<br>" + " · ".join(f"{tri(r['p'][h], h)} {esc(i)}" for h, i in zip(HORIZONS, items))

    body, panels, units = [], [], []
    kyiv_city = None
    ordered = sorted(features, key=lambda f: (f["properties"]["ours"] == "Kyiv City", f["properties"]["iso"]))  # the city last, so it is on top of its oblast
    for f in ordered:
        pr = f["properties"]
        ours = pr["ours"]
        iso = pr["iso"]
        r = rows.get(ours) if ours else None
        if ours and r is None:
            raise ValueError(f"no forecast row for {ours}")
        name = ours or NOT_MODELLED[iso]
        d = "".join(_path(poly, proj) for poly in f["geometry"]["coordinates"])
        lx, ly = proj(*pr["label"])
        units.append(iso)
        if r is None:
            shown = map_unit_name(name, lang)
            panels.append(f'<div class="d" id="d-{iso}">{detail(shown, None)}</div>')
            lab = "" if iso in NO_LABEL else (f'<text class="nodata" x="{lx:.1f}" y="{ly - 3:.1f}">{esc(shown)}</text>'
                                              f'<text class="nodata" x="{lx:.1f}" y="{ly + 9:.1f}">{T("pg_nodata", lang)}</text>')
            body.append(f'<g class="u nd" data-iso="{iso}" tabindex="0"><path d="{d}"/>{lab}</g>')
            continue
        panels.append(f'<div class="d" id="d-{iso}">{detail(ours, r)}</div>')
        classes = " ".join(f"p{h}-{bin_of(r['p'][h])}" for h in HORIZONS)
        labs = []
        for h in HORIZONS:
            if ours == "Kyiv City":
                continue
            nm = short_name(ours, lang)
            two = nm.split("-", 1)
            lines = [two[0] + "-", two[1]] if len(nm) > 11 and len(two) == 2 else [nm]
            tspans = "".join(f'<text class="nm" x="{lx:.1f}" y="{ly - 8 + 9 * i - 9 * (len(lines) - 1):.1f}">{esc(t)}</text>' for i, t in enumerate(lines))
            labs.append(f'<g class="lab l{h} q{bin_of(r["p"][h])}">{tspans}<text class="pc" x="{lx:.1f}" y="{ly + 6:.1f}">{pct(r["p"][h])} {tri(r["p"][h], h)}</text></g>')
        badge = ""
        if r["now"] and ours != "Kyiv City":
            nm = short_name(ours, lang)
            widest = max(len(t) for t in (nm.split("-", 1) if len(nm) > 11 and "-" in nm else [nm]))
            bx_ = lx - max(20, widest * 2.7) - 11  # left of the wider of the name and the percentage line, so the badge never sits on a letter
            badge = f'<g class="badge"><circle cx="{bx_:.1f}" cy="{ly + 2:.1f}" r="8"/><text x="{bx_:.1f}" y="{ly + 6:.1f}">!</text></g>'
        body.append(f'<g class="u" data-oblast="{esc(ours)}" data-iso="{iso}" tabindex="0"><path class="{classes}" d="{d}"/>{"".join(labs)}{badge}</g>')
        if ours == "Kyiv City":
            kyiv_city = (r, proj(*pr["label"]))

    # Kyiv City: the outline itself is small, so a call-out in the empty corner above the north-west of the country repeats its numbers
    callout = ""
    if kyiv_city:
        r, (cx, cy) = kyiv_city
        bx, by, bw, bh = 150, 6, 190, 50
        labs = []
        for h in HORIZONS:
            labs.append(f'<g class="lab l{h} q{bin_of(r["p"][h])}"><rect x="{bx + 6}" y="{by + 24}" width="{bw - 12}" height="22" rx="4"/>'
                        f'<text class="pc kv" x="{bx + 12}" y="{by + 40}">{pct(r["p"][h])} {tri(r["p"][h], h)}</text></g>')
        bad = f'<g class="badge"><circle cx="{bx + bw - 14}" cy="{by + 14}" r="8"/><text x="{bx + bw - 14}" y="{by + 18}">!</text></g>' if r["now"] else ""
        callout = (f'<g class="callout" data-iso="UA-30" tabindex="0"><path class="leader" d="M{cx:.1f},{cy:.1f}L{bx + bw / 2:.1f},{by + bh:.1f}"/>'
                   f'<rect class="box" x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6"/>'
                   f'<text class="kv" x="{bx + 10}" y="{by + 17}" style="font-size:12px;font-weight:700">{esc(short_name("Kyiv City", lang))}</text>{bad}'
                   f'{"".join(labs)}<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" style="fill:var(--ink)"/></g>')

    bins = T("pg_bins", lang)
    legend = "".join(f'<span class="chip"><i class="sw-{k}"></i>{esc(bins[k])}</span>' for k in range(len(RAMP)))
    legend2 = (f'<span class="chip"><i style="background:var(--nd)"></i>{T("pg_lg_nd", lang)}</span>'
               f'<span class="chip"><b>\u25b2</b> {T("pg_lg_above", lang)}</span><span class="chip"><b>\u25bd</b> {T("pg_lg_below", lang)}</span>'
               f'<span class="chip"><b class="bd">!</b> {T("pg_lg_alert", lang)}</span>')
    thr_txt = ", ".join(T("pg_thr_item", lang, h=h, v=thr[h]) for h in HORIZONS)

    tr = []
    for name in sorted(rows, key=lambda n: sort_key(short_name(n, lang), lang)):
        r = rows[name]
        cells = "".join(f'<td class="{"hot" if r["p"][h] >= thr[h] else ""}">{r["p"][h]:.3f} {T("pg_above" if r["p"][h] >= thr[h] else "pg_below", lang)}</td>' for h in HORIZONS)
        tr.append(f"<tr><td>{esc(short_name(name, lang))}</td><td>{T('pg_alert_yes' if r['now'] else 'pg_alert_no', lang)}</td>{cells}</tr>")

    warn = tuple(T("pg_warn_prefixes", lang)) + ("!",)
    notes = "".join(f'<p class="note{" warn" if n.startswith(warn) else ""}">{esc(n.lstrip("!"))}</p>' for n in payload["notes"])
    th = T("pg_th", lang)
    tabs = "".join(f'<label for="h{h}">{T("pg_tab", lang, H=h, unit=T("pg_unit1" if h == 1 else "pg_unit3", lang))}</label>' for h in HORIZONS)
    page = f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{T('pg_title', lang)}</title>
<style>
{_css(units)}
</style></head>
<body><main>
<h1>{T('pg_h1', lang)}</h1>
<p class="sub">{T('pg_sub', lang, t=origin, hm=f"{kyiv:%H:%M}", made=made, model=esc(payload['model']), version=esc(payload['version']))}</p>
<p class="note">{T('pg_note', lang, model_text=esc(payload['model_text']))}</p>
{notes}
<section class="sw">
<input type="radio" name="h" id="h1" checked><input type="radio" name="h" id="h3"><input type="radio" name="h" id="h6">
<div class="tabs">{tabs}</div>
<div class="panel" aria-live="polite"><div class="dflt"><span class="has-yes">{T('pg_panel_default', lang)}</span><span class="has-no">{T('pg_panel_nohas', lang)}</span></div>
{chr(10).join(panels)}
</div>
<div class="stage"><svg viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{esc(T('pg_aria', lang))}">
<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="7" height="7" style="fill:var(--nd)"/><line x1="0" y1="0" x2="0" y2="7" style="stroke:var(--nd-line);stroke-width:1.6"/></pattern></defs>
{chr(10).join(body)}
{callout}
</svg></div>
<div class="legend">{legend}</div>
<div class="legend">{legend2}</div>
<p class="note">{T('pg_thr', lang, thr=thr_txt)}</p>
</section>
<h2>{T('pg_h2', lang)}</h2>
<table class="tbl"><thead><tr>{"".join(f"<th>{esc(c)}</th>" for c in th)}</tr></thead><tbody>
{chr(10).join(tr)}
</tbody></table>
<footer>{T('pg_footer', lang)}</footer>
</main></body></html>
"""
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
        print(T("map_written", payload.get("lang", "en"), path=shown))
        return p
    except Exception as e:  # noqa: BLE001
        print(T("map_not_written", payload.get("lang", "en"), err=f"{type(e).__name__}: {e}"), file=sys.stderr)
        return None
