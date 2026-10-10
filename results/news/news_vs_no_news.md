Target (b). In how many oblasts the model with news has the higher within-oblast AUC than the same model without news:

| H | period | oblasts_compared | with_news_higher_auc |
|---|---|---|---|
| 1 | all 24 test days | 24 | 12 |
| 1 | Aug 7-28 (7-day lookback complete) | 24 | 10 |
| 1 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 7 |
| 3 | all 24 test days | 24 | 11 |
| 3 | Aug 7-28 (7-day lookback complete) | 24 | 6 |
| 3 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 11 |
| 6 | all 24 test days | 24 | 12 |
| 6 | Aug 7-28 (7-day lookback complete) | 24 | 11 |
| 6 | Sep 4-5 (7-day lookback partly in the outage) | 20 | 10 |

Day-block bootstrap on all 24 test days (1000 resamples of whole days, seed 0): difference with news minus without, within-oblast AUC (higher is better) and Brier (lower is better), point value and 95% percentile interval; share_auc_diff_gt_0 = share of resamples where news has the higher AUC.

| H | test_days | auc_diff | auc_lo | auc_hi | brier_diff | brier_lo | brier_hi | share_auc_diff_gt_0 |
|---|---|---|---|---|---|---|---|---|
| 1 | 24 | -0.0272 | -0.0559 | 0.0238 | 0.0002 | -0.0001 | 0.0005 | 0.3300 |
| 3 | 24 | -0.0638 | -0.1067 | 0.0267 | 0.0014 | 0.0005 | 0.0024 | 0.2530 |
| 6 | 24 | -0.0023 | -0.0258 | 0.0267 | 0.0011 | 0.0002 | 0.0019 | 0.5670 |
