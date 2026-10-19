# v2 against frozen v1 on the held-out window (2026-09-28 to 2026-10-17)

v2 = LightGBM trained on the combined official + API dataset (cut at 2026-10-18 00:00 UTC, no outage mask) with v1's features and hyperparameters, nothing tuned; split as in `PROCESS_LOG.md` (Round 16, written before any of these numbers existed): train to 2026-09-27 (windows closing by 09-28), validation fit to 09-20, validation week 09-21 to 09-27, test 09-28 to 10-17, **20 days**. **Frozen v1 was already scored on these days in the forward test** (`results/forward_api/`): its number here is not new information about v1. One period, one source (the API for these days): the intervals are wide. Target (b): a new alert starts in (t, t+H].

| H | predictor | n | base_rate | auc_within_oblast | oblasts_with_both_outcomes | brier | threshold | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | v2 LightGBM | 11520 | 0.196 | 0.692 | 23 | 0.127 | 0.252 | 0.459 | 0.608 | 0.523 |
| 1 | v2 + Platt (secondary) | 11520 | 0.196 | 0.692 | 23 | 0.127 | 0.263 | 0.459 | 0.608 | 0.523 |
| 1 | frozen v1 LightGBM | 11520 | 0.196 | 0.686 | 23 | 0.129 | 0.187 | 0.427 | 0.674 | 0.522 |
| 1 | logistic (refit on the v2 rows) | 11520 | 0.196 | 0.531 | 23 | 0.147 | 0.174 | 0.321 | 0.669 | 0.434 |
| 1 | same as now | 11520 | 0.196 | 0.400 | 23 | 0.421 | raw 0/1 | 0.133 | 0.208 | 0.162 |
| 1 | same hour yesterday | 11520 | 0.196 | 0.517 | 23 | 0.269 | raw 0/1 | 0.309 | 0.304 | 0.307 |
| 1 | train frequency | 11520 | 0.196 | 0.513 | 23 | 0.165 | 0.051 | 0.252 | 0.742 | 0.376 |
| 1 | rolling 4-week frequency | 11520 | 0.196 | 0.509 | 23 | 0.172 | 0.250 | 0.275 | 0.635 | 0.383 |
| 3 | v2 LightGBM | 11472 | 0.443 | 0.663 | 23 | 0.166 | 0.427 | 0.712 | 0.753 | 0.732 |
| 3 | v2 + Platt (secondary) | 11472 | 0.443 | 0.663 | 23 | 0.165 | 0.435 | 0.712 | 0.753 | 0.732 |
| 3 | frozen v1 LightGBM | 11472 | 0.443 | 0.660 | 23 | 0.170 | 0.243 | 0.637 | 0.897 | 0.745 |
| 3 | logistic (refit on the v2 rows) | 11472 | 0.443 | 0.547 | 23 | 0.187 | 0.355 | 0.676 | 0.776 | 0.723 |
| 3 | same as now | 11472 | 0.443 | 0.459 | 23 | 0.438 | raw 0/1 | 0.508 | 0.352 | 0.416 |
| 3 | same hour yesterday | 11472 | 0.443 | 0.541 | 23 | 0.316 | raw 0/1 | 0.646 | 0.635 | 0.640 |
| 3 | train frequency | 11472 | 0.443 | 0.516 | 23 | 0.278 | 0.119 | 0.553 | 0.787 | 0.649 |
| 3 | rolling 4-week frequency | 11472 | 0.443 | 0.521 | 23 | 0.225 | 0.250 | 0.564 | 0.883 | 0.689 |
| 6 | v2 LightGBM | 11400 | 0.595 | 0.664 | 23 | 0.131 | 0.427 | 0.830 | 0.879 | 0.854 |
| 6 | v2 + Platt (secondary) | 11400 | 0.595 | 0.664 | 23 | 0.131 | 0.407 | 0.830 | 0.879 | 0.854 |
| 6 | frozen v1 LightGBM | 11400 | 0.595 | 0.654 | 23 | 0.135 | 0.314 | 0.775 | 0.931 | 0.846 |
| 6 | logistic (refit on the v2 rows) | 11400 | 0.595 | 0.569 | 23 | 0.144 | 0.371 | 0.797 | 0.877 | 0.835 |
| 6 | same as now | 11400 | 0.595 | 0.478 | 23 | 0.443 | raw 0/1 | 0.748 | 0.385 | 0.509 |
| 6 | same hour yesterday | 11400 | 0.595 | 0.543 | 23 | 0.238 | raw 0/1 | 0.804 | 0.793 | 0.798 |
| 6 | train frequency | 11400 | 0.595 | 0.507 | 23 | 0.271 | 0.171 | 0.723 | 0.843 | 0.779 |
| 6 | rolling 4-week frequency | 11400 | 0.595 | 0.502 | 23 | 0.187 | 0.500 | 0.784 | 0.838 | 0.810 |

Thresholds: max F1 on the validation week (v2, Platt, logistic, rolling 4-week frequency: from the validation fit; train frequency: from the table fitted without the validation week); frozen v1: its own frozen threshold; 'raw 0/1': the baseline as is.
