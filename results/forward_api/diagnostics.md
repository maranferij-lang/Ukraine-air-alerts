# Forward test, diagnostics: does the feature pipeline behave the same on API data?

Produced by `scripts/forward_test.py --diagnose` before anything was scored: no outcome of the forward rows is compared with any prediction here. Source of every number below: the Ukraine Alarm API archive (`data/api_archive/`), 74 days, 2026-08-06 to 2026-10-18.

## 1. Rows
- origins 2026-09-07 00:00 to 2026-10-17 23:00 UTC: 41 days x 24 oblasts = 23616 rows; history before the first origin: 32 days (7-day windows and the 4 lags of freq4w are complete from 2026-09-04).
- features with a missing value on those rows (H=1): none

## 2. The official feed's outage masks (the one thing that behaves differently)
`src/features.py` treats the official feed's outage ([2026-08-29, 2026-09-03)) as unobserved: 7-day windows that overlap it are computed over the observed part and scaled, and a freq4w lag that touches it is skipped. On API data those hours are observed (the API has alerts there), so the right setting is no mask. The two versions on the forward rows:

| H | feature | rows differing | of | from | to | mean abs diff |
|---|---|---|---|---|---|---|
| 1 | share_7d | 1555 | 23616 | 09-07 | 09-09 | 0.011 |
| 1 | starts_7d | 1548 | 23616 | 09-07 | 09-09 | 2.666 |
| 1 | freq4w | 4206 | 23616 | 09-07 | 09-30 | 0.144 |
| 3 | share_7d | 1555 | 23616 | 09-07 | 09-09 | 0.011 |
| 3 | starts_7d | 1548 | 23616 | 09-07 | 09-09 | 2.666 |
| 3 | freq4w | 6121 | 23616 | 09-07 | 09-30 | 0.145 |
| 6 | share_7d | 1555 | 23616 | 09-07 | 09-09 | 0.011 |
| 6 | starts_7d | 1548 | 23616 | 09-07 | 09-09 | 2.666 |
| 6 | freq4w | 5600 | 23616 | 09-07 | 09-30 | 0.137 |

The frozen LightGBM's probabilities with the masked and the unmasked features (a feature-pipeline effect only; no outcome used):

| H | rows where the frozen model's probability differs by > 0.001 | largest difference | mean abs difference |
|---|---|---|---|
| 1 | 3393 | 0.0826 | 0.0014 |
| 3 | 5718 | 0.1460 | 0.0048 |
| 6 | 5551 | 0.1502 | 0.0055 |

## 3. The same features built from the official data and from the API, on the same rows
Rows 08-13 to 08-28 23:00 UTC (API 7-day history complete, before the official outage): 9216 rows. Equal = within 0.001 (the two sources time the same alert a fraction of a second apart; 0.001 h is 3.6 s). The Aug 19-20 column leaves out the wave the official feed does not have (see results/api_check.md). `freq4w` cannot be compared one to one: it needs four weeks of API history and the archive starts on Aug 6.

| feature | rows | equal (1e-3) | equal outside Aug 19-20 | mean abs diff | max abs diff | correlation |
|---|---|---|---|---|---|---|
| now | 9216 | 9188 | 8544 of 8544 | 0.0030 | 1.0000 | 0.9907 |
| hours_since_start | 9216 | 9116 | 8538 of 8544 | 0.0164 | 11.1256 | 0.9948 |
| hours_since_end | 9216 | 9109 | 8491 of 8544 | 0.0597 | 35.7801 | 0.9999 |
| share_6h | 9216 | 9009 | 8453 of 8544 | 0.0027 | 1.0000 | 0.9907 |
| share_24h | 9216 | 8726 | 8330 of 8544 | 0.0027 | 0.4934 | 0.9948 |
| share_7d | 9216 | 8237 | 7698 of 8544 | 0.0027 | 0.0706 | 0.9991 |
| starts_24h | 9216 | 9083 | 8527 of 8544 | 0.0171 | 2.0000 | 0.9989 |
| starts_7d | 9216 | 8507 | 7950 of 8544 | 0.1109 | 2.0000 | 0.9998 |
| nb_share_1h | 9216 | 9110 | 8544 of 8544 | 0.0043 | 1.0000 | 0.9891 |
| nb_starts_6h | 9216 | 9051 | 8544 of 8544 | 0.0254 | 6.0000 | 0.9979 |
| hour | 9216 | 9216 | 8544 of 8544 | 0.0000 | 0.0000 | 1.0000 |
| weekday | 9216 | 9216 | 8544 of 8544 | 0.0000 | 0.0000 | 1.0000 |

## 4. Leakage check on API rows
- features for 40 origins in the forward window recomputed from API rows cut at t (alerts started by t, ends after t unknown): 37440 values compared, mismatches 0.

## 5. How the forward rows look next to the old test rows (features and the share of origins with a new alert; no model output)

| feature (mean) | old test (official, 24 days) | forward (API, 41 days) |
|---|---|---|
| now | 0.209 | 0.288 |
| hours_since_end | 66.089 | 47.214 |
| share_24h | 0.208 | 0.286 |
| share_7d | 0.203 | 0.278 |
| starts_24h | 2.970 | 4.441 |
| starts_7d | 20.209 | 30.080 |
| nb_share_1h | 0.293 | 0.446 |
| nb_starts_6h | 3.172 | 5.013 |
| freq4w | 0.117 | 0.155 |

Where the forward features sit against the range the models were trained on (official data to 2026-08-07, H=1 train rows):

| feature | training min | training 99th pct | training max | forward max | forward rows above training 99th pct | forward rows above training max |
|---|---|---|---|---|---|---|
| now | 0.000 | 1.000 | 1.000 | 1.000 | 0.0% | 0 |
| hours_since_start | 0.000 | 6.846 | 87.204 | 42.543 | 4.4% | 0 |
| hours_since_end | 0.000 | 279.772 | 720.000 | 720.000 | 5.7% | 0 |
| share_6h | 0.000 | 1.000 | 1.000 | 1.000 | 0.0% | 0 |
| share_24h | 0.000 | 0.861 | 1.000 | 1.000 | 7.7% | 0 |
| share_7d | 0.000 | 0.817 | 0.985 | 0.985 | 8.3% | 0 |
| starts_24h | 0.000 | 9.000 | 16.000 | 19.000 | 12.4% | 40 |
| starts_7d | 0.000 | 53.000 | 81.000 | 89.000 | 19.7% | 221 |
| nb_share_1h | 0.000 | 1.000 | 1.000 | 1.000 | 0.0% | 0 |
| nb_starts_6h | 0.000 | 12.000 | 35.000 | 27.000 | 5.8% | 0 |
| freq4w | 0.000 | 0.750 | 1.000 | 1.000 | 0.4% | 0 |

Share of origins where a new alert starts in (t, t+H]:

| H | old test | forward |
|---|---|---|
| 1 | 0.121 | 0.180 |
| 3 | 0.297 | 0.414 |
| 6 | 0.432 | 0.571 |

## 6. Gaps in the API data
- oblast episodes starting per day in the forward window: min 59, median 104, max 172; days with fewer than half the median: none
- oblasts with no episode at all in the window: none
- API rows left out for having no end (`isContinue` true, end 0001-01-01): 2 hromada rows from Sep 17 (hromadas are not used by the rule) and 78 rows from Oct 18 09:51 on (after the scoring window); none inside the window affects an oblast.

