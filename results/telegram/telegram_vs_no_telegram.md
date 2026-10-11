Target (b). In how many oblasts the model with Telegram has the higher within-oblast AUC than the same model without:

| H | lag | period | oblasts_compared | with_telegram_higher_auc |
|---|---|---|---|---|
| 1 | tg0 | all 24 test days | 24 | 20 |
| 1 | tg0 | Aug 7-28 (7-day lookback complete) | 24 | 21 |
| 1 | tg0 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 8 |
| 1 | tg15 | all 24 test days | 24 | 13 |
| 1 | tg15 | Aug 7-28 (7-day lookback complete) | 24 | 11 |
| 1 | tg15 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 9 |
| 3 | tg0 | all 24 test days | 24 | 10 |
| 3 | tg0 | Aug 7-28 (7-day lookback complete) | 24 | 8 |
| 3 | tg0 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 13 |
| 3 | tg15 | all 24 test days | 24 | 9 |
| 3 | tg15 | Aug 7-28 (7-day lookback complete) | 24 | 8 |
| 3 | tg15 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 13 |
| 6 | tg0 | all 24 test days | 24 | 16 |
| 6 | tg0 | Aug 7-28 (7-day lookback complete) | 24 | 15 |
| 6 | tg0 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 12 |
| 6 | tg15 | all 24 test days | 24 | 11 |
| 6 | tg15 | Aug 7-28 (7-day lookback complete) | 24 | 11 |
| 6 | tg15 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 8 |

Day-block bootstrap on all 24 test days (1000 resamples of whole days, seed 0): difference with Telegram minus without, within-oblast AUC (higher is better) and Brier (lower is better), point value and 95% percentile interval; share_auc_diff_gt_0 = share of resamples where Telegram has the higher AUC.

| H | lag | test_days | auc_diff | auc_lo | auc_hi | brier_diff | brier_lo | brier_hi | share_auc_diff_gt_0 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | tg0 | 24 | 0.0322 | 0.0039 | 0.0531 | -0.0006 | -0.0011 | -0.0001 | 0.9980 |
| 1 | tg15 | 24 | -0.0344 | -0.0501 | 0.0078 | -0.0003 | -0.0005 | -0.0001 | 0.2570 |
| 3 | tg0 | 24 | -0.0038 | -0.0128 | 0.0096 | -0.0003 | -0.0009 | 0.0002 | 0.2910 |
| 3 | tg15 | 24 | -0.0365 | -0.0594 | 0.0104 | -0.0004 | -0.0010 | 0.0001 | 0.2710 |
| 6 | tg0 | 24 | 0.0124 | 0.0060 | 0.0191 | -0.0005 | -0.0011 | -0.0000 | 1.0000 |
| 6 | tg15 | 24 | 0.0042 | -0.0070 | 0.0125 | -0.0000 | -0.0007 | 0.0006 | 0.7380 |

Number of trees chosen by early stopping on the last train week (validation fit, 100 rounds patience); the test fit uses the same number:

| H | LightGBM full history (main) | LightGBM from 2026-01-01 | LightGBM from 2026-01-01 + Telegram (posts < t) | LightGBM from 2026-01-01 + Telegram (posts < t-15min) |
|---|---|---|---|---|
| 1 | 116 | 122 | 94 | 121 |
| 3 | 97 | 158 | 131 | 111 |
| 6 | 81 | 101 | 88 | 135 |
