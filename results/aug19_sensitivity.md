# Side note: the old test with the Aug 19-20 wave put back

`results/api_check.md` found a wave on Aug 19-20 (from about 20:52 UTC) that the Ukraine Alarm API has and our official data does not: alerts in all raions of Chernihivska oblast and in 7 raions of Kyivska oblast for about 10-13 hours. This is a sensitivity check, not a correction: `data/raw` and the old test (`results/test_table.md`) are unchanged.

## What was done
- A patched copy of the official rows, in a temporary folder only: the API's 18 raion rows of Chernihivska oblast, Kyivska oblast starting between 2026-08-19 19:00 and 2026-08-20 12:00 UTC added. That changes 25 oblast-hours from quiet to under alert (Chernihivska oblast: 14, Kyivska oblast: 11).
- The unmodified `scripts/evaluate.py` was run on the copy: the same training rows (all before 2026-08-07, so the same fitted models and thresholds), the same 24 test days and rows; only alerts, targets (b) and the features that depend on them change on the test rows (and on the same-as-now and same-hour-yesterday baselines).

## Target (b), all 24 test days: within-oblast AUC and Brier, old test against the patched copy

| H | predictor | AUC old | AUC patched | AUC change | Brier old | Brier patched | Brier change |
|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.6879 | 0.6910 | 0.0031 | 0.0875 | 0.0875 | 0.0000 |
| 1 | logistic | 0.4864 | 0.4862 | -0.0002 | 0.0971 | 0.0972 | 0.0001 |
| 1 | same as now | 0.4378 | 0.4367 | -0.0011 | 0.2879 | 0.2897 | 0.0018 |
| 1 | same hour yesterday | 0.5249 | 0.5246 | -0.0003 | 0.1814 | 0.1820 | 0.0006 |
| 1 | train frequency | 0.4952 | 0.4952 | 0.0000 | 0.1014 | 0.1016 | 0.0002 |
| 3 | LightGBM | 0.6451 | 0.6465 | 0.0014 | 0.1446 | 0.1446 | 0.0000 |
| 3 | logistic | 0.4826 | 0.4823 | -0.0003 | 0.1535 | 0.1537 | 0.0002 |
| 3 | same as now | 0.4804 | 0.4792 | -0.0012 | 0.3271 | 0.3287 | 0.0016 |
| 3 | same hour yesterday | 0.5235 | 0.5222 | -0.0013 | 0.2815 | 0.2829 | 0.0014 |
| 3 | train frequency | 0.5810 | 0.5816 | 0.0006 | 0.1773 | 0.1777 | 0.0004 |
| 6 | LightGBM | 0.6394 | 0.6396 | 0.0002 | 0.1398 | 0.1396 | -0.0002 |
| 6 | logistic | 0.5077 | 0.5074 | -0.0003 | 0.1461 | 0.1461 | 0.0000 |
| 6 | same as now | 0.4893 | 0.4876 | -0.0017 | 0.3647 | 0.3659 | 0.0012 |
| 6 | same hour yesterday | 0.5158 | 0.5134 | -0.0024 | 0.2674 | 0.2687 | 0.0013 |
| 6 | train frequency | 0.6125 | 0.6131 | 0.0006 | 0.1777 | 0.1780 | 0.0003 |

Base rate of a new alert starting in (t, t+H]: H=1: 0.1214 -> 0.1217; H=3: 0.2957 -> 0.2965; H=6: 0.4300 -> 0.4312.

Reading it: the table is the whole effect; no conclusion beyond the numbers is drawn here. Source of the added alerts: the API (one source; the official feed is the one being patched), so the patched copy is a mix of the two.
