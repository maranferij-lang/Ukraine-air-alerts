Target (b), test month. Brier = reliability - resolution + uncertainty (+ residual from 10 equal-width bins). Reliability: lower is better (miscalibration). Resolution: higher is better.

| H | predictor | mean_predicted | observed | brier | reliability | resolution | uncertainty | residual |
|---|---|---|---|---|---|---|---|---|
| 1 | model | 0.1078 | 0.1196 | 0.0866 | 0.0004 | 0.0180 | 0.1053 | -0.0011 |
| 1 | frequency | 0.0856 | 0.1196 | 0.0998 | 0.0017 | 0.0057 | 0.1053 | -0.0014 |
| 3 | model | 0.2723 | 0.2897 | 0.1434 | 0.0013 | 0.0625 | 0.2058 | -0.0012 |
| 3 | frequency | 0.2257 | 0.2897 | 0.1737 | 0.0120 | 0.0431 | 0.2058 | -0.0009 |
| 6 | model | 0.4143 | 0.4207 | 0.1414 | 0.0012 | 0.1024 | 0.2437 | -0.0011 |
| 6 | frequency | 0.3692 | 0.4207 | 0.1757 | 0.0179 | 0.0851 | 0.2437 | -0.0008 |

Reliability table, H = 6:

| predictor | bin | mean_predicted | observed | n |
|---|---|---|---|---|
| model | 0.0-0.1 | 0.069 | 0.027 | 3164 |
| model | 0.1-0.2 | 0.136 | 0.124 | 1173 |
| model | 0.2-0.3 | 0.256 | 0.265 | 809 |
| model | 0.3-0.4 | 0.350 | 0.368 | 1331 |
| model | 0.4-0.5 | 0.448 | 0.476 | 1041 |
| model | 0.5-0.6 | 0.550 | 0.607 | 991 |
| model | 0.6-0.7 | 0.650 | 0.696 | 1084 |
| model | 0.7-0.8 | 0.749 | 0.756 | 1210 |
| model | 0.8-0.9 | 0.853 | 0.881 | 1307 |
| model | 0.9-1.0 | 0.934 | 0.971 | 442 |
| frequency | 0.0-0.1 | 0.076 | 0.003 | 1046 |
| frequency | 0.1-0.2 | 0.142 | 0.071 | 3416 |
| frequency | 0.2-0.3 | 0.250 | 0.350 | 1360 |
| frequency | 0.3-0.4 | 0.347 | 0.581 | 1414 |
| frequency | 0.4-0.5 | 0.449 | 0.667 | 1324 |
| frequency | 0.5-0.6 | 0.543 | 0.707 | 1370 |
| frequency | 0.6-0.7 | 0.647 | 0.713 | 1075 |
| frequency | 0.7-0.8 | 0.754 | 0.712 | 1052 |
| frequency | 0.8-0.9 | 0.829 | 0.743 | 495 |
