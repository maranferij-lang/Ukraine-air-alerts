# SECONDARY, not the result: the forward test with the official outage mask switched on for the API features

The main result (`forward_table.md`) uses no mask, because the API observed 2026-08-29..09-02. This run applies the official feed's mask anyway (7-day windows that overlap the outage computed over the observed part and scaled, freq4w lags that touch it skipped), to show what the choice changes. Same frozen models and thresholds, same rows. Only the LightGBM, the logistic model and the rolling 4-week frequency use these features; the other predictors are identical in both runs. Point estimates only (no bootstrap).

| H | predictor | auc_within_oblast | auc_within_oblast_masked | AUC change | brier | brier_masked | Brier change | f1 | f1_masked |
|---|---|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.7079 | 0.7081 | 0.0003 | 0.1193 | 0.1194 | 0.0001 | 0.5153 | 0.5153 |
| 1 | logistic | 0.5377 | 0.5387 | 0.0010 | 0.1359 | 0.1359 | 0.0000 | 0.4258 | 0.4266 |
| 1 | same as now | 0.4066 | 0.4066 | 0.0000 | 0.4004 | 0.4004 | 0.0000 | 0.1433 | 0.1433 |
| 1 | same hour yesterday | 0.5150 | 0.5150 | 0.0000 | 0.2549 | 0.2549 | 0.0000 | 0.2854 | 0.2854 |
| 1 | train frequency | 0.5308 | 0.5308 | 0.0000 | 0.1517 | 0.1517 | 0.0000 | 0.3530 | 0.3530 |
| 1 | rolling 4-week frequency | 0.5189 | 0.5190 | 0.0001 | 0.1603 | 0.1643 | 0.0040 | 0.3739 | 0.3683 |
| 3 | LightGBM | 0.6619 | 0.6613 | -0.0006 | 0.1666 | 0.1669 | 0.0003 | 0.7212 | 0.7214 |
| 3 | logistic | 0.5609 | 0.5627 | 0.0018 | 0.1827 | 0.1828 | 0.0001 | 0.7048 | 0.7047 |
| 3 | same as now | 0.4591 | 0.4591 | 0.0000 | 0.4293 | 0.4293 | 0.0000 | 0.3886 | 0.3886 |
| 3 | same hour yesterday | 0.5319 | 0.5319 | 0.0000 | 0.3232 | 0.3232 | 0.0000 | 0.6072 | 0.6072 |
| 3 | train frequency | 0.5223 | 0.5223 | 0.0000 | 0.2590 | 0.2590 | 0.0000 | 0.6023 | 0.6023 |
| 3 | rolling 4-week frequency | 0.5361 | 0.5372 | 0.0011 | 0.2159 | 0.2242 | 0.0082 | 0.6748 | 0.6697 |
| 6 | LightGBM | 0.6535 | 0.6515 | -0.0020 | 0.1428 | 0.1433 | 0.0006 | 0.8242 | 0.8241 |
| 6 | logistic | 0.5734 | 0.5755 | 0.0022 | 0.1516 | 0.1519 | 0.0003 | 0.8213 | 0.8205 |
| 6 | same as now | 0.4748 | 0.4748 | 0.0000 | 0.4447 | 0.4447 | 0.0000 | 0.4822 | 0.4822 |
| 6 | same hour yesterday | 0.5365 | 0.5365 | 0.0000 | 0.2638 | 0.2638 | 0.0000 | 0.7676 | 0.7676 |
| 6 | train frequency | 0.5185 | 0.5185 | 0.0000 | 0.2563 | 0.2563 | 0.0000 | 0.7246 | 0.7246 |
| 6 | rolling 4-week frequency | 0.5278 | 0.5260 | -0.0017 | 0.1889 | 0.1990 | 0.0102 | 0.7968 | 0.7696 |

Calibration in the large, masked features:

| H | predictor | mean_predicted | observed | bias | bias^2 | brier | bias^2 share of Brier |
|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.1510 | 0.1796 | -0.0286 | 0.0008 | 0.1194 | 0.0069 |
| 1 | logistic | 0.1558 | 0.1796 | -0.0238 | 0.0006 | 0.1359 | 0.0042 |
| 1 | rolling 4-week frequency | 0.1507 | 0.1796 | -0.0290 | 0.0008 | 0.1643 | 0.0051 |
| 3 | LightGBM | 0.3660 | 0.4143 | -0.0483 | 0.0023 | 0.1669 | 0.0140 |
| 3 | logistic | 0.3722 | 0.4143 | -0.0421 | 0.0018 | 0.1828 | 0.0097 |
| 3 | rolling 4-week frequency | 0.3577 | 0.4143 | -0.0567 | 0.0032 | 0.2242 | 0.0143 |
| 6 | LightGBM | 0.5288 | 0.5711 | -0.0423 | 0.0018 | 0.1433 | 0.0125 |
| 6 | logistic | 0.5401 | 0.5711 | -0.0309 | 0.0010 | 0.1519 | 0.0063 |
| 6 | rolling 4-week frequency | 0.5082 | 0.5711 | -0.0628 | 0.0039 | 0.1990 | 0.0198 |
