"""Before the model: is the national news count just a slower copy of the alert history we have?

    python scripts/news_correlation.py

Correlation of news_24h and news_yesterday (src/news.py) with starts_7d, share_7d and starts_24h,
on the training rows of "LightGBM from 2026-01-01" (H = 1). News is one national number per hour,
the alert features are per oblast, so three readings:
  pooled          every (oblast, t) training row
  within oblast   correlation inside each oblast, averaged over the 24 oblasts
  national        per hour: news vs the alert feature summed (starts) or averaged (share) over oblasts
Writes results/news/correlation.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.evaluate import POST_SWITCH_START, md_table
from src.dataset import EVAL_LOOKBACK, TEST_DAYS, build_rows, split
from src.features import build_features, load_neighbours
from src.news import NEWS_FEATURES, load_news, news_features

ALERT = ["starts_7d", "share_7d", "starts_24h"]


def main():
    rows, episodes, raw, first, end = build_rows()
    test_start = end - pd.Timedelta(days=TEST_DAYS)
    oblasts = sorted(rows["oblast"].unique())
    F = build_features(rows, episodes, raw, load_neighbours(), [1], oblasts)[1]
    F = F.join(news_features(rows["t"], load_news()))
    m = split(rows, first, end, test_start, 1, EVAL_LOOKBACK)
    train = m["train"] & (rows["t"] >= POST_SWITCH_START) & F[NEWS_FEATURES].notna().all(axis=1)
    d = F[train].assign(t=rows.loc[train, "t"])
    nat = d.groupby("t").agg(news_24h=("news_24h", "first"), news_yesterday=("news_yesterday", "first"),
                             starts_7d=("starts_7d", "sum"), share_7d=("share_7d", "mean"),
                             starts_24h=("starts_24h", "sum"))
    out = []
    for news in NEWS_FEATURES:
        for a in ALERT:
            r = {"news feature": news, "alert feature": a}
            for method in ["pearson", "spearman"]:
                r[f"pooled {method}"] = d[news].corr(d[a], method=method)
                r[f"within oblast {method}"] = d.groupby("oblast", observed=True).apply(
                    lambda g: g[news].corr(g[a], method=method)).mean()
                r[f"national {method}"] = nat[news].corr(nat[a], method=method)
            out.append(r)
    out = pd.DataFrame(out)
    note = (f"Training rows of LightGBM from 2026-01-01, H = 1: {train.sum()} rows, {len(nat)} hours, "
            f"{nat.index.min():%Y-%m-%d %H:%M} to {nat.index.max():%Y-%m-%d %H:%M} UTC "
            f"({(m['train'] & (rows['t'] >= POST_SWITCH_START)).sum() - train.sum()} rows at the start of 2026 "
            "without a full news window left out here only). News is national: pooled = every (oblast, t) row; "
            "within oblast = per-oblast correlation averaged over 24 oblasts; national = per hour, starts summed "
            "and share averaged over oblasts.\n\n")
    (ROOT / "results" / "news" / "correlation.md").write_text(note + md_table(out) + "\n")
    print(note)
    with pd.option_context("display.width", 250, "display.max_columns", 20):
        print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
