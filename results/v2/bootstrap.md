v2 test window (20 days). Day-block bootstrap: whole test days resampled with replacement, 1000 resamples, seed 0, 95% percentile intervals.

Each predictor:

| H | predictor | auc | auc_lo | auc_hi | brier | brier_lo | brier_hi |
|---|---|---|---|---|---|---|---|
| 1 | v2 LightGBM | 0.692 | 0.650 | 0.722 | 0.127 | 0.117 | 0.136 |
| 1 | v2 + Platt (secondary) | 0.692 | 0.650 | 0.722 | 0.127 | 0.117 | 0.136 |
| 1 | frozen v1 LightGBM | 0.686 | 0.644 | 0.714 | 0.129 | 0.118 | 0.139 |
| 1 | logistic (refit on the v2 rows) | 0.531 | 0.501 | 0.563 | 0.147 | 0.133 | 0.160 |
| 1 | same as now | 0.400 | 0.380 | 0.417 | 0.421 | 0.382 | 0.458 |
| 1 | same hour yesterday | 0.517 | 0.506 | 0.528 | 0.269 | 0.247 | 0.289 |
| 1 | train frequency | 0.513 | 0.492 | 0.528 | 0.165 | 0.148 | 0.181 |
| 1 | rolling 4-week frequency | 0.509 | 0.499 | 0.520 | 0.172 | 0.158 | 0.185 |
| 3 | v2 LightGBM | 0.663 | 0.622 | 0.693 | 0.166 | 0.155 | 0.176 |
| 3 | v2 + Platt (secondary) | 0.663 | 0.622 | 0.693 | 0.165 | 0.155 | 0.176 |
| 3 | frozen v1 LightGBM | 0.660 | 0.620 | 0.689 | 0.170 | 0.159 | 0.180 |
| 3 | logistic (refit on the v2 rows) | 0.547 | 0.510 | 0.575 | 0.187 | 0.172 | 0.202 |
| 3 | same as now | 0.459 | 0.438 | 0.477 | 0.438 | 0.408 | 0.465 |
| 3 | same hour yesterday | 0.541 | 0.525 | 0.553 | 0.316 | 0.297 | 0.334 |
| 3 | train frequency | 0.516 | 0.485 | 0.546 | 0.278 | 0.250 | 0.304 |
| 3 | rolling 4-week frequency | 0.521 | 0.507 | 0.538 | 0.225 | 0.211 | 0.239 |
| 6 | v2 LightGBM | 0.664 | 0.616 | 0.696 | 0.131 | 0.119 | 0.143 |
| 6 | v2 + Platt (secondary) | 0.664 | 0.616 | 0.696 | 0.131 | 0.118 | 0.144 |
| 6 | frozen v1 LightGBM | 0.654 | 0.606 | 0.684 | 0.135 | 0.124 | 0.146 |
| 6 | logistic (refit on the v2 rows) | 0.569 | 0.522 | 0.600 | 0.144 | 0.131 | 0.156 |
| 6 | same as now | 0.478 | 0.458 | 0.496 | 0.443 | 0.420 | 0.466 |
| 6 | same hour yesterday | 0.543 | 0.523 | 0.559 | 0.238 | 0.213 | 0.264 |
| 6 | train frequency | 0.507 | 0.471 | 0.542 | 0.271 | 0.247 | 0.294 |
| 6 | rolling 4-week frequency | 0.502 | 0.475 | 0.534 | 0.187 | 0.173 | 0.200 |

v2 minus each other predictor (AUC: positive = v2 ahead; Brier: negative = v2 ahead; `share_*_ahead` = share of resamples in which v2 is ahead). 'v2 + Platt' has the same within-oblast AUC by construction, so its AUC difference is 0:

| H | predictor | d_auc | d_auc_lo | d_auc_hi | share_auc_ahead | d_brier | d_brier_lo | d_brier_hi | share_brier_ahead |
|---|---|---|---|---|---|---|---|---|---|
| 1 | v2 + Platt (secondary) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -0.001 | 0.001 | 0.494 |
| 1 | frozen v1 LightGBM | 0.006 | -0.001 | 0.014 | 0.946 | -0.002 | -0.003 | -0.001 | 1.000 |
| 1 | logistic (refit on the v2 rows) | 0.160 | 0.121 | 0.181 | 1.000 | -0.020 | -0.024 | -0.015 | 1.000 |
| 1 | same as now | 0.291 | 0.242 | 0.327 | 1.000 | -0.294 | -0.325 | -0.263 | 1.000 |
| 1 | same hour yesterday | 0.175 | 0.130 | 0.205 | 1.000 | -0.142 | -0.156 | -0.129 | 1.000 |
| 1 | train frequency | 0.179 | 0.135 | 0.212 | 1.000 | -0.038 | -0.046 | -0.031 | 1.000 |
| 1 | rolling 4-week frequency | 0.183 | 0.138 | 0.214 | 1.000 | -0.045 | -0.051 | -0.040 | 1.000 |
| 3 | v2 + Platt (secondary) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -0.000 | 0.001 | 0.224 |
| 3 | frozen v1 LightGBM | 0.004 | -0.003 | 0.010 | 0.879 | -0.004 | -0.006 | -0.002 | 1.000 |
| 3 | logistic (refit on the v2 rows) | 0.117 | 0.082 | 0.146 | 1.000 | -0.021 | -0.028 | -0.015 | 1.000 |
| 3 | same as now | 0.204 | 0.158 | 0.243 | 1.000 | -0.272 | -0.297 | -0.247 | 1.000 |
| 3 | same hour yesterday | 0.123 | 0.083 | 0.158 | 1.000 | -0.150 | -0.170 | -0.132 | 1.000 |
| 3 | train frequency | 0.148 | 0.102 | 0.187 | 1.000 | -0.112 | -0.136 | -0.090 | 1.000 |
| 3 | rolling 4-week frequency | 0.142 | 0.098 | 0.173 | 1.000 | -0.059 | -0.068 | -0.049 | 1.000 |
| 6 | v2 + Platt (secondary) | 0.000 | 0.000 | 0.000 | 0.000 | -0.000 | -0.001 | 0.001 | 0.635 |
| 6 | frozen v1 LightGBM | 0.011 | 0.000 | 0.020 | 0.975 | -0.004 | -0.006 | -0.002 | 1.000 |
| 6 | logistic (refit on the v2 rows) | 0.096 | 0.055 | 0.143 | 1.000 | -0.013 | -0.017 | -0.008 | 1.000 |
| 6 | same as now | 0.186 | 0.140 | 0.221 | 1.000 | -0.312 | -0.341 | -0.283 | 1.000 |
| 6 | same hour yesterday | 0.122 | 0.080 | 0.151 | 1.000 | -0.107 | -0.129 | -0.087 | 1.000 |
| 6 | train frequency | 0.157 | 0.096 | 0.201 | 1.000 | -0.140 | -0.168 | -0.111 | 1.000 |
| 6 | rolling 4-week frequency | 0.163 | 0.111 | 0.198 | 1.000 | -0.055 | -0.068 | -0.044 | 1.000 |
