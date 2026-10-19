v2 test window (20 days), target (b). Calibration in the large (mean predicted against observed; Brier = bias^2 + Var(p - y) exactly) and the Murphy decomposition (Brier = reliability - resolution + uncertainty + residual).

| H | predictor | mean_predicted | observed | bias | bias^2 | brier | reliability | resolution | uncertainty | residual |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | v2 LightGBM | 0.1762 | 0.1957 | -0.0195 | 0.0004 | 0.1269 | 0.0007 | 0.0301 | 0.1574 | -0.0011 |
| 1 | v2 + Platt (secondary) | 0.1826 | 0.1957 | -0.0132 | 0.0002 | 0.1269 | 0.0006 | 0.0300 | 0.1574 | -0.0012 |
| 1 | frozen v1 LightGBM | 0.1611 | 0.1957 | -0.0347 | 0.0012 | 0.1292 | 0.0020 | 0.0285 | 0.1574 | -0.0017 |
| 1 | logistic (refit on the v2 rows) | 0.1692 | 0.1957 | -0.0265 | 0.0007 | 0.1466 | 0.0035 | 0.0133 | 0.1574 | -0.0011 |
| 1 | train frequency | 0.0878 | 0.1957 | -0.1080 | 0.0117 | 0.1653 | 0.0121 | 0.0026 | 0.1574 | -0.0016 |
| 1 | rolling 4-week frequency | 0.1669 | 0.1957 | -0.0288 | 0.0008 | 0.1723 | 0.0210 | 0.0061 | 0.1574 | -0.0000 |
| 3 | v2 LightGBM | 0.4114 | 0.4426 | -0.0311 | 0.0010 | 0.1656 | 0.0018 | 0.0821 | 0.2467 | -0.0008 |
| 3 | v2 + Platt (secondary) | 0.4182 | 0.4426 | -0.0244 | 0.0006 | 0.1653 | 0.0017 | 0.0819 | 0.2467 | -0.0012 |
| 3 | frozen v1 LightGBM | 0.3882 | 0.4426 | -0.0543 | 0.0030 | 0.1696 | 0.0046 | 0.0807 | 0.2467 | -0.0011 |
| 3 | logistic (refit on the v2 rows) | 0.3999 | 0.4426 | -0.0427 | 0.0018 | 0.1869 | 0.0069 | 0.0663 | 0.2467 | -0.0004 |
| 3 | train frequency | 0.2302 | 0.4426 | -0.2123 | 0.0451 | 0.2780 | 0.0557 | 0.0238 | 0.2467 | -0.0005 |
| 3 | rolling 4-week frequency | 0.3909 | 0.4426 | -0.0516 | 0.0027 | 0.2247 | 0.0224 | 0.0444 | 0.2467 | -0.0000 |
| 6 | v2 LightGBM | 0.5758 | 0.5954 | -0.0196 | 0.0004 | 0.1311 | 0.0014 | 0.1106 | 0.2409 | -0.0006 |
| 6 | v2 + Platt (secondary) | 0.5751 | 0.5954 | -0.0203 | 0.0004 | 0.1312 | 0.0015 | 0.1106 | 0.2409 | -0.0005 |
| 6 | frozen v1 LightGBM | 0.5551 | 0.5954 | -0.0403 | 0.0016 | 0.1348 | 0.0031 | 0.1082 | 0.2409 | -0.0010 |
| 6 | logistic (refit on the v2 rows) | 0.5685 | 0.5954 | -0.0270 | 0.0007 | 0.1436 | 0.0031 | 0.0997 | 0.2409 | -0.0007 |
| 6 | train frequency | 0.3743 | 0.5954 | -0.2211 | 0.0489 | 0.2713 | 0.0697 | 0.0380 | 0.2409 | -0.0014 |
| 6 | rolling 4-week frequency | 0.5469 | 0.5954 | -0.0486 | 0.0024 | 0.1866 | 0.0169 | 0.0712 | 0.2409 | -0.0000 |

## Platt scaling (secondary variant)

Fitted only on the validation week, on the validation-fit model's scores, then applied to the final model's test scores (the same approximation as the thresholds):

| H | intercept | slope on logit(p) | validation-week rows | threshold plain v2 | threshold Platt |
|---|---|---|---|---|---|
| 1 | 0.1745 | 1.1076 | 4032 | 0.2519 | 0.2629 |
| 3 | 0.0558 | 1.0855 | 3984 | 0.4270 | 0.4346 |
| 6 | -0.0409 | 1.1386 | 3912 | 0.4268 | 0.4070 |

Reliability table, plain v2 and v2 + Platt (10 bins):

