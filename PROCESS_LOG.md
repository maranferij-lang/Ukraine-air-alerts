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
