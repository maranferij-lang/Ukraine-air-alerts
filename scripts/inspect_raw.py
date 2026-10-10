"""Q1: what is in the two raw CSVs. Prints only; numbers are copied into PROCESS_LOG.md.

    python scripts/inspect_raw.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.load import OFFICIAL_CSV, VOLUNTEER_CSV, load_official, load_volunteer

pd.set_option("display.width", 200)


def section(title):
    print(f"\n=== {title}")


raw_off = pd.read_csv(OFFICIAL_CSV, keep_default_na=False)
raw_vol = pd.read_csv(VOLUNTEER_CSV)

for name, df in [("official", raw_off), ("volunteer", raw_vol)]:
    section(f"{name}: {len(df)} rows, columns {list(df.columns)}")
    print("started_at range:", df["started_at"].min(), "->", df["started_at"].max())
    print("finished_at range:", df["finished_at"].min(), "->", df["finished_at"].max())
    print("exact duplicate rows:", df.duplicated().sum())

off = load_official()
vol = load_volunteer()

section("official after cleaning (relabel pass-1 Zviahelskyi rows, drop exact duplicates)")
print("rows:", len(off))
print(off["level"].value_counts().to_string())
dur = (off["end"] - off["start"]).dt.total_seconds() / 60
print("duration minutes:", dur.describe(percentiles=[0.5, 0.9, 0.99]).round(1).to_dict())
print("zero-length rows:", (dur == 0).sum())
print("rows lasting exactly 60.000 min (upstream's unflagged imputed end):", (dur == 60).sum())

section("official rows per year by level")
print(off.pivot_table(index=off["start"].dt.year, columns="level", values="oblast",
                      aggfunc="size", fill_value=0).to_string())

section("volunteer naive flag")
print(vol["naive"].value_counts().to_string())
print("share naive:", round(vol["naive"].mean(), 4))
vdur = (vol["end"] - vol["start"]).dt.total_seconds() / 60
print("naive rows with duration != 30 min:", (vol["naive"] & (vdur != 30)).sum())
print("non-naive rows with duration == 30 min exactly:", (~vol["naive"] & (vdur == 30)).sum())
print(vol.groupby(vol["start"].dt.year)["naive"].agg(["sum", "size", "mean"]).round(3).to_string())
print("by oblast (highest share):")
print(vol.groupby("oblast")["naive"].mean().sort_values(ascending=False).head(6).round(3).to_string())
