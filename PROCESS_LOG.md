# Process log

Lab notebook. Each entry records what ran, what came back, what was wrong and what changed. Newest at the bottom.
All times are UTC.

---

## 2026-10-10 — Round 1: data only (no models)

### 1. Pull
- Ran `git ls-remote` on the upstream repo, then `scripts/fetch_data.py`.
- Got upstream commit `7ccd4367b7057a4541ce109ca09cf1f0220f6a75` ("Add new data", 2026-10-10 05:01).
- Pulled at **2026-10-10 08:27:53 UTC**. Checksums are in `data/raw/PULL_INFO.md`. They are byte-identical to a
  `git clone` made at 08:12 the same morning.
- Only the `_en` files are used. The `_uk` files hold the same rows with Ukrainian names.

### 2. Read the upstream processing code before the data
This explains what a row means:
- Both feeds are parsed from Telegram channels. A row is written only after the alert **ends**. Alerts still open at
  the last run are missing from the CSV; their state sits in upstream's `processors/pkl/*.pkl`.
- If a location gets a new "alert" message while an earlier alert never got its "all clear":
  - more than 3h after the earlier start: the earlier alert is closed at **start + 30 min** with `naive=True`
    (volunteer), or at **start + 1h with no flag** (official);
  - less than 3h after: the earlier alert is **overwritten**, so its true start is lost. Nothing in the data shows
    this happened.
- Official rows are one per location in the message. A message listing 8 raions becomes 8 rows.
- Volunteer rows are oblast-level only. The oblast is guessed from keywords in free text, and the volunteer feed keeps
  one on/off state per oblast.
- There are permanent alerts in Luhansk (since 2022-04-04) and Crimea (since 2022-12-10). Neither is in the data.

### 3. Q1: what is in the files (`scripts/inspect_raw.py`)

| | official | volunteer |
|---|---|---|
| columns | oblast, raion, hromada, level, started_at, finished_at, source | region, started_at, finished_at, naive |
| rows (raw) | 299,275 | 115,793 |
| first start | 2022-03-15 16:10 | 2022-02-25 16:36 |
| last start | **2026-09-07 05:28** | 2026-10-10 04:47 |
| exact duplicate rows | **113,845 (38%)** | 0 |
| rows after cleaning | 185,364 | 115,793 |

**Wrong #1: official duplicates.**
- Rows 0–113,910 are the original history (2022-03-15 → 2026-01-25).
- Rows 113,911–227,831 are a second full pass over the same history. Upstream re-ran its processor in append mode.
- Rows 227,832+ are new data.
- Pass 2 differs from pass 1 in only 142 rows:
  - 66 Zviahelskyi-raion rows were mislabelled in pass 1 as `level=hromada, hromada="Zviahelskyi raion"`. Pass 2 has
    them correctly as raion rows.
  - 10 rows exist only in pass 2.
- No (location, start) pair has two different end times.
- **Changed:** `load_official()` relabels rows where `hromada == raion` as raion rows, then drops exact duplicates.
- Duplicates don't change the hourly panel, because identical intervals union to the same thing. They do double every
  row count up to 2026-01-25 (see the grey line in the weekly figure).

**Wrong #2: the official feed stopped.**
- Every upstream commit since 2026-09-08 touches only the volunteer files. Official data ends 2026-09-07 ~05:40.
- Nothing in the repo says why.
- So "the most recent period" for official data is **up to 2026-09-05**, a month before the pull date.

**Official levels:** raion 99,304, oblast 65,314, hromada 20,746 (cleaned).

**Durations (official, cleaned):**
- Median 49 min, 90th percentile 285 min, 99th percentile 18.8 h.
- 2 rows have zero length.
- 253 rows last exactly 60.000 min. These are upstream's unflagged imputed ends; 148 of them are in 2026.

