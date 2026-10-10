Training rows of LightGBM from 2026-01-01, H = 1: 124968 rows, 5207 hours, 2026-01-02 01:00 to 2026-08-06 23:00 UTC (600 rows at the start of 2026 without a full news window left out here only). News is national: pooled = every (oblast, t) row; within oblast = per-oblast correlation averaged over 24 oblasts; national = per hour, starts summed and share averaged over oblasts.

| news feature | alert feature | pooled pearson | within oblast pearson | national pearson | pooled spearman | within oblast spearman | national spearman |
|---|---|---|---|---|---|---|---|
| news_24h | starts_7d | 0.048 | 0.071 | 0.244 | 0.017 | 0.053 | 0.250 |
| news_24h | share_7d | 0.025 | 0.076 | 0.204 | 0.016 | 0.073 | 0.238 |
| news_24h | starts_24h | 0.057 | 0.069 | 0.182 | 0.046 | 0.079 | 0.238 |
| news_yesterday | starts_7d | 0.043 | 0.058 | 0.222 | 0.013 | 0.040 | 0.232 |
| news_yesterday | share_7d | 0.023 | 0.065 | 0.187 | 0.012 | 0.061 | 0.214 |
| news_yesterday | starts_24h | 0.038 | 0.018 | 0.122 | 0.017 | 0.032 | 0.175 |
