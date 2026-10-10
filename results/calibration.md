Target (b), test rows. Brier = reliability - resolution + uncertainty (+ residual from 10 equal-width bins). Reliability: lower is better (miscalibration). Resolution: higher is better.

| H | predictor | mean_predicted | observed | brier | reliability | resolution | uncertainty | residual |
|---|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.1106 | 0.1214 | 0.0875 | 0.0004 | 0.0185 | 0.1066 | -0.0011 |
| 1 | LightGBM from 2026-01-01 | 0.1070 | 0.1214 | 0.0865 | 0.0005 | 0.0194 | 0.1066 | -0.0013 |
| 1 | logistic (starts_7d + hour + oblast) | 0.1144 | 0.1214 | 0.0971 | 0.0010 | 0.0094 | 0.1066 | -0.0012 |
| 1 | train freq oblast x hour x weekday | 0.0857 | 0.1214 | 0.1014 | 0.0017 | 0.0054 | 0.1066 | -0.0015 |
| 3 | LightGBM | 0.2781 | 0.2957 | 0.1446 | 0.0013 | 0.0638 | 0.2083 | -0.0012 |
| 3 | LightGBM from 2026-01-01 | 0.2696 | 0.2957 | 0.1425 | 0.0015 | 0.0664 | 0.2083 | -0.0009 |
| 3 | logistic (starts_7d + hour + oblast) | 0.2867 | 0.2957 | 0.1535 | 0.0020 | 0.0562 | 0.2083 | -0.0006 |
| 3 | train freq oblast x hour x weekday | 0.2259 | 0.2957 | 0.1773 | 0.0134 | 0.0435 | 0.2083 | -0.0008 |
| 6 | LightGBM | 0.4204 | 0.4300 | 0.1398 | 0.0012 | 0.1055 | 0.2451 | -0.0010 |
| 6 | LightGBM from 2026-01-01 | 0.4081 | 0.4300 | 0.1389 | 0.0013 | 0.1066 | 0.2451 | -0.0009 |
| 6 | logistic (starts_7d + hour + oblast) | 0.4388 | 0.4300 | 0.1461 | 0.0015 | 0.0995 | 0.2451 | -0.0010 |
| 6 | train freq oblast x hour x weekday | 0.3697 | 0.4300 | 0.1777 | 0.0201 | 0.0867 | 0.2451 | -0.0007 |

Reliability table, H = 6:

| predictor | bin | mean_predicted | observed | n |
|---|---|---|---|---|
| lgbm | 0.0-0.1 | 0.068 | 0.029 | 3361 |
| lgbm | 0.1-0.2 | 0.137 | 0.131 | 1303 |
| lgbm | 0.2-0.3 | 0.256 | 0.257 | 880 |
| lgbm | 0.3-0.4 | 0.350 | 0.364 | 1386 |
| lgbm | 0.4-0.5 | 0.448 | 0.475 | 1095 |
| lgbm | 0.5-0.6 | 0.550 | 0.614 | 1024 |
| lgbm | 0.6-0.7 | 0.650 | 0.700 | 1133 |
| lgbm | 0.7-0.8 | 0.749 | 0.768 | 1356 |
| lgbm | 0.8-0.9 | 0.853 | 0.886 | 1532 |
| lgbm | 0.9-1.0 | 0.933 | 0.973 | 514 |
| frequency | 0.0-0.1 | 0.076 | 0.012 | 1123 |
| frequency | 0.1-0.2 | 0.143 | 0.074 | 3702 |
| frequency | 0.2-0.3 | 0.250 | 0.365 | 1465 |
| frequency | 0.3-0.4 | 0.347 | 0.592 | 1522 |
| frequency | 0.4-0.5 | 0.449 | 0.689 | 1442 |
| frequency | 0.5-0.6 | 0.543 | 0.717 | 1482 |
| frequency | 0.6-0.7 | 0.647 | 0.726 | 1170 |
| frequency | 0.7-0.8 | 0.754 | 0.710 | 1137 |
| frequency | 0.8-0.9 | 0.828 | 0.752 | 541 |
