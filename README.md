# Ukraine air-raid alerts: short-horizon forecasting by oblast

**Question.** At hour t, using only what is known at t: will there be an air-raid alert in
oblast X in the next H hours, for H = 1, 3, 6? The answer is yes/no plus a probability.
One model covers all oblasts, with oblast as a feature.

Ground rules (fixed):
- No leakage. Every aggregate is computed on the training period only. Splits are
  chronological, never random.
- Every model number is shown next to three baselines. If the model doesn't beat them, we say so.
- Metrics: Brier, **ROC-AUC within oblast** (main number), precision/recall at a threshold. No
  plain accuracy.
- Working rules for this repo are in `CLAUDE.md`.

**Status:** round 4. LightGBM for target (b), checked against a plain logistic regression and a
post-switch-only fit, next to the three baselines.
`PROCESS_LOG.md` has every step; results are in `results/`.

## Data

[Vadimkin/ukrainian-air-raid-sirens-dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset)
has two feeds, official and volunteer. Times are UTC.
- The snapshot is committed in `data/raw/`.
- `data/raw/PULL_INFO.md` records the pull: 2026-10-10 08:27 UTC, upstream commit `7ccd436`.
- We use the **official** feed. The volunteer feed is not reliable after mid-2025 (see below).
- Hourly agreement between the volunteer and official feeds (Cohen's κ on "under alert") falls
  from 0.985 in 2022Q3 to 0.448 in 2026Q3. The Lviv/Volyn parser bug described below accounts
  for about 0.025 of that drop. The rest is unexplained.

Known problems, handled in `src/load.py`:
- The official feed ends 2026-09-07 ~05:40 UTC.
- No official messages 2026-08-29 → 2026-09-02. These hours are masked.
- 38% of official rows are upstream duplicates. They are dropped.
- The last day of each file is incomplete, because alerts still open at the pull are missing. It is cut.

### Evaluation window: the most recent trustworthy data
The test period is the **last 30 full days of official data: 2026-08-07 00:00 → 2026-09-05 23:00
UTC**. Usable test days: **24**, i.e. Aug 7–28 and Sep 4–5. The same rows are used for every
predictor.
- Rows whose [t−24h, t+H] touches the 2026-08-29 → 09-02 outage are dropped. That removes
  Aug 29 – Sep 3.
- Sep 3 is dropped because the same-hour-yesterday baseline would point into the outage. One
  day was judged less important than scoring all predictors on identical rows.
- On Sep 4–5, the 7-day features reach back into the outage. They are computed over the observed
  part of their window: shares over observed time, counts scaled up to 7 days.
- Every number is also reported for Aug 7–28 and Sep 4–5 separately
  (`results/test_table_by_period.md`).

Why it ends a month before the pull date:
- The official feed stopped upstream on 2026-09-07.
- The only feed covering September (volunteer) mislabels oblasts after mid-2025 (next section).
- So the most recent data we can trust ends 2026-09-05.

We re-pull on Sunday with `scripts/fetch_data.py`.
- The window is anchored to the end of the official data. If upstream has fixed the feed, the
  test month moves forward on its own.
- A backfill is exactly when duplicates and outages tend to appear. So after re-pulling, re-run
  `scripts/inspect_raw.py` and re-check the outage list before trusting the new window.

### What "under alert" means for western oblasts after mid-2025
Between Jul and Dec 2025 the official system moved from whole-oblast alerts to raion-level
alerts. Alerts are now declared for the raions in a threat's path, and western oblasts rarely
are. Lviv was under alert about 5% of hours in 2024, and **0.9% in the last 90 days** of our data.

This is a change in what the official system declares, not a bug in our data. Any number for a
western oblast after mid-2025 means "the oblast's raions were declared under alert", which
happens much less often than it used to.

Two things that are *not* the reason:
- **Our half-of-raions rule.** Western raion alerts arrive as near-whole-oblast lists, so the
  "any raion" rule also gives Lviv 0.9%.
- **A competing definition in the volunteer feed.** Volunteer data has Lviv under alert 25% of
  the same period, but those alerts are mislabelled:
  - 82% of its 2026 "Lviv" alerts start within 3 minutes of an official alert in a "-Podilskyi"
    raion of *another* oblast, mostly Odesa's Podilskyi raion. Its parser maps the keyword
    "Подільський" to Lviv.
  - Volyn has the same problem: 85% of its alerts match Chernihiv's Prylutskyi raion, because
    "Прилуцький" contains "Луцьк".
  - So don't compare our western numbers with volunteer ones.

## Targets, baselines, evaluation (`scripts/evaluate.py`)
For each oblast and forecast origin t (an instant on the hour, UTC) and H ∈ {1, 3, 6}:
- `(a)` an alert is active at some moment in (t, t+H];
- `(b)` a new alert episode starts in (t, t+H].

Both use only what happens after t. They are computed exactly from episode start/end times
(`src/targets.py`), not from hour buckets.

Note: **(a) = "active at t" OR (b)**. An alert running at t keeps running just after t. If
nothing runs at t, anything overlapping the window must start inside it.
- This is exact when "active at t" is read from joined episodes.
- We read it from un-joined episodes (no peeking at a restart that hasn't happened yet). That
  breaks the identity for origins that fall inside a joined restart gap: 3 test rows at H=1.

So we model (b) and report (a) as **"1 if active at t, else model(b)"**.

Baselines (`src/baselines.py`):

| baseline | score for origin t | known at t because |
|---|---|---|
| same as now (persistence) | 1 if an alert is active at t, else 0 (same score for (a) and (b)); precision/recall of the raw 0/1 | it is the current state |
| same hour yesterday | the target's outcome for origin t−24h, i.e. window (t−24h, t−24h+H]; precision/recall of the raw 0/1 | that window closed by t−18h |
| train frequency | share of positives in training rows with the same oblast × Kyiv-local hour × weekday | fitted only on rows whose window closed before the test month |

Protocol:
- Walk-forward over the test month: every score for origin t uses only what is known at t.
- `scripts/check_no_peeking.py` rebuilds the inputs from data truncated at t and requires an
  exact match: the baseline inputs and the full model feature matrix, at 40 test origins. Two
  negative controls show the check does catch future information.
- Train = full history (2022-03-16 onward), up to the test month.
- Thresholds (model and train frequency only) maximise F1 on the **last week of train**, then
  are frozen for test. The 0/1 baselines get no threshold search.
- The model and all three baselines are scored on the same rows. Each target's base rate is in
  the table; per-oblast base rates are in `results/base_rates_by_oblast.md`.

## Model (`scripts/evaluate.py`, `src/features.py`)
One LightGBM for all 24 units and target (b), one model per H, oblast as a categorical feature.
Two comparison fits use the same split and threshold rule:
- the same LightGBM trained only on rows from 2026-01-01;
- a plain logistic regression (`src/logit.py`) on starts_7d, 24 hour-of-day dummies and oblast
  dummies.

Features, all known at t:
- **Own state:** active at t; hours since the current alert started (0 if quiet); hours since
  the last alert ended (capped at 30 days). These use episodes before restarts are joined.
- **Own history:**
  - share of time under alert in the last 6h, 24h, 7d;
  - alert starts in the last 24h and 7d.
- **Neighbours (last completed hour):**
  - share of neighbouring oblasts under alert at any point in [t−1h, t);
  - their alert starts in [t−6h, t).
  - Neighbours come from `data/neighbours.csv`, a hand-written table of land borders.
- **Calendar:** hour of day and weekday, Kyiv time.
- **Recent rate (`freq4w`):** target (b) for the same oblast and hour, 1, 2, 3 and 4 weeks
  before t, averaged. This is a rolling version of the frequency table, so it means the same
  thing in train and test.

Fitting:
- A validation fit on train minus the last week picks the number of trees (early stopping)
  and the F1 threshold on that week.
- The test model is then fit on all of train with that many trees.
- Known approximation: the threshold comes from the validation fit, a slightly different model
  than the one scored on test. The frequency baseline's threshold has the same approximation
  (it comes from a table fitted without the last week).

Test rows (24 days), target (b). Within-oblast AUC (higher is better) / Brier (lower is better):

| H | base rate | LightGBM | LightGBM from 2026-01-01 | logistic: starts_7d + hour + oblast | same as now | same hour yesterday | train frequency |
|---|---|---|---|---|---|---|---|
| 1 | 0.121 | **0.688** / 0.087 | 0.648 / 0.087 | 0.486 / 0.097 | 0.438 / 0.288 | 0.525 / 0.181 | 0.495 / 0.101 |
| 3 | 0.296 | **0.645** / 0.145 | 0.642 / 0.142 | 0.483 / 0.154 | 0.480 / 0.327 | 0.524 / 0.281 | 0.581 / 0.177 |
| 6 | 0.430 | **0.639** / 0.140 | 0.619 / 0.139 | 0.508 / 0.146 | 0.489 / 0.365 | 0.516 / 0.267 | 0.612 / 0.178 |

How to read it:
- **LightGBM earns its keep on ranking.** A logistic regression on starts_7d, hour of day and
  oblast gets within 0.006–0.010 of LightGBM's Brier, but its within-oblast AUC is near 0.5
  (0.48–0.51). LightGBM beats it in 24 / 23 / 22 of 24 oblasts.
- So "how busy was this oblast this week" sets the level, which drives most of the Brier. The
  ranking within an oblast comes from the other features.
- **H=1:** LightGBM beats the frequency baseline's within-oblast AUC in 24 of 24 oblasts.
- **H=6: not established.** On the 22-day window LightGBM beat the frequency baseline in 13 of 24
  oblasts. Adding two days (Sep 4–5) moves that to 18 of 24 with the same model. A count that
  moves by five on two extra days is not evidence either way.
- **Training from 2026-01-01 instead of full history:** about the same Brier (slightly better),
  lower mean within-oblast AUC at H=1 and H=6. Per oblast it wins 13 / 15 / 13 of 24. Neither
  helps nor hurts clearly.
- **Calibration:** LightGBM's probabilities are well calibrated overall (`results/calibration.md`,
  `figures/reliability_h6.png`). Its lowest H=6 bin (predicted < 0.1) is entirely the eight
  western oblasts. In the five furthest west the model predicts about 0.06–0.07 where 0.01–0.03
  happened (`results/lowest_bin_h6.md`).
- **Sep 4–5 alone:** every predictor has lower within-oblast AUC there, including the frequency
  baseline, which uses no lookback features. At H=6, LightGBM's 0.447 is inside the range of
  August's 2-day windows (0.42–0.65). At H=1, its 0.534 is below all of them (0.58–0.73), while
  still above the frequency baseline. LightGBM under-predicts H=6 on those two days (0.50 vs
  0.54 observed). Two days can't tell whether the 7-day scaling or the days themselves cause this.
- Full tables, including (a) and precision/recall: `results/test_table.md`,
  `results/test_table_by_period.md`, `results/oblast_wins.md`. Plot for H=6:
  `figures/model_vs_baselines_h6.png`. Feature importance: `results/feature_importance.md`.

## Run order

```bash
pip install -r requirements.txt
python scripts/fetch_data.py         # optional: re-pull (overwrites data/raw/, updates PULL_INFO.md)
python scripts/inspect_raw.py        # raw file summary: columns, ranges, duplicates, naive flag
python scripts/build_panel.py        # hourly panel -> data/processed/panel_official_min0.5.csv.gz
python scripts/build_panel.py --min-share 0          # variant: oblast = any raion
python scripts/build_panel.py --source volunteer     # variant: volunteer feed
python scripts/plot_weekly.py        # figures/alerts_per_week.png (+ .csv)
python scripts/hand_checks.py        # round-1 hand-check numbers (needs the three panels)
python scripts/evaluate.py           # model + baselines: tables in results/, H=6 plots
python scripts/check_no_peeking.py   # leakage check: baseline inputs and model features
```

## Definitions

**Oblast under alert.** Each official row is mapped to raions:
- an oblast-wide alert covers all of the oblast's raions;
- a raion alert covers that raion;
- hromada-only alerts are dropped (frontline communities under near-permanent alert).

An oblast is under alert while **at least half of its raions** are. The raion counts are the
fixed 2020 administrative lists, e.g. Lviv 7, Donetsk 8. Kyiv City is one unit. Luhansk (a
permanent alert) and Crimea are excluded, which leaves 24 units.

**Episodes.** Overlapping or touching intervals within an oblast are merged. A new alert starting
**within 5 minutes** of the previous one ending is treated as the same alert re-issued and joined
(1,924 of 84,326 episodes; 96 in the test month). The state "at t" (persistence) uses episodes
*before* this joining, since at t nobody knows whether a restart will follow.

**Hourly panel** (`scripts/build_panel.py`). One row per oblast per UTC hour bucket [h, h+1):

| column | meaning |
|---|---|
| `active` | under alert at any moment in the hour |
| `active_at_start` | an alert started strictly before h is still running at h |
| `minutes_active` | minutes of the hour under alert (0–60) |
| `n_starts` | episodes starting inside the hour |
| `data_ok` | False inside known feed outages |

The panel is for description and hand-checks. The evaluation computes targets exactly from
episodes, and the two agree on the test rows (recipe below).

Hand-check recipe: keep panel rows with `hour` in [2026-08-07, 2026-08-29) or
[2026-09-04, 2026-09-06), then average those columns. That is 13,824 rows and gives the H=1 base
rates: (b) 0.121, (a) 0.309, active at t 0.209.

## Layout

```
data/raw/            snapshot CSVs (committed) + PULL_INFO.md
data/processed/      panels (gitignored; rebuild with scripts/build_panel.py)
src/load.py          raw CSV -> cleaned alert rows (dedupe, relabel, outage list, data end)
src/panel.py         alert rows -> raion alerts -> oblast episodes -> hourly panel
src/targets.py       forecast rows, "active at t", targets (a) and (b)
src/dataset.py       rows + targets on the full grid, chronological split masks
src/features.py      model features (all known at t)
src/logit.py         plain logistic regression (Newton / IRLS), the comparison model
src/baselines.py     the three baselines
src/metrics.py       Brier (+ decomposition), AUC, precision/recall/F1, max-F1 threshold
data/neighbours.csv  hand-written oblast adjacency (land borders), used by the neighbour features
scripts/             one script per step, run from the repo root
results/             evaluation tables
figures/             plots and the tables behind them
PROCESS_LOG.md       lab notebook
CLAUDE.md            working rules for this repo
```
