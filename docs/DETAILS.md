# Details

The long version of the [README](../README.md): the data, the targets and baselines, the model, the two text experiments, the full limitations, the run order, the definitions and the layout. File paths in code spans are relative to the repository root.

## Contents
- [Data](#data): the sources, what "under alert" means, the feed outage.
- [Targets, baselines, evaluation (`scripts/evaluate.py`)](#targets-baselines-evaluation-scriptsevaluatepy): the two targets, the three simple rules, the metrics.
- [Model (`scripts/evaluate.py`, `src/features.py`)](#model-scriptsevaluatepy-srcfeaturespy): the features and the LightGBM setup.
- [News and text data](#news-and-text-data): why the main model uses no text, and two experiments that were tried: GDELT news (a negative result) and Telegram posts (a real gain that lasts only minutes, so a nowcasting signal and not a forecast). The main model uses neither.
- [Forward test on the Ukraine Alarm API](#forward-test-on-the-ukraine-alarm-api): the frozen models scored on 41 days of live API data, separate from the old test.
- [Limitations and what we would do next](#limitations-and-what-we-would-do-next)
- [Run order](#run-order): every script, in order.
- [Definitions](#definitions): oblast, episodes, the hourly panel.
- [Layout](#layout): the files.

## Data

[Vadimkin/ukrainian-air-raid-sirens-dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset)
has two feeds, official and volunteer. Times are UTC.
- The snapshot is committed in `data/raw/`.
- `data/raw/PULL_INFO.md` records the pull: 2026-10-10 18:58 UTC, upstream commit `7ccd436`. That is
  the same commit as the first pull at 08:27 UTC, and both files are byte-identical to it.
- We use the **official** feed. The volunteer feed is not reliable after mid-2025 (see below).
- Hourly agreement between the volunteer and official feeds (Cohen's κ on "under alert") falls
  from 0.985 in 2022Q3 to 0.448 in 2026Q3. The Lviv/Volyn parser bug described below accounts
  for about 0.025 of that drop. The rest is unexplained.

**Where the official data comes from, and why it stops.** The official feed is built by an upstream script that reads the state
alert channel on Telegram (`air_alert_ua`) and turns each message into an alert row. We ran that same script, unchanged, on the
channel's public posts for Aug 14–16 and compared the result with our csv: 854 of 855 alerts match to the second (the 855th is
an alert still running at the edge of the slice), and none of the 1,440 oblast-hours disagree. So the data is what the channel
says (`results/source_check.md`). The channel's last post is from 2026-09-07 06:09 UTC. We checked in three ways (no post after
that number, the same last page when asking for later ones, and "Post not found" for the next number), and the same method
returned fresh posts from another channel, so it is not a stale page. There is no newer official data to add, and that is why
the test window ends on Sep 5. It was not our choice.

Known problems, handled in `src/load.py`:
- The official feed ends 2026-09-07 ~05:40 UTC (the channel itself stops at 06:09, see above).
- No official messages 2026-08-29 → 2026-09-02. These hours are masked.
- 38% of official rows are upstream duplicates. They are dropped.
- The last day of each file is incomplete, because alerts still open at the pull are missing. It is cut.
- **A wave is missing inside the old test window (found later, not handled):** the 2026-08-19 ~20:52 UTC wave in Chernihivska and Kyivska oblast (about 10–13 hours, 25 oblast-hours) is in the Ukraine Alarm API but not in this feed, and the feed has no row starting in the 20:xx UTC hour of Aug 19. `data/raw` is as pulled and the old test is unchanged; the size of the effect is in `results/aug19_sensitivity.md` (about +0.003 AUC at most for the model), the comparison in `results/api_check.md`.

### Evaluation window: the most recent trustworthy data
The test period is the **last 30 full days of official data: 2026-08-07 00:00 → 2026-09-05 23:00
UTC**. Usable test days: **24**, i.e. Aug 7–28 and Sep 4–5. The same rows are used for every
predictor. The window ends on Sep 5 because the official source stopped on Sep 7; we did not cut it.
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

Re-pulled with `scripts/fetch_data.py` on 2026-10-10 18:58 UTC. Upstream was unchanged: same commit, same
files, official data still ending 2026-09-07. So the window stayed.
- The window is anchored to the end of the official data. If upstream fixes the feed, the test
  month moves forward on its own.
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

Sep 4–5 alone (43–48 origins per oblast depending on H; 7-day features scaled from the observed hours; within-oblast AUC over the
20 oblasts with both outcomes), same columns:

| H | base rate | LightGBM | LightGBM from 2026-01-01 | logistic: starts_7d + hour + oblast | same as now | same hour yesterday | train frequency |
|---|---|---|---|---|---|---|---|
| 1 | 0.141 | 0.534 / 0.098 | 0.555 / 0.096 | 0.419 / 0.114 | 0.359 / 0.365 | 0.538 / 0.218 | 0.466 / 0.119 |
| 3 | 0.365 | 0.476 / 0.158 | 0.471 / 0.159 | 0.361 / 0.170 | 0.395 / 0.425 | 0.519 / 0.297 | 0.424 / 0.218 |
| 6 | 0.543 | 0.447 / 0.120 | 0.440 / 0.122 | 0.325 / 0.121 | 0.392 / 0.444 | 0.501 / 0.196 | 0.409 / 0.203 |

How to read it:
- **LightGBM earns its keep on ranking.** A logistic regression on starts_7d, hour of day and
  oblast gets within 0.006–0.010 of LightGBM's Brier, but its within-oblast AUC is near 0.5
  (0.48–0.51). LightGBM beats it in 24 / 23 / 22 of 24 oblasts.
- So "how busy was this oblast this week" sets the level, which drives most of the Brier. The
  ranking within an oblast comes from the other features.
- **H=1:** LightGBM beats the frequency baseline's within-oblast AUC in 24 of 24 oblasts.
- **H=6: not established.** LightGBM beats the frequency baseline in 13 of 24
  oblasts on Aug 7–28, and in 18 of 24 on all 24 days, with the same model
  (`results/oblast_wins.md`). A count that moves by five on two extra days is not evidence either way.
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

## News and text data
The main model uses no text: not the alert messages themselves, and no news or Telegram text.
- Every alert in this data is a message. The message announcing an alert, or the launch behind
  it, *is* the target. Using its text would hand the model the answer.
- A text feature would have to come from sources other than the alert channels, timestamped
  strictly before t.

### Experiment: national news intensity from GDELT (a documented negative result)
**What we tried.**
- **Source:** GDELT 2.0 event files, 2026-01-01 → 09-07 (`scripts/fetch_gdelt_events.py`). Only the
  hourly aggregate is committed (`data/news/`); the raw files can be re-pulled with the script.
- **Content:** events located in Ukraine (ActionGeo country `UP`) with CAMEO root code 18 (assault),
  19 (fight) or 20 (unconventional mass violence). One national number per hour.
- **No oblast split:** the region field is dominated by Kyiv City (capital datelines) and has
  geocoding errors, e.g. Brovary filed under Ternopil.
- **Two features for origin t** (`src/news.py`):
  - `news_24h`: events added in [t−25h, t−1h);
  - `news_yesterday`: events added during the last full UTC day that ended by t−1h.

**Leakage rule.**
- The clock is **when a record was added to GDELT** (DATEADDED), never the event date.
- A record counts at t only if it was added before t−1h, the same lag as the neighbour features.
- Every record's DATEADDED equals the timestamp of the 15-minute file it arrived in.
- `scripts/check_no_peeking_news.py` (output in `results/news/no_peeking.txt`):
  - recomputes both columns for the 40 test origins from records added before t−1h only: 0 mismatches
    in 80 values;
  - negative control (a 24h window ending at t instead of t−1h): mismatches at 40 of 40 origins.

**Fair test.**
- "LightGBM from 2026-01-01" with and without the two columns: same rows, split, training rows
  (2026-01-01 up to the test month) and thresholds.
- The first 25 hours of 2026 have no full news window. They stay in training as missing values.
- Every row except "+ news" reproduces main's `results/test_table.csv` exactly.

**Before the model:** is news just a slower copy of the alert history? No
(`results/news/correlation.md`, training rows). `news_24h` vs `starts_7d`: Pearson 0.071 within
oblast, 0.244 nationally per hour.

**Results.** New alert within H hours (b), within-oblast AUC / Brier (`results/news/test_table.md`,
`results/news/test_table_by_period.md`):

| H | 2026 + news | 2026 | full history (main) | same as now | same hour yesterday | train frequency |
|---|---|---|---|---|---|---|
| all 24 days, 1 | 0.621 / 0.087 | 0.648 / 0.087 | 0.688 / 0.087 | 0.438 / 0.288 | 0.525 / 0.181 | 0.495 / 0.101 |
| all 24 days, 3 | 0.578 / 0.144 | 0.642 / 0.142 | 0.645 / 0.145 | 0.480 / 0.327 | 0.524 / 0.281 | 0.581 / 0.177 |
| all 24 days, 6 | 0.616 / 0.140 | 0.619 / 0.139 | 0.639 / 0.140 | 0.489 / 0.365 | 0.516 / 0.267 | 0.612 / 0.178 |
| Sep 4–5, 1 | 0.588 / 0.097 | 0.555 / 0.096 | 0.534 / 0.098 | 0.359 / 0.365 | 0.538 / 0.218 | 0.466 / 0.119 |
| Sep 4–5, 3 | 0.517 / 0.159 | 0.471 / 0.159 | 0.476 / 0.158 | 0.395 / 0.425 | 0.519 / 0.297 | 0.424 / 0.218 |
| Sep 4–5, 6 | 0.458 / 0.125 | 0.440 / 0.122 | 0.447 / 0.120 | 0.392 / 0.444 | 0.501 / 0.196 | 0.409 / 0.203 |

Paired comparison, "with news" minus "without" (`results/news/news_vs_no_news.md`):
- 95% day-block bootstrap interval for the AUC difference (whole test days resampled):
  - H=1: −0.0272 [−0.0559, 0.0238];
  - H=3: −0.0638 [−0.1067, 0.0267];
  - H=6: −0.0023 [−0.0258, 0.0267].
- Same for the Brier difference:
  - H=1: 0.0002 [−0.0001, 0.0005];
  - H=3: 0.0014 [0.0005, 0.0024];
  - H=6: 0.0011 [0.0002, 0.0019].
- Oblasts where news gives the higher AUC, all 24 days: 12, 11 and 12 of 24.

Feature importance (`results/news/feature_importance.md`):
- The news columns rank 9–10 (H=1), 7 and 10 (H=3), 4 and 8 (H=6) of 16 by gain, with 2–4% of the
  gain each.
- They take 10–17% of the splits.

**Why it most likely hurts: the trees use news as a calendar.**
- The weekly news level drifts over the months (`figures/gdelt_weekly.png`). A national number that
  drifts lets a tree tell one stretch of training weeks from another, much like a date column would.
  That fits the training months, not the next H hours.
- Two facts point this way.
  - The trees split on the news columns often (10–17% of splits) but gain little from those splits
    (2–4% each).
  - Early stopping on the last training week stops sooner with news: 80 / 64 / 60 trees instead of
    122 / 158 / 101 for H=1/3/6 (`results/news/news_vs_no_news.md`). The validation loss turns up
    sooner.
- This is a reading of those two facts. We did not test it, e.g. with a detrended count.

**Verdict: news does not help.**
- Within-oblast AUC is lower with news at H=1 and H=3 and about the same at H=6. All three
  intervals include zero.
- Brier is slightly worse, and the interval is above zero at H=3 and H=6.
- On Sep 4–5 the news model has the higher AUC at every H. That is 48 origins per oblast, so it
  shows nothing either way.
- Merged into `main` as a documented negative result, so the whole project reads in one place.
  The model in the sections above does not use the news columns.

### Experiment: per-oblast Telegram posts of the Air Force channel (a nowcasting signal)
**In one sentence:** the posts help only when they are minutes old, so they are a nowcasting signal, not a forecasting one.
With posts up to t, the within-oblast AUC gains at H=1 and H=6; with a 15-minute lag the gain is gone. Numbers and
baselines below.

**What we tried.**
- **Source:** the public preview of `t.me/s/kpszsu` (Air Force of the Armed Forces of Ukraine), pulled with
  `scripts/fetch_telegram_kpszsu.py`: 25,949 posts from 2025-12-31 to 2026-09-08, one request at a time,
  with retries after connection resets. The CSV with each post's id, UTC time, "edited" flag and text is
  committed (`data/telegram/kpszsu_posts.csv`); the posts are public.
- **Content:** short threat reports, e.g. "БпЛА на Харків з півночі". They are not the alert itself; the
  alert is the official siren in our data.
- **Per oblast, not national.** The channel's post rate rose from about 93 posts a day in January to 179
  in September, so a national count would turn into a calendar (as the GDELT count did). All columns are
  bounded or relative.

**Leakage rule.** A post counts at origin t only if its post time is strictly before t (lag 0). To show
the gain does not ride on the minutes between a post and a siren, everything is also run with posts before
t − 15 min (lag 15), with the windows shifted back by 15 minutes. `scripts/check_no_peeking_telegram.py`
(`results/telegram/no_peeking.txt`):
- 13440 values rebuilt from the posts before t − lag only: 0 mismatches; a second, independent implementation: 0 mismatches;
- negative control, a window ending 15 minutes after t: it differs at every origin with a relevant post in
  those minutes (29 of the 29 origins);
- negative control, lag 0 against lag 15: it differs at every origin with a relevant post in the 15
  minutes (28 of the 28 origins).

**Which oblast does a post name?** (`src/telegram_oblasts.py`, tests in `scripts/test_telegram_parser.py`)
- Matching is on word starts, with Ukrainian declensions and the main cities; hyphenated names such as
  Кам'янець-Подільський and Переяслав-Хмельницький are matched as whole phrases first.
- It does not repeat the volunteer feed's substring bug. "Подільський район" names no oblast, and in
  the real posts goes to Odesa through "Одещина"; "Прилуцький район" goes to Chernihiv; nothing goes to
  Lviv or Volyn by accident. The 50 random posts and every post containing these strings were read by hand
  (`results/telegram/parser_check_50.md`).
- 88.9% of the posts name at least one oblast; the rest are mostly nationwide bulletins.
- "Відбій" (all-clear) sentences count as neither a mention nor a threat.

**Seven columns** (`src/telegram_features.py`):
- `tg_m1h`, `tg_m3h`: this oblast is named in a post in the last 1 h / 3 h (0/1);
- `tg_share6h`: its share of the posts in the last 6 h, among posts that name at least one oblast;
- `tg_min_since`: minutes since it was last named, capped at 24 h;
- `tg_ballistic`, `tg_missile`, `tg_kab`: national 0/1, a post of that type in the last 3 h (ballistic;
  any missile: КР, крилат, ракет, швидкісн ціл, кинджал; glide bomb / tactical aviation: КАБ, керован
  авіабомб, тактичн авіац). Share of posts and of oblast-hours (lag 0) where each is 1 (`results/telegram/flag_prevalence.md`): ballistic in 4.5% of posts and 26.3% of oblast-hours; missile in 6.3% of posts and 26.8% of oblast-hours; kab in 21.2% of posts and 79.7% of oblast-hours.
- A national drone flag was dropped: drone posts are so constant that it would be 1 in nearly every hour (measured
  in `PROCESS_LOG.md`), and the oblast mentions already carry the drone signal.

**Fair test.** "LightGBM from 2026-01-01" with and without the seven columns: same rows, split, training
rows and thresholds. Every row except the Telegram ones reproduces `results/test_table.csv` exactly.

**Results.** New alert within H hours (b), within-oblast AUC / Brier (`results/telegram/test_table.md`,
`results/telegram/test_table_by_period.md`):

| H | 2026 + Telegram (posts < t) | 2026 + Telegram (posts < t−15 min) | 2026 | full history (main) | same as now | same hour yesterday | train frequency |
|---|---|---|---|---|---|---|---|
| all 24 days, 1 | 0.681 / 0.086 | 0.614 / 0.086 | 0.648 / 0.087 | 0.688 / 0.087 | 0.438 / 0.288 | 0.525 / 0.181 | 0.495 / 0.101 |
| all 24 days, 3 | 0.638 / 0.142 | 0.605 / 0.142 | 0.642 / 0.142 | 0.645 / 0.145 | 0.480 / 0.327 | 0.524 / 0.281 | 0.581 / 0.177 |
| all 24 days, 6 | 0.631 / 0.138 | 0.623 / 0.139 | 0.619 / 0.139 | 0.639 / 0.140 | 0.489 / 0.365 | 0.516 / 0.267 | 0.612 / 0.178 |
| Sep 4–5, 1 | 0.575 / 0.096 | 0.539 / 0.096 | 0.555 / 0.096 | 0.534 / 0.098 | 0.359 / 0.365 | 0.538 / 0.218 | 0.466 / 0.119 |
| Sep 4–5, 3 | 0.493 / 0.158 | 0.488 / 0.159 | 0.471 / 0.159 | 0.476 / 0.158 | 0.395 / 0.425 | 0.519 / 0.297 | 0.424 / 0.218 |
| Sep 4–5, 6 | 0.466 / 0.123 | 0.421 / 0.124 | 0.440 / 0.122 | 0.447 / 0.120 | 0.392 / 0.444 | 0.501 / 0.196 | 0.409 / 0.203 |

**The main model stays the full-history LightGBM without Telegram.** The best Telegram model (2026-only, posts < t) is still
under it at every H (H=1: 0.681 against 0.688, and so on in the table above), and Telegram covers only 2026.

Pooled AUC, all 24 days: H=1: 0.835 (lag 0), 0.833 (15 min) vs 0.831 without; H=3: 0.849 (lag 0), 0.849 (15 min) vs 0.848 without; H=6: 0.883 (lag 0), 0.882 (15 min) vs 0.882 without.

Paired comparison, with Telegram minus without (`results/telegram/telegram_vs_no_telegram.md`; day-block
bootstrap, point value and 95% interval):
- posts before t (lag 0):
  - H=1: +0.0322 [+0.0039, +0.0531] AUC; -0.0006 [-0.0011, -0.0001] Brier; 20 of 24 oblasts have the higher AUC
  - H=3: -0.0038 [-0.0128, +0.0096] AUC; -0.0003 [-0.0009, +0.0002] Brier; 10 of 24 oblasts have the higher AUC
  - H=6: +0.0124 [+0.0060, +0.0191] AUC; -0.0005 [-0.0011, -0.0000] Brier; 16 of 24 oblasts have the higher AUC
- posts before t − 15 min (lag 15):
  - H=1: -0.0344 [-0.0501, +0.0078] AUC; -0.0003 [-0.0005, -0.0001] Brier; 13 of 24 oblasts have the higher AUC
  - H=3: -0.0365 [-0.0594, +0.0104] AUC; -0.0004 [-0.0010, +0.0001] Brier; 9 of 24 oblasts have the higher AUC
  - H=6: +0.0042 [-0.0070, +0.0125] AUC; -0.0000 [-0.0007, +0.0006] Brier; 11 of 24 oblasts have the higher AUC

Feature importance (`results/telegram/feature_importance.md`): only `tg_min_since` carries weight; H=1: rank 9 of 21 (3.3% of gain) at lag 0, rank 10 (2.0%) at lag 15; H=3: rank 13 of 21 (1.3% of gain) at lag 0, rank 15 (0.9%) at lag 15; H=6: rank 11 of 21 (0.9% of gain) at lag 0, rank 13 (0.8%) at lag 15.
`tg_m1h` and `tg_m3h` take 0.0% of the gain (each is a threshold of `tg_min_since`: named within the last
60 or 180 minutes, plus 15 at lag 15); `tg_share6h` and the three flags take 0.1–0.5% each.

**What this says.**
- With posts up to t, Telegram improves H=1 and H=6 a little (H=1 is the clearest). The Brier change is at most 0.0006.
- With the 15-minute lag the within-oblast AUC gain is gone at H=1 and H=6 (H=1: lower, the interval
  includes zero), and H=3 shows no gain at either lag. So the gain depends on posts from the last 15 minutes:
  the signal is real but short-lived. Only two lags were tried (0 and 15 min), so how fast it decays is not known.
- Within-oblast AUC moves by 0.03–0.04 between models with the same Brier (main's full-history model
  against the 2026 model at H=1: 0.688 against 0.648, Brier 0.087 for both), and the bootstrap covers
  the sampling of days only, not a refit. Read the AUC differences with that in mind.
- On Sep 4–5 same hour yesterday still has the higher within-oblast AUC than every LightGBM variant at H=3
  and H=6.

**Limitations.**
- Deleted posts are invisible: the page shows the channel as it is now, not as it looked at t.
- Edited posts keep their original time, but their text is the text at pull time and may have changed
  after t. 602 posts (2.3%) are marked edited, 135 of 5,321 in the test window. Leaving them out changes
  at most 1.7% of the values of any column materially (last line of `no_peeking.txt`).
- The place list is not exhaustive: 11.1% of posts name no oblast, and ambiguous place names are left out
  on purpose.
- Sep 4–5 is 48 origins per oblast.

## Forward test on the Ukraine Alarm API

**Source: the Ukraine Alarm API (`api.ukrainealarm.com`), one source for every feature and every outcome.** Separate from the old test (official data, 24 days); the two are not pooled.
Files: `results/forward_api/` (made by `scripts/forward_test.py --score`), archive `data/api_archive/` (made by `scripts/archive_api.py`), consistency with the official data `results/api_check.md`.

- **What is frozen:** the round-13 LightGBM fits, the logistic weights, the train-frequency table and every F1 threshold (all from official data to 2026-08-07; thresholds from the last train week), saved by `scripts/evaluate.py`
  in `models/` (`frozen.json`). Nothing is refitted or retuned. `forward_test.py --selftest` shows the scoring code gives the old test's table back from these artifacts.
- **Rows:** origins 2026-09-07 00:00 to 2026-10-17 23:00 UTC, **41 days**, 23,616 oblast-hours per horizon; targets close by 2026-10-18 06:00. Features use the API archive only, from 2026-08-06 (so the 7-day windows and the four lags of
  `freq4w` are complete). **No outage mask:** the mask in `src/features.py` exists because the official feed had no data for 2026-08-29..09-02; the API has, so masking would throw away observed data (decided before scoring, in `PROCESS_LOG.md`).
- **Checked before scoring (`results/forward_api/diagnostics.md`):** features built from the API equal the official ones on the same rows (Aug 13-28) apart from sub-second timing and the Aug 19-20 wave; a leakage check on 40 forward origins
  (37,440 values) has 0 mismatches; no thin days in the API; the forward period is busier than the old test (share of origins with a new alert at H=1: 0.180 against 0.121; at H=6: 0.571 against 0.432).
- **Predictors:** LightGBM, logistic, the three baselines of the old test (same as now, same hour yesterday, train frequency) and, as an extra, the rolling 4-week frequency (the model's `freq4w` feature used as a score; frozen threshold).
  Target (b) only. Thresholded metrics at the frozen thresholds; 0/1 baselines raw.

### Results (within-oblast AUC, Brier, precision, recall, F1)
| H | predictor | n | base_rate | auc_within_oblast | brier | threshold | precision | recall | f1 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 23616 | 0.180 | 0.708 | 0.119 | 0.187 | 0.419 | 0.669 | 0.515 |
| 1 | logistic | 23616 | 0.180 | 0.538 | 0.136 | 0.148 | 0.306 | 0.700 | 0.426 |
| 1 | same as now | 23616 | 0.180 | 0.407 | 0.400 | raw 0/1 | 0.116 | 0.186 | 0.143 |
| 1 | same hour yesterday | 23616 | 0.180 | 0.515 | 0.255 | raw 0/1 | 0.287 | 0.283 | 0.285 |
| 1 | train frequency | 23616 | 0.180 | 0.531 | 0.152 | 0.075 | 0.246 | 0.622 | 0.353 |
| 1 | rolling 4-week frequency | 23616 | 0.180 | 0.519 | 0.160 | 0.250 | 0.266 | 0.631 | 0.374 |
| 3 | LightGBM | 23616 | 0.414 | 0.662 | 0.167 | 0.243 | 0.613 | 0.877 | 0.721 |
| 3 | logistic | 23616 | 0.414 | 0.561 | 0.183 | 0.321 | 0.642 | 0.781 | 0.705 |
| 3 | same as now | 23616 | 0.414 | 0.459 | 0.429 | raw 0/1 | 0.474 | 0.329 | 0.389 |
| 3 | same hour yesterday | 23616 | 0.414 | 0.532 | 0.323 | raw 0/1 | 0.612 | 0.603 | 0.607 |
| 3 | train frequency | 23616 | 0.414 | 0.522 | 0.259 | 0.176 | 0.549 | 0.667 | 0.602 |
| 3 | rolling 4-week frequency | 23616 | 0.414 | 0.536 | 0.216 | 0.250 | 0.546 | 0.884 | 0.675 |
| 6 | LightGBM | 23616 | 0.571 | 0.654 | 0.143 | 0.314 | 0.750 | 0.915 | 0.824 |
| 6 | logistic | 23616 | 0.571 | 0.573 | 0.152 | 0.289 | 0.756 | 0.899 | 0.821 |
| 6 | same as now | 23616 | 0.571 | 0.475 | 0.445 | raw 0/1 | 0.719 | 0.363 | 0.482 |
| 6 | same hour yesterday | 23616 | 0.571 | 0.536 | 0.264 | raw 0/1 | 0.772 | 0.763 | 0.768 |
| 6 | train frequency | 23616 | 0.571 | 0.519 | 0.256 | 0.278 | 0.732 | 0.717 | 0.725 |
| 6 | rolling 4-week frequency | 23616 | 0.571 | 0.528 | 0.189 | 0.500 | 0.769 | 0.827 | 0.797 |

### Intervals (day-block bootstrap: whole days resampled with replacement, 1,000 resamples, seed 0, 95% percentile intervals)
Each predictor:

| H | predictor | auc | auc_lo | auc_hi | brier | brier_lo | brier_hi |
|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.708 | 0.677 | 0.731 | 0.119 | 0.113 | 0.126 |
| 1 | logistic | 0.538 | 0.503 | 0.570 | 0.136 | 0.128 | 0.145 |
| 1 | same as now | 0.407 | 0.394 | 0.418 | 0.400 | 0.377 | 0.424 |
| 1 | same hour yesterday | 0.515 | 0.507 | 0.523 | 0.255 | 0.243 | 0.268 |
| 1 | train frequency | 0.531 | 0.508 | 0.550 | 0.152 | 0.141 | 0.163 |
| 1 | rolling 4-week frequency | 0.519 | 0.511 | 0.526 | 0.160 | 0.152 | 0.169 |
| 3 | LightGBM | 0.662 | 0.622 | 0.691 | 0.167 | 0.160 | 0.174 |
| 3 | logistic | 0.561 | 0.529 | 0.589 | 0.183 | 0.174 | 0.192 |
| 3 | same as now | 0.459 | 0.446 | 0.471 | 0.429 | 0.412 | 0.447 |
| 3 | same hour yesterday | 0.532 | 0.517 | 0.544 | 0.323 | 0.311 | 0.338 |
| 3 | train frequency | 0.522 | 0.498 | 0.544 | 0.259 | 0.243 | 0.276 |
| 3 | rolling 4-week frequency | 0.536 | 0.523 | 0.548 | 0.216 | 0.207 | 0.225 |
| 6 | LightGBM | 0.654 | 0.610 | 0.689 | 0.143 | 0.134 | 0.152 |
| 6 | logistic | 0.573 | 0.537 | 0.605 | 0.152 | 0.142 | 0.162 |
| 6 | same as now | 0.475 | 0.458 | 0.489 | 0.445 | 0.429 | 0.459 |
| 6 | same hour yesterday | 0.536 | 0.517 | 0.555 | 0.264 | 0.244 | 0.285 |
| 6 | train frequency | 0.519 | 0.487 | 0.548 | 0.256 | 0.243 | 0.271 |
| 6 | rolling 4-week frequency | 0.528 | 0.505 | 0.551 | 0.189 | 0.178 | 0.200 |

LightGBM minus each other predictor (AUC: positive = LightGBM ahead; Brier: negative = LightGBM ahead; `share_*_ahead` = share of resamples in which it is ahead):

| H | predictor | d_auc | d_auc_lo | d_auc_hi | share_auc_ahead | d_brier | d_brier_lo | d_brier_hi | share_brier_ahead |
|---|---|---|---|---|---|---|---|---|---|
| 1 | logistic | 0.170 | 0.138 | 0.205 | 1.000 | -0.017 | -0.019 | -0.014 | 1.000 |
| 1 | same as now | 0.301 | 0.267 | 0.328 | 1.000 | -0.281 | -0.301 | -0.262 | 1.000 |
| 1 | same hour yesterday | 0.193 | 0.161 | 0.218 | 1.000 | -0.136 | -0.144 | -0.127 | 1.000 |
| 1 | train frequency | 0.177 | 0.140 | 0.210 | 1.000 | -0.032 | -0.037 | -0.028 | 1.000 |
| 1 | rolling 4-week frequency | 0.189 | 0.159 | 0.211 | 1.000 | -0.041 | -0.044 | -0.038 | 1.000 |
| 3 | logistic | 0.101 | 0.068 | 0.138 | 1.000 | -0.016 | -0.019 | -0.013 | 1.000 |
| 3 | same as now | 0.203 | 0.165 | 0.234 | 1.000 | -0.263 | -0.278 | -0.247 | 1.000 |
| 3 | same hour yesterday | 0.130 | 0.093 | 0.159 | 1.000 | -0.157 | -0.170 | -0.145 | 1.000 |
| 3 | train frequency | 0.140 | 0.106 | 0.175 | 1.000 | -0.092 | -0.106 | -0.078 | 1.000 |
| 3 | rolling 4-week frequency | 0.126 | 0.088 | 0.157 | 1.000 | -0.049 | -0.055 | -0.043 | 1.000 |
| 6 | logistic | 0.080 | 0.050 | 0.109 | 1.000 | -0.009 | -0.011 | -0.007 | 1.000 |
| 6 | same as now | 0.179 | 0.135 | 0.215 | 1.000 | -0.302 | -0.318 | -0.286 | 1.000 |
| 6 | same hour yesterday | 0.117 | 0.079 | 0.146 | 1.000 | -0.121 | -0.137 | -0.105 | 1.000 |
| 6 | train frequency | 0.135 | 0.090 | 0.170 | 1.000 | -0.113 | -0.132 | -0.097 | 1.000 |
| 6 | rolling 4-week frequency | 0.126 | 0.078 | 0.165 | 1.000 | -0.046 | -0.053 | -0.038 | 1.000 |

### Calibration in the large, and what the higher base rate does to the Brier score
Mean predicted against observed, per horizon. Brier = (mean predicted - observed)^2 + Var(p - y) exactly, so `bias^2` is the calibration-in-the-large part of the Brier score:

| H | predictor | mean_predicted | observed | bias | bias^2 | brier | bias^2 share of Brier |
|---|---|---|---|---|---|---|---|
| 1 | LightGBM | 0.1516 | 0.1796 | -0.0280 | 0.0008 | 0.1193 | 0.0066 |
| 1 | logistic | 0.1561 | 0.1796 | -0.0235 | 0.0006 | 0.1359 | 0.0041 |
| 1 | train frequency | 0.0857 | 0.1796 | -0.0940 | 0.0088 | 0.1517 | 0.0582 |
| 1 | rolling 4-week frequency | 0.1549 | 0.1796 | -0.0247 | 0.0006 | 0.1603 | 0.0038 |
| 3 | LightGBM | 0.3681 | 0.4143 | -0.0462 | 0.0021 | 0.1666 | 0.0128 |
| 3 | logistic | 0.3731 | 0.4143 | -0.0412 | 0.0017 | 0.1827 | 0.0093 |
| 3 | train frequency | 0.2258 | 0.4143 | -0.1886 | 0.0356 | 0.2590 | 0.1373 |
| 3 | rolling 4-week frequency | 0.3680 | 0.4143 | -0.0464 | 0.0022 | 0.2159 | 0.0100 |
| 6 | LightGBM | 0.5315 | 0.5711 | -0.0396 | 0.0016 | 0.1428 | 0.0110 |
| 6 | logistic | 0.5413 | 0.5711 | -0.0298 | 0.0009 | 0.1516 | 0.0059 |
| 6 | train frequency | 0.3691 | 0.5711 | -0.2020 | 0.0408 | 0.2563 | 0.1592 |
| 6 | rolling 4-week frequency | 0.5192 | 0.5711 | -0.0519 | 0.0027 | 0.1889 | 0.0143 |

How the Brier score changed from the old test to this one (old rows re-scored with the same frozen artifacts; Murphy terms as in `results/calibration.md`; the full table and the reliability bins are in `results/forward_api/calibration.md`):

- H=1, LightGBM: Brier 0.0875 -> 0.1193 (+0.0318). The higher base rate alone changes the uncertainty term by +0.0407 (128% of the change); resolution changes by +0.0097 (a rise lowers the Brier), reliability by +0.0012, residual by -0.0003. Calibration in the large: squared bias 0.0001 -> 0.0008 (+0.0007, 2% of the Brier change).
- H=1, train frequency: Brier 0.1014 -> 0.1517 (+0.0503). The higher base rate alone changes the uncertainty term by +0.0407 (81% of the change); resolution changes by -0.0022 (a rise lowers the Brier), reliability by +0.0076, residual by -0.0002. Calibration in the large: squared bias 0.0013 -> 0.0088 (+0.0076, 15% of the Brier change).
- H=3, LightGBM: Brier 0.1446 -> 0.1666 (+0.0220). The higher base rate alone changes the uncertainty term by +0.0344 (156% of the change); resolution changes by +0.0144 (a rise lowers the Brier), reliability by +0.0019, residual by +0.0002. Calibration in the large: squared bias 0.0003 -> 0.0021 (+0.0018, 8% of the Brier change).
- H=3, train frequency: Brier 0.1773 -> 0.2590 (+0.0817). The higher base rate alone changes the uncertainty term by +0.0344 (42% of the change); resolution changes by -0.0147 (a rise lowers the Brier), reliability by +0.0328, residual by -0.0002. Calibration in the large: squared bias 0.0049 -> 0.0356 (+0.0307, 38% of the Brier change).
- H=6, LightGBM: Brier 0.1398 -> 0.1428 (+0.0030). The higher base rate alone changes the uncertainty term by -0.0001 (-5% of the change); resolution changes by -0.0015 (a rise lowers the Brier), reliability by +0.0014, residual by +0.0003. Calibration in the large: squared bias 0.0001 -> 0.0016 (+0.0015, 49% of the Brier change).
- H=6, train frequency: Brier 0.1777 -> 0.2563 (+0.0785). The higher base rate alone changes the uncertainty term by -0.0001 (-0% of the change); resolution changes by -0.0386 (a rise lowers the Brier), reliability by +0.0406, residual by -0.0005. Calibration in the large: squared bias 0.0036 -> 0.0408 (+0.0372, 47% of the Brier change).

### Secondary, not the result: the same test with the official outage mask on
`results/forward_api/secondary_mask_on.md`. Switching the mask on changes the model's within-oblast AUC by at most 0.0020 and its Brier by at most 0.0006 (any horizon); the logistic model by at most 0.0022 in AUC; the rolling 4-week frequency baseline moves more in Brier (up to +0.0102 at H=6).
Same frozen models, same thresholds, point estimates only.

### Caveats
- 41 days is short, and the intervals show it (for example the LightGBM AUC at H=1: see the interval table). One period, one source.
- The API and the official feed are probably not independent (the API names the official channel among its sources): `results/api_check.md` shows our rules give the same oblast series from both (99.8% of 14,976 oblast-hours agree), not that either is right about reality.
- The period is busier than the old test and the models predict low (see the calibration table); nothing was recalibrated. Not compared: anything after 2026-10-17, and Sep 6 (neither in the official trusted range nor in this test).

## Limitations and what we would do next
Limitations:
- **Volunteer vs official agreement** fell from κ 0.985 (2022Q3) to 0.448 (2026Q3). About 0.025
  of that is the Lviv/Volyn parser bug; the rest is unexplained.
- **Western oblasts:** Lviv, Ivano-Frankivsk and Zakarpattia had one new alert each in the 24 test
  days. Their within-oblast AUCs are close to noise. In the five furthest west, the model
  predicts about 0.06–0.07 at H=6 where 0.01–0.03 happened.
- **Sep 4–5:** two days with 7-day features scaled from the observed hours. Every predictor scores
  lower there, and two days can't say why.
- **Thresholds** come from a validation fit on train minus the last week, not from the model
  scored on test. The frequency baseline's threshold has the same approximation.
- **The official feed stopped on 2026-09-07,** so the test window ends a month before the pull. It
  can't move until upstream recovers.
- **The raion switch (Jul–Dec 2025)** changed what an alert means. The half-of-raions rule keeps
  base rates roughly continuous for most oblasts but not all (Kherson), and training mixes both
  regimes. Training only on 2026 neither clearly helped nor hurt.
- **The official feed misses one wave inside the old test window.** On 2026-08-19 from about 20:52 UTC, the Ukraine Alarm API has alerts in Chernihivska and Kyivska oblast
  (about 10–13 hours) that our official data does not have: 25 oblast-hours where the old test's target says "no alert". The data and the old test are unchanged. With those
  hours put back (a patched copy, `scripts/sensitivity_aug19.py`), the model's within-oblast AUC changes by +0.0031 / +0.0014 / +0.0002 at H = 1 / 3 / 6 and its Brier by
  0.0000 / 0.0000 / −0.0002; the baselines move by at most 0.0024 in AUC (`results/aug19_sensitivity.md`).

Next:
- Weekly refits through the test window, to see whether level drift costs the model what it
  costs the static frequency table.
- A hazard-style model: the probability of a new alert as a function of time since the last one
  ended, per oblast, instead of fixed H windows.
- Raion-level targets, so frontline raions and quieter ones are forecast separately rather than
  through the half-of-raions rule.
- Telegram. What we found: the Air Force channel's posts, matched to oblasts, add a little at H=1 and H=6 when they are
  used up to t, and nothing with a 15-minute lag, so the signal is real but short-lived (nowcasting, not
  forecasting). What we would do next: (1) a lag sweep (0, 5, 10, 15 min, and so on) to see how fast it decays;
  (2) pull the full history (about 3,850 pages, 3–5 hours) so the Telegram model can be compared with the
  full-history model on equal terms; (3) threat types per oblast instead of three national flags, which carry
  almost nothing now.

## Run order

The commands, in order. These lines can be pasted as they are, also into zsh. What each one does is under the block. The three scripts that re-pull data from the internet are left out of the block on purpose: they replace the pinned data snapshot (and with it, possibly, the numbers). They are listed at the end.

```bash
pip install -r requirements.txt
python scripts/inspect_raw.py
python scripts/build_panel.py
python scripts/build_panel.py --min-share 0
python scripts/build_panel.py --source volunteer
python scripts/plot_weekly.py
python scripts/hand_checks.py
python scripts/evaluate.py
python scripts/plot_timeline.py
python scripts/check_no_peeking.py
python scripts/predict.py --at "2026-09-05 14:00" --all
python scripts/predict.py --now --oblast Kharkivska
pip install translitua
python scripts/source_check.py
python scripts/api_check.py
python scripts/sensitivity_aug19.py
python scripts/forward_test.py --selftest
python scripts/forward_test.py --diagnose
python scripts/check_gdelt_events.py
python scripts/news_correlation.py
python scripts/evaluate_news.py
python scripts/check_no_peeking_news.py
python scripts/test_telegram_parser.py
python scripts/telegram_parser_check.py
python scripts/evaluate_telegram.py
python scripts/check_no_peeking_telegram.py
```

- `pip install -r requirements.txt`: install the packages (Python 3.9 to 3.13)
- `python scripts/inspect_raw.py`: raw file summary: columns, ranges, duplicates, naive flag
- `python scripts/build_panel.py`: hourly panel -> data/processed/panel_official_min0.5.csv.gz
- `python scripts/build_panel.py --min-share 0`: variant: oblast = any raion
- `python scripts/build_panel.py --source volunteer`: variant: volunteer feed
- `python scripts/plot_weekly.py`: figures/alerts_per_week.png (+ .csv)
- `python scripts/hand_checks.py`: round-1 hand-check numbers (needs the three panels)
- `python scripts/evaluate.py`: model + baselines: tables in results/, H=6 plots
- `python scripts/plot_timeline.py`: figures/forecast_timeline.png (+ .csv): the saved H=1 model, hour by hour, for two oblasts on five test days (needs models/)
- `python scripts/check_no_peeking.py`: leakage check: baseline inputs and model features
- `python scripts/predict.py --at "2026-09-05 14:00" --all`: model at a past hour (needs models/)
- `python scripts/predict.py --now --oblast Kharkivska`: checks the official channel for newer data; there is none, so it says so and shows the latest hour we have
- `pip install translitua`: the one package the upstream parser needs (only for `source_check.py`)
- `python scripts/source_check.py`: the unmodified upstream parser on the source channel's posts against our csv -> results/source_check.md (downloads four small upstream files from GitHub)
- `python scripts/api_check.py`: the Ukraine Alarm API history (data/api_archive/) against our official data, same rules for both -> results/api_check.md (needs translitua)
- `python scripts/sensitivity_aug19.py`: the old test on a patched copy with the Aug 19-20 wave put back -> results/aug19_sensitivity.md (about 2 minutes; the repo data is not touched)
- `python scripts/forward_test.py --selftest`: the forward test's scoring code on the old test rows must give results/test_table.csv back
- `python scripts/forward_test.py --diagnose`: does the feature pipeline behave the same on API data? -> results/forward_api/diagnostics.md (no outcome is scored)

**News experiment (scripts/evaluate_news.py runs the four steps after the re-pull)**

- `python scripts/check_gdelt_events.py`: gaps, heavy days, figures/gdelt_weekly.png (builds the panel if missing)
- `python scripts/news_correlation.py`: news vs starts_7d / share_7d on training rows
- `python scripts/evaluate_news.py`: 2026 model with and without news -> results/news/
- `python scripts/check_no_peeking_news.py`: leakage check for the news columns

**Telegram experiment (scripts/evaluate_telegram.py runs the parser check, the comparison and the leakage check)**

- `python scripts/test_telegram_parser.py`: oblast parser and threat-flag tests
- `python scripts/telegram_parser_check.py`: 50 random posts + substring traps -> results/telegram/parser_check_50.md
- `python scripts/evaluate_telegram.py`: 2026 model with and without Telegram, lag 0 and 15 min -> results/telegram/
- `python scripts/check_no_peeking_telegram.py`: leakage check for the Telegram columns

**Re-pulling the data** (optional, needs network, replaces the snapshot in the repo; run only if you want new data)

- `python scripts/fetch_data.py`: re-pull (overwrites data/raw/, updates PULL_INFO.md)
- `python scripts/fetch_gdelt_events.py`: re-pull GDELT events, about 9 minutes, needs network -> data/news/
- `python scripts/fetch_telegram_kpszsu.py`: re-pull t.me/s/kpszsu, about 70 minutes, needs network -> data/telegram/
- `python scripts/api_probe.py` and `python scripts/archive_api.py`: talk to the Ukraine Alarm API, need your own token in the shell variable `UA_ALARM_TOKEN` (never in a file) -> data/api_raw/ (git-ignored), data/api_archive/

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
src/news.py          national GDELT news features (the news experiment)
src/telegram_*.py     Telegram post parser (oblasts, threat types) and per-oblast features (the Telegram experiment)
data/neighbours.csv  hand-written oblast adjacency (land borders), used by the neighbour features
data/news/           GDELT hourly aggregate + pull record (the news experiment)
data/source_check/    public posts of the official alert channel for Aug 13–18 (compressed), for results/source_check.md
data/api_archive/      Ukraine Alarm API history saved by scripts/archive_api.py (the forward test and the API check read it)
docs/api/             the API's swagger json
data/telegram/       public posts of t.me/s/kpszsu (the Telegram experiment)
models/              fitted by scripts/evaluate.py for scripts/predict.py (gitignored)
scripts/             one script per step, run from the repo root
results/             evaluation tables
figures/             plots and the tables behind them
PROCESS_LOG.md       lab notebook
CLAUDE.md            working rules for this repo
```
