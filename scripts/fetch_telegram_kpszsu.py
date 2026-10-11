"""Pull the public preview of t.me/s/kpszsu (Air Force of the Armed Forces of Ukraine) and write posts to a CSV.

    python scripts/fetch_telegram_kpszsu.py --from-id 77125 --since 2025-12-31

Walks back from post id --from-id (exclusive, the page ?before=<id>) with 20 posts per page, one request
at a time with --pause seconds between requests, retrying with backoff on connection resets, until the
oldest post is older than --since. Raw pages are cached gzipped in data/telegram/cache/ (gitignored), so
a rerun resumes from the cache and does not request pages twice. Writes data/telegram/kpszsu_posts.csv:
id, time_utc (post time; an edit keeps the original time), edited (marked "edited" on the page when
pulled), text (plain text). Posts deleted before the pull are not visible.
"""
import argparse
import csv
import gzip
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.telegram_posts import parse_page

OUT = ROOT / "data" / "telegram"
CACHE = OUT / "cache"
URL = "https://t.me/s/kpszsu?before={}"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ukraine-air-alerts course project; sequential, polite)"}


def get(before, pause):
    f = CACHE / f"before_{before}.html.gz"
    if f.exists():
        return gzip.decompress(f.read_bytes()).decode("utf-8"), False
    for attempt in range(6):
        try:
            page = urllib.request.urlopen(urllib.request.Request(URL.format(before), headers=UA), timeout=30).read()
            f.write_bytes(gzip.compress(page))
            time.sleep(pause)
            return page.decode("utf-8"), True
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            wait = 10 * 2 ** attempt
            print(f"before={before}: {e!r}, retry in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"could not fetch before={before}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-id", type=int, default=77125, help="first page is ?before=<this>")
    ap.add_argument("--since", default="2025-12-31", help="stop once the oldest post is before this UTC date")
    ap.add_argument("--pause", type=float, default=1.75, help="seconds between requests")
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    since = pd.Timestamp(args.since, tz="UTC")
    posts, before, pages, fetched, t0 = {}, args.from_id, 0, 0, time.time()
    while True:
        page, was_fetched = get(before, args.pause)
        rows = parse_page(page)
        pages += 1
        fetched += was_fetched
        if not rows:
            break
        for r in rows:
            posts[r["id"]] = r
        before = rows[0]["id"]
        if pd.Timestamp(rows[0]["time_utc"]) < since or before <= 1:
            break
        if pages % 50 == 0:
            print(f"{pages} pages ({fetched} fetched), oldest {rows[0]['time_utc'][:16]} id {before}, "
                  f"{time.time() - t0:.0f}s", flush=True)
    keep = sorted((p for p in posts.values() if pd.Timestamp(p["time_utc"]) >= since), key=lambda p: p["id"])
    with open(OUT / "kpszsu_posts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "time_utc", "edited", "text"])
        w.writeheader()
        w.writerows(keep)
    ids = [p["id"] for p in keep]
    print(f"done: {pages} pages ({fetched} fetched) in {time.time() - t0:.0f}s; {len(keep)} posts "
          f"{keep[0]['time_utc'][:16]} .. {keep[-1]['time_utc'][:16]}; ids {ids[0]}..{ids[-1]}, "
          f"{ids[-1] - ids[0] + 1 - len(ids)} ids missing inside; edited {sum(p['edited'] for p in keep)}", flush=True)


if __name__ == "__main__":
    main()
