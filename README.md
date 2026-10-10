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

**Status:** round 3. One LightGBM model for target (b), evaluated next to the three baselines.
`PROCESS_LOG.md` has every step; results are in `results/`.

## Data

[Vadimkin/ukrainian-air-raid-sirens-dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset)
has two feeds, official and volunteer. Times are UTC.
- The snapshot is committed in `data/raw/`.
- `data/raw/PULL_INFO.md` records the pull: 2026-10-10 08:27 UTC, upstream commit `7ccd436`.
- We use the **official** feed. The volunteer feed is not reliable after mid-2025 (see below).

Known problems, handled in `src/load.py`:
- The official feed ends 2026-09-07 ~05:40 UTC.
- No official messages 2026-08-29 → 2026-09-02. These hours are masked.
- 38% of official rows are upstream duplicates. They are dropped.
- The last day of each file is incomplete, because alerts still open at the pull are missing. It is cut.

### Evaluation window: the most recent trustworthy data
The test period is the **last 30 full days of official data: 2026-08-07 00:00 → 2026-09-05 23:00
UTC**. Rows whose lookback or target window touches the outage are dropped.
- The model's longest feature window is 7 days, so every row after the outage is dropped too.
- That leaves origins from 2026-08-07 00:00 to 2026-08-28 (22 days), for the model and the
  baselines alike.

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

Test month, target (b), model next to the baselines. Within-oblast AUC (higher is better) and
Brier (lower is better):

| H | base rate | LightGBM | same as now | same hour yesterday | train frequency |
|---|---|---|---|---|---|
| 1 | 0.120 | **0.696** / **0.087** | 0.443 / 0.281 | 0.516 / 0.178 | 0.500 / 0.100 |
| 3 | 0.290 | **0.651** / **0.143** | 0.485 / 0.319 | 0.515 / 0.280 | 0.602 / 0.174 |
| 6 | 0.421 | **0.644** / **0.141** | 0.491 / 0.358 | 0.508 / 0.273 | 0.629 / 0.176 |

How to read it:
- At H=1 the model clearly ranks better: it beats the frequency baseline's AUC in 23 of 24
  oblasts.
- At H=6 its ranking edge *within* oblasts over the frequency baseline is small: it wins in
  13 of 24 oblasts.
- Its H=6 Brier gain over that baseline (0.034) splits about evenly between calibration
  (reliability 0.001 vs 0.018) and resolution (0.102 vs 0.085).
- The model's probabilities are well calibrated (`results/calibration.md`,
  `figures/reliability_h6.png`).
- Full table, including (a) and precision/recall: `results/test_table.md`. Plot for H=6:
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

Hand-check recipe: keep panel rows with `hour` in [2026-08-07, 2026-08-29), then average those
columns. That is 12,672 rows and gives the H=1 base rates: (b) 0.120, (a) 0.303, active at t 0.205.

## Layout

```
data/raw/            snapshot CSVs (committed) + PULL_INFO.md
data/processed/      panels (gitignored; rebuild with scripts/build_panel.py)
src/load.py          raw CSV -> cleaned alert rows (dedupe, relabel, outage list, data end)
src/panel.py         alert rows -> raion alerts -> oblast episodes -> hourly panel
src/targets.py       forecast rows, "active at t", targets (a) and (b)
src/dataset.py       rows + targets on the full grid, chronological split masks
src/features.py      model features (all known at t)
src/baselines.py     the three baselines
src/metrics.py       Brier (+ decomposition), AUC, precision/recall/F1, max-F1 threshold
data/neighbours.csv  hand-written oblast adjacency (land borders), used by the neighbour features
scripts/             one script per step, run from the repo root
results/             evaluation tables
figures/             plots and the tables behind them
PROCESS_LOG.md       lab notebook
CLAUDE.md            working rules for this repo
```