**`naive` flag (volunteer).**
- Means: no "all clear" message was seen, and upstream set end = start + 30 min.
- Set on 5,791 rows (5.0%). Every naive row lasts exactly 30 min. There are also 43 non-naive rows that happen to
  last exactly 30 min.
- By year: 2.0% in 2022, then 5–6% in 2023–2026.
- By oblast: Kherson 16.5%, Sumy 9.0%, Donetsk 8.9%. Luhansk is 100% (only 3 rows).
- It is a lower bound on imputation: overwritten starts (the < 3h case above) are not flagged.

### 4. Right-censoring at the end of each file
- Disassembled upstream's state pickles with `pickletools`. This reads opcodes without unpickling or executing
  anything. It shows which alerts were still open at the last run.
- Official: open alerts start from 2026-09-07 00:58 onward. There are also two hromada alerts open since 2026-03-10
  (Lypetska) and 2026-04-19 (Chervonohryhorivska).
- Volunteer: open alerts start from 2026-10-09 22:31 (Donetsk) onward.
- **Changed:** the panel ends at `floor_day(last finished_at) − 1 day`:
  - official: last hour is 2026-09-05 23:00;
  - volunteer: last hour is 2026-10-08 23:00.

### 5. Q2: alerts per week (`scripts/plot_weekly.py` → `figures/alerts_per_week.png`, numbers in `.csv`)
Weekly counts, Mon–Sun UTC, no smoothing. Partial first and last weeks are dropped.

What looks odd, and why:
1. **Raw official rows jump about 4× from Jul to Dec 2025, then halve on 2026-01-25.** Neither is real.
   - The rise comes from the switch to raion-level alerts: one alert used to be one oblast row, and now it is one row
     per raion. Donetsk lists all 8 raions every time.
   - The halving is where upstream's duplicated history ends.
   - In the cleaned data, the oblast-level series (bottom panel) has no jump.
2. **Oblast-level rows fade out over Jul–Dec 2025.** In Nov 2025 there are 328 oblast-level rows; from Dec 2025 on there
   are fewer than 120 a month. Raion-level rows replace them.
   - The switch is gradual, not a single date. A handful of raion rows also appear in Jan–Jun 2025.
   - Hromada-level rows exist throughout. They are local frontline alerts (Nikopol, Marhanets, Kharkiv-area hromadas).
3. **Official outage, 2026-08-29 ~05:00 → 2026-09-02 ~14:00.** There are zero official starts or ends for 4.4 days,
   while the volunteer feed logs ~170 starts a day.
   - Alerts open when it started got fake ends: either upstream's +1h, or the next "all clear" on Sep 2. For example,
     Kyiv oblast's Brovarskyi raion shows an alert from Aug 29 00:30 to Sep 2 16:42.
   - Scanned all history in 6h windows for "volunteer busy, official silent". This was the only real hit; the other was
     2023-03-18 18:00, with just 5 volunteer starts.
   - **Changed:** `OFFICIAL_OUTAGES` in `src/load.py`. Hours from 2026-08-29 to 2026-09-02 (whole UTC days) get
     `data_ok=False`.
