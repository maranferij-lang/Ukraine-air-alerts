Forward test (API, 41 days), target (b), frozen models.

## Calibration in the large: mean predicted against observed

Brier = (mean predicted - observed)^2 + Var(p - y), exactly, so `bias^2` is the part of the Brier score that is calibration-in-the-large.

| H | predictor | mean_predicted | observed | bias | bias^2 | brier | bias^2 share of Brier |
|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.1516 | 0.1796 | -0.0280 | 0.0008 | 0.1193 | 0.0066 |
| 1 | logistic | 0.1561 | 0.1796 | -0.0235 | 0.0006 | 0.1359 | 0.0041 |
| 1 | train frequency | 0.0857 | 0.1796 | -0.0940 | 0.0088 | 0.1517 | 0.0582 |
| 1 | rolling 4-week frequency | 0.1549 | 0.1796 | -0.0247 | 0.0006 | 0.1603 | 0.0038 |
| 3 | LightGBM | 0.3681 | 0.4143 | -0.0462 | 0.0021 | 0.1666 | 0.0128 |
| 3 | logistic | 0.3731 | 0.4143 | -0.0412 | 0.0017 | 0.1827 | 0.0093 |
| 3 | train frequency | 0.2258 | 0.4143 | -0.1886 | 0.0356 | 0.2590 | 0.1373 |
| 3 | rolling 4-week frequency | 0.3680 | 0.4143 | -0.0464 | 0.0022 | 0.2159 | 0.0100 |
| 6 | LightGBM | 0.5315 | 0.5711 | -0.0396 | 0.0016 | 0.1428 | 0.0110 |
| 6 | logistic | 0.5413 | 0.5711 | -0.0298 | 0.0009 | 0.1516 | 0.0059 |
| 6 | train frequency | 0.3691 | 0.5711 | -0.2020 | 0.0408 | 0.2563 | 0.1592 |
| 6 | rolling 4-week frequency | 0.5192 | 0.5711 | -0.0519 | 0.0027 | 0.1889 | 0.0143 |

## How the Brier score changed from the old test to the forward test

Old test = the same frozen artifacts on the old official test rows (24 days; reproduces `results/calibration.md`). Murphy terms as in `results/calibration.md`: Brier = reliability - resolution + uncertainty + residual. `uncertainty` is base rate x (1 - base rate): a higher base rate raises it for any forecaster.

| H | predictor | Brier old | Brier fwd | Brier change | uncertainty (base rate x (1 - base rate)) old | uncertainty (base rate x (1 - base rate)) fwd | uncertainty (base rate x (1 - base rate)) change | reliability old | reliability fwd | reliability change | resolution old | resolution fwd | resolution change | residual old | residual fwd | residual change | bias^2 old | bias^2 fwd | bias^2 change |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.0875 | 0.1193 | 0.0318 | 0.1066 | 0.1474 | 0.0407 | 0.0004 | 0.0015 | 0.0012 | 0.0185 | 0.0282 | 0.0097 | -0.0011 | -0.0014 | -0.0003 | 0.0001 | 0.0008 | 0.0007 |
| 1 | train frequency | 0.1014 | 0.1517 | 0.0503 | 0.1066 | 0.1474 | 0.0407 | 0.0017 | 0.0093 | 0.0076 | 0.0054 | 0.0032 | -0.0022 | -0.0015 | -0.0018 | -0.0002 | 0.0013 | 0.0088 | 0.0076 |
| 3 | LightGBM | 0.1446 | 0.1666 | 0.0220 | 0.2083 | 0.2427 | 0.0344 | 0.0013 | 0.0031 | 0.0019 | 0.0638 | 0.0782 | 0.0144 | -0.0012 | -0.0009 | 0.0002 | 0.0003 | 0.0021 | 0.0018 |
| 3 | train frequency | 0.1773 | 0.2590 | 0.0817 | 0.2083 | 0.2427 | 0.0344 | 0.0134 | 0.0462 | 0.0328 | 0.0435 | 0.0289 | -0.0147 | -0.0008 | -0.0010 | -0.0002 | 0.0049 | 0.0356 | 0.0307 |
| 6 | LightGBM | 0.1398 | 0.1428 | 0.0030 | 0.2451 | 0.2450 | -0.0001 | 0.0012 | 0.0026 | 0.0014 | 0.1055 | 0.1040 | -0.0015 | -0.0010 | -0.0007 | 0.0003 | 0.0001 | 0.0016 | 0.0015 |
| 6 | train frequency | 0.1777 | 0.2563 | 0.0785 | 0.2451 | 0.2450 | -0.0001 | 0.0201 | 0.0607 | 0.0406 | 0.0867 | 0.0482 | -0.0386 | -0.0007 | -0.0012 | -0.0005 | 0.0036 | 0.0408 | 0.0372 |

