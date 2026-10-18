# Forward test on the Ukraine Alarm API (2026-09-07 to 2026-10-17)

**Source: the Ukraine Alarm API (`api.ukrainealarm.com`), one source for every feature and every outcome; no outage mask.** The models are the frozen round-13 fits (trained on official data to 2026-08-07; every threshold from the last train week; nothing refitted, nothing retuned). **41 days, 23616 oblast-hours per horizon: a short test, so the intervals in `bootstrap.md` are wide.** This is separate from the old test (official data, 24 days, `results/test_table.md`); the two are not pooled. Target (b): a new alert starts in (t, t+H]. The forward period is busier than the old test (share of origins with a new alert at H=1: 0.180 against 0.121), so read the Brier scores with `calibration.md` next to them.

| H | predictor | n | base_rate | auc_within_oblast | brier | threshold | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 23616 | 0.180 | 0.708 | 0.119 | 0.187 | 0.419 | 0.669 | 0.515 |
| 1 | logistic | 23616 | 0.180 | 0.538 | 0.136 | 0.148 | 0.306 | 0.700 | 0.426 |
| 1 | same as now | 23616 | 0.180 | 0.407 | 0.400 | raw 0/1 | 0.116 | 0.186 | 0.143 |
| 1 | same hour yesterday | 23616 | 0.180 | 0.515 | 0.255 | raw 0/1 | 0.287 | 0.283 | 0.285 |
| 1 | train frequency | 23616 | 0.180 | 0.531 | 0.152 | 0.075 | 0.246 | 0.622 | 0.353 |
| 1 | rolling 4-week frequency | 23616 | 0.180 | 0.519 | 0.160 | 0.250 | 0.266 | 0.631 | 0.374 |
| 3 | LightGBM | 23616 | 0.414 | 0.662 | 0.167 | 0.243 | 0.613 | 0.877 | 0.721 |
| 3 | logistic | 23616 | 0.414 | 0.561 | 0.183 | 0.321 | 0.642 | 0.781 | 0.705 |
| 3 | same as now | 23616 | 0.414 | 0.459 | 0.429 | raw 0/1 | 0.474 | 0.329 | 0.389 |
| 3 | same hour yesterday | 23616 | 0.414 | 0.532 | 0.323 | raw 0/1 | 0.612 | 0.603 | 0.607 |
| 3 | train frequency | 23616 | 0.414 | 0.522 | 0.259 | 0.176 | 0.549 | 0.667 | 0.602 |
| 3 | rolling 4-week frequency | 23616 | 0.414 | 0.536 | 0.216 | 0.250 | 0.546 | 0.884 | 0.675 |
| 6 | LightGBM | 23616 | 0.571 | 0.654 | 0.143 | 0.314 | 0.750 | 0.915 | 0.824 |
| 6 | logistic | 23616 | 0.571 | 0.573 | 0.152 | 0.289 | 0.756 | 0.899 | 0.821 |
| 6 | same as now | 23616 | 0.571 | 0.475 | 0.445 | raw 0/1 | 0.719 | 0.363 | 0.482 |
| 6 | same hour yesterday | 23616 | 0.571 | 0.536 | 0.264 | raw 0/1 | 0.772 | 0.763 | 0.768 |
| 6 | train frequency | 23616 | 0.571 | 0.519 | 0.256 | 0.278 | 0.732 | 0.717 | 0.725 |
| 6 | rolling 4-week frequency | 23616 | 0.571 | 0.528 | 0.189 | 0.500 | 0.769 | 0.827 | 0.797 |

Thresholds are the frozen max-F1 thresholds from the last train week; 'raw 0/1' means the baseline is taken as is.