4. **The volunteer feed drifts away from official.**
   - It tracks official closely in 2022, runs about 10–20% above it from 2023, and from late 2025 is roughly double.
   - Hourly agreement (Cohen's κ on `active`, all oblasts): 0.98 in 2022Q3, 0.86 in 2024Q1, 0.69 in 2025Q1,
     **0.42 in 2026Q3**.
   - In 2026, per oblast: Lviv is under alert 17% of hours in volunteer vs 2% in official, and Volyn 29% vs 3%. κ ranges
     from 0.03 (Donetsk) to 0.86 (Ivano-Frankivsk).
   - Likely cause: the volunteer keyword parser has one on/off state per oblast, and raion-level messages toggle it.
   - **Decision:** volunteer is not a stand-in for official in the recent period.
5. **Late Nov 2022 dip (~90 starts a week).** Real. The share of hours under alert also drops (4.3% vs 11–15% around it),
   and both feeds agree.
6. **2026 drifts up** (~400 → ~550 oblast starts a week). No data artifact found. It looks like real intensification.

### 6. Q3: hourly panel (`scripts/build_panel.py`, `src/panel.py`)

**Overlaps and hour boundaries.**
- Per unit, all alert intervals are first merged into disjoint episodes. Any overlap or touch (gap ≤ 0) joins them.
- Then an episode marks `active` in every hour bucket [h, h+1) it overlaps.
- `minutes_active` is the exact overlap.
- `n_starts` counts the episode start once, in its own bucket.
- `active_at_start` uses a strict `start < h`. An alert starting exactly at hh:00:00 is a new start in hour h, not
  "already on at h". So the "now" feature and the new-start target can never both claim the same event.
- Tested on toy cases (boundary crossing, overlaps, touching intervals, exact-hour ends, zero-length rows) and checked
  on real data:
  - `minutes_active` sums match episode durations to 1e-11;
  - 84,224 episode starts match `n_starts` exactly;
  - `active_at_start` implies `active`, and `n_starts > 0` implies `active`.

**Geographic level change.** Your hunch was right, and it is the biggest design decision so far. Share of hours "under
alert" in 2026Q3, by definition:

| oblast, 2026Q3 | oblast rows only | any raion | ≥ half of raions | center raion | all raions |
|---|---|---|---|---|---|
| Kharkiv | 0.000 | 0.994 | 0.823 | 0.940 | 0.382 |
| Dnipro | 0.000 | 0.991 | 0.525 | 0.437 | 0.208 |
| Lviv | 0.000 | 0.004 | 0.004 | 0.004 | 0.004 |

- **Oblast rows only** dies after the switch.
- **All levels including hromada** is worse than any raion: Kharkiv is at 100% from mid-2024 because of one 604-day
  hromada alert (Lypetska).
- **Any raion** saturates: in 2026, Dnipro is under alert 97% of hours, and its new starts *fall* from 5.6 to 3.3 a day.
  That is a definition artifact, not de-escalation. It also turns a 2-of-6-raion Zakarpattia alert with a missing
  "all clear" (Nov 19–24, 2025) into 128 hours under alert. Volunteer and the half rule both show 7 hours.
- **≥ half of raions** equals the oblast-wide alert before the switch. Across it, it keeps base rates close to
  continuous: Dnipro 0.41 → 0.43 hours under alert, 5.6 → 5.7 starts a day. It needs no hand-picked raions.
  - Known quirk: Kherson's raion list includes three mostly-occupied raions that only appear in oblast-wide lists. So for
    Kherson, the half rule effectively means "oblast-wide list", and its share drops from 0.30 to 0.15.
- **Center raion** behaves like the half rule but needs a hand-picked raion per oblast, and Kyiv oblast has no center
  inside it.
- **Changed:** default is ≥ half of raions (`--min-share 0.5`). The any-raion variant is one flag away.
- The raion list per oblast is "every raion name seen in a raion-level row". Kyiv City has no raions and is its own unit.

**Gap merging for new starts (not done).**
- Under the half rule, 2–4% of episodes start within 5 min of the previous one ending: 3.6% in 2026, 11% within 15 min.
- The default is no gap merging (literal data). `merge_episodes(max_gap=...)` exists if we want it. Open question below.

**Output.** `panel_official_min0.5.csv.gz` has 941,760 rows: 24 units × 39,240 hours, from 2022-03-16 00:00 to
2026-09-05 23:00. 2,880 rows have `data_ok=False`. Overall: 20.8% of hours under alert, 2.15 new starts per
oblast-day.

**Portability.** Built the panels and weekly table under pandas 2.2.3 and 3.0.5; the outputs are identical.

### 7. Q4: hand-check numbers (`scripts/hand_checks.py`)
1. **Alerts in Kyiv oblast (not Kyiv City), September 2026.**
   - Only the volunteer feed covers the month: **346** rows. The count is the same with UTC or Kyiv-time month bounds.
   - Official covers only Sep 2 13:48 → Sep 6: 149 raion rows (one per raion per alert), which make 21 oblast episodes
     under the half rule.
   - Don't compare 346 with 149; they count different things.
2. **Longest single alert:** Kharkiv oblast, Kharkivskyi raion, **Lypetska hromada**, 2024-05-12 08:37:29 → 2026-01-06
   09:53:57 UTC, **604.05 days** (official, hromada level).
   - Runner-up: Vovchanska hromada, 438.6 days.
   - Longest at oblast or raion level: Zakarpattia, Mukachivskyi and Berehivskyi raions, 2025-11-19 → 11-24,
     5.09 days. This is likely a missed "all clear".
   - Longest in the volunteer feed: Zaporizhzhia, 2022-03-04 → 03-11, 7.43 days.
   - The permanent Luhansk and Crimea alerts are longer, but they are not in the data.
3. **Share of hours with an active alert, last 90 days.** Official panel, window [2026-06-08, 2026-09-06), outage hours
   excluded, 2,040 usable hours:
   - **Kharkiv 0.841 vs Lviv 0.009** (share of *time* under alert: 0.593 vs 0.003).
   - Any-raion variant: Kharkiv 0.994, Lviv 0.009.
   - Volunteer (window [2026-07-11, 2026-10-09)): Kharkiv 0.685, Lviv 0.242. That Lviv number is the post-switch
     volunteer problem again.

---

## Proposal for round 2 (not built, for discussion)

**Rows and targets.**
- One row per (oblast, t). Forecast origin is the instant t, the top of a UTC hour.
- Targets come from panel hours t … t+H−1:
  - `y_active_H = any(active)`;
  - `y_start_H = any(n_starts > 0)`.
- Drop rows whose lookback (168h) or target window touches `data_ok=False`.
- Report `y_start_H` on all rows **and** on currently quiet rows (`active_at_start = False`). When an alert is running,
  a "new start" first needs that alert to end.

**Split.** Chronological, with H-hour purge gaps so no training target window reaches into the next block.
- test = 2026-08-01 → 2026-09-05, outage removed (~31 usable days);
- validation = July 2026;
- train = 2025-12-01 → 2026-06-30, post-switch only. The alternative is all history since 2022-03; pick on validation.
- Train-only aggregates are refit whenever the training window changes.

**Baselines.** Same three for both targets and all H:
1. **same as now:** the target's own value over the window that just closed, [t−H, t). For `y_active_1` this is
   "active in the last hour". The alternative is `active_at_start`.
2. **same hour yesterday:** the target's value over [t−24h, t−24h+H).
3. **training frequency:** mean of the target on training rows with the same oblast × Kyiv-local hour × weekday.

Baselines 1 and 2 are 0/1 scores. Report them as is, and also "calibrated" (0/1 mapped to the training-period
P(y=1 | baseline value)), so Brier doesn't punish them just for being hard 0/1.

**Features.** All come from panel hours before t.
- **Own state:**
  - `active_at_start`;
  - hours since the current alert started, or since the last one ended (capped at 72, log1p).
- **Own recent history:**
  - minutes active in the last 1 / 3 / 6 / 24 h;
  - number of starts in the last 6 / 24 / 168 h.
- **Calendar (Europe/Kyiv local time):** hour of day, weekday.
- **Spatial:**
  - share of the other 23 units under alert at t;
  - share of *neighbouring* oblasts under alert at t (needs a hand-written adjacency table);
  - number of units with a new start in the last 1 h and 3 h, as a proxy for an attack wave moving across the country.
- **Identity:** oblast one-hot, plus the training-period oblast × hour × weekday frequency (baseline 3) as a feature.
- **Not proposed:**
  - the volunteer feed as a feature (degraded after the switch);
  - raion-level detail;
  - external data (weather, news, Telegram text);
  - date or trend features, which would extrapolate badly.

**Models.** Logistic regression first, then sklearn `HistGradientBoostingClassifier`. That adds `scikit-learn` to
requirements.

**Metrics.**
- Brier.
- ROC-AUC **pooled and mean within-oblast**. Pooled AUC is inflated just by "Kharkiv is busier than Lviv".
- Precision and recall at a threshold chosen on validation (max F1), then frozen for test.
- One table per target × H, with the model and the three baselines side by side.

**Repo additions.**
```
src/targets.py     y_active_H, y_start_H, row masking (data_ok, lookback)
src/features.py    feature builder; train-only aggregates take an explicit train cutoff
src/baselines.py   the three baselines          <- good candidate to write by hand
src/metrics.py     brier / auc / precision-recall tables   <- same
data/adjacency.csv oblast neighbour pairs       <- same
scripts/make_dataset.py, scripts/evaluate.py
```

**Open questions.**
1. Oblast definition: ≥ half of raions (current default), any raion, or center raion?
2. Evaluation ends 2026-09-05 because the official feed stopped upstream. Options: accept that; re-pull before Monday in
   case upstream recovers; or find another official source for Sep 7 – Oct 9.
3. Train on post-switch data only, or all history?
4. Gap-merge for `y_start` (e.g., treat a restart within 5 min as the same alert), or keep the literal data?
5. "Same as now": the target over [t−H, t) (proposed), or `active_at_start`?

---

## 2026-10-10 — Round 2: targets, baselines, evaluation (no model)

### 0. Decisions taken (from review of round 1)
1. Oblast under alert = at least half of its raions. README gets a note on what this means for western oblasts.
2. Evaluation = last 30 full days of official data, ending 2026-09-05, with outage hours masked. Re-pull on Sunday;
   if upstream fixed the official feed, move the window forward. The reasoning is in the README.
3. Train on full history. Features must not depend on the level (shares of hours, not counts of rows). One later
   experiment: train on post-switch data only and compare on the test month.
4. A new start within 5 min of the previous end is a re-issued message, not a new alert. Join them and log how many.
5. "Same as now" = alert active at time t.

### 1. Western-oblast note: the volunteer Lviv number is mislabelled, not a definition
- Before writing the README note, checked *why* volunteer has Lviv under alert 24–25% of recent hours while official
  has 0.9%.
- Matched each 2026 volunteer start to official starts within ±3 min:
  - Lviv: 627 volunteer starts. 7% match an official Lviv alert. **82% match an official alert in a "-Podilskyi"
    raion of another oblast and not Lviv**: Odesa's Podilskyi raion 70%, Mohyliv-Podilskyi (Vinnytsia) 20%,
    Kamianets-Podilskyi (Khmelnytskyi) 12%.
  - Upstream's Lviv keyword list contains "Подільський", so these raion messages get assigned to Lviv.
  - In 2024, before the switch, 74% of volunteer Lviv starts matched official Lviv.
  - Chance level: Odesa's Podilskyi raion has ~500 starts in 2026, so a random ±3 min match is ~1%.
- Volyn: 868 starts. 9% match Volyn; **85% match Chernihiv's Prylutskyi raion**. "Прилуцький" contains "Луцьк",
  a Volyn keyword.
- Other western oblasts mostly match themselves: Zakarpattia 83%, Chernivtsi 80%, Ternopil 67%, Khmelnytskyi 61%.
- Our own Lviv 0.9% does not come from the half rule either; any-raion also gives 0.9%. The fall from 4.7% of hours
  (2024) to 0.9% is the official system declaring raion-level alerts along threat paths.
- **Changed:** the README note says exactly this. It does not say "the 25% is the definition", because it isn't.

### 2. Joining restarts within 5 min (`RESTART_GAP` in `src/panel.py`)
- Joined **1,924 of 84,326** oblast episodes (2.3%). By year: 2022 231, 2023 287, 2024 514, 2025 355, 2026 537.
- **96 in the test month** (1,986 → 1,890 episode starts).
- Any-raion variant, for reference: 2,647 of 87,763.
- Effect on the panel: share of hours active unchanged (0.208); new starts per oblast-day 2.15 → 2.10.
- Round-1 hand checks are unchanged at three decimals (Kyiv September 21 episodes, Kharkiv 0.841, Lviv 0.009).
  Kharkiv's share of *time* moved 0.593 → 0.595.
- The state "at t" (persistence) is computed from episodes *before* joining. At t nobody knows whether a restart will
  follow within 5 min, so using joined episodes there would peek.
- **Changed:** `oblast_episodes` now takes the raion count per oblast from the fixed 2020 administrative list (Lviv 7,
  Donetsk 8, Kherson 5, …) instead of counting raions seen in whatever data it is given.
  - On full data nothing changes (panel byte-identical).
  - On data truncated at t, the old version could silently shrink the denominator. The leakage check (below) found
    this need.

### 3. Targets (`src/targets.py`)
- Rows are (oblast, t), with t an instant on the hour.
- Definitions:
  - (a) `y_active` = some episode overlaps (t, t+H];
  - (b) `y_start` = some episode starts in (t, t+H];
  - "now" = some (un-joined) episode has start ≤ t < end.
- All three are computed with `searchsorted` on episode times, so the boundaries are exact: a start at exactly t is
  "now", not a new start; a start at exactly t+H is inside the window.
- Tested on toy episodes, boundary cases included.
- Identity **(a) = now OR (b)** holds by construction. On the test month it fails on 3 rows (H=1), all origins that
  fall inside a joined ≤5-min restart gap.

### 4. Baselines, metrics, protocol
- Baselines are in `src/baselines.py`; see the README table.
  - Kyiv local time (`Europe/Kyiv`) is used for the hour and weekday cells.
  - The frequency table is fitted on all training rows (2022-03-17 → 2026-08-06). That includes the last train week
    used to pick thresholds, which is a small in-sample effect: about 1 of ~230 observations per cell.
- Metrics (`src/metrics.py`) use numpy/pandas only.
  - AUC is rank-based with tied scores averaged.
  - The max-F1 threshold is picked among the observed scores; ties go to the higher threshold.
  - Both match brute-force versions on 300 random cases, including ties and 0/1 scores.
- Test window: origins 2026-08-07 00:00 → 2026-09-05 23:00 UTC.
  - A row is dropped if [t−24h, t+H] touches the outage.
  - That leaves 576 / 572 / 566 origins per oblast for H = 1 / 3 / 6, i.e. 13,824 / 13,728 / 13,584 rows.
  - Every baseline is scored on the identical rows.
- Train: rows with t + H ≤ 2026-08-07. Threshold week: train rows from 2026-07-31.
- **No-peeking check** (`scripts/check_no_peeking.py`):
  - For 40 random test origins, rebuilt the episodes from rows known at t: rows starting after t dropped, ends after t
    set to unknown. Recomputed "now" and yesterday's outcomes: **0 mismatches in 6,720 values**.
  - Every training window closes by 2026-08-07 00:00.
  - Negative control: recomputing the *future* (b) H=6 from truncated data mismatches exactly the 421 true positives.
    So the check would catch peeking.
- Cross-check against the panel CSV: on the test rows, share of `n_starts > 0` = 0.121, `active` = 0.309 and
  `active_at_start` = 0.209. These are identical to the table's base rates.

### 5. Results (`results/baselines_test.md`, `figures/baselines_h6.png`)

| target | H | base rate | best Brier | persistence Brier / AUC within | yesterday Brier / AUC within | frequency Brier / AUC pooled / AUC within |
|---|---|---|---|---|---|---|
| (a) active | 1 | 0.309 | persistence 0.100 | 0.100 / 0.753 | 0.217 / 0.524 | 0.150 / 0.884 / 0.559 |
| (a) active | 3 | 0.416 | frequency 0.152 | 0.207 / 0.657 | 0.234 / 0.513 | 0.152 / 0.895 / 0.558 |
| (a) active | 6 | 0.502 | frequency 0.138 | 0.293 / 0.598 | 0.217 / 0.512 | 0.138 / 0.913 / 0.599 |
| (b) start | 1 | 0.121 | frequency 0.101 | 0.288 / 0.438 | 0.181 / 0.525 | 0.101 / 0.736 / 0.491 |
| (b) start | 3 | 0.296 | frequency 0.177 | 0.327 / 0.480 | 0.281 / 0.524 | 0.177 / 0.784 / 0.579 |
| (b) start | 6 | 0.430 | frequency 0.178 | 0.365 / 0.489 | 0.267 / 0.516 | 0.178 / 0.830 / 0.611 |

What it says:
- **Target (a) at H=1 is mostly persistence. That is the headline.**
  - 67.5% of (a)-positives are an alert that is already running at t; at H=3 it's 50.1%, at H=6 41.6%.
  - Persistence has precision 1.000 by construction, and recall exactly equal to those shares.
  - At H=1 it is the best of the three on Brier (0.100) and within-oblast AUC (0.753).
  - Everything in (a) beyond persistence *is* (b) on rows that are quiet at t. That has base rate 12.7% / 26.2% /
    37.0% for H = 1/3/6.
  - So (a) should be reported as "persistence + (b)", and the forecasting effort belongs on (b).
- **Pooled AUC flatters anything that knows the oblast.**
  - The frequency baseline has pooled AUC 0.74–0.91 but within-oblast AUC only 0.49–0.61.
  - Most of its ranking power is "Kharkiv is busier than Lviv", not "this hour is riskier than that one".
  - For (b) at H=1, within-oblast AUC is 0.491: no skill at all within an oblast.
- **Persistence is anti-informative for (b) within an oblast** (AUC 0.44–0.49). Being under alert now makes a *new*
  alert in the next hours slightly less likely. Its pooled AUC above 0.5 at H=3/6 is again just busy oblasts being
  busy.
- **Same hour yesterday carries almost nothing within an oblast** (AUC 0.51–0.53).
- **The full-history frequency table is miscalibrated for the test month.** Mean prediction vs actual:
  - (a) H=1: 0.207 vs 0.309;
  - (b) H=1: 0.086 vs 0.121;
  - (b) H=6: 0.370 vs 0.430.
  - The last train week's rates (0.295 / 0.123 / 0.433) are close to the test month's. Recency matters.
  - This motivates the post-switch-only experiment; it should mostly help Brier. Not run yet, as agreed.
- **The F1 threshold degenerates to "always yes" for 0/1 baselines in several cells.** This happens for persistence on
  (a) H=6 and on (b) at every H (threshold 0.000, recall 1, precision = base rate).
  - "Always yes" scores F1 = 2p/(1+p): 0.22 at base rate p = 0.12, up to 0.67 at p = 0.5. On the last train week
    that beat the 0/1 rule in those cells.
  - This is the max-F1 rule working as specified, not a bug. But those precision/recall cells describe "always yes",
    not persistence.
- Within-oblast AUC for (a) at H=3/6 averages over 23 and 21 oblasts. The rest (frontline, e.g. Donetsk) are positive
  in every test row, so AUC is undefined for them.

### 6. Next (not done)
- Model round: features as proposed in round 1, level-independent (shares of hours, state ages, neighbour shares).
- Post-switch-only training experiment on the same test month.
- Sunday re-pull: re-run `inspect_raw.py`, check duplicates and outages, then re-run everything. The test window
  follows the data end.
