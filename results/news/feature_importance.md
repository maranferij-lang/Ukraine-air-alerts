LightGBM from 2026-01-01 + news, test fit, all 16 features by share of total gain, per H.

| rank | H=1 | H=3 | H=6 |
|---|---|---|---|
| 1 | oblast (21.2%) | oblast (35.3%) | oblast (55.8%) |
| 2 | starts_7d (16.9%) | starts_7d (20.2%) | starts_7d (14.0%) |
| 3 | now (12.3%) | share_7d (14.4%) | share_7d (7.8%) |
| 4 | share_7d (11.6%) | hours_since_end (7.0%) | news_yesterday (3.8%) |
| 5 | hours_since_end (9.3%) | hour (3.6%) | hours_since_end (3.7%) |
| 6 | share_24h (6.2%) | nb_share_1h (3.2%) | hour (2.4%) |
| 7 | hour (5.3%) | news_yesterday (2.9%) | nb_share_1h (2.1%) |
| 8 | nb_share_1h (4.9%) | now (2.3%) | news_24h (2.1%) |
| 9 | news_24h (3.2%) | share_24h (2.2%) | share_6h (2.1%) |
| 10 | news_yesterday (3.0%) | news_24h (2.1%) | share_24h (1.7%) |
| 11 | nb_starts_6h (1.9%) | nb_starts_6h (1.5%) | starts_24h (1.2%) |
| 12 | share_6h (1.7%) | hours_since_start (1.5%) | weekday (1.1%) |
| 13 | hours_since_start (0.9%) | share_6h (1.2%) | nb_starts_6h (0.6%) |
| 14 | weekday (0.8%) | freq4w (1.1%) | hours_since_start (0.6%) |
| 15 | freq4w (0.4%) | starts_24h (0.8%) | now (0.6%) |
| 16 | starts_24h (0.2%) | weekday (0.6%) | freq4w (0.4%) |

The two news features:

| H | feature | rank by gain | share of gain | share of splits |
|---|---|---|---|---|
| 1 | news_24h | 9 | 0.032 | 0.123 |
| 1 | news_yesterday | 10 | 0.030 | 0.120 |
| 3 | news_24h | 10 | 0.021 | 0.101 |
| 3 | news_yesterday | 7 | 0.029 | 0.125 |
| 6 | news_24h | 8 | 0.021 | 0.099 |
| 6 | news_yesterday | 4 | 0.038 | 0.174 |
