"""Load and clean the two raw alert CSVs (one row per alert, times in UTC).

Cleaning is deliberately minimal; every rule here is written up in PROCESS_LOG.md.
"""
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
OFFICIAL_CSV = RAW_DIR / "official_data_en.csv"
VOLUNTEER_CSV = RAW_DIR / "volunteer_data_en.csv"

# Luhansk has had a permanent alert since 2022-04-04 (it is absent from both CSVs apart
# from 2-3 stray rows). Crimea's permanent alert is not in the data at all.
PERMANENT_ALERT_OBLASTS = {"Luhanska oblast"}

# Periods where the official feed is broken, as [start, end) in UTC. Hours inside them get
# data_ok=False in the panel. 2026-08-29..09-02: no official messages for ~4.4 days while the
# volunteer feed kept going; alerts open at the start were closed with fake +1h or 4-day ends.
OFFICIAL_OUTAGES = [("2026-08-29", "2026-09-03")]


def _parse_utc(s):
    return pd.to_datetime(s, utc=True, format="ISO8601")


def load_official(path=OFFICIAL_CSV, dedupe=True):
    """Official channel: one row per alert per location (oblast / raion / hromada).

    With dedupe=True:
      - rows where hromada == raion are a pass-1 labelling bug (Zviahelskyi raion was
        written as level='hromada'); they are relabelled as raion-level rows
      - exact duplicate rows are dropped (upstream re-appended its whole history once)
    """
    df = pd.read_csv(path, keep_default_na=False)
    if dedupe:
        bad = (df["level"] == "hromada") & (df["hromada"] == df["raion"])
        df.loc[bad, "level"] = "raion"
        df.loc[bad, "hromada"] = ""
        df = df.drop_duplicates()
    df["start"] = _parse_utc(df["started_at"])
    df["end"] = _parse_utc(df["finished_at"])
    df = df[["oblast", "raion", "hromada", "level", "start", "end"]]
    return df.sort_values("start", kind="stable").reset_index(drop=True)


def load_volunteer(path=VOLUNTEER_CSV):
    """Volunteer (eTryvoga) channel: oblast level only. naive=True means no end message
    was seen and upstream set end = start + 30 min."""
    df = pd.read_csv(path)
    df = df.rename(columns={"region": "oblast"})
    df["start"] = _parse_utc(df["started_at"])
    df["end"] = _parse_utc(df["finished_at"])
    df = df[["oblast", "start", "end", "naive"]]
    return df.sort_values("start", kind="stable").reset_index(drop=True)


def data_end(df):
    """Last hour boundary we trust. Alerts still open when upstream last ran are missing
    from the CSV, so drop the last partial UTC day and one more day as a margin."""
    return df["end"].max().floor("D") - pd.Timedelta(days=1)
