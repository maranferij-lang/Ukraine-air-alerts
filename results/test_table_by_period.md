Every predictor on all 24 test days, on Aug 7-28 only and on Sep 4-5 only (same thresholds). On Sep 4-5 the 7-day features are computed over the observed part of their window. Sep 4-5 is 48 origins per oblast: within-oblast AUC there covers only oblasts with both outcomes and is very noisy.

| target | H | predictor | period | n_test | base_rate | auc_within_oblast | n_oblasts_auc | brier | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) new alert starts in (t, t+H] | 1 | LightGBM | all 24 test days | 13824 | 0.121 | 0.688 | 24 | 0.087 | 0.345 | 0.573 | 0.431 |
| (b) new alert starts in (t, t+H] | 1 | LightGBM | Aug 7-28 (7-day lookback complete) | 12672 | 0.120 | 0.696 | 24 | 0.087 | 0.342 | 0.552 | 0.422 |
| (b) new alert starts in (t, t+H] | 1 | LightGBM | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.141 | 0.534 | 20 | 0.098 | 0.370 | 0.767 | 0.499 |
| (b) new alert starts in (t, t+H] | 1 | LightGBM from 2026-01-01 | all 24 test days | 13824 | 0.121 | 0.648 | 24 | 0.087 | 0.366 | 0.539 | 0.436 |
| (b) new alert starts in (t, t+H] | 1 | LightGBM from 2026-01-01 | Aug 7-28 (7-day lookback complete) | 12672 | 0.120 | 0.652 | 24 | 0.086 | 0.365 | 0.519 | 0.428 |
| (b) new alert starts in (t, t+H] | 1 | LightGBM from 2026-01-01 | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.141 | 0.555 | 20 | 0.096 | 0.377 | 0.724 | 0.496 |
| (b) new alert starts in (t, t+H] | 1 | logistic (starts_7d + hour + oblast) | all 24 test days | 13824 | 0.121 | 0.486 | 24 | 0.097 | 0.255 | 0.606 | 0.359 |
| (b) new alert starts in (t, t+H] | 1 | logistic (starts_7d + hour + oblast) | Aug 7-28 (7-day lookback complete) | 12672 | 0.120 | 0.480 | 24 | 0.095 | 0.257 | 0.587 | 0.358 |
| (b) new alert starts in (t, t+H] | 1 | logistic (starts_7d + hour + oblast) | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.141 | 0.419 | 20 | 0.114 | 0.241 | 0.785 | 0.368 |
| (b) new alert starts in (t, t+H] | 1 | same as now | all 24 test days | 13824 | 0.121 | 0.438 | 24 | 0.288 | 0.101 | 0.174 | 0.128 |
| (b) new alert starts in (t, t+H] | 1 | same as now | Aug 7-28 (7-day lookback complete) | 12672 | 0.120 | 0.443 | 24 | 0.281 | 0.106 | 0.182 | 0.134 |
| (b) new alert starts in (t, t+H] | 1 | same as now | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.141 | 0.359 | 20 | 0.365 | 0.058 | 0.104 | 0.075 |
| (b) new alert starts in (t, t+H] | 1 | same hour yesterday | all 24 test days | 13824 | 0.121 | 0.525 | 24 | 0.181 | 0.248 | 0.244 | 0.246 |
| (b) new alert starts in (t, t+H] | 1 | same hour yesterday | Aug 7-28 (7-day lookback complete) | 12672 | 0.120 | 0.516 | 24 | 0.178 | 0.247 | 0.240 | 0.243 |
| (b) new alert starts in (t, t+H] | 1 | same hour yesterday | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.141 | 0.538 | 20 | 0.218 | 0.258 | 0.288 | 0.272 |
| (b) new alert starts in (t, t+H] | 1 | train freq oblast x hour x weekday | all 24 test days | 13824 | 0.121 | 0.495 | 24 | 0.101 | 0.209 | 0.785 | 0.330 |
| (b) new alert starts in (t, t+H] | 1 | train freq oblast x hour x weekday | Aug 7-28 (7-day lookback complete) | 12672 | 0.120 | 0.500 | 24 | 0.100 | 0.208 | 0.790 | 0.329 |
| (b) new alert starts in (t, t+H] | 1 | train freq oblast x hour x weekday | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.141 | 0.466 | 20 | 0.119 | 0.222 | 0.742 | 0.341 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM | all 24 test days | 13728 | 0.296 | 0.645 | 24 | 0.145 | 0.538 | 0.843 | 0.656 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM | Aug 7-28 (7-day lookback complete) | 12624 | 0.290 | 0.651 | 24 | 0.143 | 0.532 | 0.839 | 0.651 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.365 | 0.476 | 20 | 0.158 | 0.596 | 0.878 | 0.710 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM from 2026-01-01 | all 24 test days | 13728 | 0.296 | 0.642 | 24 | 0.142 | 0.545 | 0.842 | 0.661 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM from 2026-01-01 | Aug 7-28 (7-day lookback complete) | 12624 | 0.290 | 0.651 | 24 | 0.141 | 0.538 | 0.837 | 0.655 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM from 2026-01-01 | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.365 | 0.471 | 20 | 0.159 | 0.611 | 0.886 | 0.723 |
| (b) new alert starts in (t, t+H] | 3 | logistic (starts_7d + hour + oblast) | all 24 test days | 13728 | 0.296 | 0.483 | 24 | 0.154 | 0.563 | 0.722 | 0.633 |
| (b) new alert starts in (t, t+H] | 3 | logistic (starts_7d + hour + oblast) | Aug 7-28 (7-day lookback complete) | 12624 | 0.290 | 0.478 | 24 | 0.152 | 0.557 | 0.709 | 0.624 |
| (b) new alert starts in (t, t+H] | 3 | logistic (starts_7d + hour + oblast) | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.365 | 0.361 | 20 | 0.170 | 0.612 | 0.846 | 0.710 |
| (b) new alert starts in (t, t+H] | 3 | same as now | all 24 test days | 13728 | 0.296 | 0.480 | 24 | 0.327 | 0.425 | 0.299 | 0.351 |
| (b) new alert starts in (t, t+H] | 3 | same as now | Aug 7-28 (7-day lookback complete) | 12624 | 0.290 | 0.485 | 24 | 0.319 | 0.430 | 0.304 | 0.356 |
| (b) new alert starts in (t, t+H] | 3 | same as now | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.365 | 0.395 | 20 | 0.425 | 0.380 | 0.261 | 0.309 |
| (b) new alert starts in (t, t+H] | 3 | same hour yesterday | all 24 test days | 13728 | 0.296 | 0.524 | 24 | 0.281 | 0.525 | 0.516 | 0.520 |
| (b) new alert starts in (t, t+H] | 3 | same hour yesterday | Aug 7-28 (7-day lookback complete) | 12624 | 0.290 | 0.515 | 24 | 0.280 | 0.517 | 0.504 | 0.510 |
| (b) new alert starts in (t, t+H] | 3 | same hour yesterday | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.365 | 0.519 | 20 | 0.297 | 0.587 | 0.625 | 0.606 |
| (b) new alert starts in (t, t+H] | 3 | train freq oblast x hour x weekday | all 24 test days | 13728 | 0.296 | 0.581 | 24 | 0.177 | 0.492 | 0.838 | 0.620 |
| (b) new alert starts in (t, t+H] | 3 | train freq oblast x hour x weekday | Aug 7-28 (7-day lookback complete) | 12624 | 0.290 | 0.602 | 24 | 0.174 | 0.485 | 0.842 | 0.615 |
| (b) new alert starts in (t, t+H] | 3 | train freq oblast x hour x weekday | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.365 | 0.424 | 20 | 0.218 | 0.568 | 0.806 | 0.667 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM | all 24 test days | 13584 | 0.430 | 0.639 | 24 | 0.140 | 0.673 | 0.903 | 0.771 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM | Aug 7-28 (7-day lookback complete) | 12552 | 0.421 | 0.644 | 24 | 0.141 | 0.661 | 0.903 | 0.763 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.543 | 0.447 | 20 | 0.120 | 0.812 | 0.904 | 0.855 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM from 2026-01-01 | all 24 test days | 13584 | 0.430 | 0.619 | 24 | 0.139 | 0.662 | 0.921 | 0.770 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM from 2026-01-01 | Aug 7-28 (7-day lookback complete) | 12552 | 0.421 | 0.621 | 24 | 0.140 | 0.650 | 0.922 | 0.762 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM from 2026-01-01 | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.543 | 0.440 | 20 | 0.122 | 0.799 | 0.909 | 0.850 |
| (b) new alert starts in (t, t+H] | 6 | logistic (starts_7d + hour + oblast) | all 24 test days | 13584 | 0.430 | 0.508 | 24 | 0.146 | 0.657 | 0.905 | 0.761 |
| (b) new alert starts in (t, t+H] | 6 | logistic (starts_7d + hour + oblast) | Aug 7-28 (7-day lookback complete) | 12552 | 0.421 | 0.498 | 24 | 0.148 | 0.643 | 0.905 | 0.752 |
| (b) new alert starts in (t, t+H] | 6 | logistic (starts_7d + hour + oblast) | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.543 | 0.325 | 20 | 0.121 | 0.814 | 0.905 | 0.857 |
| (b) new alert starts in (t, t+H] | 6 | same as now | all 24 test days | 13584 | 0.430 | 0.489 | 24 | 0.365 | 0.657 | 0.318 | 0.429 |
| (b) new alert starts in (t, t+H] | 6 | same as now | Aug 7-28 (7-day lookback complete) | 12552 | 0.421 | 0.491 | 24 | 0.358 | 0.653 | 0.318 | 0.427 |
| (b) new alert starts in (t, t+H] | 6 | same as now | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.543 | 0.392 | 20 | 0.444 | 0.695 | 0.325 | 0.443 |
| (b) new alert starts in (t, t+H] | 6 | same hour yesterday | all 24 test days | 13584 | 0.430 | 0.516 | 24 | 0.267 | 0.693 | 0.680 | 0.686 |
| (b) new alert starts in (t, t+H] | 6 | same hour yesterday | Aug 7-28 (7-day lookback complete) | 12552 | 0.421 | 0.508 | 24 | 0.273 | 0.679 | 0.666 | 0.672 |
| (b) new alert starts in (t, t+H] | 6 | same hour yesterday | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.543 | 0.501 | 20 | 0.196 | 0.825 | 0.811 | 0.818 |
| (b) new alert starts in (t, t+H] | 6 | train freq oblast x hour x weekday | all 24 test days | 13584 | 0.430 | 0.612 | 24 | 0.178 | 0.679 | 0.885 | 0.769 |
| (b) new alert starts in (t, t+H] | 6 | train freq oblast x hour x weekday | Aug 7-28 (7-day lookback complete) | 12552 | 0.421 | 0.629 | 24 | 0.176 | 0.668 | 0.888 | 0.762 |
| (b) new alert starts in (t, t+H] | 6 | train freq oblast x hour x weekday | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.543 | 0.409 | 20 | 0.203 | 0.812 | 0.859 | 0.835 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM | all 24 test days | 13824 | 0.309 | 0.825 | 24 | 0.069 | 0.927 | 0.754 | 0.831 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM | Aug 7-28 (7-day lookback complete) | 12672 | 0.303 | 0.831 | 24 | 0.068 | 0.933 | 0.753 | 0.833 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.380 | 0.699 | 19 | 0.083 | 0.872 | 0.765 | 0.815 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM from 2026-01-01 | all 24 test days | 13824 | 0.309 | 0.804 | 24 | 0.068 | 0.886 | 0.781 | 0.830 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM from 2026-01-01 | Aug 7-28 (7-day lookback complete) | 12672 | 0.303 | 0.807 | 24 | 0.067 | 0.892 | 0.779 | 0.832 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM from 2026-01-01 | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.380 | 0.715 | 19 | 0.082 | 0.835 | 0.797 | 0.815 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | logistic (starts_7d + hour + oblast) | all 24 test days | 13824 | 0.309 | 0.742 | 24 | 0.076 | 0.889 | 0.753 | 0.816 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | logistic (starts_7d + hour + oblast) | Aug 7-28 (7-day lookback complete) | 12672 | 0.303 | 0.733 | 24 | 0.074 | 0.892 | 0.751 | 0.815 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | logistic (starts_7d + hour + oblast) | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.380 | 0.729 | 19 | 0.089 | 0.865 | 0.776 | 0.818 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same as now | all 24 test days | 13824 | 0.309 | 0.753 | 24 | 0.100 | 1.000 | 0.675 | 0.806 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same as now | Aug 7-28 (7-day lookback complete) | 12672 | 0.303 | 0.750 | 24 | 0.098 | 1.000 | 0.676 | 0.807 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same as now | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.380 | 0.770 | 19 | 0.127 | 1.000 | 0.667 | 0.800 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same hour yesterday | all 24 test days | 13824 | 0.309 | 0.524 | 24 | 0.217 | 0.650 | 0.644 | 0.647 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same hour yesterday | Aug 7-28 (7-day lookback complete) | 12672 | 0.303 | 0.508 | 24 | 0.215 | 0.647 | 0.635 | 0.641 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same hour yesterday | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.380 | 0.543 | 19 | 0.236 | 0.676 | 0.728 | 0.701 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | train freq oblast x hour x weekday | all 24 test days | 13824 | 0.309 | 0.563 | 24 | 0.149 | 0.690 | 0.704 | 0.697 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | train freq oblast x hour x weekday | Aug 7-28 (7-day lookback complete) | 12672 | 0.303 | 0.569 | 24 | 0.146 | 0.685 | 0.713 | 0.699 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | train freq oblast x hour x weekday | Sep 4-5 (7-day lookback partly in the outage) | 1152 | 0.380 | 0.474 | 19 | 0.192 | 0.749 | 0.626 | 0.682 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM | all 24 test days | 13728 | 0.416 | 0.742 | 23 | 0.099 | 0.760 | 0.885 | 0.817 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM | Aug 7-28 (7-day lookback complete) | 12624 | 0.406 | 0.745 | 23 | 0.099 | 0.751 | 0.881 | 0.811 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.520 | 0.525 | 17 | 0.100 | 0.845 | 0.920 | 0.881 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM from 2026-01-01 | all 24 test days | 13728 | 0.416 | 0.734 | 23 | 0.098 | 0.755 | 0.894 | 0.818 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM from 2026-01-01 | Aug 7-28 (7-day lookback complete) | 12624 | 0.406 | 0.741 | 23 | 0.098 | 0.745 | 0.891 | 0.811 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM from 2026-01-01 | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.520 | 0.514 | 17 | 0.102 | 0.850 | 0.922 | 0.885 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | logistic (starts_7d + hour + oblast) | all 24 test days | 13728 | 0.416 | 0.635 | 23 | 0.106 | 0.778 | 0.853 | 0.813 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | logistic (starts_7d + hour + oblast) | Aug 7-28 (7-day lookback complete) | 12624 | 0.406 | 0.626 | 23 | 0.106 | 0.768 | 0.847 | 0.806 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | logistic (starts_7d + hour + oblast) | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.520 | 0.552 | 17 | 0.102 | 0.862 | 0.906 | 0.884 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same as now | all 24 test days | 13728 | 0.416 | 0.657 | 23 | 0.207 | 1.000 | 0.501 | 0.668 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same as now | Aug 7-28 (7-day lookback complete) | 12624 | 0.406 | 0.654 | 23 | 0.202 | 1.000 | 0.504 | 0.670 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same as now | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.520 | 0.661 | 17 | 0.270 | 1.000 | 0.481 | 0.649 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same hour yesterday | all 24 test days | 13728 | 0.416 | 0.513 | 23 | 0.234 | 0.721 | 0.712 | 0.716 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same hour yesterday | Aug 7-28 (7-day lookback complete) | 12624 | 0.406 | 0.499 | 23 | 0.239 | 0.710 | 0.698 | 0.704 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same hour yesterday | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.520 | 0.510 | 17 | 0.183 | 0.814 | 0.840 | 0.827 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | train freq oblast x hour x weekday | all 24 test days | 13728 | 0.416 | 0.561 | 23 | 0.152 | 0.700 | 0.874 | 0.777 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | train freq oblast x hour x weekday | Aug 7-28 (7-day lookback complete) | 12624 | 0.406 | 0.573 | 23 | 0.149 | 0.689 | 0.878 | 0.772 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | train freq oblast x hour x weekday | Sep 4-5 (7-day lookback partly in the outage) | 1104 | 0.520 | 0.447 | 17 | 0.190 | 0.828 | 0.838 | 0.833 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM | all 24 test days | 13584 | 0.502 | 0.701 | 21 | 0.102 | 0.784 | 0.928 | 0.850 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM | Aug 7-28 (7-day lookback complete) | 12552 | 0.492 | 0.704 | 21 | 0.104 | 0.772 | 0.928 | 0.843 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.620 | 0.412 | 14 | 0.079 | 0.915 | 0.925 | 0.920 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM from 2026-01-01 | all 24 test days | 13584 | 0.502 | 0.678 | 21 | 0.102 | 0.765 | 0.942 | 0.845 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM from 2026-01-01 | Aug 7-28 (7-day lookback complete) | 12552 | 0.492 | 0.679 | 21 | 0.103 | 0.755 | 0.944 | 0.839 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM from 2026-01-01 | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.620 | 0.437 | 14 | 0.083 | 0.887 | 0.930 | 0.908 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | logistic (starts_7d + hour + oblast) | all 24 test days | 13584 | 0.502 | 0.601 | 21 | 0.106 | 0.773 | 0.922 | 0.841 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | logistic (starts_7d + hour + oblast) | Aug 7-28 (7-day lookback complete) | 12552 | 0.492 | 0.587 | 21 | 0.109 | 0.761 | 0.923 | 0.834 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | logistic (starts_7d + hour + oblast) | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.620 | 0.420 | 14 | 0.079 | 0.926 | 0.917 | 0.922 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same as now | all 24 test days | 13584 | 0.502 | 0.598 | 21 | 0.293 | 1.000 | 0.416 | 0.587 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same as now | Aug 7-28 (7-day lookback complete) | 12552 | 0.492 | 0.595 | 21 | 0.287 | 1.000 | 0.416 | 0.588 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same as now | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.620 | 0.612 | 14 | 0.366 | 1.000 | 0.409 | 0.581 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same hour yesterday | all 24 test days | 13584 | 0.502 | 0.512 | 21 | 0.217 | 0.788 | 0.776 | 0.782 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same hour yesterday | Aug 7-28 (7-day lookback complete) | 12552 | 0.492 | 0.500 | 21 | 0.224 | 0.776 | 0.764 | 0.770 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same hour yesterday | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.620 | 0.517 | 14 | 0.126 | 0.903 | 0.892 | 0.898 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | train freq oblast x hour x weekday | all 24 test days | 13584 | 0.502 | 0.601 | 21 | 0.138 | 0.787 | 0.920 | 0.848 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | train freq oblast x hour x weekday | Aug 7-28 (7-day lookback complete) | 12552 | 0.492 | 0.617 | 21 | 0.137 | 0.775 | 0.923 | 0.842 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | train freq oblast x hour x weekday | Sep 4-5 (7-day lookback partly in the outage) | 1032 | 0.620 | 0.373 | 14 | 0.156 | 0.933 | 0.891 | 0.911 |
