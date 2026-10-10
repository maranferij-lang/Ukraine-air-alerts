Target (b): in how many oblasts the first predictor has the higher within-oblast AUC, on all 24 test days and on each period separately.

| H | period | comparison | oblasts_compared | first_wins |
|---|---|---|---|---|
| 1 | all 24 test days | LightGBM vs train freq oblast x hour x weekday | 24 | 24 |
| 1 | all 24 test days | LightGBM vs logistic (starts_7d + hour + oblast) | 24 | 24 |
| 1 | all 24 test days | LightGBM from 2026-01-01 vs LightGBM | 24 | 13 |
| 1 | Aug 7-28 (7-day lookback complete) | LightGBM vs train freq oblast x hour x weekday | 24 | 23 |
| 1 | Aug 7-28 (7-day lookback complete) | LightGBM vs logistic (starts_7d + hour + oblast) | 24 | 24 |
| 1 | Aug 7-28 (7-day lookback complete) | LightGBM from 2026-01-01 vs LightGBM | 24 | 13 |
| 1 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM vs train freq oblast x hour x weekday | 20 | 12 |
| 1 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM vs logistic (starts_7d + hour + oblast) | 20 | 16 |
| 1 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM from 2026-01-01 vs LightGBM | 20 | 14 |
| 3 | all 24 test days | LightGBM vs train freq oblast x hour x weekday | 24 | 19 |
| 3 | all 24 test days | LightGBM vs logistic (starts_7d + hour + oblast) | 24 | 23 |
| 3 | all 24 test days | LightGBM from 2026-01-01 vs LightGBM | 24 | 15 |
| 3 | Aug 7-28 (7-day lookback complete) | LightGBM vs train freq oblast x hour x weekday | 24 | 17 |
| 3 | Aug 7-28 (7-day lookback complete) | LightGBM vs logistic (starts_7d + hour + oblast) | 24 | 22 |
| 3 | Aug 7-28 (7-day lookback complete) | LightGBM from 2026-01-01 vs LightGBM | 24 | 16 |
| 3 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM vs train freq oblast x hour x weekday | 20 | 12 |
| 3 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM vs logistic (starts_7d + hour + oblast) | 20 | 13 |
| 3 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM from 2026-01-01 vs LightGBM | 20 | 10 |
| 6 | all 24 test days | LightGBM vs train freq oblast x hour x weekday | 24 | 18 |
| 6 | all 24 test days | LightGBM vs logistic (starts_7d + hour + oblast) | 24 | 22 |
| 6 | all 24 test days | LightGBM from 2026-01-01 vs LightGBM | 24 | 13 |
| 6 | Aug 7-28 (7-day lookback complete) | LightGBM vs train freq oblast x hour x weekday | 24 | 13 |
| 6 | Aug 7-28 (7-day lookback complete) | LightGBM vs logistic (starts_7d + hour + oblast) | 24 | 22 |
| 6 | Aug 7-28 (7-day lookback complete) | LightGBM from 2026-01-01 vs LightGBM | 24 | 13 |
| 6 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM vs train freq oblast x hour x weekday | 20 | 11 |
| 6 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM vs logistic (starts_7d + hour + oblast) | 20 | 15 |
| 6 | Sep 4-5 (7-day lookback partly in the outage) | LightGBM from 2026-01-01 vs LightGBM | 20 | 10 |