In words (generated from the table above; percentages can exceed 100 or be negative because the terms offset each other):

- H=1, LightGBM: Brier 0.0875 -> 0.1193 (+0.0318). The higher base rate alone changes the uncertainty term by +0.0407 (128% of the change); resolution changes by +0.0097 (a rise lowers the Brier), reliability by +0.0012, residual by -0.0003. Calibration in the large: squared bias 0.0001 -> 0.0008 (+0.0007, 2% of the Brier change).
- H=1, train frequency: Brier 0.1014 -> 0.1517 (+0.0503). The higher base rate alone changes the uncertainty term by +0.0407 (81% of the change); resolution changes by -0.0022 (a rise lowers the Brier), reliability by +0.0076, residual by -0.0002. Calibration in the large: squared bias 0.0013 -> 0.0088 (+0.0076, 15% of the Brier change).
- H=3, LightGBM: Brier 0.1446 -> 0.1666 (+0.0220). The higher base rate alone changes the uncertainty term by +0.0344 (156% of the change); resolution changes by +0.0144 (a rise lowers the Brier), reliability by +0.0019, residual by +0.0002. Calibration in the large: squared bias 0.0003 -> 0.0021 (+0.0018, 8% of the Brier change).
- H=3, train frequency: Brier 0.1773 -> 0.2590 (+0.0817). The higher base rate alone changes the uncertainty term by +0.0344 (42% of the change); resolution changes by -0.0147 (a rise lowers the Brier), reliability by +0.0328, residual by -0.0002. Calibration in the large: squared bias 0.0049 -> 0.0356 (+0.0307, 38% of the Brier change).
- H=6, LightGBM: Brier 0.1398 -> 0.1428 (+0.0030). The higher base rate alone changes the uncertainty term by -0.0001 (-5% of the change); resolution changes by -0.0015 (a rise lowers the Brier), reliability by +0.0014, residual by +0.0003. Calibration in the large: squared bias 0.0001 -> 0.0016 (+0.0015, 49% of the Brier change).
- H=6, train frequency: Brier 0.1777 -> 0.2563 (+0.0785). The higher base rate alone changes the uncertainty term by -0.0001 (-0% of the change); resolution changes by -0.0386 (a rise lowers the Brier), reliability by +0.0406, residual by -0.0005. Calibration in the large: squared bias 0.0036 -> 0.0408 (+0.0372, 47% of the Brier change).

## Brier decomposition, forward test

| H | predictor | mean_predicted | observed | brier | reliability | resolution | uncertainty | residual |
|---|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.1516 | 0.1796 | 0.1193 | 0.0015 | 0.0282 | 0.1474 | -0.0014 |
| 1 | logistic | 0.1561 | 0.1796 | 0.1359 | 0.0026 | 0.0130 | 0.1474 | -0.0011 |
| 1 | train frequency | 0.0857 | 0.1796 | 0.1517 | 0.0093 | 0.0032 | 0.1474 | -0.0018 |
| 1 | rolling 4-week frequency | 0.1549 | 0.1796 | 0.1603 | 0.0191 | 0.0061 | 0.1474 | 0.0000 |
| 3 | LightGBM | 0.3681 | 0.4143 | 0.1666 | 0.0031 | 0.0782 | 0.2427 | -0.0009 |
| 3 | logistic | 0.3731 | 0.4143 | 0.1827 | 0.0049 | 0.0646 | 0.2427 | -0.0003 |
| 3 | train frequency | 0.2258 | 0.4143 | 0.2590 | 0.0462 | 0.0289 | 0.2427 | -0.0010 |
| 3 | rolling 4-week frequency | 0.3680 | 0.4143 | 0.2159 | 0.0191 | 0.0458 | 0.2427 | 0.0000 |
| 6 | LightGBM | 0.5315 | 0.5711 | 0.1428 | 0.0026 | 0.1040 | 0.2450 | -0.0007 |
| 6 | logistic | 0.5413 | 0.5711 | 0.1516 | 0.0028 | 0.0953 | 0.2450 | -0.0009 |
| 6 | train frequency | 0.3691 | 0.5711 | 0.2563 | 0.0607 | 0.0482 | 0.2450 | -0.0012 |
| 6 | rolling 4-week frequency | 0.5192 | 0.5711 | 0.1889 | 0.0167 | 0.0727 | 0.2450 | 0.0000 |

Reliability table (10 bins):