| H | predictor | bin | mean_predicted | observed | n |
|---|---|---|---|---|---|
| 1 | v2 LightGBM | 0.0-0.1 | 0.044 | 0.056 | 5234 |
| 1 | v2 LightGBM | 0.1-0.2 | 0.142 | 0.156 | 2736 |
| 1 | v2 LightGBM | 0.2-0.3 | 0.246 | 0.315 | 975 |
| 1 | v2 LightGBM | 0.3-0.4 | 0.354 | 0.376 | 848 |
| 1 | v2 LightGBM | 0.4-0.5 | 0.449 | 0.472 | 976 |
| 1 | v2 LightGBM | 0.5-0.6 | 0.543 | 0.558 | 548 |
| 1 | v2 LightGBM | 0.6-0.7 | 0.643 | 0.645 | 155 |
| 1 | v2 LightGBM | 0.7-0.8 | 0.749 | 0.821 | 39 |
| 1 | v2 LightGBM | 0.8-0.9 | 0.817 | 1.000 | 9 |
| 1 | v2 + Platt (secondary) | 0.0-0.1 | 0.041 | 0.059 | 5427 |
| 1 | v2 + Platt (secondary) | 0.1-0.2 | 0.142 | 0.159 | 2494 |
| 1 | v2 + Platt (secondary) | 0.2-0.3 | 0.246 | 0.305 | 895 |
| 1 | v2 + Platt (secondary) | 0.3-0.4 | 0.352 | 0.361 | 712 |
| 1 | v2 + Platt (secondary) | 0.4-0.5 | 0.451 | 0.425 | 871 |
| 1 | v2 + Platt (secondary) | 0.5-0.6 | 0.545 | 0.528 | 714 |
| 1 | v2 + Platt (secondary) | 0.6-0.7 | 0.641 | 0.623 | 300 |
| 1 | v2 + Platt (secondary) | 0.7-0.8 | 0.739 | 0.650 | 80 |
| 1 | v2 + Platt (secondary) | 0.8-0.9 | 0.837 | 0.926 | 27 |
| 3 | v2 LightGBM | 0.0-0.1 | 0.044 | 0.042 | 2026 |
| 3 | v2 LightGBM | 0.1-0.2 | 0.149 | 0.152 | 1596 |
| 3 | v2 LightGBM | 0.2-0.3 | 0.248 | 0.313 | 1277 |
| 3 | v2 LightGBM | 0.3-0.4 | 0.348 | 0.426 | 929 |
| 3 | v2 LightGBM | 0.4-0.5 | 0.450 | 0.521 | 936 |
| 3 | v2 LightGBM | 0.5-0.6 | 0.550 | 0.592 | 1072 |
| 3 | v2 LightGBM | 0.6-0.7 | 0.650 | 0.677 | 1122 |
| 3 | v2 LightGBM | 0.7-0.8 | 0.752 | 0.784 | 1336 |
| 3 | v2 LightGBM | 0.8-0.9 | 0.845 | 0.862 | 983 |
| 3 | v2 LightGBM | 0.9-1.0 | 0.921 | 0.903 | 195 |
| 3 | v2 + Platt (secondary) | 0.0-0.1 | 0.041 | 0.048 | 2199 |
| 3 | v2 + Platt (secondary) | 0.1-0.2 | 0.146 | 0.157 | 1517 |
| 3 | v2 + Platt (secondary) | 0.2-0.3 | 0.246 | 0.325 | 1211 |
| 3 | v2 + Platt (secondary) | 0.3-0.4 | 0.348 | 0.430 | 873 |
| 3 | v2 + Platt (secondary) | 0.4-0.5 | 0.450 | 0.522 | 843 |
| 3 | v2 + Platt (secondary) | 0.5-0.6 | 0.551 | 0.584 | 965 |
| 3 | v2 + Platt (secondary) | 0.6-0.7 | 0.650 | 0.652 | 1058 |
| 3 | v2 + Platt (secondary) | 0.7-0.8 | 0.753 | 0.763 | 1259 |
| 3 | v2 + Platt (secondary) | 0.8-0.9 | 0.846 | 0.830 | 1186 |
| 3 | v2 + Platt (secondary) | 0.9-1.0 | 0.925 | 0.906 | 361 |
| 6 | v2 LightGBM | 0.0-0.1 | 0.053 | 0.030 | 1285 |
| 6 | v2 LightGBM | 0.1-0.2 | 0.148 | 0.165 | 905 |
| 6 | v2 LightGBM | 0.2-0.3 | 0.255 | 0.238 | 905 |
| 6 | v2 LightGBM | 0.3-0.4 | 0.349 | 0.361 | 924 |
| 6 | v2 LightGBM | 0.4-0.5 | 0.448 | 0.501 | 700 |
| 6 | v2 LightGBM | 0.5-0.6 | 0.553 | 0.631 | 628 |
| 6 | v2 LightGBM | 0.6-0.7 | 0.652 | 0.744 | 625 |
| 6 | v2 LightGBM | 0.7-0.8 | 0.752 | 0.800 | 999 |
| 6 | v2 LightGBM | 0.8-0.9 | 0.857 | 0.861 | 1932 |
| 6 | v2 LightGBM | 0.9-1.0 | 0.935 | 0.952 | 2497 |
| 6 | v2 + Platt (secondary) | 0.0-0.1 | 0.045 | 0.051 | 1598 |
| 6 | v2 + Platt (secondary) | 0.1-0.2 | 0.147 | 0.186 | 839 |
| 6 | v2 + Platt (secondary) | 0.2-0.3 | 0.250 | 0.264 | 940 |
| 6 | v2 + Platt (secondary) | 0.3-0.4 | 0.347 | 0.395 | 798 |
| 6 | v2 + Platt (secondary) | 0.4-0.5 | 0.447 | 0.526 | 587 |
| 6 | v2 + Platt (secondary) | 0.5-0.6 | 0.552 | 0.642 | 558 |
| 6 | v2 + Platt (secondary) | 0.6-0.7 | 0.651 | 0.733 | 554 |
| 6 | v2 + Platt (secondary) | 0.7-0.8 | 0.754 | 0.791 | 845 |
| 6 | v2 + Platt (secondary) | 0.8-0.9 | 0.857 | 0.839 | 1566 |
| 6 | v2 + Platt (secondary) | 0.9-1.0 | 0.944 | 0.941 | 3115 |
