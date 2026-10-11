LightGBM from 2026-01-01 + Telegram, test fit, all 21 features by share of total gain, per H.

### lag 0 (posts < t)

| rank | H=1 | H=3 | H=6 |
|---|---|---|---|
| 1 | oblast (21.3%) | oblast (34.9%) | oblast (56.3%) |
| 2 | starts_7d (16.0%) | starts_7d (19.4%) | starts_7d (13.9%) |
| 3 | share_7d (12.5%) | share_7d (14.1%) | share_7d (8.6%) |
| 4 | now (12.2%) | hours_since_end (7.7%) | hours_since_end (4.0%) |
| 5 | hours_since_end (10.1%) | hour (4.8%) | hour (3.1%) |
| 6 | share_24h (6.0%) | nb_share_1h (3.5%) | share_24h (2.2%) |
| 7 | hour (5.5%) | share_24h (2.6%) | nb_share_1h (2.1%) |
| 8 | nb_share_1h (5.0%) | now (2.3%) | share_6h (1.9%) |
| 9 | tg_min_since (3.3%) | weekday (1.8%) | weekday (1.7%) |
| 10 | nb_starts_6h (1.8%) | hours_since_start (1.5%) | starts_24h (1.4%) |
| 11 | share_6h (1.7%) | share_6h (1.4%) | tg_min_since (0.9%) |
| 12 | weekday (1.3%) | nb_starts_6h (1.3%) | nb_starts_6h (0.9%) |
| 13 | hours_since_start (1.0%) | tg_min_since (1.3%) | hours_since_start (0.8%) |
| 14 | freq4w (0.4%) | freq4w (1.2%) | now (0.7%) |
| 15 | tg_share6h (0.4%) | starts_24h (1.0%) | freq4w (0.6%) |
| 16 | starts_24h (0.4%) | tg_share6h (0.5%) | tg_share6h (0.4%) |
| 17 | tg_missile (0.3%) | tg_missile (0.3%) | tg_kab (0.3%) |
| 18 | tg_kab (0.3%) | tg_kab (0.3%) | tg_missile (0.1%) |
| 19 | tg_ballistic (0.3%) | tg_ballistic (0.3%) | tg_ballistic (0.1%) |
| 20 | tg_m3h (0.0%) | tg_m1h (0.0%) | tg_m3h (0.0%) |
| 21 | tg_m1h (0.0%) | tg_m3h (0.0%) | tg_m1h (0.0%) |

The seven Telegram features:

| H | feature | rank by gain | share of gain | share of splits |
|---|---|---|---|---|
| 1 | tg_m1h | 21 | 0.000 | 0.000 |
| 1 | tg_m3h | 20 | 0.000 | 0.000 |
| 1 | tg_share6h | 15 | 0.004 | 0.024 |
| 1 | tg_min_since | 9 | 0.033 | 0.091 |
| 1 | tg_ballistic | 19 | 0.003 | 0.013 |
| 1 | tg_missile | 17 | 0.003 | 0.016 |
| 1 | tg_kab | 18 | 0.003 | 0.015 |
| 3 | tg_m1h | 20 | 0.000 | 0.000 |
| 3 | tg_m3h | 21 | 0.000 | 0.000 |
| 3 | tg_share6h | 16 | 0.005 | 0.029 |
| 3 | tg_min_since | 13 | 0.013 | 0.048 |
| 3 | tg_ballistic | 19 | 0.003 | 0.013 |
| 3 | tg_missile | 17 | 0.003 | 0.013 |
| 3 | tg_kab | 18 | 0.003 | 0.012 |
| 6 | tg_m1h | 21 | 0.000 | 0.000 |
| 6 | tg_m3h | 20 | 0.000 | 0.000 |
| 6 | tg_share6h | 16 | 0.004 | 0.018 |
| 6 | tg_min_since | 11 | 0.009 | 0.036 |
| 6 | tg_ballistic | 19 | 0.001 | 0.006 |
| 6 | tg_missile | 18 | 0.001 | 0.006 |
| 6 | tg_kab | 17 | 0.003 | 0.014 |