| H | predictor | bin | mean_predicted | observed | n |
|---|---|---|---|---|---|
| 1 | LightGBM | 0.0-0.1 | 0.043 | 0.052 | 11671 |
| 1 | LightGBM | 0.1-0.2 | 0.141 | 0.162 | 5580 |
| 1 | LightGBM | 0.2-0.3 | 0.248 | 0.309 | 2100 |
| 1 | LightGBM | 0.3-0.4 | 0.349 | 0.430 | 2264 |
| 1 | LightGBM | 0.4-0.5 | 0.442 | 0.515 | 1350 |
| 1 | LightGBM | 0.5-0.6 | 0.544 | 0.580 | 419 |
| 1 | LightGBM | 0.6-0.7 | 0.639 | 0.725 | 200 |
| 1 | LightGBM | 0.7-0.8 | 0.735 | 0.906 | 32 |
| 1 | train frequency | 0.0-0.1 | 0.041 | 0.140 | 15237 |
| 1 | train frequency | 0.1-0.2 | 0.140 | 0.239 | 6237 |
| 1 | train frequency | 0.2-0.3 | 0.236 | 0.300 | 2006 |
| 1 | train frequency | 0.3-0.4 | 0.333 | 0.162 | 136 |
| 3 | LightGBM | 0.0-0.1 | 0.049 | 0.046 | 4616 |
| 3 | LightGBM | 0.1-0.2 | 0.151 | 0.175 | 3477 |
| 3 | LightGBM | 0.2-0.3 | 0.246 | 0.290 | 3024 |
| 3 | LightGBM | 0.3-0.4 | 0.348 | 0.419 | 2202 |
| 3 | LightGBM | 0.4-0.5 | 0.451 | 0.524 | 2226 |
| 3 | LightGBM | 0.5-0.6 | 0.552 | 0.615 | 2380 |
| 3 | LightGBM | 0.6-0.7 | 0.650 | 0.746 | 2511 |
| 3 | LightGBM | 0.7-0.8 | 0.748 | 0.808 | 2132 |
| 3 | LightGBM | 0.8-0.9 | 0.836 | 0.889 | 941 |
| 3 | LightGBM | 0.9-1.0 | 0.918 | 0.963 | 107 |
| 3 | train frequency | 0.0-0.1 | 0.063 | 0.176 | 7524 |
| 3 | train frequency | 0.1-0.2 | 0.143 | 0.471 | 5017 |
| 3 | train frequency | 0.2-0.3 | 0.249 | 0.510 | 3671 |
| 3 | train frequency | 0.3-0.4 | 0.347 | 0.532 | 3389 |
| 3 | train frequency | 0.4-0.5 | 0.448 | 0.621 | 1959 |
| 3 | train frequency | 0.5-0.6 | 0.545 | 0.633 | 1436 |
| 3 | train frequency | 0.6-0.7 | 0.633 | 0.488 | 609 |
| 3 | train frequency | 0.7-0.8 | 0.711 | 0.000 | 11 |
| 6 | LightGBM | 0.0-0.1 | 0.069 | 0.039 | 2687 |
| 6 | LightGBM | 0.1-0.2 | 0.144 | 0.158 | 2455 |
| 6 | LightGBM | 0.2-0.3 | 0.253 | 0.313 | 1714 |
| 6 | LightGBM | 0.3-0.4 | 0.351 | 0.384 | 2128 |
| 6 | LightGBM | 0.4-0.5 | 0.447 | 0.467 | 1725 |
| 6 | LightGBM | 0.5-0.6 | 0.549 | 0.635 | 1415 |
| 6 | LightGBM | 0.6-0.7 | 0.651 | 0.728 | 1876 |
| 6 | LightGBM | 0.7-0.8 | 0.756 | 0.810 | 2688 |
| 6 | LightGBM | 0.8-0.9 | 0.856 | 0.908 | 5374 |
| 6 | LightGBM | 0.9-1.0 | 0.920 | 0.976 | 1554 |
| 6 | train frequency | 0.0-0.1 | 0.077 | 0.166 | 1936 |
| 6 | train frequency | 0.1-0.2 | 0.142 | 0.318 | 6433 |
| 6 | train frequency | 0.2-0.3 | 0.250 | 0.729 | 2576 |
| 6 | train frequency | 0.3-0.4 | 0.347 | 0.682 | 2672 |
| 6 | train frequency | 0.4-0.5 | 0.449 | 0.702 | 2502 |
| 6 | train frequency | 0.5-0.6 | 0.543 | 0.738 | 2587 |
| 6 | train frequency | 0.6-0.7 | 0.648 | 0.817 | 2014 |
| 6 | train frequency | 0.7-0.8 | 0.754 | 0.733 | 1972 |
| 6 | train frequency | 0.8-0.9 | 0.829 | 0.722 | 924 |
