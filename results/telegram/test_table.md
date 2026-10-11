Telegram experiment (merged into main as a documented result). Test origins: last 30 days of official data from 2026-08-07 UTC, minus rows whose [t-24h, t+H] touches the 2026-08-29..09-02 outage: 24 days (Aug 7-28, Sep 4-5), the same rows as main. All 2026 models train on the same 2026 rows; '+ Telegram' adds seven per-oblast columns from the Air Force channel posts (src/telegram_features.py): posts strictly before t, or before t-15min. Every row without '+ Telegram' reproduces results/test_table.csv exactly. auc_within_oblast = mean of per-oblast AUCs (main number). Thresholds: max F1 on the last train week; 0/1 baselines as is. By period: test_table_by_period.md.

| target | H | predictor | n_test | base_rate | auc_within_oblast | n_oblasts_auc | brier | auc_pooled | threshold | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) new alert starts in (t, t+H] | 1 | LightGBM full history (main) | 13824 | 0.121 | 0.688 | 24 | 0.087 | 0.826 | 0.187 | 0.345 | 0.573 | 0.431 |
| (b) new alert starts in (t, t+H] | 1 | LightGBM from 2026-01-01 | 13824 | 0.121 | 0.648 | 24 | 0.087 | 0.831 | 0.192 | 0.366 | 0.539 | 0.436 |
| (b) new alert starts in (t, t+H] | 1 | LightGBM from 2026-01-01 + Telegram (posts < t) | 13824 | 0.121 | 0.681 | 24 | 0.086 | 0.835 | 0.162 | 0.345 | 0.619 | 0.443 |
| (b) new alert starts in (t, t+H] | 1 | LightGBM from 2026-01-01 + Telegram (posts < t-15min) | 13824 | 0.121 | 0.614 | 24 | 0.086 | 0.833 | 0.193 | 0.371 | 0.548 | 0.442 |
| (b) new alert starts in (t, t+H] | 1 | same as now | 13824 | 0.121 | 0.438 | 24 | 0.288 | 0.480 | raw 0/1 | 0.101 | 0.174 | 0.128 |
| (b) new alert starts in (t, t+H] | 1 | same hour yesterday | 13824 | 0.121 | 0.525 | 24 | 0.181 | 0.571 | raw 0/1 | 0.248 | 0.244 | 0.246 |
| (b) new alert starts in (t, t+H] | 1 | train freq oblast x hour x weekday | 13824 | 0.121 | 0.495 | 24 | 0.101 | 0.736 | 0.075 | 0.209 | 0.785 | 0.330 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM full history (main) | 13728 | 0.296 | 0.645 | 24 | 0.145 | 0.844 | 0.243 | 0.538 | 0.843 | 0.656 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM from 2026-01-01 | 13728 | 0.296 | 0.642 | 24 | 0.142 | 0.848 | 0.242 | 0.545 | 0.842 | 0.661 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM from 2026-01-01 + Telegram (posts < t) | 13728 | 0.296 | 0.638 | 24 | 0.142 | 0.849 | 0.246 | 0.546 | 0.838 | 0.661 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM from 2026-01-01 + Telegram (posts < t-15min) | 13728 | 0.296 | 0.605 | 24 | 0.142 | 0.849 | 0.246 | 0.546 | 0.841 | 0.663 |
| (b) new alert starts in (t, t+H] | 3 | same as now | 13728 | 0.296 | 0.480 | 24 | 0.327 | 0.565 | raw 0/1 | 0.425 | 0.299 | 0.351 |
| (b) new alert starts in (t, t+H] | 3 | same hour yesterday | 13728 | 0.296 | 0.524 | 24 | 0.281 | 0.660 | raw 0/1 | 0.525 | 0.516 | 0.520 |
| (b) new alert starts in (t, t+H] | 3 | train freq oblast x hour x weekday | 13728 | 0.296 | 0.581 | 24 | 0.177 | 0.784 | 0.176 | 0.492 | 0.838 | 0.620 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM full history (main) | 13584 | 0.430 | 0.639 | 24 | 0.140 | 0.881 | 0.314 | 0.673 | 0.903 | 0.771 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM from 2026-01-01 | 13584 | 0.430 | 0.619 | 24 | 0.139 | 0.882 | 0.264 | 0.662 | 0.921 | 0.770 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM from 2026-01-01 + Telegram (posts < t) | 13584 | 0.430 | 0.631 | 24 | 0.138 | 0.883 | 0.306 | 0.678 | 0.900 | 0.773 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM from 2026-01-01 + Telegram (posts < t-15min) | 13584 | 0.430 | 0.623 | 24 | 0.139 | 0.882 | 0.267 | 0.664 | 0.917 | 0.770 |
| (b) new alert starts in (t, t+H] | 6 | same as now | 13584 | 0.430 | 0.489 | 24 | 0.365 | 0.596 | raw 0/1 | 0.657 | 0.318 | 0.429 |
| (b) new alert starts in (t, t+H] | 6 | same hour yesterday | 13584 | 0.430 | 0.516 | 24 | 0.267 | 0.726 | raw 0/1 | 0.693 | 0.680 | 0.686 |
| (b) new alert starts in (t, t+H] | 6 | train freq oblast x hour x weekday | 13584 | 0.430 | 0.612 | 24 | 0.178 | 0.830 | 0.278 | 0.679 | 0.885 | 0.769 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM full history (main) | 13824 | 0.309 | 0.825 | 24 | 0.069 | 0.951 | 0.392 | 0.927 | 0.754 | 0.831 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM from 2026-01-01 | 13824 | 0.309 | 0.804 | 24 | 0.068 | 0.952 | 0.339 | 0.886 | 0.781 | 0.830 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM from 2026-01-01 + Telegram (posts < t) | 13824 | 0.309 | 0.825 | 24 | 0.068 | 0.954 | 0.397 | 0.933 | 0.758 | 0.836 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM from 2026-01-01 + Telegram (posts < t-15min) | 13824 | 0.309 | 0.786 | 24 | 0.068 | 0.953 | 0.385 | 0.920 | 0.764 | 0.834 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same as now | 13824 | 0.309 | 0.753 | 24 | 0.100 | 0.838 | raw 0/1 | 1.000 | 0.675 | 0.806 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same hour yesterday | 13824 | 0.309 | 0.524 | 24 | 0.217 | 0.745 | raw 0/1 | 0.650 | 0.644 | 0.647 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | train freq oblast x hour x weekday | 13824 | 0.309 | 0.563 | 24 | 0.149 | 0.884 | 0.251 | 0.690 | 0.704 | 0.697 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM full history (main) | 13728 | 0.416 | 0.742 | 23 | 0.099 | 0.935 | 0.317 | 0.760 | 0.885 | 0.817 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM from 2026-01-01 | 13728 | 0.416 | 0.734 | 23 | 0.098 | 0.936 | 0.282 | 0.755 | 0.894 | 0.818 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM from 2026-01-01 + Telegram (posts < t) | 13728 | 0.416 | 0.732 | 23 | 0.098 | 0.937 | 0.277 | 0.754 | 0.901 | 0.821 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM from 2026-01-01 + Telegram (posts < t-15min) | 13728 | 0.416 | 0.704 | 23 | 0.098 | 0.936 | 0.316 | 0.778 | 0.880 | 0.825 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same as now | 13728 | 0.416 | 0.657 | 23 | 0.207 | 0.751 | raw 0/1 | 1.000 | 0.501 | 0.668 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same hour yesterday | 13728 | 0.416 | 0.513 | 23 | 0.234 | 0.758 | raw 0/1 | 0.721 | 0.712 | 0.716 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | train freq oblast x hour x weekday | 13728 | 0.416 | 0.561 | 23 | 0.152 | 0.895 | 0.247 | 0.700 | 0.874 | 0.777 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM full history (main) | 13584 | 0.502 | 0.701 | 21 | 0.102 | 0.937 | 0.314 | 0.784 | 0.928 | 0.850 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM from 2026-01-01 | 13584 | 0.502 | 0.678 | 21 | 0.102 | 0.937 | 0.245 | 0.765 | 0.942 | 0.845 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM from 2026-01-01 + Telegram (posts < t) | 13584 | 0.502 | 0.690 | 21 | 0.101 | 0.937 | 0.343 | 0.812 | 0.907 | 0.857 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM from 2026-01-01 + Telegram (posts < t-15min) | 13584 | 0.502 | 0.683 | 21 | 0.102 | 0.936 | 0.247 | 0.769 | 0.942 | 0.847 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same as now | 13584 | 0.502 | 0.598 | 21 | 0.293 | 0.708 | raw 0/1 | 1.000 | 0.416 | 0.587 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same hour yesterday | 13584 | 0.502 | 0.512 | 21 | 0.217 | 0.783 | raw 0/1 | 0.788 | 0.776 | 0.782 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | train freq oblast x hour x weekday | 13584 | 0.502 | 0.601 | 21 | 0.138 | 0.913 | 0.304 | 0.787 | 0.920 | 0.848 |
