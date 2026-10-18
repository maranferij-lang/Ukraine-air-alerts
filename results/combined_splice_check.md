# The combined dataset: do features behave the same at the splice?

Produced by `scripts/check_combined.py`, offline; nothing was trained. Splice instant T = 2026-08-29 00:00 UTC: official data before, the Ukraine Alarm API from there on, with the Aug 19-20 Chernihivska / Kyivska wave patched from the API (`scripts/build_combined.py`, `data/combined/MANIFEST.md`). The same feature code is run three ways: official only (the old pipeline, official outage mask on), API only (the forward test's, no mask) and combined (no mask). 'Equal' = within 0.001 (the sources time the same alert a fraction of a second apart). H = 1 features; every feature is the same for all H except freq4w.

## A. Before the splice: combined against official-only

Rows 2026-08-12 to 08-19 19:59 UTC, before the patched wave can reach any window (4512 oblast-hours): the combined features are the official ones, apart from the official rows that span T being replaced (they start after these rows).

| feature | rows | equal (1e-3) | mean abs diff | max abs diff |
|---|---|---|---|---|
| now | 4512 | 4512 | 0.0000 | 0.0000 |
| hours_since_start | 4512 | 4512 | 0.0000 | 0.0000 |
| hours_since_end | 4512 | 4512 | 0.0000 | 0.0000 |
| share_6h | 4512 | 4512 | 0.0000 | 0.0000 |
| share_24h | 4512 | 4512 | 0.0000 | 0.0000 |
| share_7d | 4512 | 4512 | 0.0000 | 0.0000 |
| starts_24h | 4512 | 4512 | 0.0000 | 0.0000 |
| starts_7d | 4512 | 4512 | 0.0000 | 0.0000 |
| nb_share_1h | 4512 | 4512 | 0.0000 | 0.0000 |
| nb_starts_6h | 4512 | 4512 | 0.0000 | 0.0000 |
| hour | 4512 | 4512 | 0.0000 | 0.0000 |
| weekday | 4512 | 4512 | 0.0000 | 0.0000 |
| freq4w | 4512 | 4512 | 0.0000 | 0.0000 |

Rows 2026-08-19 20:00 to 08-28 23:00 UTC (5280 oblast-hours), where the patched wave is inside the 7-day windows (and freq4w lags): the difference here is the patch, by design.

| feature | rows | equal (1e-3) | mean abs diff | max abs diff |
|---|---|---|---|---|
| now | 5280 | 5259 | 0.0040 | 1.0000 |
| hours_since_start | 5280 | 5253 | 0.0201 | 11.1256 |
| hours_since_end | 5280 | 5260 | 0.0950 | 35.7801 |
| share_6h | 5280 | 5242 | 0.0040 | 1.0000 |
| share_24h | 5280 | 5206 | 0.0040 | 0.4934 |
| share_7d | 5280 | 4920 | 0.0040 | 0.0705 |
| starts_24h | 5280 | 5209 | 0.0182 | 2.0000 |
| starts_7d | 5280 | 4921 | 0.1273 | 2.0000 |
| nb_share_1h | 5280 | 5183 | 0.0061 | 1.0000 |
| nb_starts_6h | 5280 | 5181 | 0.0205 | 2.0000 |
| hour | 5280 | 5280 | 0.0000 | 0.0000 |
| weekday | 5280 | 5280 | 0.0000 | 0.0000 |
| freq4w | 5280 | 5276 | 0.0002 | 0.2500 |

## B. Around the splice (T - 48 h to T + 48 h)

Combined against API-only, all features but freq4w (2304 oblast-hours): this is the same alerts from the other source on the side before T, and the same rows after T.

| feature | rows | equal (1e-3) | mean abs diff | max abs diff |
|---|---|---|---|---|
| now | 2304 | 2304 | 0.0000 | 0.0000 |
| hours_since_start | 2304 | 2301 | 0.0001 | 0.0641 |
| hours_since_end | 2304 | 2304 | 0.0001 | 0.0006 |
| share_6h | 2304 | 2286 | 0.0001 | 0.0107 |
| share_24h | 2304 | 2250 | 0.0001 | 0.0061 |
| share_7d | 2304 | 2304 | 0.0001 | 0.0009 |
| starts_24h | 2304 | 2304 | 0.0000 | 0.0000 |
| starts_7d | 2304 | 2304 | 0.0000 | 0.0000 |
| nb_share_1h | 2304 | 2304 | 0.0000 | 0.0000 |
| nb_starts_6h | 2304 | 2304 | 0.0000 | 0.0000 |
| hour | 2304 | 2304 | 0.0000 | 0.0000 |
| weekday | 2304 | 2304 | 0.0000 | 0.0000 |

Combined against official-only on the rows before T that the patch cannot reach any more (2026-08-27 20:00 to 08-28 23:00 UTC, 672 oblast-hours; the official features after T are the outage and are not meaningful):

| feature | rows | equal (1e-3) | mean abs diff | max abs diff |
|---|---|---|---|---|
| now | 672 | 672 | 0.0000 | 0.0000 |
| hours_since_start | 672 | 672 | 0.0000 | 0.0003 |
| hours_since_end | 672 | 672 | 0.0000 | 0.0000 |
| share_6h | 672 | 672 | 0.0000 | 0.0001 |
| share_24h | 672 | 672 | 0.0000 | 0.0000 |
| share_7d | 672 | 672 | 0.0000 | 0.0000 |
| starts_24h | 672 | 672 | 0.0000 | 0.0000 |
| starts_7d | 672 | 672 | 0.0000 | 0.0000 |
| nb_share_1h | 672 | 672 | 0.0000 | 0.0000 |
| nb_starts_6h | 672 | 672 | 0.0000 | 0.0000 |
| hour | 672 | 672 | 0.0000 | 0.0000 |
| weekday | 672 | 672 | 0.0000 | 0.0000 |
| freq4w | 672 | 672 | 0.0000 | 0.0000 |

At the splice hour itself (2026-08-29 00:00 UTC): oblasts under alert (feature `now`): combined 9, API-only 9, equal in 24 of 24 oblasts.

## C. After the splice: combined against API-only

2026-08-29 to 09-05 (4608 oblast-hours), all features but freq4w. The 7-day windows reach back into the official side for the first 7 days, so any difference here is the official-versus-API difference plus the patch.

| feature | rows | equal (1e-3) | mean abs diff | max abs diff |
|---|---|---|---|---|
| now | 4608 | 4608 | 0.0000 | 0.0000 |
| hours_since_start | 4608 | 4608 | 0.0000 | 0.0002 |
| hours_since_end | 4608 | 4608 | 0.0000 | 0.0006 |
| share_6h | 4608 | 4608 | 0.0000 | 0.0001 |
| share_24h | 4608 | 4606 | 0.0000 | 0.0011 |
| share_7d | 4608 | 4608 | 0.0001 | 0.0009 |
| starts_24h | 4608 | 4608 | 0.0000 | 0.0000 |
| starts_7d | 4608 | 4608 | 0.0000 | 0.0000 |
| nb_share_1h | 4608 | 4608 | 0.0000 | 0.0000 |
| nb_starts_6h | 4608 | 4608 | 0.0000 | 0.0000 |
| hour | 4608 | 4608 | 0.0000 | 0.0000 |
| weekday | 4608 | 4608 | 0.0000 | 0.0000 |

freq4w, 2026-09-03 to 09-19 (9792 oblast-hours; the API-only version has all four weekly lags from 09-03). Its lags reach back to Aug 6-22, the official side and the patch:

| feature | rows | equal (1e-3) | mean abs diff | max abs diff |
|---|---|---|---|---|
| freq4w | 9792 | 9760 | 0.0008 | 0.2500 |

## D. Continuity across the splice

Daily means of the main features in the combined series, 2026-08-24 to 09-03 (the splice is at the start of 08-29):

| day | now | starts_24h | share_24h | starts_7d | share_7d | hours_since_end | nb_share_1h | nb_starts_6h | freq4w |
|---|---|---|---|---|---|---|---|---|---|
| 08-24 | 0.165 | 2.703 | 0.183 | 19.073 | 0.203 | 91.556 | 0.228 | 2.872 | 0.120 |
| 08-25 | 0.189 | 2.835 | 0.171 | 19.068 | 0.201 | 100.796 | 0.281 | 3.385 | 0.110 |
| 08-26 | 0.210 | 3.226 | 0.192 | 19.934 | 0.205 | 103.723 | 0.275 | 3.319 | 0.118 |
| 08-27 | 0.318 | 4.040 | 0.300 | 20.927 | 0.204 | 97.578 | 0.473 | 5.102 | 0.105 |
| 08-28 | 0.248 | 4.924 | 0.273 | 23.481 | 0.218 | 77.724 | 0.403 | 4.785 | 0.109 |
| 08-29 | 0.349 | 4.413 | 0.307 | 25.073 | 0.231 | 83.346 | 0.482 | 5.132 | 0.118 |
| 08-30 | 0.304 | 4.399 | 0.308 | 26.540 | 0.248 | 88.539 | 0.436 | 4.642 | 0.106 |
| 08-31 | 0.255 | 4.587 | 0.272 | 28.424 | 0.261 | 90.814 | 0.386 | 4.408 | 0.117 |
| 09-01 | 0.274 | 3.948 | 0.276 | 29.536 | 0.275 | 76.185 | 0.419 | 4.627 | 0.125 |
| 09-02 | 0.276 | 4.276 | 0.257 | 30.587 | 0.285 | 60.573 | 0.460 | 4.943 | 0.123 |
| 09-03 | 0.288 | 4.623 | 0.303 | 31.170 | 0.285 | 61.796 | 0.432 | 4.642 | 0.128 |

The change in each feature's mean between the 48 h before T and the 48 h after, against the same change for every other pair of neighbouring 48 h blocks that start on a day boundary (2026-08-15 to 10-16, 63 pairs). If the splice made a jump, its change would be larger than most of the others (last column near 0). Two features, starts_7d and share_7d, do change more at T than most pairs: they are 7-day windows of a series whose alert rate was rising from 08-27 on (see starts_24h and the daily means above), and sections B and C show the combined series equals the API-only series after T and the official-only series before T, so the change is in the data, not made by the splice.

| feature | mean 48 h before T | mean 48 h after T | change at T | median |change| between neighbouring 48 h blocks | share of other block pairs with a larger |change| |
|---|---|---|---|---|---|
| now | 0.283 | 0.326 | 0.043 | 0.042 | 0.444 |
| starts_24h | 4.482 | 4.406 | -0.076 | 0.332 | 0.873 |
| share_24h | 0.287 | 0.308 | 0.021 | 0.040 | 0.698 |
| starts_7d | 22.204 | 25.806 | 3.602 | 1.360 | 0.111 |
| share_7d | 0.211 | 0.239 | 0.029 | 0.016 | 0.127 |
| hours_since_end | 87.651 | 85.942 | -1.709 | 8.743 | 0.873 |
| nb_share_1h | 0.438 | 0.459 | 0.021 | 0.054 | 0.794 |
| nb_starts_6h | 4.944 | 4.887 | -0.056 | 0.464 | 0.952 |
| freq4w | 0.107 | 0.112 | 0.005 | 0.006 | 0.524 |

Volume across the splice (oblast episodes that start each day, and the raion rows by source):

| day | oblast episodes starting | api | official |
|---|---|---|---|
| 08-24 | 64 | 0 | 373 |
| 08-25 | 81 | 0 | 406 |
| 08-26 | 81 | 0 | 421 |
| 08-27 | 110 | 0 | 521 |
| 08-28 | 113 | 43 | 519 |
| 08-29 | 107 | 486 | 0 |
| 08-30 | 107 | 460 | 0 |
| 08-31 | 105 | 432 | 0 |
| 09-01 | 96 | 432 | 0 |
| 09-02 | 106 | 458 | 0 |
| 09-03 | 94 | 419 | 0 |

## E. Leakage at the splice
- features at 24 origins from T - 12 h to T + 11 h rebuilt from the combined rows cut at t (rows started by t, ends after t unknown): 22464 values compared, mismatches 0.