### lag 15 (posts < t-15min)

| rank | H=1 | H=3 | H=6 |
|---|---|---|---|
| 1 | oblast (19.4%) | oblast (33.6%) | oblast (54.2%) |
| 2 | starts_7d (17.6%) | starts_7d (19.8%) | starts_7d (15.1%) |
| 3 | share_7d (12.4%) | share_7d (16.1%) | share_7d (7.3%) |
| 4 | now (12.0%) | hours_since_end (7.5%) | hours_since_end (4.7%) |
| 5 | hours_since_end (10.4%) | hour (4.5%) | hour (3.6%) |
| 6 | hour (6.2%) | nb_share_1h (3.4%) | share_24h (2.4%) |
| 7 | share_24h (5.9%) | share_24h (2.7%) | share_6h (2.1%) |
| 8 | nb_share_1h (4.8%) | now (2.3%) | weekday (2.1%) |
| 9 | nb_starts_6h (2.4%) | nb_starts_6h (1.6%) | nb_share_1h (2.1%) |
| 10 | tg_min_since (2.0%) | weekday (1.6%) | starts_24h (1.4%) |
| 11 | share_6h (1.9%) | hours_since_start (1.5%) | nb_starts_6h (1.0%) |
| 12 | weekday (1.6%) | share_6h (1.4%) | hours_since_start (0.9%) |
| 13 | hours_since_start (1.0%) | freq4w (1.1%) | tg_min_since (0.8%) |
| 14 | freq4w (0.5%) | starts_24h (0.9%) | now (0.7%) |
| 15 | tg_missile (0.4%) | tg_min_since (0.9%) | freq4w (0.6%) |
| 16 | tg_kab (0.4%) | tg_kab (0.4%) | tg_share6h (0.5%) |
| 17 | starts_24h (0.4%) | tg_share6h (0.3%) | tg_missile (0.3%) |
| 18 | tg_share6h (0.4%) | tg_missile (0.3%) | tg_kab (0.2%) |
| 19 | tg_ballistic (0.3%) | tg_ballistic (0.2%) | tg_ballistic (0.2%) |
| 20 | tg_m1h (0.0%) | tg_m3h (0.0%) | tg_m3h (0.0%) |
| 21 | tg_m3h (0.0%) | tg_m1h (0.0%) | tg_m1h (0.0%) |

The seven Telegram features:

| H | feature | rank by gain | share of gain | share of splits |
|---|---|---|---|---|
| 1 | tg_m1h | 20 | 0.000 | 0.001 |
| 1 | tg_m3h | 21 | 0.000 | 0.000 |
| 1 | tg_share6h | 18 | 0.004 | 0.023 |
| 1 | tg_min_since | 10 | 0.020 | 0.066 |
| 1 | tg_ballistic | 19 | 0.003 | 0.010 |
| 1 | tg_missile | 15 | 0.004 | 0.018 |
| 1 | tg_kab | 16 | 0.004 | 0.017 |
| 3 | tg_m1h | 21 | 0.000 | 0.000 |
| 3 | tg_m3h | 20 | 0.000 | 0.000 |
| 3 | tg_share6h | 17 | 0.003 | 0.018 |
| 3 | tg_min_since | 15 | 0.009 | 0.040 |
| 3 | tg_ballistic | 19 | 0.002 | 0.011 |
| 3 | tg_missile | 18 | 0.003 | 0.014 |
| 3 | tg_kab | 16 | 0.004 | 0.018 |
| 6 | tg_m1h | 21 | 0.000 | 0.000 |
| 6 | tg_m3h | 20 | 0.000 | 0.000 |
| 6 | tg_share6h | 16 | 0.005 | 0.026 |
| 6 | tg_min_since | 13 | 0.008 | 0.031 |
| 6 | tg_ballistic | 19 | 0.002 | 0.009 |
| 6 | tg_missile | 17 | 0.003 | 0.013 |
| 6 | tg_kab | 18 | 0.002 | 0.010 |
