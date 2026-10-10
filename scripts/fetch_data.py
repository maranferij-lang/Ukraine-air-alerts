"""Pull a fresh copy of the two English CSVs from the upstream repo and record the pull.

Pins the download to the upstream commit that HEAD points to at pull time and writes
data/raw/PULL_INFO.md (pull time, commit, sha256, row counts, date ranges).

    python scripts/fetch_data.py
"""
import hashlib
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = "Vadimkin/ukrainian-air-raid-sirens-dataset"
FILES = ["official_data_en.csv", "volunteer_data_en.csv"]
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def main():
    out = subprocess.run(["git", "ls-remote", f"https://github.com/{REPO}", "HEAD"],
                         capture_output=True, text=True, check=True).stdout
    commit = out.split()[0]
    pulled_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# Raw data pull",
        "",
        f"- pulled at: {pulled_at}",
        f"- source: https://github.com/{REPO}/tree/{commit}/datasets",
        f"- upstream commit: {commit}",
        "",
        "| file | rows | sha256 | first started_at | last started_at |",
        "|---|---|---|---|---|",
    ]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        url = f"https://raw.githubusercontent.com/{REPO}/{commit}/datasets/{name}"
        data = urllib.request.urlopen(url).read()
        (RAW_DIR / name).write_bytes(data)
        starts = pd.read_csv(RAW_DIR / name, usecols=["started_at"])["started_at"]
        sha = hashlib.sha256(data).hexdigest()
        lines.append(f"| {name} | {len(starts)} | `{sha}` | {starts.min()} | {starts.max()} |")
        print(f"{name}: {len(starts)} rows, sha256 {sha[:12]}…")

    (RAW_DIR / "PULL_INFO.md").write_text("\n".join(lines) + "\n")
    print(f"pulled commit {commit} at {pulled_at}")


if __name__ == "__main__":
    main()
