Test origins from 2026-08-07 00:00 UTC (last 30 days of official data); rows whose 7-day lookback or target window touches the outage are dropped. auc_within_oblast = mean of per-oblast AUCs (main number). Thresholds: max F1 on the last train week (model: validation fit; frequency: table without that week); 0/1 baselines are taken as is.

| target | H | predictor | n_test | base_rate | auc_within_oblast | n_oblasts_auc | brier | auc_pooled | threshold | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) new alert starts in (t, t+H] | 1 | LightGBM | 12672 | 0.120 | 0.696 | 24 | 0.087 | 0.826 | 0.187 | 0.342 | 0.552 | 0.422 |
| (b) new alert starts in (t, t+H] | 1 | same as now | 12672 | 0.120 | 0.443 | 24 | 0.281 | 0.487 | raw 0/1 | 0.106 | 0.182 | 0.134 |
| (b) new alert starts in (t, t+H] | 1 | same hour yesterday | 12672 | 0.120 | 0.516 | 24 | 0.178 | 0.570 | raw 0/1 | 0.247 | 0.240 | 0.243 |
| (b) new alert starts in (t, t+H] | 1 | train freq oblast x hour x weekday | 12672 | 0.120 | 0.500 | 24 | 0.100 | 0.740 | 0.075 | 0.208 | 0.790 | 0.329 |
| (b) new alert starts in (t, t+H] | 3 | LightGBM | 12624 | 0.290 | 0.651 | 24 | 0.143 | 0.844 | 0.243 | 0.532 | 0.839 | 0.651 |
| (b) new alert starts in (t, t+H] | 3 | same as now | 12624 | 0.290 | 0.485 | 24 | 0.319 | 0.570 | raw 0/1 | 0.430 | 0.304 | 0.356 |
| (b) new alert starts in (t, t+H] | 3 | same hour yesterday | 12624 | 0.290 | 0.515 | 24 | 0.280 | 0.656 | raw 0/1 | 0.517 | 0.504 | 0.510 |
| (b) new alert starts in (t, t+H] | 3 | train freq oblast x hour x weekday | 12624 | 0.290 | 0.602 | 24 | 0.174 | 0.787 | 0.176 | 0.485 | 0.842 | 0.615 |
| (b) new alert starts in (t, t+H] | 6 | LightGBM | 12552 | 0.421 | 0.644 | 24 | 0.141 | 0.878 | 0.314 | 0.661 | 0.903 | 0.763 |
| (b) new alert starts in (t, t+H] | 6 | same as now | 12552 | 0.421 | 0.491 | 24 | 0.358 | 0.597 | raw 0/1 | 0.653 | 0.318 | 0.427 |
| (b) new alert starts in (t, t+H] | 6 | same hour yesterday | 12552 | 0.421 | 0.508 | 24 | 0.273 | 0.718 | raw 0/1 | 0.679 | 0.666 | 0.672 |
| (b) new alert starts in (t, t+H] | 6 | train freq oblast x hour x weekday | 12552 | 0.421 | 0.629 | 24 | 0.176 | 0.831 | 0.278 | 0.668 | 0.888 | 0.762 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | LightGBM | 12672 | 0.303 | 0.831 | 24 | 0.068 | 0.951 | 0.392 | 0.933 | 0.753 | 0.833 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same as now | 12672 | 0.303 | 0.750 | 24 | 0.098 | 0.838 | raw 0/1 | 1.000 | 0.676 | 0.807 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | same hour yesterday | 12672 | 0.303 | 0.508 | 24 | 0.215 | 0.742 | raw 0/1 | 0.647 | 0.635 | 0.641 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 1 | train freq oblast x hour x weekday | 12672 | 0.303 | 0.569 | 24 | 0.146 | 0.887 | 0.251 | 0.685 | 0.713 | 0.699 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | LightGBM | 12624 | 0.406 | 0.745 | 23 | 0.099 | 0.935 | 0.317 | 0.751 | 0.881 | 0.811 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same as now | 12624 | 0.406 | 0.654 | 23 | 0.202 | 0.752 | raw 0/1 | 1.000 | 0.504 | 0.670 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | same hour yesterday | 12624 | 0.406 | 0.499 | 23 | 0.239 | 0.751 | raw 0/1 | 0.710 | 0.698 | 0.704 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 3 | train freq oblast x hour x weekday | 12624 | 0.406 | 0.573 | 23 | 0.149 | 0.896 | 0.247 | 0.689 | 0.878 | 0.772 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | LightGBM | 12552 | 0.492 | 0.704 | 21 | 0.104 | 0.935 | 0.314 | 0.772 | 0.928 | 0.843 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same as now | 12552 | 0.492 | 0.595 | 21 | 0.287 | 0.708 | raw 0/1 | 1.000 | 0.416 | 0.588 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | same hour yesterday | 12552 | 0.492 | 0.500 | 21 | 0.224 | 0.775 | raw 0/1 | 0.776 | 0.764 | 0.770 |
| (a) active in (t, t+H]  [model = active at t, else model(b)] | 6 | train freq oblast x hour x weekday | 12552 | 0.492 | 0.617 | 21 | 0.137 | 0.913 | 0.304 | 0.775 | 0.923 | 0.842 |
