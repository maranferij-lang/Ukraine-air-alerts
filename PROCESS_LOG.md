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

---

## 2026-10-10 — Round 3: first model (LightGBM, target b)

### 0. Decisions taken (review of round 2, plus two questions asked before building)
- Lviv/Volyn: confirmed upstream bug (substring match; the Lviv and Volyn keyword lists come before Odesa,
  Vinnytsia and Chernihiv in the parser's dict). The README note stays as written. Recompute κ without them.
- From now on, **within-oblast AUC is the main number**. Pooled AUC stays in the table, not in summaries.
- 0/1 baselines (persistence, yesterday): no threshold search. Report precision/recall of the raw 0/1 prediction.
- We model (b) and report (a) as "1 if active at t, else model(b)".
- Added `CLAUDE.md` verbatim, as written by the user (the `---` fences in the message were not included).
- Model spec as given: LightGBM, one model for all oblasts, oblast categorical, target (b), H = 1/3/6. Two changes,
  each flagged and agreed before building:
  1. **`freq4w` is rolling, not a fixed table.**
     - As specified (one table from the last 4 weeks of train, applied to every row), each oblast × hour × weekday cell
       is the mean of 4 outcomes. For training rows inside those 4 weeks, one of the 4 is the row's own target. For
       older rows the table comes from their future.
     - Now: for each origin t, target (b) at the same oblast and hour, 1–4 weeks earlier, averaged. Same meaning in
       train and test.
  2. **Validation fit + final fit.**
     - Picking the F1 threshold on the last train week from a model trained on that week would tune it on in-sample,
       overconfident scores.
     - Now: a validation fit on train minus the last week picks the number of trees (early stopping) and the
       threshold on that week. The test model is fit on all of train with those settings.
     - **Known approximation:** the threshold comes from a slightly different model than the one scored on test. The
       same applies to the frequency baseline: its threshold comes from a table fitted without the last week, its
       test scores from the full-train table. The user chose to refit rather than drop the last week, because of the
       drift finding (that week is the most valuable one to train on).
- Post-switch-only training: not this round.
- Git: the user renamed the working branch to `main` on GitHub. Fetched: `origin/main` = `cc7db72` (round 2), identical
  to the local tree.

### 1. κ without Lviv and Volyn: the parser bug is a small part of the drop
Hourly `active`, volunteer vs official, pooled over oblasts, by quarter. This uses the current panels (restarts joined,
outage hours masked), which is why 2026Q3 reads 0.448 here vs 0.415 in round 1. Round 1 counted the outage hours.

| quarter | all 24 | without Lviv, Volyn | also without Donetsk, Zaporizhzhia, Kharkiv, Sumy, Dnipro |
|---|---|---|---|
| 2022Q3 | 0.985 | 0.985 | 0.987 |
| 2024Q1 | 0.863 | 0.859 | 0.900 |
| 2025Q1 | 0.691 | 0.682 | 0.718 |
| 2025Q3 | 0.652 | 0.654 | 0.729 |
| 2025Q4 | 0.549 | 0.573 | 0.653 |
| 2026Q1 | 0.522 | 0.538 | 0.631 |
| 2026Q2 | 0.502 | 0.517 | 0.588 |
| 2026Q3 | 0.448 | 0.473 | 0.568 |

- The Lviv/Volyn bug accounts for about **0.025** of a ~0.54 drop.
- The five frontline oblasts with the lowest 2026 κ account for roughly another 0.1.
- The remaining ~0.4 is a gradual divergence across the other 17 oblasts, and it starts *before* the raion switch
  (0.86 in 2024Q1 → 0.69 in 2025Q1). Not explained by anything found so far. Logged as unexplained.

### 2. The 3 rows where (a) ≠ (now or b) at H=1
All three are origins that fall inside a joined restart gap:

| oblast | t (UTC) | raw episode ended | restart | gap | joined episode |
|---|---|---|---|---|---|
| Dnipropetrovska | 2026-08-27 01:00 | 00:59:44 | 01:03:59 | 4.2 min | 08-26 23:01 → 08-27 02:32 |
| Donetska | 2026-08-26 14:00 | 13:58:59 | 14:01:54 | 2.9 min | 08-26 05:22 → 15:18 |
| Odeska | 2026-08-24 12:00 | 11:57:18 | 12:00:55 | 3.6 min | 08-24 11:33 → 12:09 |

- "now" is read from raw episodes, so it says quiet. The joined episode spans t, so (a) = 1. The restart is joined,
  so (b) = 0.
- The identity is exact only with joined "now", which would peek at the restart.
- Round-2 wording ("holds by construction") was too strong. README corrected.

### 3. CLAUDE.md vs what we already do
Nothing contradicts work already done. Two lines conflict with this round's decisions, and one needed interpretation:
- "precision/recall at a threshold chosen on the last train week" vs this round's "0/1 baselines: raw prediction, no
  threshold search". The rule as written has no 0/1 exception.
- "frequency tables and any encodings fitted on train only" vs the rolling `freq4w`. Inside the test month, `freq4w`
  uses test-month outcomes already observed by t (1–4 weeks earlier). That is known at t, the same way "starts in the
  last 7d" is, but it is not "fitted on train only" in the literal sense.
- "neighbours lagged one hour" is implemented as "the last completed hour": under alert at some point in [t−1h, t),
  and starts in [t−6h, t). The alternative reading, the state at the instant t−1h with starts in (t−7h, t−1h], would
  throw away the most recent hour.

### 4. Rows
- Features look back 7 days, so a row is used only if [t−7d, t+H] stays clear of the outage. That drops every test
  origin after the outage: rows from Sep 3–5 have a 7-day window that includes Aug 29 – Sep 2.
- Test origins: 2026-08-07 00:00 → 2026-08-28. That is 528 / 526 / 523 per oblast for H = 1/3/6, i.e.
  **12,672 / 12,624 / 12,552 rows**, down from 13,824 / 13,728 / 13,584 in round 2.
- The baselines are re-scored on these rows, so their numbers shift slightly from round 2. Example: persistence on
  (a) at H=1 goes from Brier 0.100 to 0.098.
- Train: 920,448 rows (H=1), 2022-03-23 onward. Validation fit: 916,416. Last week: 4,032.
- Panel hand-check recipe updated: hours in [2026-08-07, 2026-08-29) give 12,672 rows. Shares 0.120 (`n_starts > 0`),
  0.303 (`active`) and 0.205 (`active_at_start`), equal to the table's H=1 base rates.

### 5. Features (`src/features.py`) and neighbours (`data/neighbours.csv`)
- Implemented as specified, with exact boundaries from episode times.
- State and coverage come from raw episodes. Start counts come from joined episodes; whether a start joins the
  previous alert is decided at the start, so starts up to t are known at t.
- Two choices made here:
  - `hours_since_end` is capped at 720 h (30 days).
  - Share-of-hours features are share of *time* under alert (minutes / 60).
- Toy test: every value matched hand computation, including:
  - a just-ended alert whose restart comes 3 min after t (quiet at t);
  - a joined restart not counted as a new start;
  - a neighbour alert starting exactly at t, ignored.
- Real-data spot check: Kharkiv, 2026-08-20 15:00, `freq4w` = 1.0, equal to the four lagged targets by hand.
- `data/neighbours.csv`: land borders between the 24 units, written by hand from the administrative map. 50 pairs;
  Luhansk and Crimea are left out. It is not in `data/raw`, so the "never edit data/raw" rule is not affected.
  **Worth a look by eye.**

### 6. Model
- Native LightGBM API, so no scikit-learn dependency (the sklearn wrapper requires it).
- Parameters: binary objective, learning rate 0.05, 31 leaves, min 200 rows per leaf, seed 0, deterministic.
- Trees from early stopping on the last train week: **116 / 97 / 81** for H = 1/3/6.
- No other tuning.

### 7. No-peeking check (`scripts/check_no_peeking.py`)
- Same 40 origins as round 2; confirmed identical to the saved list.
- Rebuilt from data truncated at t:
  - **0 mismatches in 6,720** baseline-input values;
  - **0 mismatches in 37,440** feature values (13 numeric features × 3 H × 24 oblasts × 40 origins).
- Negative controls:
  - the future target (b) H=6 mismatches on all 421 true positives;
  - a deliberately leaky feature (`share_6h` evaluated 1h past t) mismatches on 161 of 960.
- Training windows close by 2026-08-07 00:00; validation-fit windows close by 2026-07-31 00:00.

### 8. Results (`results/test_table.md`, `figures/model_vs_baselines_h6.png`)
Target (b), within-oblast AUC / Brier:

| H | base rate | LightGBM | same as now | same hour yesterday | train frequency |
|---|---|---|---|---|---|
| 1 | 0.120 | **0.696 / 0.087** | 0.443 / 0.281 | 0.516 / 0.178 | 0.500 / 0.100 |
| 3 | 0.290 | **0.651 / 0.143** | 0.485 / 0.319 | 0.515 / 0.280 | 0.602 / 0.174 |
| 6 | 0.421 | **0.644 / 0.141** | 0.491 / 0.358 | 0.508 / 0.273 | 0.629 / 0.176 |

- The model beats all three baselines on both numbers at every H.
- F1 (threshold from the last train week): 0.422 / 0.651 / 0.763, vs the frequency baseline's 0.329 / 0.615 / 0.762.
  At H=6 they are tied.
- **The within-oblast mean is noisy.**
  - Seven western oblasts had fewer than 10 new alerts in the test rows: Lviv, Ivano-Frankivsk and Zakarpattia 1
    each, Chernivtsi and Volyn 2, Ternopil 6, Rivne 9. Their AUCs are close to noise but count equally in the mean.
  - Restricted to the 17 oblasts with ≥10 alerts: H=1 model 0.670 vs frequency 0.560; H=6 model 0.611 vs 0.592.
  - Oblast by oblast, the model beats the frequency baseline in **23 of 24 at H=1 but only 13 of 24 at H=6**.
- So the H=1 gain is real. The H=6 ranking gain within oblasts is not established.
- Target (a) as "active at t, else model(b)", within-oblast AUC / Brier:
  - H=1: 0.831 / 0.068 vs persistence 0.750 / 0.098;
  - H=6: 0.704 / 0.104 vs frequency 0.617 / 0.137.
- Per-oblast base rates of (b) are in `results/base_rates_by_oblast.md`.
  - Sumy (0.941 at H=6) and Kharkiv (0.939) are at the top; Lviv, Ivano-Frankivsk and Zakarpattia (0.011 each, the
    same single western alert) at the bottom.
  - Donetsk is only 0.358, because it is almost always on, so new starts are rare.

### 9. Do the probabilities mean anything (`results/calibration.md`, `figures/reliability_h6.png`)
Brier ≈ reliability − resolution + uncertainty, 10 equal-width bins, target (b), test month:

| H | predictor | mean predicted | observed | Brier | reliability (miscalibration) | resolution |
|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.108 | 0.120 | 0.0866 | 0.0004 | 0.0180 |
| 1 | frequency | 0.086 | 0.120 | 0.0998 | 0.0017 | 0.0057 |
| 3 | LightGBM | 0.272 | 0.290 | 0.1434 | 0.0013 | 0.0625 |
| 3 | frequency | 0.226 | 0.290 | 0.1737 | 0.0120 | 0.0431 |
| 6 | LightGBM | 0.414 | 0.421 | 0.1414 | 0.0012 | 0.1024 |
| 6 | frequency | 0.369 | 0.421 | 0.1757 | 0.0179 | 0.0851 |

- **The model's probabilities are well calibrated.** Reliability is ≤ 0.0013 at every H, and its mean prediction is
  within 0.02 of the observed rate.
  - At H=6 the lowest bin over-predicts (0.069 predicted vs 0.027 observed).
  - The bins from 0.4 up under-predict by 0.01–0.06.
- **The frequency baseline is the badly calibrated one.** At H=6, predicted 0.35 means observed 0.58, and the
  extremes are too extreme. That's the stale full-history table again.
- Where the model's Brier gain over frequency comes from:
  - H=1: mostly resolution (+0.012 vs +0.001 from calibration);
  - H=6: about half each (calibration +0.017, resolution +0.017).
- It is not "well separated but badly calibrated". If anything, it is the reverse: well calibrated, and at H=6 only
  modestly better separated.

### 10. Feature importance (`results/feature_importance.md`, share of total gain, test-fit model)
- `starts_7d` dominates: **48.5% / 62.6% / 71.8%** for H = 1/3/6. In effect, the oblast's current week of activity
  is a recency-weighted base rate.
- At H=1 the short-term signals matter next: `now` 11.2%, `nb_share_1h` 8.5%, `hour` 7.6%, `share_7d` 6.1%.
- At H=6, `oblast` (7.5%), `freq4w` (6.5%) and `hour` (4.2%) follow.
- Reading: the model is mostly "how busy has this oblast been this week", plus neighbours and current state for the
  next hour. That fits the 23-of-24 vs 13-of-24 pattern above.

### 11. Found / broken / changed along the way
- The LightGBM sklearn wrapper needs scikit-learn → switched to `lgb.train`. `requirements.txt` gains `lightgbm>=4.0`.
- The feature-importance table first aligned the H columns by feature name (NaN cells). Fixed to align by rank.
- My first README draft said the H=6 Brier gain is "mostly calibration". The decomposition says half and half.
  Corrected before commit.
- `scripts/evaluate_baselines.py` and its outputs (`results/baselines_test.*`, `figures/baselines_h6.png`) are
  removed. `scripts/evaluate.py` produces the same baseline columns on the model's rows. Round-2 numbers stay in this
  log and in commit `cc7db72`.
- Shared row/target/split code moved from the round-2 script into `src/dataset.py`. `split` now also returns the
  "before last week" mask used by the validation fit.

### 12. Next (not done)
- Post-switch-only training on the same test month.
- Weekly refits if the test month drifts. One check: the frequency baseline's under-prediction says the level
  drifts; the model's `starts_7d` already tracks it.
- Sunday re-pull (the user does it): re-run `inspect_raw.py`, check for duplicates and outages, then re-run everything.

---

## 2026-10-10 — Round 4: getting Sep 4–5 back; logistic and post-switch comparisons

### 0. Decisions taken
- PR #1 merged. From now on: commit straight to `main`, no PRs, no reminders, no watching the repo.
- CLAUDE.md was edited by the user on GitHub and re-read. It now says:
  - neighbours = the last completed hour;
  - static tables are fitted on train only, while rolling features may use anything already observed by t;
  - 0/1 baselines are reported raw;
  - the test window: if anything shrinks it, ask before running.
- **My mistake in round 3.** I cut the test window from 30 to 22 days (7-day lookback × outage) and only logged it.
  Under the new rule that needs asking first. Asked this round before building anything.
- Agreed approach for the rows after the outage:
  - compute the 7-day features over the observed part of their window, with counts scaled to the full window;
  - "lookback complete" is kept only as a reporting label, not a feature. It is always 1 in training (the only
    outage is in the test month), so a model could never learn from it.
  - Sep 3 stays out, because same-hour-yesterday would point into the outage; identical rows for all predictors
    matter more than one day.
  - **Test = 24 days: Aug 7–28 + Sep 4–5.**
- Sep 4–5 is reported both inside the pooled numbers and separately.
- Also this round: a logistic regression on starts_7d + hour + oblast; LightGBM trained only from 2026-01-01; which
  oblasts are in the lowest reliability bin (look, don't fix).
- README: H=6 stays "not established"; κ stays "unexplained", no speculation.

### 1. Lookback over the outage (`src/features.py`)
- For each window [t−w, t] (6h, 24h, 7d), the part inside a known outage (`OFFICIAL_OUTAGES`) is removed:
  - `share_*` = time under alert / observed time;
  - `starts_*` = starts in the observed part × w / observed time.
- Toy tests:
  - one 2h alert per day with 5 days masked gives exactly the unmasked values (7 starts, share 2/24);
  - extra alerts placed inside the masked days are ignored (7, not 10).
- Where no window touches an outage, which is every training row, the values are bit-identical to before.
- State features: on Sep 4–5 no row's `hours_since_end` or `hours_since_start` points into the outage (0 of 1,152).
  `scripts/evaluate.py` now asserts this on every test row, so a future outage that breaks it fails loudly.
- The split now requires [t−24h, t+H] clear of outages (`EVAL_LOOKBACK`), instead of 7 days.

### 2. A bug I introduced this round and fixed before the results
- Lowering the lookback to 24h also moved the "enough history" condition, so training started on 2022-03-17
  instead of 03-23.
- The first six days then got 7-day features over a window reaching before the data begins, i.e. undercounted.
- Spotted because the feature importances shifted slightly when the model should not have changed.
- **Fixed:** `FEATURE_HISTORY = 7d` in `src/dataset.py`, applied separately from the outage lookback.
- After the fix, training rows are back to 920,448 (H=1) and the full-history LightGBM again uses 116 / 97 / 81
  trees.
- Its Aug 7–28 numbers equal round 3 to the third decimal (within-oblast AUC 0.696 / 0.651 / 0.644), so it is the
  same model. The only change in its pooled numbers is the two added days.

### 3. Sep 4–5 separately (`results/test_table_by_period.md`)
LightGBM, target (b), within-oblast AUC / Brier:

| H | Aug 7–28 | Sep 4–5 | all 24 days |
|---|---|---|---|
| 1 | 0.696 / 0.087 | 0.534 / 0.098 | 0.688 / 0.087 |
| 3 | 0.651 / 0.143 | 0.476 / 0.158 | 0.645 / 0.145 |
| 6 | 0.644 / 0.141 | 0.447 / 0.120 | 0.639 / 0.140 |

**Sep 4–5 look off, and that is not hidden:**
- Within-oblast AUC drops for *every* predictor on those two days, including the frequency baseline, which uses no
  lookback features (H=6: 0.413). So it is not only the scaling.
- **Comparison with August's 2-day windows**, same model, eleven blocks of two days each:
  - H=6: LightGBM's 2-day AUC ranges 0.423–0.654. Sep 4–5's 0.447 is inside that range.
  - H=1: the August blocks range 0.579–0.725. **Sep 4–5's 0.534 is below all of them.** The frequency baseline is
    near its own minimum too (0.466 vs 0.468–0.687), and LightGBM keeps its usual margin over it.
- Calibration on Sep 4–5:
  - H=1: fine (0.141 predicted vs 0.141 observed).
  - **H=6: under-predicts (0.495 vs 0.543)**, against 0.414 vs 0.421 in August.
- Only 20 oblasts have both outcomes in those 48 hours, so within-oblast AUC there is very noisy.
- Two days cannot separate "the 7-day scaling hurts" from "these two days were unusual". Logged as open.

### 4. H=6 per-oblast comparison is unstable
- LightGBM beats the frequency baseline's within-oblast AUC (target b, H=6) in:
  - 13 of 24 oblasts on Aug 7–28 (as in round 3);
  - **18 of 24 on all 24 days**, same model;
  - 11 of 20 on Sep 4–5 alone.
- Two extra days move the count by five. At H=6 it is not evidence either way: the README says "not established",
  with both counts.
- H=1: 23 of 24 on August alone, 24 of 24 pooled. Stable.

### 5. Is LightGBM earning its keep? Logistic regression (`src/logit.py`)
- Plain logistic regression fitted by Newton/IRLS in numpy (no scikit-learn). Inputs: starts_7d (linear),
  24 hour-of-day dummies (Kyiv time) and oblast dummies.
- A 1e-6 ridge term is there only for numerical safety.
- Verified on simulated data: coefficients (−1, 0.8, 0.5) recovered as (−1.007, 0.799, 0.502).
- Converges in 6–8 iterations. The starts_7d coefficient is 0.035 / 0.048 / 0.064 for H = 1/3/6.
- Same split and threshold rule as LightGBM: a validation fit for the last-week threshold, then a test fit on all
  of train.

| H | LightGBM AUC within / Brier | logistic AUC within / Brier | LightGBM wins (oblasts) |
|---|---|---|---|
| 1 | 0.688 / 0.0875 | 0.486 / 0.0971 | 24 of 24 |
| 3 | 0.645 / 0.1446 | 0.483 / 0.1535 | 23 of 24 |
| 6 | 0.639 / 0.1398 | 0.508 / 0.1461 | 22 of 24 |

- **Not within 0.01 AUC: LightGBM is 0.13–0.20 ahead.** The logistic model has essentially no ranking within an
  oblast (≈0.5), but gets within 0.006–0.010 of LightGBM's Brier.
- **Correction of my round-3 reading.** I wrote that the model is "mostly how busy this oblast has been this week",
  based on `starts_7d` holding 48–72% of the gain.
  - starts_7d (with oblast and hour) sets the *level*. That is what Brier mostly rewards, and the logistic model
    gets it too.
  - The *ranking within an oblast* comes from the other features: state, neighbours, interactions.
  - Gain importance measures neither of these directly.

### 6. Full history vs trained from 2026-01-01
- Same features, same protocol; train rows from 2026-01-01 only (125,568 at H=1 instead of 920,448). Trees:
  122 / 158 / 101.

| H | full history AUC within / Brier | from 2026 AUC within / Brier | from-2026 wins (oblasts) |
|---|---|---|---|
| 1 | 0.688 / 0.0875 | 0.648 / 0.0865 | 13 of 24 |
| 3 | 0.645 / 0.1446 | 0.642 / 0.1425 | 15 of 24 |
| 6 | 0.639 / 0.1398 | 0.619 / 0.1389 | 13 of 24 |

- The post-switch fit has slightly better Brier everywhere (it is a bit better calibrated to 2026 levels).
- It has lower mean within-oblast AUC at H=1 and H=6.
- Per oblast it is a coin flip.
- Four years of history neither clearly help nor hurt. Kept full history as the main model.

### 7. Lowest reliability bin (`results/lowest_bin_h6.md`); looked at, not fixed
LightGBM, H=6, predictions below 0.1 on the 24 test days: 3,361 rows, **all from the eight western oblasts**.

| oblast | rows in bin (of 566) | mean predicted | observed |
|---|---|---|---|
| Zakarpatska | 541 | 0.062 | 0.011 |
| Ivano-Frankivska | 539 | 0.063 | 0.011 |
| Lvivska | 533 | 0.064 | 0.011 |
| Volynska | 480 | 0.064 | 0.025 |
| Chernivetska | 424 | 0.073 | 0.028 |
| Ternopilska | 402 | 0.074 | 0.052 |
| Rivnenska | 223 | 0.082 | 0.063 |
| Khmelnytska | 219 | 0.082 | 0.096 |

- Your guess was right.
- The five furthest west get ~0.06–0.07 where 0.01–0.03 happened: the model does not go as low as their test-month
  rate (one new alert in 24 days for Lviv, Ivano-Frankivsk and Zakarpattia).
- Rivne and Khmelnytskyi are roughly right; Khmelnytskyi is slightly under-predicted.

### 8. No-peeking check
- Same 40 origins; 2 of them are on Sep 4–5, so the masked path is exercised.
- 0 mismatches in 6,720 baseline-input values and 0 in 37,440 feature values.
- Both negative controls fire (421 of 421; 161 of 960).
- Training windows close by 2026-08-07, validation-fit windows by 2026-07-31.

### 9. Other changes
- `scripts/evaluate.py` rewritten for the extra predictors and the period split. New outputs:
  - `results/test_table_by_period.md`
  - `results/oblast_wins.md`
  - `results/lowest_bin_h6.md`
- `results/test_table.md` is the pooled 24-day table.
- `scripts/check_no_peeking.py` uses the 24h evaluation lookback for its structural check.
- README:
  - test window = 24 days, with the reason;
  - κ drop stated as unexplained;
  - results table with the logistic and post-switch columns;
  - H=6 "not established" with both counts;
  - the Sep 4–5 caveat;
  - the lowest bin;
  - hand-check recipe updated (13,824 rows; 0.121 / 0.309 / 0.209).

### 10. Next (not done)
- Sep 4–5: two days are not enough to tell whether the scaled 7-day features hurt. If the Sunday re-pull brings
  September data, those rows will have complete lookbacks and the question answers itself.
- Weekly refits if the model drifts over the test window.

---

## 2026-10-10 — Round 5: final pass (re-pull, reproduction, README)

### 0. CLAUDE.md
Pulled `6cca252`. Two new lines:
- never compare western oblasts with volunteer numbers (Lviv/Volyn parser bug);
- rows after the outage use scaled 7-day features and must always be reported separately next to the pooled numbers.

Both were already true of the round-4 outputs. The README now also has a Sep 4–5 table next to the pooled one (§3).

### 1. Re-pull
- `scripts/fetch_data.py` at **2026-10-10 18:58:48 UTC**. Upstream HEAD is still `7ccd436`, the same commit as the
  08:27 pull (upstream's last commit was 05:01 UTC that morning).
- sha256 of both CSVs is identical to `PULL_INFO.md` before the re-pull. Only the pull time in `PULL_INFO.md` changed.
- `scripts/inspect_raw.py`, all unchanged:
  - official ends 2026-09-07 05:28:22 (start) / 05:39:33 (end);
  - 113,845 exact duplicate rows; 185,364 rows after cleaning.
- Outage scan (6h windows with no official message while the volunteer feed has ≥5 starts): the same 18 windows as
  round 1. 17 are the known Aug 29 – Sep 2 outage; the 18th is 2023-03-18 18:00, judged a quiet evening in round 1.
  **No new outage.**
- **The official data did not change, so the test window stays.**

### 2. Reproduction
- Snapshot of `results/` and `figures/` taken before the re-pull (both equal to the round-4 commit).
- Full pipeline from an empty `data/processed/`, in the documented order (8 scripts).
- **`results/` and `figures/` are byte-identical to round 4** (`diff -rq`).
- `check_no_peeking.py`: 0 / 0 mismatches; both negative controls fire.

### 3. One code change, then README
- The README's H=6 "13 of 24 oblasts" (Aug 7–28) came from an ad-hoc check in round 4 and was not in `results/`.
- **Changed:** `scripts/evaluate.py` writes the oblast win counts per period (all / Aug 7–28 / Sep 4–5) into
  `results/oblast_wins.md`. Re-ran it: only `results/oblast_wins.md` differs from round 4; every other result and
  figure is still byte-identical.
- At H=6, LightGBM vs frequency: 13 of 24 (Aug), 18 of 24 (all), 11 of 20 (Sep 4–5).
- README additions:
  - "Results in brief" right after the question: 6 lines, numbers extracted by script from `results/test_table.md`,
    `results/test_table_by_period.md` and `results/oblast_wins.md`;
  - a Sep 4–5 table under the pooled table, generated from `results/test_table_by_period.md`;
  - "News and text data";
  - "Limitations and what we would do next";
  - the re-pull recorded; the status line.
- Cross-check: the pooled README table (18 cells) matches `results/test_table.md`, 0 mismatches.
- **Rounding:** `results/test_table.csv` keeps 4 decimals, and rounding those again to 3 can be off by 0.001 from the
  markdown tables. Example: frequency within-oblast AUC at H=6 is 0.612 in the markdown, 0.613 from the CSV. README
  numbers are copied from the markdown tables, which round once from full precision.
- Caught in my own draft before commit:
  - "frequency is the strongest baseline" is wrong at H=1, where same-hour-yesterday has the higher within-oblast AUC
    (0.525 vs 0.495). Changed to "best of the three on Brier at every H" (0.101 / 0.177 / 0.178 vs yesterday
    0.181 / 0.281 / 0.267 and persistence 0.288 / 0.327 / 0.365).
  - "48 origins per oblast" on Sep 4–5 holds only at H=1. Changed to 43–48.
- **Tension flagged:** the instruction for the brief block asked for the frequency baseline next to the model numbers;
  CLAUDE.md asks for all three baselines. The brief block names frequency, says it is the best baseline on Brier, and
  points to the full tables with all three right below it.

### 4. After this commit
`main` is left alone. Any further experiment goes on a branch.

---

## 2026-10-10 — News experiment (branch `news`), step 1: GDELT events pull

Experiment, not a deliverable. `main` stays as it is; everything here lives on `news`.

### Source scouting
- First attempt: the environment's network policy denied `api.gdeltproject.org`, `data.gdeltproject.org`,
  `wikimedia.org` and `dumps.wikimedia.org`. The user then set network access to full.
- **GDELT DOC API** (keyword timelines; about the last 3 months, per my knowledge, not verified): every request was
  answered with 429 "limit requests to one every 5 seconds". This included a single request after two idle minutes,
  so the shared outbound IP is rate-limited. Depth and resolution could not be checked.
- **Wikipedia:** the per-article pageviews API is daily or monthly only; asking for hourly returns 400. Hourly data
  exists only in whole-Wikipedia dump files, about 55 MB per hour (~120 GB for 3 months).
- **GDELT raw 15-minute files:** reachable, not rate-limited, back past March 2022.
- **Picked (user):** GDELT 2.0 *events* files, 2026-01-01 → 2026-09-07. They are compared against the existing
  "LightGBM from 2026-01-01", so no full-history pull is needed.

### Pull (`scripts/fetch_gdelt_events.py` → `data/news/`)
- Each 15-minute export file is read in memory; only aggregated counts are kept. Raw files are not committed.
- Rows kept: `ActionGeo_CountryCode == "UP"` (event located in Ukraine).
- **CAMEO choice:** conflict = root codes 18 (assault), 19 (fight), 20 (unconventional mass violence). The aerial
  subset (CAMEO 195x, aerial weapons incl. drones) is kept as a column but is too thin to use (median day: 8 events).
- **Timestamp = DATEADDED** (when the record entered GDELT), floored to the hour. **Not** the event date. A sample
  record added 2026-04-15 describes an event dated 2026-03-16.
- Result:
  - 23,999 of 24,000 files (one missing: 2026-05-09 23:xx);
  - 372,499 Ukraine-located events, of which 57,795 are conflict;
  - every record's DATEADDED equals its file's slot (0 mismatches);
  - 9 minutes to pull.
- **Leakage rule** for the model features: for origin t, only records with DATEADDED before t−1h count, the same lag
  as the neighbour features.

### Sanity check (`scripts/check_gdelt_events.py`, `figures/gdelt_weekly.png`)
- **Gaps:** one partial hour (2026-05-09 23:00, 3 of 4 files). No complete hour has zero Ukraine events.
- **Weekly level** co-moves with official alert starts. GDELT conflict goes from ~1,100–1,600/week in Jan–Apr to
  ~1,900–2,300 in Jun–Aug; alert starts from ~300–400 to ~450–550.
- **Daily link is weak:**
  - On the 10 days with all 24 oblasts under alert at some point, GDELT conflict counts were 107–379, against a
    median day of 216. About half are below the median.
  - Spearman correlation with daily alert starts is 0.23–0.28, the same day or the next.
- **Fixed in the plot:** it first marked the partial edge weeks (Jan 1–4, Sep 7) as gaps. Now partial weeks are
  dropped, and only the week with the missing file (May 4) is grey.

### Oblast split: dropped (user decision)
- 72% of conflict events carry an ADM1 code, and the codes map 1:1 onto our units. But:
  - Kyiv City dominates (17,151 events), presumably the capital dateline;
  - there are geocoding errors ("Brovary, Ternopil's'ka Oblast'");
  - western oblasts have 57–240 events in 8 months.
- **National series only.** `gdelt_adm1_names.csv` is kept as the record; the per-region hourly file is git-ignored.

This is a safety commit of step 1 on the experiment branch, by agreement. The one-commit-per-round rule applies to
`main`.

## 2026-10-10 — News experiment, step 2: features, correlation first, then the model

### Features (`src/news.py`)
- Both features are **national** (one value per hour, the same for every oblast). They count conflict events
  (CAMEO 18/19/20) located in Ukraine.
  - `news_24h`: events added to GDELT in [t−25h, t−1h).
  - `news_yesterday`: events added during the last full UTC day that ended by t−1h. For t = 00:00 that is the day
    before yesterday, because yesterday's last hour is not complete by t−1h.
- **Leakage rule:** a record counts at origin t only if its DATEADDED is before t−1h, the same lag as the
  neighbours. The event date is never used.
- The first 25 hours of 2026 (600 train rows) have no full window: NaN, which LightGBM handles. They are not
  dropped, so the rows stay the same. Test rows all have both features.
- The one partial hour (2026-05-09 23:00, 3 of 4 files) is left unscaled. It touches 24 hourly windows and one day.

### Correlation with what the model already has (`scripts/news_correlation.py` → `results/news/correlation.md`)
Written down before the model was run. Train rows of "LightGBM from 2026-01-01", H=1: 124,968 rows,
2026-01-02 01:00 → 08-06 23:00.

| | starts_7d | share_7d | starts_24h |
|---|---|---|---|
| `news_24h`, within oblast (Pearson / Spearman) | 0.071 / 0.053 | 0.076 / 0.073 | 0.069 / 0.079 |
| `news_24h`, national per hour (Pearson / Spearman) | 0.244 / 0.250 | 0.204 / 0.238 | 0.182 / 0.238 |
| `news_yesterday`, national (Pearson / Spearman) | 0.222 / 0.232 | 0.187 / 0.214 | 0.122 / 0.175 |

- Pooled correlation over all rows is 0.01–0.06.
- **The user's guess (high correlation: news is a slower copy of starts_7d) does not hold on these numbers.**
  The national level co-moves weakly (about 0.2–0.25), and within an oblast there is almost no linear or rank
  relation.
- Low correlation does not mean the feature helps. Mostly it says the series carries something different, which
  may be noise. The daily link to alert starts was already weak in step 1 (Spearman 0.23–0.28).

### The model comparison (`scripts/evaluate_news.py` → `results/news/`)
**Setup.**
- "LightGBM from 2026-01-01" with and without `news_24h` + `news_yesterday`.
- Same rows, split, 2026 training rows (125,568 / 125,520 / 125,448 for H=1/3/6, 600 of them with NaN news),
  same validation fit and last-week threshold as main.
- Next to them: main's full-history LightGBM (no news, since there is no news history before 2026) and the three
  baselines.
- **Reproduction check:** the 90 rows shared with main's `results/test_table.csv` are identical in all 720
  compared values. So the only difference between the two 2026 models is the two columns.

**Target (b), within-oblast AUC / Brier, all 24 days** (from `results/news/test_table.md`):
- H=1: 0.621 / 0.087 with news vs 0.648 / 0.087 without.
- H=3: 0.578 / 0.144 vs 0.642 / 0.142.
- H=6: 0.616 / 0.140 vs 0.619 / 0.139.
- Baselines are unchanged from main. The best on Brier is still frequency: 0.101 / 0.177 / 0.178.

**Sep 4–5 alone:**
- H=1: 0.588 / 0.097 vs 0.555 / 0.096.
- H=3: 0.517 / 0.159 vs 0.471 / 0.159.
- H=6: 0.458 / 0.125 vs 0.440 / 0.122.
- News is higher on AUC at every H here, but this is 48 origins per oblast.

**Paired, day-block bootstrap** (1000 resamples of the 24 test days, seed 0, `results/news/news_vs_no_news.md`).
Figures are with news minus without, point value and 95% interval.

| H | AUC difference | Brier difference |
|---|---|---|
| 1 | −0.0272 [−0.0559, 0.0238] | +0.0002 [−0.0001, 0.0005] |
| 3 | −0.0638 [−0.1067, 0.0267] | +0.0014 [0.0005, 0.0024] |
| 6 | −0.0023 [−0.0258, 0.0267] | +0.0011 [0.0002, 0.0019] |

- News has the higher AUC in 12 / 11 / 12 of 24 oblasts.
- I added the bootstrap because 24 days are too few to read a 0.003 difference by eye. It is a sanity check, not
  a test I would put weight on.

**Importance and early stopping:**
- The news columns rank 9–10 (H=1), 7 and 10 (H=3), 4 and 8 (H=6) of 16 by gain, with 2–4% of the gain each,
  but 10–17% of the splits.
- Early stopping on the last train week stops sooner with news: 80 / 64 / 60 trees vs 122 / 158 / 101.
- So the trees split on the news columns often, for little gain, and the validation loss turns up sooner. That
  pattern is consistent with a national time series being used to tell training periods apart. I did not test
  this further.

**Verdict: news does not help.**
- AUC is lower at H=1 and H=3 and level at H=6, with all intervals including zero.
- Brier is slightly worse, with the interval above zero at H=3 and H=6.
- Not merged, by the rule agreed up front. The branch stays.

### Leakage check for the news columns (`scripts/check_no_peeking_news.py`, `results/news/no_peeking.txt`)
- Same 40 origins as `check_no_peeking.py`. For each one, the GDELT buckets are cut to records added before
  t−1h, and both columns are recomputed two ways: with `src/news.py` and by a direct sum.
  - Result: 0 mismatches in 80 values, both ways.
- The columns are identical across oblasts at every t, as a national series should be.
- **Negative control:** a 24h window ending at t instead of t−1h. It mismatches at 40 of 40 origins, which is
  every origin that had events in [t−1h, t).
- **Publication time:** I fetched the Last-Modified header of four GDELT files (Jan 15, May 9, Aug 20, Sep 5).
  Each was written 11–12 minutes *before* its slot timestamp, so a record's DATEADDED is not earlier than its
  publication. With the t−1h rule, the newest record used was public at least about an hour before t.

### Housekeeping
- `src/news.py`: the grid check first used `.asi8` in nanoseconds. pandas 3 parses these timestamps in
  microseconds, so a complete grid failed the check. The check now compares Timedeltas.
- README numbers were checked against `results/news`:
  - Checking against the 4-dp CSV first gave 5 "mismatches". That is the known double rounding again: e.g.
    Brier 0.0865 in the CSV is 0.087 in the md table, which rounds once from full precision. The README is
    copied from the md tables, and all 36 cells match those.
  - I dropped the event count (57,795) from the README because it is not in `results/`. It stays here and in
    the step-1 entry.
- Re-ran correlation, evaluation and the leakage check from scratch: `results/news/` is byte-identical (`diff -r`).
- `main` is untouched.
- **Proposed for main, not applied (waiting for the user):** two sentences in main's README "News and text data"
  section, in place of "No text experiment has been run":
  > We tried one news feature in the 2026-only LightGBM: the national hourly count of GDELT conflict events
  > located in Ukraine, timed by when each record was added to GDELT and lagged one hour. It did not improve
  > within-oblast AUC or Brier at any H; the numbers, next to the three baselines, are on branch `news`.
- The proposal has no numbers on purpose. A model number on main without its baselines would break the README
  rule, and the full table belongs on the branch.

### Follow-up (user): the "calendar" reading goes in the README; pointer on main
- The user asked to put the calendar explanation in the README news section ("the most useful sentence in the
  whole experiment"). It is there now, with its two facts and a note that it is a reading, not tested:
  - many splits for little gain;
  - early stopping comes sooner.
- The tree counts were only printed to stdout. `scripts/evaluate_news.py` now also writes them to
  `results/news/news_vs_no_news.md`, so the README number can be copied from `results/`:
  - with news: 80 / 64 / 60;
  - 2026 without news: 122 / 158 / 101;
  - full history: 116 / 97 / 81.
- Re-ran it: apart from the new trees table, `results/news/` is unchanged.
- The weekly GDELT levels behind "the level drifts" are not in `results/`, so the README points at
  `figures/gdelt_weekly.png` instead of quoting them.
- The user approved the two-sentence pointer on main, with a GitHub link to this branch, together with the
  ground-rules wording fix there. That is one commit on main, after which main is frozen. Main is then merged
  into this branch so `news` stays "main + the experiment".
## 2026-10-10 — Round 6 (main): pointer to the news experiment, ground-rules wording

This is the one commit on `main` the user approved after round 5. After it, `main` is frozen.

### News experiment (lives on branch `news`, not merged)
- **What was tried:** two national features on "LightGBM from 2026-01-01": the hourly count of GDELT conflict events
  (CAMEO 18/19/20) located in Ukraine, over 24h and over the previous full day.
  - **Leakage rule:** timed by when each record was added to GDELT and lagged one hour.
  - Same rows, split and thresholds as main, with the three baselines in the same rows.
- **Result:** it did not help.
  - Within-oblast AUC is lower at H=1 and H=3 and level at H=6.
  - Brier is slightly worse.
  - The trees most likely use the drifting national count as a calendar: many splits for little gain, and early
    stopping comes sooner. This is untested.
- The full write-up, numbers and log are in the branch's README ("News and text data") and its PROCESS_LOG.
  Branch commits: 80847e3, 0fe68ab, e67cdc7.
- **README:** "No text experiment has been run" is replaced by two sentences that point to the branch, with a link
  to its README section on GitHub.
  - Following the README rule, they quote no model numbers, since a model number on main would need its baselines
    next to it.
  - The first line of that section ("We did not use … any news or Telegram text") stays. It is still true of the
    model on main.

### Ground rules block in the README
- The README still said "Every aggregate is computed on the training period only". That has been stale since
  round 3, when the rolling features (share/starts windows, freq4w) arrived: they use everything observed by t,
  including test-period history.
- Reworded to match `CLAUDE.md`:
  - every feature for origin t uses only what is known at t;
  - neighbours use the last completed hour [t−1h, t);
  - static tables (the frequency baseline) are fitted on train only;
  - rolling features may use anything already observed by t.
- No code or result changed on `main`. The round-5 outputs stand as committed.

---

## 2026-10-10 — Round 7 (main): quick start in the README

The user asked for this one commit on `main`: README only, no code changes.

### What the block says
- It sits right after "Results in brief": clone, venv, `pip install -r requirements.txt`, then the commands that
  rewrite every tracked file in `results/` and `figures/`, with timings.
- **Only two commands are needed:**
  - `plot_weekly.py` writes `figures/alerts_per_week.png/.csv`. It reads `data/raw` directly.
  - `evaluate.py` writes the 9 files in `results/` plus `figures/model_vs_baselines_h6.png` and
    `figures/reliability_h6.png`. It builds its rows from `data/raw` and does not need the panels.
  - `build_panel.py`, `inspect_raw.py` and `hand_checks.py` write nothing tracked. They stay in "Run order",
    which is unchanged.
- `check_no_peeking.py` is listed as optional. It prints the leakage check and writes nothing.
- One line says the data snapshot is in the repo, so nothing needs to be downloaded.

### How it was tested
- Each Python version (3.11.17, 3.12.3, 3.13.16) got a fresh `git clone` of `main` from GitHub (4cf73fb) in a new
  scratch folder, not the working tree, plus a new venv and `pip install -r requirements.txt`.
- The installed packages were pandas 3.0.6, matplotlib 3.11.2 and lightgbm 4.7.0 everywhere. numpy was 2.5.4 on
  3.12/3.13 and 2.4.6 on 3.11.
- Then the three commands ran in order, on a 4-core container:

  | step | 3.13 | 3.12 | 3.11 |
  |---|---|---|---|
  | pip install | 32 s | 29 s | 31 s |
  | `plot_weekly.py` | 12 s | 10 s | 11 s |
  | `evaluate.py` | 84 s | 84 s | 84 s |
  | `check_no_peeking.py` | 22 s | 24 s | 23 s |

- **Result:**
  - Every run exited 0, and every leakage-check assert passed.
  - On all three versions, all 13 tracked files in `results/` and `figures/` were rewritten after the clone.
  - `git status` was empty afterwards, so they are byte-identical to the committed ones.
- The README rounds the timings to ~30 s / ~10 s / ~1.5 min / ~25 s.

### Housekeeping
- `data/news/gdelt_conflict_adm1_hourly.csv` showed up as untracked while `main` was checked out. It is the
  per-region GDELT file from the experiment: git-ignored on `news`, but not on `main`.
- I moved it out of the working tree rather than touch `.gitignore` on `main`, because this round is README only.
  `scripts/fetch_gdelt_events.py` on `news` regenerates it.

---

## 2026-10-10 — Round 8 (main): usability (quick start fixes, quiet evaluate, predict.py, logit warnings)

A usability round, not a model round. Everything tracked in `results/` and `figures/` is byte-identical to round 7.
The user's input came from running the quick start on their Mac: Python 3.9 from Xcode, numpy 2.0.2, pandas 2.3.3,
lightgbm 4.6.0, arm64.

### Before the round: main had changed
- The user merged `news` into main through PR #2 (53f50d0), then updated the Status line (7216588). They confirmed
  the merge was on purpose: one place to read is simpler for a reviewer.
- So `main` now carries the news experiment in full: `results/news/`, `figures/gdelt_weekly.png`, `data/news/`,
  the news scripts and the long README section.
- Two things on main were therefore out of date, and both were fixed this round (see "README" below):
  - the README still said "branch `news` only, not merged";
  - the round-7 quick start claimed that two commands reproduce all of `results/` and `figures/`.

### 1. The logit warnings: the user's sigmoid guess was wrong
- **Report:** on macOS, `src/logit.py` printed "divide by zero / overflow / invalid value encountered in matmul" at
  lines 22, 23, 24 and 33, for every H. The results were identical to ours (0.688 / 0.087 at H=1, logistic coef
  0.035).
- **The user guessed the sigmoid was overflowing on large negative logits. The user was wrong**, and said so after
  seeing the evidence:
  - All four lines are matrix products, and lines 23 and 24 contain no `exp` at all.
  - A sigmoid overflow would be reported as "overflow encountered in exp".
  - The logits on train and test rows range from −4.74 to 4.45 at most (H=1: −4.74..0.52, H=3: −3.70..2.54,
    H=6: −2.89..4.45). `exp` overflows only beyond about 709.
  - The same code prints no warnings on Linux under Python 3.11, 3.12 and 3.13.
- **Diagnosis:** numpy's Accelerate BLAS on Apple silicon can leave stray floating-point flags after a correct
  matrix product. numpy then reports them as warnings. The numpy 2.3.1 release notes list a fix for Accelerate
  runtime warnings, but that needs Python 3.11 or newer, and the user is on 3.9.
- **Agreed fix:** `src/logit.py` routes its four matrix products through `_matmul`:
  - a narrow `np.errstate` around the product only;
  - an immediate `FloatingPointError` if the product contains inf or NaN, so a real numerical problem still stops
    the run;
  - the sigmoid's `exp` stays outside the guard, so a real overflow there would still warn.
- The arithmetic is unchanged and the results are byte-identical. I can't reproduce the macOS warnings here, so
  whether they are gone on the user's Mac is confirmed by the user, not by me.

### 2. `evaluate.py`: quiet by default
- **Default output:**
  - one progress line per step, with elapsed seconds: rows, features, and one line per H with tree counts and row
    counts;
  - one "wrote …" line per file in `results/` and `figures/`, plus one line for `models/`;
  - a short summary: target (b), within-oblast AUC / Brier, LightGBM next to the train-frequency baseline, on all
    24 days and on Sep 4–5 separately. It points to `results/test_table.md` for all three baselines, like the
    README brief block.
- `--verbose` also prints every table, as before.
- **New output, `models/`** (git-ignored; written for `predict.py`):
  - the three full-history LightGBM test fits, one per H (`lgbm_b_start_h{H}.txt`);
  - the train-frequency tables for target (b) (`frequency_b_start_h{H}.csv`);
  - `info.json`, with the data range, the start of the test window, the feature list and the tree counts.
- `evaluate_news.py` now behaves the same way and runs the whole news chain, so one optional quick-start line
  rebuilds every tracked news output:
  - `news_correlation.py`;
  - the comparison itself;
  - `check_no_peeking_news.py`, which now writes `results/news/no_peeking.txt` itself (it used to be captured
    with `tee`);
  - the weekly plot from `check_gdelt_events.py`, which builds the official hourly panel if
    `data/processed/` lacks it, exactly as `build_panel.py` would. That panel is the only reason
    `gdelt_weekly.png` needed `build_panel.py` first.
  - The note inside `results/news/test_table.md` still says "News experiment (branch news)". It stays, because
    `results/` must stay byte-identical.

### 3. `scripts/predict.py`
- **What it does:** `--at <hour> --oblast <name>`, or `--all`, prints for H = 1, 3, 6:
  - the model's probability of a new alert in (t, t+H];
  - next to it the three baselines (same as now, same hour yesterday, train frequency), because `CLAUDE.md` puts
    every model number next to them;
  - what actually happened;
  - for one oblast, also the time of the next new alert.
- **Inputs:** recomputed from `known_at(official, t)`: rows that had started by t, with any end after t unknown.
  This is the truncation `check_no_peeking.py` validates. "Happened" comes from the full data. It is "n/a" after
  the end of the data, or when (t, t+H] touches the outage.
- **Times:** UTC by default; an offset such as `+03:00` is accepted; times are rounded down to the hour.
  - Parsing is strict ISO, so "05.09.2026" is rejected instead of being read as 9 May.
  - An empty input gets the "Cannot read --at" message.
  - Allowed range: 2022-03-16 00:00 → 2026-09-05 23:00 UTC.
- **Status line:**
  - Every hour before 2026-08-07 00:00 is marked "TRAINING PERIOD … not forecasts" (see the review below).
  - After the end of training, it says whether the hour is a test row for every H, for some H (naming them), or
    for none.
  - Separate notes cover an hour inside the outage, a last 24 hours that overlap it, a 7-day lookback that
    overlaps it ("as on Sep 4–5"), and the first 7 days of data.
- **Oblast names:**
  - a name without "oblast", in any case, or a unique start of one;
  - "Kyiv" alone is rejected as ambiguous (Kyiv City or Kyivska), and an empty name is rejected;
  - Luhansk gets its own message: excluded, permanent alert.
- **Missing models:** it says "Run `python scripts/evaluate.py` first". If `models/` comes from another data
  snapshot or another feature list, it asks for a re-run.
- **Verified** (scratch script, not committed):
  - the saved models reproduce the test-table numbers for every H;
  - at H=1, the saved model's test predictions are identical to a fresh deterministic refit;
  - `predict.forecast()` at 76 origins, compared with the full-data pipeline of `evaluate.py`:
    - origins: 40 test hours (the `check_no_peeking.py` sample), 20 training hours, and 16 edge hours (the
      outage, Sep 3, the hours just before the end of training, the first month of data, the end of the data);
    - 1,824 oblast rows × 3 H;
    - **0 mismatches** in probabilities (exact equality), "now", same hour yesterday, train frequency and
      "happened";
    - n/a appears only where the window passes the end of the data or touches the outage.
- **Bug found by this check, fixed in `src/features.py`:**
  - On truncated data, an oblast with no alert in the last 32 days has no episodes. `_own` and
    `_neighbour_inputs` then indexed an empty array (IndexError at a training hour).
  - The full-data pipeline never meets an empty oblast, so no result changed.
  - The fix: `_at(a, i)` returns `a[i]` unchanged when the array is not empty.
  - `check_no_peeking.py` still passes, and `results/` is byte-identical.
- **Also fixed during CLI testing:**
  - a name left over from the refactor crashed the next-alert line;
  - `predict.py … | head` now exits quietly instead of raising a BrokenPipeError.

### 4. README
- **Quick start:**
  - a Windows activate line;
  - `brew install libomp` for macOS (without it, `import lightgbm` crashes, as the user found);
  - an optional `evaluate_news.py` line with its time;
  - `evaluate.py` now also writes `models/`;
  - the data line covers both snapshots, and says `fetch_data.py` / `fetch_gdelt_events.py` only re-pull and need
    network;
  - Python 3.9 is listed from the user's macOS run (every number matched), next to my own fresh-clone tests below.
- **Usage section (new):**
  - `predict.py` examples (one oblast in UTC, the same hour in Kyiv time, `--all`) and what the output contains;
  - the `--verbose` flags of `evaluate.py` and `evaluate_news.py`.
  - No example output: its probabilities are not copied from `results/`.
- **News wording:**
  - the Status line now reads rounds 1–8, with the news experiment merged as a documented negative result;
  - the "Branch `news`" line became a "News experiment" line;
  - the section heading, the verdict bullet and the Run order / Layout comments no longer say "branch only" or
    "not merged";
  - the first sentence of the section now says the main model uses no text.
- **Run order:** gained the `predict.py` line, and a note that `evaluate_news.py` runs the news steps.

### Review
- **Setup:** a review workflow with four independent read-only reviewers, one lens each:
  - leakage and correctness of `predict.py`;
  - unchanged computations, plus Python 3.9 / pandas 2 compatibility;
  - README and log against `CLAUDE.md`;
  - a hostile command-line user.
- Each reviewer's findings then went to a separate skeptic who tried to refute them.
- **Confirmed and fixed:**
  - **The first month of data gave the wrong model numbers in `predict.py`.** Its feature grid reached back before
    2022-03-16, so `freq4w` counted pre-data hours as "no alert" instead of skipping them. Model probabilities
    were off by up to 0.19 at origins from 2022-03-16 to 04-12, all of them training hours. The grid now starts no
    earlier than the data. Those hours are in the 76-origin check above, with 0 mismatches.
  - **"PARTLY TRAINING" was misleading.** For the hours just before the cutoff, it implied the other horizons were
    clean forecasts, but the training labels of neighbouring rows already covered their outcome. The first week
    of data was not marked as training at all. Every hour before 2026-08-07 is now TRAINING PERIOD, which is what
    the README says.
  - **"Outside the 24-day test window" was printed for hours whose H=1 (and H=3) rows are scored test rows**
    (Aug 28 and Sep 5, 19:00–23:00). Test membership is now reported per H.
  - **Sep 3 hours were told their inputs were "as on Sep 4–5".** In fact their 6h/24h windows sit in the outage,
    and `hours_since_end` can point inside it. They now get their own warning.
  - **Wrong outage wording.** The outage was printed with an exclusive end ("..2026-09-03"), and the message said
    "no alert data" although the feed has rows on Aug 29 before 05:00. It now reads "2026-08-29..09-02, masked …
    missing or incomplete".
  - **Bad input crashed or was silently misread.** `--oblast ""` silently printed Cherkaska oblast. `--at ""`
    crashed with a traceback. Day-first dates were read month-first.
  - **The `evaluate.py` summary showed Sep 4–5 against the frequency baseline only, but same hour yesterday has the
    higher within-oblast AUC than LightGBM there at every H.** The summary keeps the layout the user asked for and
    adds a computed note wherever any baseline beats the model on AUC. `evaluate_news.py` gets the same note. The
    pointers now name the by-period tables too.
  - **`requirements.txt` allowed pandas 2.0, but `md_table` uses `DataFrame.map` (pandas 2.1+).** This was older
    than round 8: `evaluate.py` would crash after fitting. The floor is now `pandas>=2.1`, which the reviewer
    checked to be byte-identical on 2.1.4.
- **Found by my own Python 3.9 / pandas 2.3.3 run:** `news_correlation.py`'s `groupby().apply()` printed a
  FutureWarning per correlation. Selecting the two columns first removes it; `correlation.md` is identical on
  pandas 2.3.3 and on 3.
- **Refuted or left as is:**
  - **Windows.** The quick start is a bash block: `&&` fails in PowerShell 5.1, and `#` is not a comment in cmd.
    The skeptic called this presentation, not a bug, but a one-line Windows note was added anyway.
  - **"happened" shows n/a for longer H even when a shorter H already says yes.** Refuted: n/a marks windows the
    evaluation also leaves unscored. A legend line now explains it.
- **Left as is, needs the user (the requests conflict):** `results/news/test_table.md` line 1 still says
  "News experiment (branch news)" and "reproduces results/test_table.csv on main". Removing it would change a file
  in `results/`, and the round requires `results/` to stay byte-identical. That requirement wins until the user
  decides.
- **Not changed, raised with the user:** the README brief block's "Sep 4–5 alone" line has the same blind spot as
  the old summary (frequency only, while same hour yesterday has the higher AUC there). The user approved that
  block as is in round 5.

### Accident during this round (repaired, nothing pushed)
- I appended this log entry with an unquoted shell heredoc, so bash ran the backtick-quoted names in the text as
  commands.
- Almost all of them failed harmlessly with "command not found". But `pandas>=2.1` created an empty file named
  `=2.1` in the repo root, and an outdated draft of this entry was appended.
- Both went into a local commit that was never pushed.
- I checked the rest of the filesystem for files changed in that minute: only caches had changed. I then deleted
  the stray file, restored `PROCESS_LOG.md` to its pre-round state, re-applied the entry with a quoted heredoc,
  and amended the local commit.

### Fresh-clone tests
- **Setup:** I committed locally, then for each Python version made a `git clone` of that commit into a new
  scratch folder, created a new venv and ran `pip install -r requirements.txt`. Then, in order:
  - `predict.py` before any model exists: exit 1, with "run evaluate.py first";
  - `plot_weekly.py`, `evaluate.py`, `evaluate_news.py`, `check_no_peeking.py`;
  - `predict.py` for one oblast, `--all`, and a training hour;
  - then `git status`.
- The four runs were sequential on an otherwise idle 4-core container. Times in seconds:

  | step | 3.9.25 | 3.11.17 | 3.12.3 | 3.13.16 |
  |---|---|---|---|---|
  | pip install | 22 | 27 | 31 | 21 |
  | `plot_weekly.py` | 9 | 8 | 11 | 11 |
  | `evaluate.py` | 80 | 82 | 82 | 80 |
  | `evaluate_news.py` (incl. building the panel) | 111 | 106 | 112 | 110 |
  | `check_no_peeking.py` | 22 | 23 | 25 | 25 |
  | `predict.py` (each call) | 4–5 | 4–5 | 4–5 | 4–5 |

- **Packages installed:**
  - Python 3.9: pandas 2.3.3, numpy 2.0.2, matplotlib 3.9.4, lightgbm 4.6.0 (the user's Mac stack, apart from
    matplotlib);
  - Python 3.11–3.13: pandas 3.0.6, numpy 2.4.6 / 2.5.4, matplotlib 3.11.2, lightgbm 4.7.0.
- **Result:**
  - Every step exited 0, and every leakage-check assert passed.
  - No step printed a warning: 0 lines matching "warning" in any output, so the quiet output is clean on
    pandas 2 and 3.
  - All 21 tracked files in `results/` and `figures/`, including `results/news/` and `gdelt_weekly.png`, were
    rewritten after the clone.
  - **Python 3.11, 3.12, 3.13:** `git status` empty, so all 21 are byte-identical.
  - **Python 3.9:** all 16 files in `results/` and `alerts_per_week.csv` are byte-identical. The four PNGs differ:
    matplotlib 3.9.4 lays out the tight bounding box a few pixels differently (for example 1021×1530 vs
    1026×1530). The tables they are drawn from are identical.
- The README quick start now lists `evaluate_news.py` at ~2 min, and the tested versions as above.
- The `requirements.txt` comment says the same.

---

## 2026-10-11 — Round 9 (main): caption and brief-block note; main is done

**The user's Mac run of round 8** (Python 3.9, numpy 2.0.2, pandas 2.3.3, lightgbm 4.6.0, arm64):
- No warnings at all now, and the `evaluate.py` output fits on one screen.
- `predict.py --at "2026-09-05 14:00" --oblast Kyivska` gives:
  - 0.075 / 0.451 / 0.703 for H = 1 / 3 / 6;
  - under alert at that moment;
  - no new alert in the window;
  - the next new alert 7h26 later.
- Kharkivska gives 0.505 at H=1, and an alert did start.
- These match the output here, so the `_matmul` guard is confirmed on Apple silicon.

**Changes this round** (the user approved both):
1. **The `results/news/test_table.md` caption.**
   - The caption is generated by `scripts/evaluate_news.py`, so editing only the results file would have been
     undone by the next run, and the quick start's byte-identical claim would have broken. The user chose to
     change the generator string as well.
   - "News experiment (branch news)." became "News experiment (merged into main as a documented negative
     result).", and "... reproduces results/test_table.csv on main exactly" became "... exactly".
   - Re-running `evaluate_news.py` changed line 1 of that file only. Every other file in `results/` and
     `figures/` was rewritten byte-identically, and the reproduction check against `results/test_table.csv`
     still shows 0 differences.
   - This is a deliberate text change in one results file; no number changed.
2. **README brief block.** The "Sep 4–5 alone" bullet now ends with the same note the `evaluate.py` summary
   prints: "Note: on Sep 4–5, same hour yesterday has a higher within-oblast AUC than LightGBM at H = 1, 3, 6."
   This is true in `results/test_table_by_period.md`: same hour yesterday 0.538 / 0.519 / 0.501, LightGBM
   0.534 / 0.476 / 0.447.

**Scope.** Files changed: `README.md`, `results/news/test_table.md`, `scripts/evaluate_news.py` (one string) and
this log. The user agreed to all four instead of "README and the results file only". After this commit, main is
done.

---

## 2026-10-11 — Telegram experiment (branch `telegram`, cut from main at f102a89; main untouched)

Experiment, not a deliverable. Question: do the Air Force channel's public threat posts help the 2026 model?
Compared against "LightGBM from 2026-01-01", with and without the new columns. Time limit: two hours of building
after the pull ended (14:41 UTC), so until 16:41; everything below was finished before that.

### Scouting (about 10 of 15 minutes, nothing built)
- I had not done any scouting before the usability rounds. The session transcript held no earlier message about it,
  so I worked from the five questions in the user's message.
- `t.me/s/kpszsu` returns 20 posts per page. `?before=<id>` pages back to post 1 (2019-02-11), but the channel only
  gets dense from late February 2022 (post ~100).
- Post rate: about 40 a day in 2024, 60–75 in 2025, 100 in spring 2026, 220 in early September, 245 over the last
  month before the pull.
- Cost estimate: 2026 only (posts 51283..77124) is about 1,300 pages; the full alert history is about 3,850 pages
  (2.8–5 h). By the user's rule (over an hour: 2026 only) the user chose 2026 only, against
  "LightGBM from 2026-01-01".
- Every sampled post was a short threat report, e.g. "БпЛА на Харків з півночі". This raised the question of
  leakage, which the user settled (see below).

### Decisions by the user
- **Leakage rule:** public posts are fine as long as only posts published before t are used, so post time
  strictly < t, with no 1h lag ("too careful for GDELT"). To show that the gain does not ride on the seconds
  between a post and a siren, everything is also run with posts < t − 15 min, and both are reported.
  The 15-minute lag shifts the windows back by 15 minutes. `tg_min_since` is still measured to t.
- **Per oblast, not national**, because the post rate more than doubles over 2026 and a national count would
  become a calendar again, like GDELT's.
- **Parser:** word starts with Ukrainian declensions and main cities, tested against the upstream substring bug
  (podilskyi to Lviv, pryluky to Volyn), then a hand check of 50 random posts before any model.
  The user read the 50 and the trap posts and approved the parser.
- **Features and flags:** see the changes after the check.
- **Limitations to write down:** deleted posts are invisible; edited posts keep their original time but the text
  may have changed later.
- **Safety commits are fine on the experiment branch** (the user's standing preference); the final commit is the
  one that matters.

### The pull (`scripts/fetch_telegram_kpszsu.py`)
- Sequential, 1.75 s pause between requests, retry with doubling backoff on connection resets.
- Range: from 2025-12-31 00:00 UTC (24 hours of lookback for the first rows of 2026) to the posts of 2026-09-08.
- Run: 13:30 → 14:41 UTC, 1,298 pages, 4,256 s, so 3.3 s a page. That is 44 connection resets, about one in 30
  requests; all were fixed by the retry. No 429 and no Retry-After.
- Result: 25,949 posts, ids 51138..77124, with 38 ids missing inside the range (0.15%: deleted or hidden), 602
  marked edited (2.3%). Kept: id, UTC post time, edited flag, text. The raw pages are cached gzipped and
  git-ignored; a rerun resumes from the cache.
- `data/telegram/kpszsu_posts.csv` (4.5 MB) is committed; the posts are public.
- The first post of the file is at 00:07 on 2025-12-31, so the coverage check uses 2025-12-31 00:00, the start of
  the pull. My first version used the first post's time and failed by 7 minutes.

### The parser (`src/telegram_oblasts.py`, `scripts/test_telegram_parser.py`)
- A pattern fires only at the start of a word. Hyphenated and multi-word names are matched first as whole
  phrases and blanked out, so the halves cannot fire elsewhere: Кам'янець-Подільський is Khmelnytska (not
  Vinnytska), Переяслав-Хмельницький is Kyivska (not Khmelnytska). Other hyphens become spaces.
- Ambiguous names that exist in several oblasts are left out (Тростянець, Первомайськ, Золочів, Ямпіль,
  Олександрівка, ...). "Поділ…" alone maps to nothing, since Podilskyi districts and the town Podilsk exist in
  several oblasts. Kyiv city and Kyiv oblast are told apart by word form (Київ / Київщина); Славутич is Kyivska
  (administratively), and "славут" cannot fire inside it.
- Found while testing on real posts, and fixed:
  - Genitive alternations i/o: Борисполя, Обухова, Ірпеня, Гостомеля, Ріпок.
  - Dropped apostrophes: "Камянське".
  - Contracted forms: Вінничині, Хмельничин, Запорізька.
- Tests: 56 oblast cases (including both upstream bug cases) and 17 threat-flag cases; the parser knows exactly
  the 24 units of the alert data.
- The user's review of the 50 random posts and of every post containing 'поділ', 'прилуц', 'луцьк', 'київ',
  'дніпр', 'хмельницьк' and 'франківськ': every oblast was right. In particular Кам'янець-Подільський is Khmelnytska,
  Подільський район goes to Odesa through "Одещина", Прилуцький район goes to Chernihiv, and nothing goes to
  Lviv or Volyn.
- 88.9% of the posts name at least one oblast. The 11.1% that name none are mostly nationwide bulletins ("Загроза
  застосування балістичного озброєння з півночі").

### Flaws found by reading the posts, before the user's check (all fixed)
- 125 of the 135 "Відбій загрози …" (all-clear) posts set a threat flag. All-clear sentences are now removed before
  matching, so they count as neither a mention nor a threat. A mixed post keeps its real threat part.
- Cruise missiles are written "КР" in this channel (104 posts), which the first cruise pattern missed.
  Loitering munitions ("Бандероль", 163 posts) were not counted as drones.
- Every post over 300 characters was dropped from the flags as a "summary", which wrongly dropped real multi-region
  drone reports. Only the nightly "ЗБИТО/ПОДАВЛЕНО" tallies and "знищено понад" / "Протягом …" period totals are
  now excluded (273 posts).
- At the user's check, two more things: posts 54390 ("Ракета … вектор – Київ") and 55829 ("Швидкісні цілі") had no
  flag, and 7 of the 50 were КАБ or tactical aviation with none.

### Flag set, as decided by the user after the check
- **Dropped** `tg_drone`: with the fixes it was 1 in 97.9% of the 2026 oblast-hours (124 of 5,952 hours had no drone
  post in the 3 hours before). The oblast mentions already carry the drone signal.
- **Dropped** `tg_cruise` as its own column: 1 in 2.4% of hours.
- **Kept** `tg_ballistic`: балісти*, іскандер, кинджал, циркон.
- **New** `tg_missile` (any missile): КР, крилат*, ракет*, швидкісн* ціл*, кинджал.
- **New** `tg_kab` (glide bombs / tactical aviation): КАБ, керован* авіабомб* (also "авіаційних бомб"), тактичн* авіац*.
  I followed the user's lists literally: калібр, Х-nnn and Ту-nn are not in the missile pattern. They are rare
  (39, 99 and 14 posts).
- **Denominator of the 6h share:** only posts that name at least one oblast. 720 oblast-hours have no such post in
  the 6 hours and get NaN.
- Prevalence, lag 0 (`results/telegram/flag_prevalence.md`): ballistic 4.5% of posts / 26.3% of oblast-hours;
  missile 6.3% / 26.8%; kab 21.2% / 79.7%. So the kab flag still varies little (it is 0 in about one hour in five).
- 1,276 posts say "ракет*" and 604 "швидкісн* ціл*", and these are covered by the missile flag now. Not covered by
  any flag: the glide-bomb family beyond the patterns above, and unspecified "Баражуючі боєприпаси" go to
  nothing (they are drone-like and were counted by the dropped drone flag only).

### Features (`src/telegram_features.py`): 7 columns
`tg_m1h`, `tg_m3h` (0/1, oblast named in the last 1h / 3h), `tg_share6h`, `tg_min_since` (minutes since last
named, capped at 24h), `tg_ballistic`, `tg_missile`, `tg_kab` (national 0/1 in the last 3h). Windows are [e − w, e)
with e = t − lag. No raw national counts.

### Leakage check (`scripts/check_no_peeking_telegram.py`, `results/telegram/no_peeking.txt`)
- 40 origins, the same as `check_no_peeking.py`; both lags.
- Features rebuilt from only the posts published before t − lag (a plain pandas filter): 13,440 values, 0 mismatches.
- A second, slow implementation written separately (loops and boolean masks): 13,440 values, 0 mismatches.
- Negative control, window ending 15 minutes after t: it differs at all 29 origins that had a post that can change a
  column in [t, t + 15 min) (and at 36 of 40 overall, since the shifted window also drops posts at its old end).
- Negative control, lag 0 against lag 15: it differs at all 28 origins with such a post in [t − 15 min, t) (39 of 40).
- My first version asserted "differs at exactly the origins with any post in the extra minutes", which was wrong
  (shifting a window changes it at both ends, and a post that names nothing changes nothing). I changed the
  assertion, not the check, to "every origin with a relevant post differs".
- Edited posts: 602 of 25,949 (2.3%); 135 of 5,321 in the test window. Dropping them changes at most 1.7% of the
  values of any column materially (share6h by more than 0.05, minutes by more than 15, a 0/1 flipped).
  The first version counted any change at all, which showed 14.8% for share6h and meant nothing.

### The comparison (`scripts/evaluate_telegram.py` → `results/telegram/`)
- Same rows, split, 2026 training rows and thresholds as main; the 90 rows shared with `results/test_table.csv`
  match it (720 values, 0 differences). Test window: 24 days, unchanged.
- Within-oblast AUC / Brier, all 24 days (with lag 0 | lag 15 | without Telegram | train frequency):
  - H=1: 0.681 / 0.086 | 0.614 / 0.086 | 0.648 / 0.087 | 0.495 / 0.101
  - H=3: 0.638 / 0.142 | 0.605 / 0.142 | 0.642 / 0.142 | 0.581 / 0.177
  - H=6: 0.631 / 0.138 | 0.623 / 0.139 | 0.619 / 0.139 | 0.612 / 0.178
- Paired, day-block bootstrap (AUC difference with Telegram minus without, 95% interval):
  - lag 0: H=1 +0.0322 [+0.0039, +0.0531], H=3 −0.0038 [−0.0128, +0.0096], H=6 +0.0124 [+0.0060, +0.0191];
  - lag 15: H=1 −0.0344 [−0.0501, +0.0078], H=3 −0.0365 [−0.0594, +0.0104], H=6 +0.0042 [−0.0070, +0.0125].
- Brier differences are tiny: at most 0.0006 in magnitude, at lag 0 for H=1.
- Oblasts with the higher within-oblast AUC on all 24 days: lag 0: 20 / 10 / 16 of 24 at H = 1 / 3 / 6;
  lag 15: 13 / 9 / 11.
- Importance: only `tg_min_since` carries weight (rank 9 of 21 at H=1, lag 0, with 3.3% of the gain). `tg_m1h` and
  `tg_m3h` take 0.0% (each is a threshold of `tg_min_since`); `tg_share6h` and the flags 0.1–0.5%.
- Trees chosen by early stopping barely change (H=1: 122 without, 94 with lag 0, 121 with lag 15).
- By month, the columns do not follow the post rate (93 → 179 posts a day from January to September), except
  `tg_min_since`, which falls in September (550 minutes against 760–880 earlier) with the same rate (`feature_drift_by_month.md`).
- **Reading:** Telegram helps a little with posts up to t at H=1 and H=6; the within-oblast AUC gain is gone with the
  15-minute lag (H=1 is lower, the interval includes zero), and H=3 shows nothing at either lag. So the gain
  depends on posts from the last 15 minutes. Within-oblast AUC is noisy: it differs by 0.04 between main's
  full-history and 2026 models with the same Brier, and the bootstrap covers days only, not refits.
- On Sep 4–5 same hour yesterday still has the higher within-oblast AUC than every LightGBM variant at H=3 and H=6.

### Limitations (also in the README)
Deleted posts are invisible (the page is the channel as it is today). Edited posts keep their original time, but
the text is the text at pull time and may have changed after t. The place list is not exhaustive. Sep 4–5 is 48
origins per oblast.

### Other
- `scripts/evaluate.py`: `baseline_notes` takes an optional `labels` argument so the new models show readable names.
  The output on main's data is unchanged.
- Safety commits on this branch: beb4991, 2086a06, 0be2f07, 18c6e6c (code, then the posts file and parser check).
- Not decided: whether this goes anywhere near main. Main is frozen and untouched.

---

## 2026-10-11 — Round 10 (main): the Telegram experiment merged as a documented result

The user's decision: the result is real and short-lived ("nowcasting, not forecasting"), so `telegram` is merged
into `main`, as `news` was, "one place to read". Done as a merge commit (the branch history stays visible), with
the main-side edits inside that one commit.

### What the user asked for, and where I deviated (said before doing it)
- **"A 1 hour nowcasting signal"** is not what the numbers show:
  - With posts up to t, H=6 also gains (+0.0124 [+0.0060, +0.0191], 16 of 24 oblasts); only H=3 shows nothing.
  - With the 15-minute lag the Brier gain at H=1 is still there, at half size (−0.0003 [−0.0005, −0.0001]); it is
    only the within-oblast AUC gain that disappears.
  - Only two lags (0 and 15 minutes) were tried, so how fast the signal decays is not known.
- So the README sentence reads: the posts help only when they are minutes old, so they are a nowcasting signal and
  not a forecasting one; with posts up to t the within-oblast AUC gains at H=1 and H=6, and with a 15-minute lag the
  gain is gone. The 5-minute lag sweep is under next steps.
- **The "next steps" bullet about Telegram** did not exist on main. I added one: what we found, then (1) a lag sweep,
  (2) the full-history pull (about 3,850 pages, 3–5 hours), (3) threat types per oblast instead of the three
  national flags, which carry 0.1–0.5% of the gain.

### On main
- **README:**
  - the Telegram section, as on the branch, headed as a documented result (it includes the lag 0 / lag 15 table next
    to all three baselines, the paired comparison, the limitations);
  - a one-sentence summary at the top of the section;
  - the sentence "the main model stays the full-history LightGBM without Telegram", placed under the table so
    the two numbers have their baselines next to them: the best Telegram model (2026-only, posts < t) is under main's
    model at every H (H=1: 0.681 against 0.688), and Telegram covers only 2026;
  - one bullet in "Results in brief" pointing at it (no model numbers in it);
  - the Status line (rounds 1–10, both experiments merged), the new "Next:" bullet, one optional quick-start line
    (`evaluate_telegram.py`, about 3 minutes, from the committed posts), and the Run order / Layout lines.
- **Headline numbers unchanged:** the brief block's numbers, `results/*.md|csv` and `figures/` of the main model are
  untouched; the check is below.
- **One quick-start line rebuilds all of `results/telegram/`.** `evaluate_telegram.py` now also runs the 50-post
  parser check and the leakage check (as `evaluate_news.py` does), so nobody has to run three scripts.
  `telegram_parser_check.py` got a `main(argv)` for that. The posts are read from the committed CSV, no network.
- **The table caption in `results/telegram/test_table.md`** said "(branch telegram)". As in round 9, I changed the
  string in `evaluate_telegram.py` and regenerated: only line 1 of that file changed, and now reads "merged into main
  as a documented result". It is a new file from the merge, not a file of main's existing results.
- `data/telegram/cache/` (raw pages, from the pull) stays git-ignored and is not part of the merge.

### Checks
- Fresh `git clone` of the merge commit (7719e59, main) into a new folder with a new venv, then the whole quick
  start in order: `plot_weekly.py`, `evaluate.py`, `evaluate_news.py`, `check_no_peeking.py`, `evaluate_telegram.py`,
  `test_telegram_parser.py`, `predict.py`. Times in seconds, Python 3.13.16 | 3.9.25:

  | step | 3.13 | 3.9 |
  |---|---|---|
  | pip install | 28 | 32 |
  | `plot_weekly.py` | 9 | 11 |
  | `evaluate.py` | 80 | 84 |
  | `evaluate_news.py` | 96 | 110 |
  | `check_no_peeking.py` | 22 | 25 |
  | `evaluate_telegram.py` (parser check, comparison, leakage check) | 168 | 176 |
  | `test_telegram_parser.py` | 2 | 1 |
  | `predict.py` | 6 | 5 |

- Every step exited 0 with no warning lines.
- **Python 3.13** (pandas 3.0.6, numpy 2.5.4, matplotlib 3.11.2, lightgbm 4.7.0): `git status` empty. All 30 tracked
  files in `results/` and `figures/` are byte-identical, 14 of them main's own (`results/*.md|csv`, `figures/`), the
  rest `results/news/`, `results/telegram/` and `figures/gdelt_weekly.png`.
- **Python 3.9** (pandas 2.3.3, numpy 2.0.2, matplotlib 3.9.4, lightgbm 4.6.0): every table is byte-identical,
  including all of `results/telegram/`. The same four PNGs as in round 8 differ by a few pixels of layout
  (matplotlib 3.9), as the README already says.
- Python 3.11 and 3.12 were not re-run this round (they were in round 8; the Telegram line is untested there).
- Main's results and figures were not touched by the merge commit: `git diff` of the commit against main's previous
  tip lists nothing in `results/` outside `results/telegram/`, and nothing in `figures/`.

---

## 2026-10-11 — Round 11 (main): zsh-safe README, plain-words output, README top for a cold reader

Printed text and README only. No model, no result, no figure changed (check at the end).

### 1. The quick start broke in zsh
- **What happened (user's report):** pasted into zsh (the macOS default), the quick start ran nothing. Interactive zsh does
  not treat `#` as a comment, so:
  - `brew install libomp  # macOS only …` searched for a formula called "#" and printed ~8,000 lines, and the
    backticks around `import lightgbm` ran `import` as a command;
  - `pip install -r requirements.txt  # ~30 s` gave pip the arguments `#`, `~30`, `s`, and zsh expanded `~30` as a
    directory-stack entry ("not enough directory stack entries").
- **Cause:** my fault. I put comments, backticks and timings into the copy-paste blocks. bash and the Linux tests accept
  them, so nothing I ran showed it.
- **Fix:** every fenced block in the README now holds only commands. Timings and notes moved to a list under the block.
  The brew line is a block of its own marked "macOS only". The Windows activation line is in the list. The README has
  seven fenced blocks (quick start, brew, optional runs, the predict command, its output, Run order, Layout); none has
  a `#` or a backtick.
- **Also changed:** the venv line is `python3 -m venv .venv`, because stock macOS has no `python` before the venv exists.
- **Found while doing it:** the Run order block held `fetch_data.py`, `fetch_gdelt_events.py` and
  `fetch_telegram_kpszsu.py`. Once comment-free and "paste as it is", pasting the block would have re-pulled all
  three sources and replaced the pinned snapshot. The three fetch scripts are out of the pasted block now; they are a
  separate list marked as replacing the snapshot.
- **Proof:** the README's Quick start blocks, taken verbatim from the committed README, were pasted into `zsh -i` (zsh 5.9, no rc
  files, so `#` is not a comment, as on a Mac) as one stream, in the order a Mac user would paste them: the brew block,
  the main block, the optional block.
  - **Control first:** the two OLD lines (brew, pip) in the same setup reproduced the report exactly. The brew command
    received 10 arguments including `#`; `import` ran as ImageMagick's screen-capture command; pip's line died with
    "zsh: not enough directory stack entries".
  - **New blocks:** the `brew install libomp` line (a stub on Linux) received exactly 2 arguments. The clone, venv,
    `pip install`, `plot_weekly.py`, `evaluate.py`, `evaluate_news.py`, `evaluate_telegram.py` and `check_no_peeking.py`
    all ran with no error and no warning (6 min 35 s in total). The summary printed in plain words.
  - `git status` in that clone was empty: all tracked files in `results/` and `figures/` byte-identical (Python 3.13).
  - Not a Mac: zsh ran on Linux, and `brew` is a stub. So it proves the pasted text parses and runs in zsh, not that
    lightgbm loads on a Mac.
  - Done on fa1b682. The commit was then amended once (below); the README text did not change.

### 2. Output written for a user
- **`evaluate.py` summary:** the numbers are the same, now with plain words: what the question is, what AUC and Brier
  mean, and one sentence per H ("the model ranks risky hours inside an oblast at 0.688. The simple rules: same as now
  0.438, same hour yesterday 0.525, train frequency 0.495. Brier …"), a Sep 4–5 sentence, the existing "Note" line, then
  "Where to look": the full paths of `results/` and `figures/`, and three files to open first
  (`results/test_table.md`, `figures/model_vs_baselines_h6.png`, `results/feature_importance.md`), plus the predict command.
  `--verbose` still prints every table.
- **Deviation from the example:** the example said "the best simple rule at 0.495". That is train frequency, but it is not
  the best on within-oblast AUC at H=1: same hour yesterday has 0.525. So the text names all three simple rules
  (which CLAUDE.md wants next to each model number anyway), not "the best".
- **`predict.py`:** the first line is now one plain sentence, e.g. "Kharkivska, 17:00 Kyiv time on 5 Sep: 51% chance a
  new alert starts within 1 hour, 87% within 3, 96% within 6. It did start, 22 minutes later." (the example said 50%; the
  model's value is 0.505, which rounds to 51%). The detailed output follows as before.
  - If no alert started in 6 hours, it says so and when the next one came; if the window is after the end of the data or
    in the feed outage, it says it is not known. If the feed was down for part of the window, it adds that the real start
    may be earlier.
  - Hours in the training period add "this hour was part of the training data, so this is not a real forecast".
  - `--all` gets a plain line too: the three oblasts with the highest chance within 1 hour, and how many did start.
- **Experiments:** `evaluate_news.py` and `evaluate_telegram.py` now end with a short "Where to look" as well.

### 3. The README top
- New order: what this is (four plain sentences), the question, why new alerts, results as a small table (H, model, the
  three simple rules, in words) with the two metric definitions, quick start, one predict example with what it means and
  where files land, how this was built, contents. Data, targets, model, news and Telegram, limitations, run order,
  definitions and layout are below, unchanged except Run order. The old "Usage" and "Flags" sections and the Status
  lines are folded into the new top.
- **Deviations, said before doing them (CLAUDE.md: say so first):**
  - "Most alert-active hours are the current alert continuing" is true at H=1 only. From
    `results/persistence_vs_target_a.md`: 67.5% at H=1, 50.1% at H=3, 41.6% at H=6. The README gives the three figures.
  - The results table has all three simple rules, not "the best simple rule": the best one differs by metric and by H
    (see above), and CLAUDE.md wants all three next to every model number.
  - "The two leaks in the spec" are written as documented in the log: the frequency table over the last 4 weeks (it holds
    each row's own outcome, or a future one) and the F1 threshold picked on a week the model was trained on. The second is
    in-sample tuning more than a leak; the README says "picked on a week the model had been trained on".
  - The "H=6 not established" bullet is unchanged.
- **Figures:** the quick start now says tables in `results/` are byte-identical across the machines tried and figures can
  differ slightly (fonts, matplotlib version), as the four PNGs do on Python 3.9.

### Checks
- **Amended once after the zsh test:** `predict.py` printed "the next came 281 h 26 min later" for a quiet hour; gaps of
  two days or more now read "11 days 17 h". Only the `span()` helper changed (printed text). The final commit is
  c0a8486; Python 3.9 below was run on it.
- **Python 3.13 (zsh clone, fa1b682):** besides the paste, `test_telegram_parser.py` (56 + 17 cases) passed and
  `predict.py` was run for one oblast, for a training hour and for `--all`; the clone stayed clean.
- **Python 3.9.25 on c0a8486** (pandas 2.3.3, numpy 2.0.2, matplotlib 3.9.4, lightgbm 4.6.0): fresh clone, fresh venv,
  `plot_weekly.py`, `evaluate.py`, `evaluate_news.py`, `check_no_peeking.py`, `evaluate_telegram.py`,
  `test_telegram_parser.py`, `predict.py`. Times in seconds: pip 20, plot 9, evaluate 82, news 106, no-peeking 23,
  telegram 185, parser test 1, predict 5. All exit 0, no warning lines.
  - Every table is byte-identical. The same four PNGs differ by a few pixels (matplotlib 3.9), as the README now says
    in so many words: tables byte-identical, figures can differ.
- **`results/` and `figures/` on main were not touched by this round:** `git diff` of the commit against the previous
  tip lists nothing in either.
- Python 3.11 and 3.12 were not re-run this round.

---

## 2026-10-12 — Round 12 (main): the official source channel, and why "now" is not available

**Decision (user):** option A from the scouting, "nothing more". No API token came and the deadline is tonight. Hard limit 45
minutes; if over, stop and do not commit (it was not over, see the times at the end). Round 11's untouched rule stands:
`results/` byte-identical.

### Why (the scouting, 2026-10-11 17:28–17:43 UTC; scratch work only, nothing in the repo)
- The user wanted `predict.py` to take "now" and the test window to end at the pull, by reading the official source ourselves.
  The source of the official feed is the public Telegram channel `air_alert_ua` (the upstream script
  `processors/official_channel_processor.py` turns its messages into alert rows).
- **The channel loads and pages back** (`t.me/s/air_alert_ua?before=<id>`, 20 posts a page). About 585 posts a day
  (post 320000 on Aug 6 to post 338380 on Sep 7: 18,380 posts in 31.4 days). A pull of Aug 1 to the end would be about
  21,700 posts, 1,085 pages, 60–76 minutes at the pace seen (4.2 s a page with connection resets).
- **The channel stopped:** the newest post is 338380 at **2026-09-07 06:09:04 UTC**, in the middle of an alert wave, no
  all-clear after it. Three checks agree: `?after=338380` returns no posts; `?before=999999` returns the same last page; a
  direct link to post 338381 says "Post not found". The preview is not stale in general: the same method returned fresh posts
  of `kpszsu` the same day. The description does not mention a move. So there is no newer official data than the upstream
  feed, which stopped the same day.
- **No format change** before the stop: the same templates (🔴 start, 🟢 all-clear, 🟡 partial all-clear, 🔴🔴 / 🟠 notices) on
  Aug 6, Sep 2 and Sep 7.
- **The upstream parser** was ported by running it unmodified: `OfficialAirAlertProcessor` and `states.json` from the pinned
  upstream commit `7ccd436`; only the Telethon import is stubbed, and messages are shaped like Telethon's (text, UTC date, id)
  and fed in id order. It skips 321 of 3,280 posts (298 🟠 warnings and 23 other notices), no unknown hashtag.
- **Validation** on 3 days of starts (Aug 14–16; the full Aug 1–28 would have been about 45 minutes of pulling, so it was not
  done): 854 of the 855 rows of our cleaned csv are reproduced to the second; the one other row is a Marhanets alert that ends
  on Aug 19, after the posts I pulled stop (Aug 18 19:00): an edge of the slice. Nothing in the channel is missing from the csv.
  Over 1,440 oblast-hours (the series the model uses) **0** disagree, and both show 139 alert starts.
- So the source is the right one; it just has nothing after Sep 7.

### What was built (A)
1. **`scripts/source_check.py` → `results/source_check.md`**: the comparison and its output. It downloads the four upstream
   files at the pinned commit into `data/source_check/upstream/` (git-ignored; their SHA-256 are in the output; not vendored,
   so no upstream code is copied into the repo) and runs them over the committed posts. It needs one extra package,
   `translitua` (the upstream parser's own dependency, for the English names). Output is deterministic (run twice, identical).
   The "channel stopped" paragraph in the output is a hand-recorded, dated note (it cannot be reproduced offline).
2. **`data/source_check/channel_posts_aug13_18.csv.gz`**: the 3,280 public posts of Aug 13–18 that the check uses (id, UTC
   time, text), 60 KB compressed. The raw pages are not committed.
3. **README:** a plain-words paragraph in "Data" (we re-derived the official data from its source and it matched; the channel
   stopped on 2026-09-07 06:09 UTC, three checks; no newer official data; that is why the test window ends Sep 5, not our
   choice); one line in "Results"; one sentence in the evaluation window section; a "Try it" bullet for `--now`; Run order and
   Layout lines. Code blocks stay comment-free.
4. **`predict.py --now`:** one request to the channel's public page (10 s timeout, one retry), then one plain sentence and the
   forecast for the latest hour we have (2026-09-05 23:00 UTC, "which is not now"). Three outcomes, all tested:
   - nothing newer: "The official alert channel has posted nothing since 2026-09-07 06:09 UTC, which is where our data ends
     too, so no newer official data exists; here is the forecast for the latest hour we have …";
   - channel unreachable (tested with a dead proxy): "Could not reach the official alert channel (network error) …";
   - the channel has posts newer than the snapshot (not the case today; tested by calling the function with fake times):
     "… cannot turn live posts into forecasts yet …". It does not crash and builds nothing from live posts.
   No volunteer-feed fallback and no API code anywhere.
   - **"Newer" rule:** the channel's last post (06:09) is 41 minutes after the last row of our csv (05:28 start), because the
     csv holds only alerts that have ended and the channel's last posts open alerts that never got an end. So "newer" means
     more than 2 hours after our last row, not any later post. Without that margin the dead channel would look "newer".
   - `--now` and `--at` are mutually exclusive; one of them is required.

### Not done on purpose (options B and C of the scouting)
- A live path that pulls the last 8 days and builds features from them (it could only be tested by replay, and there is nothing to
  run it on today).
- Moving the data end to Sep 6 (one more full day).
- A longer validation than Aug 14–16.

### Checks
- **Fresh clone** of the final commit (Python 3.13.16, pandas 3.0.6, numpy 2.5.4, lightgbm 4.7.0), the whole run order:
  `plot_weekly`, `evaluate`, `evaluate_news`, `check_no_peeking`, `evaluate_telegram`, `test_telegram_parser`, `predict --at`,
  `predict --now`, then `pip install translitua` and `source_check.py`: every step exit 0, 0 warnings. `git status` empty
  afterwards: `results/` and `figures/` byte-identical to the commit, and `results/source_check.md` regenerated unchanged
  (also identical on two runs in the working tree). `results/` differs from round 11 only by the new `results/source_check.md`.
- **zsh paste test** (zsh 5.9, `zsh -f -i`, stdin paste of the README quick start blocks: clone, venv, `pip install`,
  `plot_weekly`, `evaluate`, `brew install libomp` (stub), `evaluate_news`, `evaluate_telegram`, `check_no_peeking`, the two
  `predict` lines of "Try it"): no zsh error (no "command not found", "no matches" or parse error), output of the `--at` example
  equals the README block, `--now` prints the one-sentence notice and the Sep 5 23:00 UTC forecast, `git status` empty.
  README fenced blocks: 7, none with `#` or a backtick.
- `predict.py --now`: nothing newer (real channel), dead proxy ("Could not reach the official alert channel (network error)"),
  and `--now` with `--at` (argparse error). The "newer posts" branch only by calling the function with fake times.
- **Note on wording:** the request said "854 of 854 alerts match"; measured is 854 of 855 (the 855th is the edge row, which
  `source_check.md` and the README explain). The files state the measured numbers.
- **Time:** started 16:35 UTC, committed locally 16:38, checks finished 17:10 (the two long checks ran at the same time at
  first and slowed each other; I paused one until the other finished), pushed before 17:20, inside the 45 minutes.

---

## 2026-10-12 — Round 13 (main): shorter README, and the model shown working

**Request (user):** last round, hard stop 21:10 Kyiv time (18:10 UTC); if not done and tested by then, stop and do not commit.
The README (625 lines) is too long for a reviewer, and nobody sees how it works without running it. Started 17:27 UTC.
No model, data or result changes: `results/` byte-identical.

### 1. README cut, details moved
- **README.md: 625 → 115 lines.** Kept: what this is, results (table, metric lines), quick start, try it (with the `--now` line),
  how this was built (the rules, where the checks caught mistakes), a five-bullet limitations list, a link to the details.
  Status line now "final (round 13)".
- **docs/DETAILS.md** (new, 537 lines): everything else, moved verbatim: Contents, Data (with the evaluation window and the
  western-oblast definition), Targets / baselines / evaluation, Model, News and text data (GDELT and Telegram), the full
  Limitations and next steps, Run order, Definitions, Layout. A diff of the old README's lines from "## Data" on against the
  new file shows only three differences, all additions for the new script: `plot_timeline.py` in the run-order block, its
  bullet in the run-order list, and the end-of-file newline. Two lines of introduction were added at the top of the file
  (a link back to the README; paths are relative to the repo root).
- **Links:** the README's Contents list moved with its sections, so its anchors still point inside the same file. In the README
  I added links to `docs/DETAILS.md` (and its sections); the Telegram line in the results now links to the News and text data
  section. A script resolved every markdown link, anchor (GitHub's slug rule) and image path in both files: 0 problems.
- **Five limitations bullets** are taken from the full list (western oblasts, Sep 4–5, the feed stop, the raion switch,
  thresholds). Not in the five, still in the details: the Volunteer-vs-official κ drop (unexplained, not speculated about here),
  and the "next" list. The H=6 "not established" note stays in the results block, where the number is.
- Code blocks: README has 5, DETAILS has 2; none contains `#` or a backtick.

### 2. Showing it working
- **scripts/plot_timeline.py → figures/forecast_timeline.png (+ .csv with the numbers behind it).** Uses the saved models/
  (`evaluate.py` writes them) and does not refit or write into `results/`. The probabilities come from the saved H=1 LightGBM
  on the same full-data features `evaluate.py` scores the test set with (the `check_no_peeking.py` results say these equal the
  known-at-t features); the script asserts that every hour shown is a scored test row. Two panels (Kharkivska, Kyivska), x =
  hour in Kyiv time, line = the model's chance of a new alert in the next hour, orange triangle = exact start of an alert that
  really started, light grey = hours when an alert was already running (the "now" column). Same palette, fonts and `style()`
  as `evaluate.py`'s figures.
- **Window chosen:** 24–28 Aug 2026 (UTC days), i.e. 5 of the 24 test days, picked by a rule that is in the script: the
  5-day window inside Aug 7–28 with the most alert starts in the less active of the two oblasts, earliest first. Counts:
  Kharkivska 42, Kyivska 25 new alerts. (Kyivska is the oblast around Kyiv; Kyiv City is a separate unit.) Both have alerts;
  I did not look at other windows to find a nicer picture. Note that this is the busiest end of August, not a typical week.
- **README:** the timeline sits under "Try it"; `model_vs_baselines_h6.png` and `reliability_h6.png` sit under Results, each
  with one plain sentence on what to look at. The sentences contain no numbers (so none are retyped from the figures).
  `plot_timeline.py` is the last line of the quick start block (optional, about 10 s, listed under the block).

### Checks
- `results/` byte-identical: sha256 of every file under `results/` before and after the round are the same; the only changes
  are the new files `docs/DETAILS.md`, `scripts/plot_timeline.py`, `figures/forecast_timeline.png` and `.csv`, and the
  edited `README.md` and `PROCESS_LOG.md`. The four existing figures were not touched.
- **Links and code blocks:** every markdown link, anchor and image path in `README.md` and `docs/DETAILS.md` resolves
  (0 problems); no code block in either file contains `#` or a backtick.
- **zsh paste test** (zsh 5.9, `zsh -f -i`, the README's own blocks pasted in order: `brew install libomp` (stub), clone, venv,
  `pip install`, `plot_weekly`, `evaluate`, `plot_timeline`, `evaluate_news`, `evaluate_telegram`, `check_no_peeking`, the two
  `predict` lines): no zsh error, no warning, `plot_timeline.py` printed its window line, `git status` empty (so the
  regenerated `forecast_timeline.png` and `.csv` equal the committed ones byte for byte on this machine).
- **Fresh clone** of the committed `main` (Python 3.13.16, pandas 3.0.6, numpy 2.5.4, lightgbm 4.7.0, matplotlib 3.11.2): the quick
  start, then `plot_timeline` (9 s), `evaluate_news`, `check_no_peeking`, `evaluate_telegram`, `test_telegram_parser`,
  both `predict` lines, `pip install translitua`, `source_check.py`: every step exit 0, 0 warnings, `git status` empty.
  The earlier run in the same session had the two long checks running at once and it was far slower; this time they ran one
  after the other (`evaluate.py` 79 s alone).
- **Not checked this round:** Python 3.9 and a Mac (nothing in `plot_timeline.py` is version-specific, but I did not run it
  there); the figure may differ by a few pixels across matplotlib versions, as the other figures do.
- **Time:** started 17:27 UTC, committed locally 17:31, tests finished 17:45, pushed before 18:10, inside the limit.

---

## 2026-10-18 — Round 14 (branch `live`, from main): alerts.in.ua API. IN PROGRESS, stopped after step 1

**Request (user):** work on a new branch `live` from main (main stays as submitted). Step 1 read the API docs; step 2 consistency
check against our official panel (stop and show after it); step 3 forward test on data after Sep 7 with the frozen round-13
models; step 4 `predict.py --now` on live data. The user supplied an API token. Rules for it: never print it, never write it to a
file, never put it in a commit, a log line or an error message; on a failed request print the status code only.

### How the token was handled
- It is not in any file, commit or this log. A scratch relay outside the repo (`alerts_relay.py` in the session scratchpad)
  took it once from its process environment, kept it in memory only, sent it as an `Authorization: Bearer` header (never in a URL),
  paced requests to the documented limits, and answered errors with the status code only. It was stopped after the probe below.
- Unavoidable: the token was typed in the chat and passed once in the command that started the relay, so it is in the session
  transcript (and in any export of it, see `ai-log` on that branch: that file was written before the token and does not contain it;
  do not regenerate it without removing the token first).

### Step 1: what the docs say (https://devs.alerts.in.ua/, read 2026-10-18)
- **Active alerts:** `GET /v1/alerts/active.json`: regions with an alert or any other threat now (fields: location title and uid, type
  oblast/raion/city/hromada, `started_at`, `alert_type`, `alert_level` red/yellow, `threats`).
- **History:** only `GET /v1/regions/{uid}/alerts/{period}.json`, and the only documented `period` is **`month_ago`**: one month back
  from the current date. No date-range parameters. `uid` may be an oblast, raion or hromada. Alert fields: `started_at`, `finished_at`
  (null while running), `location_type`, `location_uid`, `location_oblast(_uid)`, `location_raion`, `alert_type` (air_raid,
  artillery_shelling, urban_fights, chemical, nuclear), `notes`.
- **Consequence for the plan:** today is 2026-10-18, so the history reaches back to about 2026-09-18. It does **not** cover late Aug / early Sep
  (step 2's overlap with our official data, which ends 2026-09-07), nor Sep 7 to Sep 18 (step 3's start). Unless the endpoint returns more
  than documented (not tested: see below), step 2 as specified cannot be run and step 3 can only start around Sep 18, with a gap
  Sep 7 to Sep 18 between our data and the API's.
- **Rate limits:** general soft 8–10 requests a minute and hard 12 per IP (429 above; systematic abuse gets IP and token blocked);
  **history 2 requests a minute**. `If-Modified-Since` caching allowed. A public service must proxy; the token must not be in client code.
- **Region ids:** oblasts have uids 3–31 (e.g. 22 Kharkivska, 14 Kyivska, 31 Kyiv City as its own unit; Crimea 29, Sevastopol 30, Luhansk
  16). The full list (public Google Sheet linked from the docs) has 1,622 locations: 25 oblasts, 2 special cities, 126 raions, 1,469
  hromadas, each with a uid. Our 24 units map one to one to oblast uids by name; the mapping still has to be written down and checked.
- **Raion and hromada level:** present in the schema (`location_type`), and uids exist for all of them; whether the history of an oblast uid
  returns raion/hromada alerts (needed for the half-of-raions rule) or only oblast-level ones is not documented and is untested.
- Also: IoT endpoints (`/v1|v2/iot/...`) give the current state as a compact string (A all oblast, P partial, N none); no history.
  The service is volunteer-run, says it uses the official API, the Telegram channel and regional sources, and warns of delays.

### Step 1 result of the probe: the token was refused
- One request to `/v1/alerts/active.json` with the supplied token returned **HTTP 401** (documented as: token missing, wrong, revoked or
  expired). No retries and no guesses at variants (the docs warn that systematic misuse gets a token blocked). Nothing about the data
  itself is tested yet: that the history is limited to one month, what level it returns and how current it is are from the docs only.

### State
Nothing run on data, no code added; this entry is the only change on `live` so far (uncommitted). Steps 2–4 not started. Waiting for the user.

### Update (same day, later): the token was for a different service; alerts.in.ua dropped
- **Correction from the user:** the token belongs to the **Ukraine Alarm API** (`api.ukrainealarm.com`), not to alerts.in.ua. So the 401
  above was the wrong service rejecting a key it never issued, not a bad or expired token. The alerts.in.ua work is dropped (it never got
  past reading its docs); the entry above stays as the record of it.
- **New plan (same four steps, adapted):** (1) read the swagger: endpoints, auth format, region ids vs our oblasts, raion level, rate
  limits, and above all how far back history goes, tested with as few calls as possible; (2) if history reaches late Aug / early Sep, a real
  consistency check against the official data (same idea as `source_check`), otherwise a sanity check only (alerts and starts per day per
  oblast vs August) and a plain statement that there is no overlap; (3) forward test of the frozen round-13 models from the first hour with
  full feature history, reported separately with the source named; (4) `scripts/archive_api.py` saving the API data daily into
  `data/api_archive/`; (5) `predict.py --now` on live data. Stop and show after step 2. The token is read only from the environment
  variable `UA_ALARM_TOKEN`, never from a command line, never printed.
- **Blocked at the start, nothing run on data:**
  1. `UA_ALARM_TOKEN` is **not set** in this session's environment (checked for presence only; no other variable with a matching name
     either). Environment variables are read when a session starts, so it needs to be added in the environment's settings and a new
     session started.
  2. **The API host is behind a Cloudflare browser challenge from this sandbox.** `https://api.ukrainealarm.com/swagger/index.html`,
     `/swagger/v1/swagger.json` and an unauthenticated `/api/v3/regions` all answered HTTP 403 with a "Just a moment..." page
     (`server: cloudflare`), i.e. a bot challenge before any token check. It is not known whether a request that carries a valid key is
     let through from this IP; the user's own test (200) came from another network. I did not try to get around the challenge.
- **So the swagger has not been read.** Nothing in this log about the Ukraine Alarm API's endpoints, limits or history depth is known yet;
  I have not filled the gap from memory.

### Update (later still): the pushed "swagger" is the Cloudflare challenge page
- New setup from the user: I write the code, the user runs everything that touches the API on their own machine; the token stays there in
  `UA_ALARM_TOKEN` and I never see it. The user pushed `docs/api/ukrainealarm_swagger.json` (commit 1aa8449) to `live`.
- **That file is not the swagger.** It is 5,490 bytes of HTML whose title is "Just a moment..." (the Cloudflare browser challenge; same size
  as the 403 pages I got from the sandbox). It is not valid JSON (the parse fails at character 0). So the endpoints, auth format, region
  ids, raion level, rate limits and history endpoints are **still unknown**.
- Not done on purpose: `scripts/api_probe.py` and `scripts/archive_api.py`. Their paths, parameters and response fields would be guesses,
  and a probe that guesses the history call could waste rate-limited requests or save the wrong thing. They are written once the real
  swagger is here. The wrong file is left in place for the user to replace (it is their commit).

### Update (2026-10-18, later): the real swagger is in; scripts written, nothing run against the real API
**Setup:** Cloudflare challenges this sandbox, so I write the code and the user runs everything that touches the API on their own Mac,
with the token in `UA_ALARM_TOKEN` in their shell. I never see it. The user replaced `docs/api/ukrainealarm_swagger.json` with the real
swagger (OpenAPI 3.0.4, "Ukraine Alert API" v3, by Stfalcon; commit d7db329).

**What the swagger says** (read from the file; nothing here is measured yet)
- **Auth:** one `apiKey` scheme named `Token`: header `Authorization`, whose value is the token itself (no `Bearer` prefix is stated); applies to
  every endpoint. Base URL is not in the file; the host is `https://api.ukrainealarm.com`, paths start `/api/v3`.
- **Endpoints:** `GET /alerts` (regions with an alert now, with `activeAlerts` and levels Red/Yellow), `GET /alerts/{regionId}` (one region now),
  `GET /alerts/status` (a "last action" counter for cheap change detection), `GET /alerts/dateHistory?date=YYYYMMDD`,
  `GET /alerts/regionHistory?regionId=` ("the last 25 alerts of a region"), `GET /regions` (the id tree), `GET /geo-data`, `/geo-data/all`,
  `POST /geo-data/check-coordinates`, and `POST/PATCH/DELETE /webhook` (push on new alerts and all-clears).
- **History endpoints:** `dateHistory` (one calendar day per call; the date parameter's example is `20220224`, which is only an example, not a
  statement of depth) and `regionHistory` (only the last 25 alerts of one region: no use for depth). Records (`AlertDurationResponse`):
  `regionId`, `regionName`, `startDate`, `endDate`, `duration`, `alertType`, `isContinue`. Not stated: the time zone of the dates, whether a day
  means "alerts that started that day" or "alerts active that day", and what a date before the start of the history returns.
- **Alert types** include non-air ones: `UNKNOWN, AIR, ARTILLERY, URBAN_FIGHTS, CHEMICAL, NUCLEAR, INFO, CUSTOM`. A consistency check and any
  forward test must keep `AIR` only (to be confirmed against the official feed's meaning).
- **Region ids:** strings. `/regions` returns a tree `states -> regionChildIds -> ...` with `regionType` in `State, District, Community,
  CityOrVillage, CityDistrict, Null`; names are Ukrainian (`regionName`); `/alerts` also carries `regionEngName`. The history records have only
  `regionId` and `regionName` (no type, no parent): the level has to be looked up in the `/regions` tree.
- **Raion level:** the id tree has districts and communities, so the model data exists in principle; **whether `dateHistory` returns
  district/community-level records (needed for the half-of-raions rule) or only state-level ones is not in the swagger.** The probe counts it.
- **Rate limits:** none stated anywhere in the file (no 429 documented either). The client keeps at least 2.5 s between calls, waits and
  retries on HTTP 429 (Retry-After if given), and the archive stops after repeated 429.
- **How far back history goes:** not stated. That is the key question for the consistency check, and it is what the probe measures.

**Written (all on `live`; run only offline against a fake server so far)**
- `src/ukrainealarm.py`: small stdlib client (Python 3.9 compatible). Token only from `UA_ALARM_TOKEN`, sent as the `Authorization` header,
  never printed, logged or saved; every failure is reduced to a status code (no response text, no exception message); 0 = no connection,
  598 = HTTP 200 but not JSON (for example a challenge page). `UA_ALARM_BASE` exists for tests and may only point at the real API or at
  `http://127.0.0.1` (the token must not go elsewhere). Also the Ukrainian-name -> our-oblast-name mapping (25 names; Crimea and Sevastopol are
  not in our data) and `region_index()` (id -> name, type, state).
- `scripts/api_probe.py`: about 20-25 requests: `/regions` (counts by level, how many of our 25 oblasts are matched by name, the unmatched names),
  `/alerts/status`, `/alerts`, one `regionHistory` (Kharkivska), then `dateHistory` for a ladder of dates (2022-02-24, 2023-01-01, 2024-01-01,
  2025-01-01, 2025-07-01, 2026-01-01, 2026-06-01, 2026-08-15, 2026-08-31 (inside our official feed's outage), 2026-09-05, yesterday) and, if the
  oldest ones are empty, a bisection to the first date with data. Per date: status, items, ids by level, alert types, `isContinue`, earliest and
  latest raw start strings, whether the strings carry a time zone, how many starts fall on / before / after the requested day (UTC). Prints a
  `PROBE SUMMARY` block that is safe to paste; raw answers go to `data/api_raw/` (added to `.gitignore`; the user decides what to commit).
- `scripts/archive_api.py`: daily mode saves `/regions` (only when changed), `/alerts` (a timestamped snapshot) and `dateHistory` for the last 3
  days (refetched each run because a running alert gets its end later); `--from/--to` backfills a range and is resumable (existing files older
  than 3 days are skipped). Files go to `data/api_archive/` as the API sent them, plus `log.csv` (time, endpoint, date, status, items, bytes). A new empty answer
  never replaces a file that has alerts. Stops on 401/403 and after repeated 429.

**Tests (offline, a fake local API with a history cutoff at 2023-03-10, a one-time 429, and a check of the Authorization header):**
the probe found the cutoff exactly by bisection (24 requests, the 429 handled); the archive wrote daily, backfill and resume as intended, a wrong
token stopped it with "HTTP 401" and a missing token or a foreign `UA_ALARM_BASE` was refused; the fake token appears in no output and no file,
and the fake server's reply to a wrong token (which echoed the header) never reached an output either. The test outputs were deleted.
**Not tested:** anything against the real API: the real response shapes (field names come from the swagger only), the real name mapping, the
real history depth, the real rate limit.

**Open:** the probe output from the user's Mac decides the consistency check (a real overlap with the official data or a sanity check only) and
the forward test.

### Update (2026-10-18, later): probe output from the user's Mac, and a first real consistency check (one day)
**Probe result (user's run, 43 requests, 21 of them HTTP 429; token never seen):**
- `/regions`: 1,606 nodes, 29 states, **25 of our 25 oblasts matched by name** (the name map in `src/ukrainealarm.py` works).
- **History depth:** `dateHistory` returns data from **2025-10-03** (2025-10-02 and everything before it is empty, HTTP 200 with 0 items; the
  bisection is exact if the data is continuous). About one year back, so it **does** cover our late-Aug / early-Sep overlap, the official feed's
  outage (2026-08-31: 494 items) and everything after the feed's end (2026-09-07 to today).
- **Rate limit:** real. 21 of 43 requests got 429 at the 2.5 s pacing (the probe did not record Retry-After). Fixed in `src/ukrainealarm.py`:
  the pace now starts at 6 s, honours Retry-After, slows down after a 429 (x1.5, at most 60 s) and speeds up again after 10 clean calls; the probe
  and the archive print the Retry-After values and the final gap. Tested offline only (a 429 with Retry-After 1 s raised the gap, 10 clean calls lowered it).
- **What a day file is:** `dateHistory` for a UTC day returns every alert that was **active** on that day: on 2026-08-15, 399 items, 362 started on
  the day and 37 the day before, none after; the latest end seen was 2026-08-16. Times are UTC with a `Z` and microseconds; `isContinue` was false for all.
- **Levels:** on 2026-08-15, 20 State, 369 District and 10 Community items (the same shape on 08-31, 09-05, 10-17). Looking at the saved day, the
  State-level items are all `м. Київ` (no oblast-wide record for any other oblast): an oblast-wide alert comes as a set of districts, as in our own
  rows. Communities are city hromadas (Kharkiv, Nikopol, Zaporizhzhia). Alert types: AIR 396, ARTILLERY 3 (09-05 also one URBAN_FIGHTS).
- **Mapping without the region tree:** all 82 district names of that day turn into one of our 118 raion names with `translitua` (the package the
  upstream parser uses): 82 of 82, and each of our raion names belongs to one oblast, so the tree is not needed. Hromada-level records are dropped, as
  `src/panel.py` already does.

**`scripts/api_check.py` (new): the consistency check, same idea as `source_check.py`.** Offline, from the saved day files. Rules: AIR only;
district -> raion row, `м. Київ` / `... область` -> oblast row, hromada dropped; the same 118-raion list, half of the raions, restarts under 5 minutes
joined, the same `official_episodes` and `hourly_panel` code for both sides. Compares oblast-hours (under alert; a new alert starts in the hour),
oblast episodes (start within 1 min / 5 min / 1 h) and raion alert rows (same raion, start within 5 s / 60 s, end within 60 s), on the days that
have a file, outside the official outage and before the official trusted end. Writes `results/api_check.md`.
- **First real run, one day (2026-08-15, the only day pushed):** oblast-hours 576 compared, **576 of 576 same "under alert", 576 of 576 same
  "a new alert starts in the hour"**; oblast episodes 67 official / 67 API, 66 of 67 starts within 1 minute, 67 of 67 within 5 minutes; raion rows
  336 / 336, **330 of 336 official rows have an API row of the same raion with a start within 5 s**. The 6 others are one batch (Kherson, Beryslav,
  Skadovsk, Kakhovka, Henichesk raions at 01:16:04 and Bashtanka at 01:16:08 UTC) where the API's start is 98-133 s earlier. Of the 330 matched rows,
  327 also have an end within 60 s; the other 3 (Lozova, Konotop, Dnipro raions) end 213-253 s earlier in the API.
- **Controls (a copy of the day, not kept):** with 7 districts removed, 557 of 576 oblast-hours agree (episodes 57 vs 67); with every time shifted by
  25 minutes, 536 of 576 (raion rows matched within 60 s: 1). So the comparison does react to differences.
- **Caveats:** one day is not the late-Aug / early-Sep check; 576 oblast-hours is a small sample. The two sources are probably not independent (the
  API says it takes the official channel among its sources); the agreement shows our rules are applied the same way to both and that the API's rows are
  the same alerts, not that either is right about the real world. `results/api_check.md` as committed is this one-day run and is regenerated
  when more days are saved.

**Next, for the user to run:** a backfill into `data/api_archive/` (resumable) and commit it, then the check over the full late-Aug / early-Sep
window (and, if we go on, the forward test from Sep 7). Nothing else was run against the real API by me. Step 3 (forward test) is not started:
the user asked to stop after step 2.

### Update (2026-10-18, later): the full consistency check, API vs official (step 2 done)
**Input:** the user's backfill (`data/api_archive/`, commit df16ea6): 74 daily files 2026-08-06 to 2026-10-18, every call HTTP 200, 8.8 MB, 84 requests
with 10 HTTP 429 (the client's pace had risen to 60 s by the end). Run: `python scripts/api_check.py` (offline, 4 s) -> `results/api_check.md`.

**One mapping fix found by the check:** the API calls one raion "Шептицький район" (19 rows dropped as "not in our raion list"). Our list has 7 raions
for Lviv oblast, six of which appear in the API under the same name; the seventh, "Chervonohradskyi raion", never appeared, and Sheptytskyi is the former
Chervonohrad raion. Added `RAION_ALIASES = {"Sheptytskyi raion": "Chervonohradskyi raion"}` (`src/ukrainealarm.py`), applied in `api_check.py`.
It changes one row's match and none of the oblast-hour numbers. This is an inference from the lists (plus the known renaming), not something the API states.

**Result.** Compared hours: the 26 UTC days with a file inside the official data's trusted range (Aug 6-28 and Sep 3-5; the official outage
[Aug 29, Sep 3) and everything from Sep 6 00:00 are excluded): 624 hours x 24 oblasts = **14,976 oblast-hours**.
| | |
|---|---|
| same "under alert" | **14,942 of 14,976 (99.8%)**: official only 0, API only 34 |
| same "a new alert starts in the hour" | **14,954 of 14,976 (99.9%)**: official only 7, API only 15, both 1,824 |
| oblast episodes, official / API | 1,882 / 1,890; official starts matched by an API start within 1 min 1,866, 5 min 1,875, 1 h 1,882 (all) |
| raion alert rows, official / API | 9,360 / 9,395; official rows with an API row of the same raion starting within 5 s 9,263, within 60 s 9,301; of those, end within 60 s: 9,218 of 9,301 |
- **The disagreement sits on 3 days.** Aug 19 and Aug 20 hold 33 of the 34 "under alert" differences and 20 of the 22 start differences; Sep 5 holds
  the other 1 and 2. Outside Aug 19-20 (1,152 oblast-hours removed): 13,823 of 13,824 agree on "under alert" and 13,822 of 13,824 on starts.
- **Aug 19-20, what is different** (looked at, not explained): from about 20:52 UTC on Aug 19 the API has an alert in all 5 raions of Chernihivska oblast
  (to 08:26-09:52 on Aug 20, one raion to 18:49) and in 7 raions of Kyivska oblast (to 05:37-10:31), plus Mykolaiv, Dnipropetrovsk, Cherkasy and
  others for shorter times. **Our official data has no Chernihiv or Kyivska oblast alert at all in that period** (0 minutes active, 14 and 11 hours),
  and no row starting in the 20:xx UTC hour of Aug 19 (0 rows, against 58 in the API; 46 official rows start in the 21:xx hour). So it looks like a gap
  in the official feed (or its parsing) of about an hour at the start of that wave, and a missing wave for those two oblasts. I do not know which.
  **This is inside our old test window** (Aug 19-20, 25 oblast-hours where the official target says "no alert" and the API says "alert"); the old test
  is not changed and this is not fixed by editing data (`data/raw` stays as pulled).
- **The official outage window:** the API days for [Aug 29, Sep 3) give 521 oblast episodes starting in it, in 22 oblasts: the API has data where the
  official feed has none. Not compared with anything.
- **Caveats (as before):** the two sources are probably not independent (the API says it takes the official channel among its sources), so this shows
  that our rules produce the same oblast series from both and that the API is a usable substitute, not that either one is right about reality. The
  API rows have `isContinue = false` everywhere in this period; 80 rows without an end and 312 non-AIR rows were dropped (as the report lists).
- **Added to the report:** a table of the days with the most disagreeing oblast-hours (so the Aug 19-20 cluster is visible in the file).

**Decision for the user:** go on to the forward test (step 3) or not; and whether the Aug 19-20 official gap should be recorded in the README / log as a
known limitation of the old test (its effect is small: 34 of 14,976 hours, one event), which I have not touched.

### Update (2026-10-18, evening): forward test prepared and diagnosed, NOT scored; Aug 19-20 limitation; the rename
**User's decisions:** (1) forward test: go, frozen round-13 models and thresholds, no refit or retuning, score 2026-09-07 to 2026-10-17 (Oct 18 left out),
features from the API archive only, same metrics as the old test (within-oblast AUC, Brier with decomposition, calibration, day-block bootstrap), own section, source
named, "about 41 days, wide intervals", and **stop before scoring if the feature pipeline behaves differently on API data**; (2) put the Aug 19-20 gap into README and
DETAILS as a known limitation of the old test, data untouched, plus a side note with those hours flipped; (3) Sheptytskyi is a real rename (Chervonohrad and its raion,
renamed 2024): **stated as a fact now**, which supersedes the word "inference" in the earlier entry (the log is append-only; `src/ukrainealarm.py` says it as a fact).

**Flag on the baselines (said before doing it, as CLAUDE.md asks):** the request listed "logit, freq4w, persistence" as the baselines. CLAUDE.md fixes the three baselines
(same as now, same hour yesterday, train frequency), and the old test also showed the logistic regression. So the forward test reports **all** of them: the three
baselines, the logistic model, and, as an extra, the rolling 4-week frequency (the model's `freq4w` feature used directly as a score; its threshold is also frozen, from the
last train week). Nothing was left out.

**Frozen artifacts (code changes; the old test's outputs are byte-identical):**
- `scripts/evaluate.py` now also saves `models/frozen.json` (every F1 threshold it already computed, per predictor and H, plus the logistic weights, plus the freq4w
  threshold). The old pipeline was rerun: `results/`, `figures/` and the saved LightGBM and frequency files in `models/` are **byte-identical** to before.
- `src/features.build_features(..., outages=...)` and `src/dataset.build_rows(..., first=, end=)`: optional arguments, defaults unchanged (the official feed's outage,
  the official data's own start and end).
- `scripts/forward_test.py` (`--selftest`, `--diagnose`, `--score`). **Self-test passed:** the scoring code applied to the OLD official test rows with the frozen
  artifacts reproduces every AUC, Brier, precision, recall and F1 cell of `results/test_table.csv` (target b, all 24 days) for LightGBM, logistic, same as now, same hour
  yesterday and train frequency, at H = 1, 3, 6. It found one bug first: pandas' default CSV reader is off by 1 ulp on the saved frequency table, which moved 194 test rows
  that tie exactly at the threshold (the thresholded metrics of the frequency baseline at H=1 differed); the table is now read with `float_precision="round_trip"`.

**Diagnostics on API data (`results/forward_api/diagnostics.md`; run before scoring; no outcome of the forward rows compared with any prediction):**
1. **The one real difference: the official outage mask.** `src/features.py` treats 2026-08-29..09-02 as unobserved (7-day windows over the observed part, scaled; freq4w
   lags that touch it skipped). The API has data there (521 oblast episodes). With the mask left on, 1,555 forward rows (Sep 7-9) get different `share_7d` / `starts_7d`
   (mean abs diff of starts_7d 2.67) and 4,206-6,121 rows (to Sep 30) a different `freq4w` (mean abs diff 0.14), and the frozen LightGBM's probability differs by more than
   0.001 on 3,393 / 5,718 / 5,551 rows (H = 1 / 3 / 6; largest 0.083 / 0.146 / 0.150). The right setting for API data is **no mask**, which is what the code uses (`outages=[]`).
   This is the thing the user asked me to stop on: it is a deliberate setting I would score with, not a surprise, but it is a choice and it is not in the old pipeline.
2. **Same features from official and API on the same rows** (Aug 13-28, 9,216 rows; freq4w excluded, it needs 4 weeks of API history and the archive starts Aug 6): equal within
   0.001 on all but a few dozen rows outside the Aug 19-20 wave (for example `now`, `nb_share_1h`, `nb_starts_6h`: 8,544 of 8,544; `starts_7d` 7,950; `share_7d` 7,698 of 8,544, the
   rest are sub-second timing differences); correlations 0.989-1.000.
3. **Leakage check on API rows:** features for 40 forward origins rebuilt from API rows cut at t: 37,440 values, 0 mismatches.
4. **Gaps in the API:** episodes per day in the window min 59, median 104, max 172, no thin day, every oblast has episodes. Rows left out for having no end (`isContinue` true,
   end 0001-01-01): 2 hromada rows from Sep 17 (not used by the rule) and 78 rows from Oct 18 09:51 (after the window).
5. **Not a pipeline difference, but the forward period is a busier regime than the old test** (features and shares of origins, no model output): share of origins with a new alert in
   (t, t+H]: H=1 0.121 -> 0.180, H=3 0.297 -> 0.414, H=6 0.432 -> 0.571; `now` 0.209 -> 0.288; `starts_7d` mean 20.2 -> 30.1. Against the training range: 221 forward rows (0.9%) have
   `starts_7d` above the training maximum (81) and 40 have `starts_24h` above its maximum (16); every other feature stays inside it. So the frozen models see mostly familiar
   inputs, but their probabilities were calibrated to a quieter level (expect the calibration to show it; nothing is retuned).

**Scoring was not run on the API data.** `forward_test.py --score` exists (tables, calibration, day-block bootstrap, all baselines) and is ready; it waits for the user to
confirm the no-mask setting and to say go.

**Side note, Aug 19-20 (`scripts/sensitivity_aug19.py` -> `results/aug19_sensitivity.md`):** a patched copy of the official rows in a temporary folder (data/raw untouched) with the
API's 18 raion rows of Chernihivska and Kyivska oblast for alerts starting Aug 19 19:00 to Aug 20 12:00 UTC added: **25 oblast-hours** flip from quiet to under alert (Chernihivska 14,
Kyivska 11). The unmodified `evaluate.py` was run on the copy (same training rows, so the same models). Target (b), all 24 days, within-oblast AUC (Brier) old -> patched:
LightGBM H=1 0.6879 -> 0.6910 (0.0875 -> 0.0875), H=3 0.6451 -> 0.6465 (0.1446 -> 0.1446), H=6 0.6394 -> 0.6396 (0.1398 -> 0.1396); the baselines move by at most 0.0024 in AUC and 0.0018 in
Brier (same as now, same hour yesterday); train frequency by at most 0.0006. Base rate of a new alert: 0.1214 -> 0.1217 (H=1), 0.2957 -> 0.2965 (H=3), 0.4300 -> 0.4312 (H=6). The
patched copy mixes the two sources (the API's alerts added to the official ones). No ordering of the model against the baselines changes.
- **README and DETAILS:** one bullet in the README limitations (now six; the earlier "five" was a shape asked for in round 13, this one was asked for explicitly), a bullet in the Data
  "Known problems" and in the full Limitations of DETAILS, and the new scripts in the run order. Links and anchors checked (0 problems); no code block has `#` or a backtick.

**Open, for the user:** (a) confirm the forward test scores with **no outage mask** (recommended: the API observed those hours); (b) go for `--score`; (c) optional: the old-window
equivalence test (the frozen models on API-source features for Aug 7-28) needs the API archive back to about Jul 1 (4 weeks of lags before Aug 7): one more backfill
(`archive_api.py --from 2026-07-01 --to 2026-08-05`, about 36 days); not required for the forward test.

### Decision (2026-10-18, before scoring): the forward test uses no outage mask; a masked run is reported as secondary
**User's decision:** the forward test builds its features from the API archive **with no outage mask**. The mask in `src/features.py` exists only because the official feed had no data
for 2026-08-29..09-02; the API does have data for those days, so masking would throw away observed data. The main result is therefore the unmasked one (`outages=[]`). As a side note
the test is also scored once with the official mask switched on, reported next to the main result and labelled secondary (it is not the result).
Also decided: baselines as in CLAUDE.md (same as now, same hour yesterday, train frequency) plus the logistic model and the rolling 4-week frequency as extras; thresholded metrics stay at the
frozen thresholds; nothing is refitted or retuned; the Jul 1 - Aug 5 backfill is skipped for now.

**Declared before scoring: how calibration-in-the-large and the Brier change will be reported** (the forward rows have a higher base rate: the diagnostics showed 0.180 vs 0.121 at H=1).
- Calibration-in-the-large per horizon and predictor: mean predicted probability against the observed rate. Exactly, Brier = (mean predicted - observed)^2 + Var(p - y), so the squared
  bias is the part of the Brier score that is calibration-in-the-large; its share of the Brier is reported.
- The change of the LightGBM Brier from the old test to the forward test (old rows re-scored with the same frozen artifacts, which reproduces `results/calibration.md`) is split with the
  Murphy decomposition already used in `results/calibration.md`: uncertainty = base(1-base) (what a higher base rate does to ANY forecaster's Brier), reliability (miscalibration),
  resolution, residual; and the squared bias is shown next to them. How much of the change is the base-rate level is read off the uncertainty term (and, for the model itself, the bias).
- The same table for train frequency, so the model's Brier change can be read against a predictor that does not adapt.
- Not done to "fix" anything: no recalibration, no threshold moved, no refit.

### Update (2026-10-18, night): the forward test, scored (main: no outage mask; secondary: mask on)
Run after the decision above was logged and committed (ec944ba): `python scripts/forward_test.py --score` (the self-test passed again just before). The result is deterministic (a second run gave the same
table). Files: `results/forward_api/` (`forward_table.md/.csv`, `bootstrap.md`, `calibration.md`, `secondary_mask_on.md`, `diagnostics.md`); a README section and a DETAILS section.
**Source: the Ukraine Alarm API for every feature and outcome; frozen round-13 models and thresholds; 41 days (2026-09-07 to 10-17), 23,616 oblast-hours per horizon; target (b) only.**

**Main result, within-oblast AUC (95% day-block bootstrap interval) / Brier, no mask:**
| H | LightGBM | logistic | train frequency | same hour yesterday | same as now | rolling 4-week freq. |
|---|---|---|---|---|---|---|
| 1 | 0.708 (0.677-0.731) / 0.119 | 0.538 / 0.136 | 0.531 / 0.152 | 0.515 / 0.255 | 0.407 / 0.400 | 0.519 / 0.160 |
| 3 | 0.662 (0.622-0.691) / 0.167 | 0.561 / 0.183 | 0.522 / 0.259 | 0.532 / 0.323 | 0.459 / 0.429 | 0.536 / 0.216 |
| 6 | 0.654 (0.610-0.689) / 0.143 | 0.573 / 0.152 | 0.519 / 0.256 | 0.536 / 0.264 | 0.475 / 0.445 | 0.528 / 0.189 |
- LightGBM is ahead of every other predictor on AUC and on Brier at every horizon, and in every day-resampling the difference has the same sign: all 15 AUC-difference intervals lie above zero and all 15 Brier-difference intervals
  below zero (for example against train frequency: AUC +0.177 [0.140, 0.210] at H=1, +0.135 [0.090, 0.170] at H=6). The old test's "not established" for the H=6 ranking edge over train frequency stands for that test; here the
  interval excludes zero. This is one 41-day period from one source, so it is one more piece of evidence, not a verdict.
- Thresholded metrics at the frozen thresholds (in `forward_table.md`): LightGBM precision/recall/F1 0.419/0.669/0.515 (H=1), 0.613/0.877/0.721 (H=3), 0.750/0.915/0.824 (H=6).

**Calibration in the large (requested), mean predicted against observed:** LightGBM 0.1516 vs 0.1796 (H=1), 0.3681 vs 0.4143 (H=3), 0.5315 vs 0.5711 (H=6): it predicts low by 0.028 / 0.046 / 0.040, and the squared
bias is 0.7% / 1.3% / 1.1% of its Brier. Train frequency is much further off (0.0857 vs 0.1796, 0.2258 vs 0.4143, 0.3691 vs 0.5711: bias^2 is 5.8% / 13.7% / 15.9% of its Brier), as it cannot follow the level.
**How much of the Brier change is the base rate** (old test re-scored with the same frozen artifacts -> forward; terms generated in `calibration.md`):
- H=1: LightGBM Brier 0.0875 -> 0.1193 (+0.0318). The higher base rate alone raises the uncertainty term by +0.0407, i.e. **more than the whole change** (128%); the model's better separation (resolution +0.0097) offsets part of it;
  calibration-in-the-large (squared bias 0.0001 -> 0.0008) is 2% of the change.
- H=3: 0.1446 -> 0.1666 (+0.0220); uncertainty +0.0344 (156%), resolution +0.0144 offsets; squared bias 0.0003 -> 0.0021, 8% of the change.
- H=6: 0.1398 -> 0.1428 (+0.0030); the uncertainty term does not move (0.4300 and 0.5711 are symmetric around 0.5), so the base rate's direct effect is nil; the change is calibration-in-the-large (squared bias 0.0001 -> 0.0016,
  49% of the change) plus slightly lower resolution (-0.0015).
- Train frequency over the same change: Brier +0.0503 / +0.0817 / +0.0785, mostly reliability (squared bias +0.0076 / +0.0307 / +0.0372).
- So the Brier score is worse than in the old test mainly because the period is busier (a harder forecasting problem for anyone), while the model's skill relative to the simple rules is higher here, not lower. Nothing was recalibrated.

**Secondary, not the result: the official outage mask switched on** (`secondary_mask_on.md`): LightGBM within-oblast AUC changes by +0.0003 / -0.0006 / -0.0020 and Brier by +0.0001 / +0.0003 / +0.0006 at H = 1 / 3 / 6; the logistic AUC by
+0.0010 / +0.0018 / +0.0022; the rolling 4-week frequency baseline's Brier by +0.0040 / +0.0082 / +0.0102 (it is the predictor that depends most on the lagged windows); the three baselines that do not use these features are identical.
The mask choice does not change any conclusion.

**README and DETAILS:** the README gets a short "Forward test on live data (a separate test)" block under the results (numbers copied from the generated tables; links and anchors checked, 0 problems; no code block has `#` or a
backtick), its status line now says main is final (round 13) and this branch adds round 14; DETAILS gets a full section (frozen artifacts, rows, checks, results, intervals, calibration and the Brier split, the secondary run, caveats), a
Contents entry and the `data/api_archive/` and `docs/api/` layout lines. The old test's files in `results/` are byte-identical to before.
**Caveats:** 41 days, one period, one source; the API and the official feed are probably not independent (99.8% of 14,976 oblast-hours agree), so this says the frozen models hold up on a second feed of the same alerts, not that either feed is
the real world; the period is busier than the old test; Sep 6 and Oct 18 are not scored.
**Next (not started, as asked):** `predict.py --now` on live API data; what it needs is written in the reply to the user (token on their machine, a complete 29-day archive, open alerts handled as unknown-end, an offline replay test).

### Update (2026-10-18/19): `predict.py --now` on live API data (built and tested offline; not yet run against the real API)
**User's decisions:** (1) on a missing day, first fetch it from the API automatically; if the API still cannot give it, refuse, name the missing days and print the exact archive command to fix it; no scaling, no
filling; (2) running alerts (no end) count as running with an unknown end; (3) a freshness line, and the last completed hour as the origin; (4) replace the Telegram path, no fallback; (5) the replay test first,
offline: as of 2026-10-10 12:00 from a truncated archive, the same features as the forward test at that hour; (6) output per oblast: the probability for H = 1/3/6 and whether it is above the frozen threshold, sorted
by H = 1, plus one line saying the model tends to predict a bit low in the current period (per the forward test).

**Replay test first (`scripts/check_live_replay.py`, offline), PASSED:** the archive is cut by `live_api.as_of` to what the API would have said at the moment (only alerts that had started; every alert that ended later has
no end, `isContinue` true, end year 0001), and only the days the live path reads (33 day files). As of **2026-10-10 12:00 UTC**: 20,155 items read, 19,661 after the cut, 66 of them running; 7 of 24 oblasts under alert at
the origin. The live path (the same feature code as the forward test, no outage mask) gives **0 mismatches in 936 feature values and 0 in 72 LightGBM probabilities** against the forward test's full-data pipeline at
that hour. As of **12:37** (the origin is still 12:00, everything is cut at it): the same, 0 and 0 (76 running alerts at that moment). Negative controls, which must differ and do: running alerts dropped (213 / 159 feature
mismatches, 31 / 26 probabilities) and features read at the next hour (520 mismatches, 69 probabilities). So the open-alert handling, the day-file assembly and the cut at the origin reproduce the forward test.

**What was built**
- `scripts/live_api.py`: `origin_for` (the last completed hour), `needed_days` (the UTC days from t - 32 days to t: an alert is in the file of every day it was active), `read_days`, `live_rows` (running alerts kept with
  an unknown end), `features_at` (cut at the origin by `known_at`, no mask), `probabilities`, `stale_open`, and `live_forecast` (the live run). `scripts/api_check.py`: `rows_from_items`, `to_official_rows(keep_open=...)`
  (default unchanged: `results/api_check.md` and the forward-test table are byte-identical after the change; the running alerts keep their `regionId` only in the live mode).
- `scripts/archive_api.py`: `fetch_days`, `fetch_active` as importable functions (same behaviour), and `--force` (refetch days that are already saved).
- `scripts/predict.py --now`: the Telegram path is gone (no channel page, no fallback of any kind). `--now` needs `UA_ALARM_TOKEN`; `--oblast` is optional (all oblasts by default) and is checked **before** any request.
  `--at` is unchanged. The old `--now` message (nothing newer than the snapshot) no longer exists.
- Output of `--now`: the origin hour in UTC and Kyiv time; a freshness line (now, the newest alert start and end in the API, when the API's active-alerts list was last updated, and the sentence that a quiet spell and a late API
  look the same from here); the forward-test note read from `results/forward_api/calibration.md` ("mean predicted against observed 0.152 against 0.180 at 1 h, 0.368 against 0.414 at 3 h, 0.531 against 0.571 at 6 h ... nothing is
  recalibrated"); the frozen thresholds; a table per oblast sorted by the 1 h probability: alert now, probability and above/not above the frozen threshold for 1, 3 and 6 h.
- Missing days: the days from t - 32 days to today are fetched when they are not saved, and the last three are always refreshed (an alert still running when a day was saved has no end in that file). If any of them cannot be
  fetched (HTTP code per day printed, no response text), it refuses: "Missing or not refreshed: <days> ... python scripts/archive_api.py --from <first> --to <last>". A refused token (401/403) is reported as such, with no archive command.
- A guard against stale running alerts: a running alert older than the refreshed days whose region has a newer running alert, or is not in the API's active list now, means its day file is out of date (it may have ended after the
  file was saved): it refuses and prints `archive_api.py --from <day> --to <today> --force`. Written after the first test showed that checking only "is the region active now" misses a region that has a different alert running.

**Offline tests (a fake local API that serves the real saved days as they would have looked at 2026-10-10 12:37; the token never leaves the process environment):** happy path (a temp archive missing Oct 5-10: 6 days fetched, a
24-row table, all 72 probabilities equal the forward test's at that hour); the API answering 500 for one day (refuses, names it, prints the command); a refused token (HTTP 401 reported, no command); a stale running alert in an
old day file (refuses, prints the `--force` command); `--oblast Kyivska`; an ambiguous `--oblast Kyiv` (rejected before any request); the fake token appears in no output and no saved file. `archive_api.py` was re-tested after the
refactor (daily, backfill, resume, `--force`).
- **A test mishap, caught and undone:** my first archive test used `runpy`, which re-executes the script in a fresh namespace, so the temporary-folder patch did not apply and the test wrote into the real `data/api_archive/`:
  a fake active-alerts snapshot, rows in `log.csv`, and (with `--force`) five day files (Oct 1-5) overwritten by the fake server's re-serialised copies. It was seen in `git status` at once; the tracked files were restored with
  `git checkout`, the stray folders removed, `git status` for `data/` is clean, and nothing was committed. The test was redone importing the module (with an assertion that its output folder is a temp one).

**Not tested (cannot be from here):** anything against the real API: the real `/api/v3/alerts` payload (the code uses `regionId` and `lastUpdate` from the swagger), real latency and rate limits for a first top-up
(about 6 s per call; a first run after a few days needs a handful of calls), and the first live forecast itself. The stale-running guard could refuse wrongly if the real active list does not contain district-level ids; it
only matters for a running alert older than 3 days, and the message names it.
**New requirements on the user's machine:** `pip install translitua` (the API names are Ukrainian); `models/frozen.json`, which `scripts/evaluate.py` now writes (models/ is not committed), so `python scripts/evaluate.py` must be run once
after pulling; the token in `UA_ALARM_TOKEN`. README ("Try it") and DETAILS (run order) describe `--now`; links and anchors checked (0 problems), no code block has `#` or a backtick; the old results are byte-identical.

### Update (2026-10-18/19): the first live run, a cross-machine difference in one table, and the close of round 14
**First live run (reported by the user, on their Mac):** `predict.py --now` against the real API at 18:38 UTC: origin 18:00 UTC, freshness 0 min, no refusal, all 24 oblasts printed. So the code path that could only be tested offline (the
real `/api/v3/alerts` payload, the top-up of the archive, the stale-alert guard staying quiet) worked on real data on the first try. The archive files written by that run are on the user's machine and are **not committed** (their decision).

**A cross-machine difference the user saw after running `scripts/evaluate.py` on the Mac:** `results/base_rates_by_oblast.md` and the two figures (`figures/model_vs_baselines_h6.png`, `figures/reliability_h6.png`) showed as modified; the user restored
them with `git checkout`. Looked at here (I cannot see the Mac's diff):
- **Figures:** expected and already documented (README: figures can differ slightly with fonts and the matplotlib version; Python 3.9 draws them a few pixels differently). The numbers behind them are the results tables.
- **`base_rates_by_oblast.md`: cause not confirmed, one candidate found.** The table is `pd.DataFrame(base_rates).sort_values("b_start_6", ascending=False)` (`scripts/evaluate.py`, line 381): one single-key `sort_values` with the default, **unstable** sort.
  Three oblasts tie exactly on that key (Ivano-Frankivska, Lvivska, Zakarpatska: one new alert each, b_start_6 = 0.0106), so their relative order is whatever the sort algorithm of that numpy build does with ties. On this machine (x86, numpy 2.5.3,
  pandas 3.0.5) the default, quicksort, stable and heapsort all give the committed order, so I cannot reproduce a difference here. Against the candidate: a Mac run in round 8 matched every table byte for byte with the same ties, so if the Mac's
  environment did not change since, the tie order is not the whole story. The other single-key sorts in the code have no ties in the committed outputs (`lowest_bin_h6.md`: no shared counts; the feature-importance gains are floats); every other sort is stable
  or multi-key.
- **Does it matter? No for any result.** The table is a descriptive per-oblast breakdown of the target columns over the same test rows that feed `test_table.md`, `calibration.md` and the rest. The user reports that only this table and the two figures differed;
  since all the metric tables matched byte for byte, the rows, targets and models are identical on the two machines, so the per-oblast base rates cannot differ in value; at most the row order of tied oblasts or the last printed digit. No model number, baseline,
  forward-test number or README number comes from this table.
- **To confirm** (not done, needs the Mac): `python -c "import sys, numpy, pandas; print(sys.version.split()[0], numpy.__version__, pandas.__version__)"`, then `python scripts/evaluate.py` and `git diff results/base_rates_by_oblast.md` (it shows whether only the three tied rows moved).
- **A fix, if wanted (not applied; evaluate.py and the committed tables stay as they are):** sort by the rate and then by the oblast name, `sort_values(["b_start_6", "oblast"], ascending=[False, True])` after `reset_index()`; on this machine that reproduces the committed file byte for byte, and it would make the table
  the same on any machine. The README sentence "Tables in `results/` are byte-identical across the machines we tried" is not changed here because the cause is unconfirmed; if the tie order is confirmed, the sentence should name this one exception or the sort should be fixed.

### Round 14 closed (branch `live`; main untouched at 5c8cede)
**What round 14 delivered** (all on `live`, logged above in order): the alerts.in.ua detour (docs read, token was for another service); the Ukraine Alarm swagger read; `src/ukrainealarm.py` (client: token only from `UA_ALARM_TOKEN`, status codes only, adaptive rate limit),
`scripts/api_probe.py` (history reaches back to 2025-10-03), `scripts/archive_api.py` (daily save, resumable backfill, `--force`, importable `fetch_days`/`fetch_active`), the archive of 74 days (Aug 6 - Oct 18) the user pushed; `scripts/api_check.py` and
`results/api_check.md` (API vs official: 99.8% of 14,976 oblast-hours agree; one wave on Aug 19-20 missing from the official feed); `scripts/sensitivity_aug19.py` and `results/aug19_sensitivity.md` (putting it back moves the model's AUC by at most +0.0031);
`scripts/forward_test.py` and `results/forward_api/` (frozen models, 41 days of API data, no outage mask, LightGBM ahead of every baseline on AUC and Brier at H = 1, 3, 6; calibration in the large and the Brier split; a secondary masked run);
`scripts/live_api.py`, `scripts/check_live_replay.py` and the API version of `predict.py --now` (replay test passed: 0 of 936 features and 0 of 72 probabilities differ from the forward test; run once on the real API); README and DETAILS sections, the Aug 19-20
limitation, the Sheptytskyi rename stated as fact. `models/frozen.json` (thresholds, logistic weights) is written by `scripts/evaluate.py` (models/ is not committed); the old test's tables are unchanged by the round (byte-identical on the machine used here).
**Rules check (CLAUDE.md):** no leakage (features at t from what was known at t; the leakage check on API rows and the replay test passed); the old test window is unchanged and the forward test is reported separately; every model number is next to the baselines; thresholds frozen, none chosen on test;
`data/raw` never edited; the volunteer feed was not used; the token never appeared in a file, a commit, a log line or an error message (status codes only; it was typed once in this conversation, so rotate it).
**Open items, all outside this round's scope:** (1) the `base_rates_by_oblast.md` difference on the Mac: confirm the cause and decide on the sort fix (above); (2) the archive updates from the live run, on the user's machine, uncommitted; (3) the optional Jul 1 - Aug 5 backfill (an old-window test on API features),
skipped; (4) `live` is not merged anywhere: the submitted state is `main` (round 13); (5) if the README sentence about byte-identical tables should change after (1).

### Update (2026-10-19): the tie in `base_rates_by_oblast.md` confirmed and fixed
**Confirmed by the user on the Mac** (Python 3.9.6, numpy 2.0.2, pandas 2.3.3): `git diff results/base_rates_by_oblast.md` shows only Lvivska and Zakarpatska swapped, all values identical. So the cause is the one named in the entry above: three oblasts tie exactly on
b_start_6 (Ivano-Frankivska, Lvivska, Zakarpatska), and the default `sort_values` is not stable, so numpy 2.0.2 on that machine ordered the tied rows differently from numpy 2.5.3 here. (The Mac's round-8 match was luck of the same tie order under a different numpy; the data and the ties did not change.)
**The fix (`scripts/evaluate.py`):** the table is built with `reset_index().sort_values(["b_start_6", "oblast"], ascending=[False, True], kind="stable")`: the rate first, the oblast name second, so tied rows come out alphabetically on any machine. Only this one sort was changed. The other single-key sorts
(`lowest_bin_h6.md` by rows_in_bin, the feature-importance gains) have no ties in the committed outputs and were left as they are; the same one-line pattern would fix them if a tie ever appears.
**Checked here (Linux x86, numpy 2.5.3, pandas 3.0.5):** `scripts/evaluate.py` rerun with the fix: `results/base_rates_by_oblast.md` is **byte-identical to the committed file** (the committed order was already the alphabetical tie order), every other file in `results/` and `figures/` is unchanged
(`git diff` empty), and the six saved model files (`lgbm_b_start_h*.txt`, `frequency_b_start_h*.csv`) are byte-identical to before. Not re-run on the Mac: the user can confirm there with `python scripts/evaluate.py` and `git status` (the two figures may still differ by a few pixels, as documented).
**README:** the sentence on byte-identical tables now names the one exception and says the tie order is fixed.
**Scope:** `live` only. `main` still has the old sort (it is the submitted state): the same one-line change would go there if a new round on main is ever opened.
