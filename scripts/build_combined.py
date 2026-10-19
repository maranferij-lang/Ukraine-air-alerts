"""The combined alert dataset for the next round: official data up to 2026-08-28, the Ukraine Alarm API archive from 2026-08-29 on, and the Aug 19-20
Chernihivska / Kyivska gap filled from the API.

    python scripts/build_combined.py          writes data/combined/alerts_combined.csv (git-ignored, about 30 MB) and data/combined/MANIFEST.md (committed)

Offline: it reads data/raw/official_data_en.csv (as cleaned by src/load.py) and data/api_archive/ (needs `pip install translitua` for the API's district names).
Nothing is trained. The splice points are documented in docs/DETAILS.md ("The combined dataset") and checked by scripts/check_combined.py.

Rows, in the schema of the official file plus `source`:
  official   official rows that END at or before the splice instant T = 2026-08-29 00:00:00 UTC (hromada rows included; the rule ignores them)
  api        API rows (alertType AIR, our 24 oblasts; district -> raion row, "м. Київ" -> oblast row; hromada rows do not exist on this side) that END after T.
             An alert that started before T and was still running at T therefore comes from the API, with the API's start. The official rows that span T are not used
             (the feed broke on the day after; its rows that reach into 2026-08-29 are the last ones before the outage).
  api_patch  the API's raion rows of Chernihivska and Kyivska oblast that START between 2026-08-19 19:00 and 2026-08-20 12:00 UTC: a wave the official feed does not have
             (results/api_check.md). Added on top of the official rows (a few official rows of the same wave exist; episodes are unions, so an overlap changes nothing).
Luhansk (permanent alert) is left out as in src/dataset.load_inputs.
The cut (CUT = 2026-10-18 00:00 UTC, i.e. 2026-10-17 23:59:59 is the last second in): API rows that start at or after CUT are ignored, and an end after CUT (also the end of an alert that was still running when the archive was fetched, which has none) is clipped to CUT.
An alert running at the cut is therefore a row that ends at the cut; only origins up to the cut are ever used with it, and a forecast at t only needs what is known at t.
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.api_check import day_files, load_api, to_official_rows
from src.dataset import load_inputs

SPLICE = pd.Timestamp("2026-08-29", tz="UTC")
PATCH_OBLASTS = ["Chernihivska oblast", "Kyivska oblast"]
PATCH_FROM, PATCH_TO = pd.Timestamp("2026-08-19 19:00", tz="UTC"), pd.Timestamp("2026-08-20 12:00", tz="UTC")
CUT = pd.Timestamp("2026-10-18 00:00", tz="UTC")  # everything is cut here (all of 2026-10-17 UTC is in): rows that start later are ignored and ends are clipped to this instant,
#                                                   so the file does not depend on when the archive was last refreshed
ARCHIVE = ROOT / "data" / "api_archive" / "date_history"
OUT_DIR = ROOT / "data" / "combined"
COLUMNS = ["oblast", "raion", "hromada", "level", "start", "end", "source"]


def build_combined(archive=ARCHIVE, cut=CUT):
    """Returns (DataFrame with COLUMNS, dict of counts for the manifest). `cut` defaults to CUT (the cut of v1/v2); a later cut is only for scripts/score_v3.py."""
    official, raions = load_inputs()                     # cleaned official rows without Luhansk, fixed raion list
    oblasts = sorted(official["oblast"].unique())
    files = day_files(archive)
    api, _, dropped = to_official_rows(load_api(files), raions, keep_open=True)    # running alerts have end = 2100-01-01 here
    api = api[api["oblast"].isin(oblasts)].drop(columns="regionId")
    n_after_cut = int((api["start"] >= cut).sum())
    n_clipped = int(((api["start"] < cut) & (api["end"] > cut)).sum())
    api = api[api["start"] < cut].assign(end=lambda d: d["end"].clip(upper=cut))

    keep_off = official["end"] <= SPLICE
    keep_api = api["end"] > SPLICE
    patch = api[(api["level"] == "raion") & api["oblast"].isin(PATCH_OBLASTS) & (api["start"] >= PATCH_FROM) & (api["start"] < PATCH_TO)]
    span_off = official[(official["start"] < SPLICE) & (official["end"] > SPLICE)]
    off_in_patch = official[official["oblast"].isin(PATCH_OBLASTS) & (official["start"] >= PATCH_FROM) & (official["start"] < PATCH_TO)]
    n = {
        "official rows (cleaned, without Luhansk)": len(official),
        "official rows kept (end at or before the splice)": int(keep_off.sum()),
        "official rows dropped, spanning the splice (start before, end after)": len(span_off),
        "official rows dropped, started at or after the splice": int((official["start"] >= SPLICE).sum()),
        "api rows (AIR, our oblasts) that start before the cut": len(api),
        "api rows ignored, start at or after the cut": n_after_cut,
        "api rows whose end was clipped to the cut (running or ending after it)": n_clipped,
        "api rows kept (end after the splice)": int(keep_api.sum()),
        "api rows not used (end at or before the splice: the official side has them)": int((~keep_api).sum()),
        "api_patch rows": len(patch),
        "official rows of the two patch oblasts starting in the patch window (kept as they are)": len(off_in_patch),
        "api days read": len(files),
    }
    parts = [official[keep_off].assign(source="official"), api[keep_api].assign(source="api"), patch.assign(source="api_patch")]
    df = pd.concat([p[["oblast", "raion", "hromada", "level", "start", "end", "source"]] for p in parts], ignore_index=True)
    df = df.sort_values(["start", "oblast", "raion", "end"], kind="stable").reset_index(drop=True)
    return df, n


def to_csv_bytes(df):
    out = df.copy()
    for c in ("start", "end"):
        out[c] = out[c].map(lambda t: t.isoformat(sep=" "))
    out = out.rename(columns={"start": "started_at", "end": "finished_at"})
    return out.to_csv(index=False, lineterminator="\n").encode("utf-8")


def load_combined():
    """The combined rows as a DataFrame (read from data/combined/alerts_combined.csv if it is there, else built); schema = src.load.load_official plus `source`."""
    path = OUT_DIR / "alerts_combined.csv"
    if path.exists():
        df = pd.read_csv(path, keep_default_na=False)
        df["start"] = pd.to_datetime(df["started_at"], utc=True, format="ISO8601")
        df["end"] = pd.to_datetime(df["finished_at"], utc=True, format="ISO8601")
        return df[COLUMNS]
    return build_combined()[0]


def main():
    df, n = build_combined()
    data = to_csv_bytes(df)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "alerts_combined.csv").write_bytes(data)
    by_src = df.groupby(["source", "level"]).size().unstack(fill_value=0)
    sha = lambda b: hashlib.sha256(b).hexdigest()
    inputs = {
        "data/raw/official_data_en.csv": sha((ROOT / "data" / "raw" / "official_data_en.csv").read_bytes())[:16],
        "data/api_archive/date_history/ (all day files, in date order)": sha(b"".join(f.read_bytes() for _, f in sorted(day_files(ARCHIVE).items())))[:16],
    }
    lines = ["# Manifest: the combined alert dataset", "",
             "Produced by `scripts/build_combined.py` (offline, deterministic). `alerts_combined.csv` is not committed (about 30 MB); rebuild it with the script and check the SHA-256 below. "
             "The rules and every splice point are in `docs/DETAILS.md`, \"The combined dataset\"; `results/combined_splice_check.md` has the checks.", "",
             f"- splice instant T: {SPLICE:%Y-%m-%d %H:%M:%S} UTC (official before, API after)",
             f"- patch: API raion rows of {', '.join(PATCH_OBLASTS)} starting {PATCH_FROM:%Y-%m-%d %H:%M} to {PATCH_TO:%Y-%m-%d %H:%M} UTC",
             f"- the cut: {CUT:%Y-%m-%d %H:%M} UTC (rows that start later are not in the file; ends are clipped to it)",
             f"- rows: {len(df)}; first start {df['start'].min()}; last start {df['start'].max()}; last end {df['end'].max()}",
             f"- `alerts_combined.csv`: {len(data)} bytes, SHA-256 `{sha(data)}`",
             "- inputs (SHA-256 prefix):", *[f"  - `{k}`: `{v}`" for k, v in inputs.items()], "",
             "## What each rule did", "", *[f"- {k}: {v}" for k, v in n.items()], "",
             "## Rows by source and level", "",
             "| source | " + " | ".join(by_src.columns) + " |", "|" + "---|" * (len(by_src.columns) + 1),
             *[f"| {src} | " + " | ".join(str(v) for v in row) + " |" for src, row in by_src.iterrows()], ""]
    (OUT_DIR / "MANIFEST.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
