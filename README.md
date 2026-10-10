# Ukraine air-raid alerts: short-horizon forecasting by oblast

**Question.** Standing at the start of hour *t* (UTC), using only what is known at that moment:
will there be an air-raid alert in oblast X in the next H hours, for H = 1, 3, 6? The answer is
yes/no plus a probability. One model covers all oblasts, with oblast as a feature.

Two targets:
- `y_active_H`: an alert is active at any moment in [t, t+H). This is easy, because alerts are long.
- `y_start_H`: a new alert *starts* in [t, t+H). This is the real question.

Ground rules (fixed):
- No leakage. A forecast at t only uses data known at t. Every aggregate (means, frequencies)
  is computed on the training period only. Splits are chronological, never random.
- Every model number is reported next to three baselines: same as now, same hour yesterday,
  and the training-period frequency for oblast x hour x weekday. If the model doesn't beat
  them, we say so.
- Metrics: Brier, ROC-AUC, precision/recall at a threshold. No plain accuracy, because the
  classes are imbalanced.

**Status:** round 1, data only. Nothing is trained yet. See `PROCESS_LOG.md` for what was run and
found, and for the round-2 feature proposal.

## Data

[Vadimkin/ukrainian-air-raid-sirens-dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset)
has two feeds, official and volunteer. Times are in UTC. The snapshot used is committed in
`data/raw/`; `data/raw/PULL_INFO.md` records when it was pulled and from which upstream commit
(pulled 2026-10-10 08:27 UTC, commit `7ccd436`).

Things to know before using it (details in `PROCESS_LOG.md`):
- **The official feed ends 2026-09-07 ~05:40 UTC.** Upstream has updated only the volunteer
  files since 2026-09-08. The most recent usable official period ends 2026-09-05.
- **Official outage 2026-08-29 → 2026-09-02.** No messages for ~4.4 days, and the alerts open
  at the time got fake end times. These hours are masked with `data_ok=False`.
- **38% of official rows are duplicates.** Upstream re-appended its whole history once. The
  loader drops them.
- **Official alerts moved from oblast level to raion level, Jul–Dec 2025.** The panel's oblast
  definition is built to survive this (see below).
- **The volunteer feed is not a substitute for official after the switch.** Their agreement
  falls from κ≈0.97 in 2022 to κ≈0.42 in 2026Q3.

## Run order

```bash
pip install -r requirements.txt
python scripts/fetch_data.py        # optional: re-pull a fresh snapshot (overwrites data/raw/)
python scripts/inspect_raw.py       # Q1: columns, ranges, counts, naive flag
python scripts/build_panel.py       # Q3: data/processed/panel_official_min0.5.csv.gz
python scripts/build_panel.py --min-share 0         # variant: oblast = any raion
python scripts/build_panel.py --source volunteer    # variant: volunteer feed
python scripts/plot_weekly.py       # Q2: figures/alerts_per_week.png (+ .csv with the numbers)
python scripts/hand_checks.py       # Q4: the three hand-check numbers (needs all three panels)
```

## Hourly panel

One row per oblast per UTC hour. Hour `h` means the bucket [h, h+1h). There are 24 units:
23 oblasts plus Kyiv City, which is separate from Kyiv oblast. Luhansk is excluded because its
alert has been permanent since 2022-04-04; Crimea is not in the data.

| column | meaning |
|---|---|
| `active` | the oblast is under alert at any moment inside [h, h+1) |
| `active_at_start` | an alert started strictly before h is still running at h. This is the "now" state for a forecast made at h |
| `minutes_active` | minutes of the hour under alert (0–60) |
| `n_starts` | oblast alert episodes that start inside [h, h+1) |
| `data_ok` | False inside known feed outages; don't train or evaluate on these hours |

**What "oblast X is under alert" means (official feed).** Every official row is mapped to raions:
- an oblast-wide alert covers every raion of the oblast;
- a raion alert covers that raion;
- hromada-only alerts are dropped. These are frontline communities under near-permanent alert;
  one Kharkiv hromada has a single 604-day row.

The oblast counts as under alert while **at least half of its raions** are under alert. Before
mid-2025 this is exactly the oblast-wide alert. After the switch to raion-level alerts it avoids
"some frontline raion is always on", which puts Kharkiv and Dnipro at 99% of hours. The share
is a parameter (`--min-share`): 0 = any raion, 1 = all raions.

**Boundaries and overlaps.** Overlapping or touching intervals within an oblast are merged
into one episode *before* gridding. So overlaps and duplicate rows can't double count, and an
alert crossing an hour boundary marks every bucket it touches. `minutes_active` holds the exact
overlap. An episode's start is counted once, in the bucket where it begins.

## Layout

```
data/raw/         snapshot CSVs (committed) + PULL_INFO.md
data/processed/   panels (gitignored; rebuild with scripts/build_panel.py)
src/load.py       raw CSV -> cleaned alert rows (dedupe, relabel, outage list, data end)
src/panel.py      alert rows -> raion alerts -> oblast episodes -> hourly panel
scripts/          one script per step, run from the repo root
figures/          plots and the tables behind them
PROCESS_LOG.md    lab notebook
```
