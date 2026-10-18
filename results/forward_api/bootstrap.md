Forward test (API, 41 days). Day-block bootstrap, whole days resampled with replacement, 1000 resamples, seed 0, 95% percentile intervals.

Each predictor (within-oblast AUC, Brier):

| H | predictor | auc | auc_lo | auc_hi | brier | brier_lo | brier_hi |
|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.708 | 0.677 | 0.731 | 0.119 | 0.113 | 0.126 |
| 1 | logistic | 0.538 | 0.503 | 0.570 | 0.136 | 0.128 | 0.145 |
| 1 | same as now | 0.407 | 0.394 | 0.418 | 0.400 | 0.377 | 0.424 |
| 1 | same hour yesterday | 0.515 | 0.507 | 0.523 | 0.255 | 0.243 | 0.268 |
| 1 | train frequency | 0.531 | 0.508 | 0.550 | 0.152 | 0.141 | 0.163 |
| 1 | rolling 4-week frequency | 0.519 | 0.511 | 0.526 | 0.160 | 0.152 | 0.169 |
| 3 | LightGBM | 0.662 | 0.622 | 0.691 | 0.167 | 0.160 | 0.174 |
| 3 | logistic | 0.561 | 0.529 | 0.589 | 0.183 | 0.174 | 0.192 |
| 3 | same as now | 0.459 | 0.446 | 0.471 | 0.429 | 0.412 | 0.447 |
| 3 | same hour yesterday | 0.532 | 0.517 | 0.544 | 0.323 | 0.311 | 0.338 |
| 3 | train frequency | 0.522 | 0.498 | 0.544 | 0.259 | 0.243 | 0.276 |
| 3 | rolling 4-week frequency | 0.536 | 0.523 | 0.548 | 0.216 | 0.207 | 0.225 |
| 6 | LightGBM | 0.654 | 0.610 | 0.689 | 0.143 | 0.134 | 0.152 |
| 6 | logistic | 0.573 | 0.537 | 0.605 | 0.152 | 0.142 | 0.162 |
| 6 | same as now | 0.475 | 0.458 | 0.489 | 0.445 | 0.429 | 0.459 |
| 6 | same hour yesterday | 0.536 | 0.517 | 0.555 | 0.264 | 0.244 | 0.285 |
| 6 | train frequency | 0.519 | 0.487 | 0.548 | 0.256 | 0.243 | 0.271 |
| 6 | rolling 4-week frequency | 0.528 | 0.505 | 0.551 | 0.189 | 0.178 | 0.200 |

LightGBM minus each other predictor (AUC: positive = LightGBM ahead; Brier: negative = LightGBM ahead):

| H | predictor | d_auc | d_auc_lo | d_auc_hi | share_auc_ahead | d_brier | d_brier_lo | d_brier_hi | share_brier_ahead |
|---|---|---|---|---|---|---|---|---|---|
| 1 | logistic | 0.170 | 0.138 | 0.205 | 1.000 | -0.017 | -0.019 | -0.014 | 1.000 |
| 1 | same as now | 0.301 | 0.267 | 0.328 | 1.000 | -0.281 | -0.301 | -0.262 | 1.000 |
| 1 | same hour yesterday | 0.193 | 0.161 | 0.218 | 1.000 | -0.136 | -0.144 | -0.127 | 1.000 |
| 1 | train frequency | 0.177 | 0.140 | 0.210 | 1.000 | -0.032 | -0.037 | -0.028 | 1.000 |
| 1 | rolling 4-week frequency | 0.189 | 0.159 | 0.211 | 1.000 | -0.041 | -0.044 | -0.038 | 1.000 |
| 3 | logistic | 0.101 | 0.068 | 0.138 | 1.000 | -0.016 | -0.019 | -0.013 | 1.000 |
| 3 | same as now | 0.203 | 0.165 | 0.234 | 1.000 | -0.263 | -0.278 | -0.247 | 1.000 |
| 3 | same hour yesterday | 0.130 | 0.093 | 0.159 | 1.000 | -0.157 | -0.170 | -0.145 | 1.000 |
| 3 | train frequency | 0.140 | 0.106 | 0.175 | 1.000 | -0.092 | -0.106 | -0.078 | 1.000 |
| 3 | rolling 4-week frequency | 0.126 | 0.088 | 0.157 | 1.000 | -0.049 | -0.055 | -0.043 | 1.000 |
| 6 | logistic | 0.080 | 0.050 | 0.109 | 1.000 | -0.009 | -0.011 | -0.007 | 1.000 |
| 6 | same as now | 0.179 | 0.135 | 0.215 | 1.000 | -0.302 | -0.318 | -0.286 | 1.000 |
| 6 | same hour yesterday | 0.117 | 0.079 | 0.146 | 1.000 | -0.121 | -0.137 | -0.105 | 1.000 |
| 6 | train frequency | 0.135 | 0.090 | 0.170 | 1.000 | -0.113 | -0.132 | -0.097 | 1.000 |
| 6 | rolling 4-week frequency | 0.126 | 0.078 | 0.165 | 1.000 | -0.046 | -0.053 | -0.038 | 1.000 |
