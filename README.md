# Ukraine air-raid alerts: short-horizon forecasting by oblast

**Question.** At hour t, using only what is known at t: will there be an air-raid alert in
oblast X in the next H hours, for H = 1, 3, 6? The answer is yes/no plus a probability.
One model covers all oblasts, with oblast as a feature.

Ground rules (fixed):
- No leakage. Every aggregate is computed on the training period only. Splits are
  chronological, never random.
- Every model number is shown next to three baselines. If the model doesn't beat them, we say so.
- Metrics: Brier, ROC-AUC, precision/recall at a threshold. No plain accuracy.

**Status:** round 2. Targets, baselines and the evaluation harness are built. No model yet.
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
UTC**. Rows whose 24h lookback or target window touches the outage are dropped, which leaves about
24 usable days.

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

## Targets, baselines, evaluation (`scripts/evaluate_baselines.py`)
For each oblast and forecast origin t (an instant on the hour, UTC) and H ∈ {1, 3, 6}:
- `(a)` an alert is active at some moment in (t, t+H];
- `(b)` a new alert episode starts in (t, t+H].

Both use only what happens after t. They are computed exactly from episode start/end times
(`src/targets.py`), not from hour buckets.

Note: **(a) = "active at t" OR (b)**, by construction. An alert running at t keeps running
just after t. If nothing runs at t, anything overlapping the window must start inside it.

Baselines (`src/baselines.py`):

| baseline | score for origin t | known at t because |
|---|---|---|
| same as now (persistence) | 1 if an alert is active at t, else 0 (same score for (a) and (b)) | it is the current state |
| same hour yesterday | the target's outcome for origin t−24h, i.e. window (t−24h, t−24h+H] | that window closed by t−18h |
| train frequency | share of positives in training rows with the same oblast × Kyiv-local hour × weekday | fitted only on rows whose window closed before the test month |

Protocol:
- Walk-forward over the test month: every score for origin t uses only what is known at t.
  `scripts/check_no_peeking.py` rebuilds the inputs from data truncated at t and requires an
  exact match. It also runs a negative control showing the check does catch future information.
- Train = full history (2022-03-16 onward), up to the test month.
- The threshold for precision/recall is the one that maximises F1 on the **last week of train**,
  then frozen for test.
- All three baselines are scored on the same rows. The table includes each target's base rate.

Results: `results/baselines_test.md` (full table), `results/persistence_vs_target_a.md`,
`figures/baselines_h6.png`.

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
python scripts/evaluate_baselines.py # round 2: baseline table, persistence analysis, H=6 plot
python scripts/check_no_peeking.py   # round 2: leakage check
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
episodes. They agree: on test-month rows, the share of `n_starts > 0` (0.121), `active` (0.309)
and `active_at_start` (0.209) reproduce the base rates of (b) H=1 and (a) H=1, and the share
active at t.

Hand-check recipe: keep panel rows with `hour` in [2026-08-07, 2026-09-06) and not in
[2026-08-29, 2026-09-04), then average those columns.

## Layout

```
data/raw/            snapshot CSVs (committed) + PULL_INFO.md
data/processed/      panels (gitignored; rebuild with scripts/build_panel.py)
src/load.py          raw CSV -> cleaned alert rows (dedupe, relabel, outage list, data end)
src/panel.py         alert rows -> raion alerts -> oblast episodes -> hourly panel
src/targets.py       forecast rows, "active at t", targets (a) and (b)
src/baselines.py     the three baselines
src/metrics.py       Brier, AUC, precision/recall/F1, max-F1 threshold
scripts/             one script per step, run from the repo root
results/             evaluation tables
figures/             plots and the tables behind them
PROCESS_LOG.md       lab notebook
```
