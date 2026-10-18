"""Oblast boundaries for the forecast map: Natural Earth admin-1 (public domain) -> data/geo/ukraine_oblasts.geojson (about 100 KB, committed).

    python scripts/build_geo.py PATH_TO_ne_10m_admin_1_states_provinces.geojson     (download link, pinned commit and licence: data/geo/README.md)

Offline. The source file (40 MB, not committed) is checked against the pinned SHA-256 first. What is done to it:
  - the 27 Ukrainian units are picked by ISO 3166-2 code, not by the file's country field: Natural Earth's default file lists Crimea (UA-43) and Sevastopol (UA-40)
    under Russia; they are Ukraine's units by their ISO code and by international law, so they are taken as such (they are drawn as "no data", never modelled)
  - coordinates are simplified (Douglas-Peucker, 0.012 degrees, about 1.3 km) and rounded to 3 decimals. Shared borders are simplified once: the rings are cut into
    arcs wherever the set of units owning a vertex changes, and each arc is simplified in a fixed direction, so two neighbours keep the same border (no slivers)
  - each unit gets a label point (the point farthest from its border, computed on the largest piece, holes respected)
Names and the match with our 24 units are in scripts/forecast_map.py and checked by scripts/check_forecast_map.py.
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.forecast_map import GEO, NOT_MODELLED, OURS

SOURCE_SHA256 = "22d0e3ad85eb3e27f17cabf8ba2d50e554fbc27a87796ff891d958185da62fb5"
TOLERANCE = 0.012
COS_LAT = 0.66  # cos(48.5 degrees): longitude degrees are this much shorter than latitude degrees here


def rdp(pts, tol):
    """Douglas-Peucker on a list of (x, y) in a fixed direction; the end points stay."""
    if len(pts) < 3:
        return list(pts)
    a, b = np.array(pts[0]), np.array(pts[-1])
    p = np.array(pts[1:-1])
    ab = b - a
    n = np.hypot(*ab)
    d = np.hypot(*(p - a).T) if n == 0 else np.abs(ab[0] * (p[:, 1] - a[1]) - ab[1] * (p[:, 0] - a[0])) / n
    i = int(np.argmax(d))  # first maximum: deterministic
    if d[i] <= tol:
        return [pts[0], pts[-1]]
    return rdp(pts[:i + 2], tol)[:-1] + rdp(pts[i + 1:], tol)


def arcs_of(ring, owners):
    """Cut a closed ring (first point repeated at the end) into runs whose vertices all have the same set of owning units; returns lists of points, consecutive runs share an end."""
    pts = [tuple(c) for c in ring[:-1]]
    sig = [owners[p] for p in pts]
    n = len(pts)
    cuts = [i for i in range(n) if sig[i] != sig[i - 1] or sig[i] != sig[(i + 1) % n]]
    if not cuts:  # a ring that is shared as a whole (an island, a city inside a oblast): cut it at its smallest vertex and at the vertex farthest from that one
        s0 = pts.index(min(pts))
        pts = pts[s0:] + pts[:s0]
        far = int(np.argmax([(x - pts[0][0]) ** 2 + (y - pts[0][1]) ** 2 for x, y in pts]))
        return [pts[:far + 1], pts[far:] + [pts[0]]]
    cuts = sorted(set(cuts))
    out = []
    for k, s in enumerate(cuts):
        e = cuts[(k + 1) % len(cuts)]
        run = pts[s:e + 1] if e > s else pts[s:] + pts[:e + 1]
        out.append(run)
    return out


def simplify_ring(ring, owners, tol):
    res = []
    for run in arcs_of(ring, owners):
        scaled = [(x * COS_LAT, y) for x, y in run]
        forward = run[0] <= run[-1]  # canonical direction, so both neighbours simplify the same arc the same way
        seq = scaled if forward else scaled[::-1]
        keep = rdp(seq, tol)
        keep = keep if forward else keep[::-1]
        res.append([(x / COS_LAT, y) for x, y in keep])
    out = []
    for run in res:
        out.extend(run if not out else run[1:])
    out = [(round(x, 3), round(y, 3)) for x, y in out]
    dedup = [out[0]] + [p for i, p in enumerate(out[1:], 1) if p != out[i - 1]]
    if dedup[0] != dedup[-1]:
        dedup.append(dedup[0])
    return dedup


def polygons(geom):
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def inside(pt, rings):
    x, y = pt
    c = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring[:-1], ring[1:]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
    return c


def seg_dist(p, ring):
    a = np.array(ring[:-1]); b = np.array(ring[1:])
    ab = b - a
    t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0, 1)
    return np.hypot(*(a + t[:, None] * ab - p).T).min()


def label_point(poly):
    """Pole of inaccessibility of the largest polygon (grid search, then a finer grid around the best cell), in lon/lat."""
    rings = [[(x * COS_LAT, y) for x, y in r] for r in poly]
    xs = [p[0] for p in rings[0]]; ys = [p[1] for p in rings[0]]
    best, bd = None, -1
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    for step_div in (40, 40):
        for x in np.linspace(x0, x1, step_div):
            for y in np.linspace(y0, y1, step_div):
                if inside((x, y), rings):
                    d = min(seg_dist(np.array([x, y]), r) for r in rings)
                    if d > bd:
                        best, bd = (x, y), d
        w, h = (x1 - x0) / 20, (y1 - y0) / 20
        x0, x1, y0, y1 = best[0] - w, best[0] + w, best[1] - h, best[1] + h
    return round(best[0] / COS_LAT, 3), round(best[1], 3)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    raw = Path(sys.argv[1]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        sys.exit("The source file is not the pinned one (SHA-256 differs); see data/geo/README.md for the exact file.")
    feats = json.loads(raw)["features"]
    iso_ours = {iso: name for name, (iso, _) in OURS.items()}
    want = set(iso_ours) | set(NOT_MODELLED)
    picked = [f for f in feats if f["properties"]["iso_3166_2"] in want]
    assert len(picked) == len(want) == 27, (len(picked), len(want))
    owners = defaultdict(set)
    for i, f in enumerate(picked):
        for poly in polygons(f["geometry"]):
            for ring in poly:
                for c in ring:
                    owners[tuple(c)].add(i)
    owners = {k: frozenset(v) for k, v in owners.items()}
    shared = sum(len(v) > 1 for v in owners.values())
    out = []
    for f in sorted(picked, key=lambda f: f["properties"]["iso_3166_2"]):
        p = f["properties"]
        iso = p["iso_3166_2"]
        polys = [[simplify_ring(r, owners, TOLERANCE) for r in poly] for poly in polygons(f["geometry"])]
        polys = [pl for pl in polys if all(len(r) >= 4 for r in pl)]
        biggest = max(polys, key=lambda pl: abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pl[0][:-1], pl[0][1:]))))
        out.append({"type": "Feature",
                    "properties": {"iso": iso, "ne_name": p["name"], "ne_name_en": p["name_en"], "ne_name_alt": p["name_alt"],
                                   "ours": iso_ours.get(iso), "label": list(label_point(biggest))},
                    "geometry": {"type": "MultiPolygon", "coordinates": [[[list(c) for c in r] for r in pl] for pl in polys]}})
    n_in = sum(len(r) for f in picked for poly in polygons(f["geometry"]) for r in poly)
    n_out = sum(len(r) for f in out for poly in f["geometry"]["coordinates"] for r in poly)
    text = json.dumps({"type": "FeatureCollection", "features": out}, separators=(",", ":"), ensure_ascii=False)
    GEO.write_text(text + "\n", encoding="utf-8")
    print(f"vertices {n_in} -> {n_out} ({shared} source vertices are shared between units); wrote {GEO.relative_to(ROOT)}, {len(text)} bytes, sha256 {hashlib.sha256(text.encode()).hexdigest()[:16]}")


if __name__ == "__main__":
    main()
