Test origins 2026-08-07 00:00 .. 2026-09-05 23:00 UTC (last 30 days of official data), outage rows dropped. Threshold = max F1 on the last 7 days of train. auc_within_oblast = mean of per-oblast AUCs (oblasts with both classes in test).

| target | H | baseline | n_test | base_rate | brier | auc | auc_within_oblast | n_oblasts_auc | threshold | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) alert active in (t, t+H] | 1 | same as now | 13824 | 0.309 | 0.100 | 0.838 | 0.753 | 24 | 1.000 | 1.000 | 0.675 | 0.806 |
| (a) alert active in (t, t+H] | 1 | same hour yesterday | 13824 | 0.309 | 0.217 | 0.745 | 0.524 | 24 | 1.000 | 0.650 | 0.644 | 0.647 |
| (a) alert active in (t, t+H] | 1 | train freq oblast x hour x weekday | 13824 | 0.309 | 0.150 | 0.884 | 0.559 | 24 | 0.253 | 0.689 | 0.704 | 0.696 |
| (b) new alert starts in (t, t+H] | 1 | same as now | 13824 | 0.121 | 0.288 | 0.480 | 0.438 | 24 | 0.000 | 0.121 | 1.000 | 0.216 |
| (b) new alert starts in (t, t+H] | 1 | same hour yesterday | 13824 | 0.121 | 0.181 | 0.571 | 0.525 | 24 | 1.000 | 0.248 | 0.244 | 0.246 |
| (b) new alert starts in (t, t+H] | 1 | train freq oblast x hour x weekday | 13824 | 0.121 | 0.101 | 0.736 | 0.491 | 24 | 0.083 | 0.213 | 0.745 | 0.332 |
| (a) alert active in (t, t+H] | 3 | same as now | 13728 | 0.416 | 0.207 | 0.751 | 0.657 | 23 | 1.000 | 1.000 | 0.501 | 0.668 |
| (a) alert active in (t, t+H] | 3 | same hour yesterday | 13728 | 0.416 | 0.234 | 0.758 | 0.513 | 23 | 1.000 | 0.721 | 0.712 | 0.716 |
| (a) alert active in (t, t+H] | 3 | train freq oblast x hour x weekday | 13728 | 0.416 | 0.152 | 0.895 | 0.558 | 23 | 0.245 | 0.694 | 0.884 | 0.778 |
| (b) new alert starts in (t, t+H] | 3 | same as now | 13728 | 0.296 | 0.327 | 0.565 | 0.480 | 24 | 0.000 | 0.296 | 1.000 | 0.456 |
| (b) new alert starts in (t, t+H] | 3 | same hour yesterday | 13728 | 0.296 | 0.281 | 0.660 | 0.524 | 24 | 1.000 | 0.525 | 0.516 | 0.520 |
| (b) new alert starts in (t, t+H] | 3 | train freq oblast x hour x weekday | 13728 | 0.296 | 0.177 | 0.784 | 0.579 | 24 | 0.179 | 0.492 | 0.841 | 0.621 |
| (a) alert active in (t, t+H] | 6 | same as now | 13584 | 0.502 | 0.293 | 0.708 | 0.598 | 21 | 0.000 | 0.502 | 1.000 | 0.668 |
| (a) alert active in (t, t+H] | 6 | same hour yesterday | 13584 | 0.502 | 0.217 | 0.783 | 0.512 | 21 | 1.000 | 0.788 | 0.776 | 0.782 |
| (a) alert active in (t, t+H] | 6 | train freq oblast x hour x weekday | 13584 | 0.502 | 0.138 | 0.913 | 0.599 | 21 | 0.349 | 0.807 | 0.884 | 0.843 |
| (b) new alert starts in (t, t+H] | 6 | same as now | 13584 | 0.430 | 0.365 | 0.596 | 0.489 | 24 | 0.000 | 0.430 | 1.000 | 0.601 |
| (b) new alert starts in (t, t+H] | 6 | same hour yesterday | 13584 | 0.430 | 0.267 | 0.726 | 0.516 | 24 | 1.000 | 0.693 | 0.680 | 0.686 |
| (b) new alert starts in (t, t+H] | 6 | train freq oblast x hour x weekday | 13584 | 0.430 | 0.178 | 0.830 | 0.611 | 24 | 0.284 | 0.680 | 0.883 | 0.768 |
