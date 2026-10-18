# Details

The long version of the [README](../README.md): the data, the targets and baselines, the model, the two text experiments, the full limitations, the run order, the definitions and the layout. File paths in code spans are relative to the repository root.

## Contents
- [Data](#data): the sources, what "under alert" means, the feed outage.
- [Targets, baselines, evaluation (`scripts/evaluate.py`)](#targets-baselines-evaluation-scriptsevaluatepy): the two targets, the three simple rules, the metrics.
- [Model (`scripts/evaluate.py`, `src/features.py`)](#model-scriptsevaluatepy-srcfeaturespy): the features and the LightGBM setup.
- [News and text data](#news-and-text-data): why the main model uses no text, and two experiments that were tried: GDELT news (a negative result) and Telegram posts (a real gain that lasts only minutes, so a nowcasting signal and not a forecast). The main model uses neither.
- [Forward test on the Ukraine Alarm API](#forward-test-on-the-ukraine-alarm-api): the frozen models scored on 41 days of live API data, separate from the old test.
- [The combined dataset](#the-combined-dataset-official-data--the-api-archive): official data up to 2026-08-28, the API archive after it, the Aug 19-20 patch; every splice point and its checks.
- [The live forecast log and its scorer](#the-live-forecast-log-and-its-scorer)
- [v2: LightGBM trained on the combined dataset](#v2-lightgbm-trained-on-the-combined-dataset): the round-16 model, the held-out comparison with frozen v1, the decision rule.
- [The forecast map](#the-forecast-map): `output/forecast_map.html`, written by `predict.py --now` and `--at`.
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

## The combined dataset (official data + the API archive)

For the next round. **Nothing is trained on it yet.** Built by `scripts/build_combined.py` (offline, deterministic) into `data/combined/alerts_combined.csv` (about 22 MB, not committed; rebuild it and compare the SHA-256 in `data/combined/MANIFEST.md`, which is committed together with the counts below).
Checked by `scripts/check_combined.py` -> `results/combined_splice_check.md`. The SHA-256 in the manifest is the one to compare after a rebuild on another machine: with the cut, later days saved in the archive do not change the file (only a re-fetch of days up to 2026-10-17 can). Rows keep the schema of the official file plus a `source` column: `official`, `api`, `api_patch`.

**Every splice point**
1. **Official -> API at T = 2026-08-29 00:00:00 UTC.** Official rows that END at or before T are kept (183,292). API rows (alertType AIR, closed, our oblasts) that END after T are kept (27,497); the 8,237 API rows that end earlier are not used because the official side has those alerts.
   An alert that was running at T therefore comes from the API, with the API's start time. The 46 official rows that span T (start before, end after: 43 raion rows and 3 hromada rows; 43 of 46 have an API row of the same raion starting within 60 s, the 3 others are the hromada
   rows, which do not exist on the API side) are dropped. The official rows that START at or after T (2,025, dated 2026-08-29 00:06 to 09-07 05:28 UTC: 88 on Aug 29, 241 on Sep 2, then 448, 461, 381, 357 and 49 on Sep 3 to 7, so the official outage was patchy, not a blackout) are not used either: after T there is one source, so there is no second splice and no hole.
2. **The Aug 19-20 patch (`api_patch`).** The API's raion rows of Chernihivska and Kyivska oblast that start between 2026-08-19 19:00 and 2026-08-20 12:00 UTC (18 rows) are added on top of the official rows. The official feed has 6 rows of the same wave (1 Chernihivska, 5 Kyivska); they are
   kept as they are, and since episodes are unions, an overlap changes nothing. This is the same set that `results/aug19_sensitivity.md` put back (25 oblast-hours change from quiet to under alert).
3. **Time stamps.** The official side has second resolution; the API side has microseconds (written as they are). Where the two describe the same alert they differ by a fraction of a second, usually (results/api_check.md: 9,263 of 9,360 official raion rows have an API row of the same raion starting within 5 s).
4. **Levels.** After T there are raion rows and oblast-level rows (only `Kyiv City` comes as an oblast-level row from the API); there are no hromada rows (the API's community records are dropped, as `src/panel.py` ignores hromada alerts anyway). Before T the official hromada rows (20,653) stay in the file and are ignored by the rule.
5. **Names and filters.** Oblast and raion names are the official feed's (API names are mapped by transliteration; Sheptytskyi raion is our Chervonohradskyi raion, a 2024 rename); the raion list stays the official one (118 raions) for the half-of-raions rule; Luhansk (permanent alert) is left out as in `src/dataset.load_inputs`; alertType other than AIR is dropped.
6. **The cut at the end.** Everything is cut at 2026-10-18 00:00:00 UTC (all of 2026-10-17 is in): API rows that start at or after it are ignored (534) and an end after it is clipped to it (47 rows, among them the alerts that were still running when the archive was fetched, which have no end), so the file does not depend on when the archive was last refreshed. An alert running at the cut is a row that ends at the cut; a forecast at t only uses what is known at t, so only origins up to the cut are ever used with it. (The first version, in round 15, left out running alerts and trusted the archive to 2026-10-18 06:00; the rebuilt file replaces it.)
7. **The outage mask is not used on this dataset.** The official feed's outage (2026-08-29 to 09-02) is covered by the API, so the combined series has no unobserved period: features are built with `build_features(..., outages=[])`, and the rows that `src.dataset.split` removes for touching `OFFICIAL_OUTAGES`
   must not be removed for the combined data (they are observed). The old test and `evaluate.py` still use the official-only data and the mask.

**Does a feature behave the same at the splice?** (`results/combined_splice_check.md`)
- Before the splice, on rows the patch cannot reach (2026-08-12 to 08-19 19:59 and 08-27 20:00 to 08-28 23:00), the combined features equal the official-only ones exactly (all 13 features, 0.0000 mean difference). From 08-19 20:00 the 7-day windows contain the patched wave, so they differ there by design (for example
  `starts_7d` mean difference 0.13 over 5,280 oblast-hours).
- Around and after the splice (T -48 h to 09-05), combined against API-only: equal within 0.001 on all features but a handful of rows (largest differences 0.06 h in `hours_since_start`, 0.011 in `share_6h`); at the splice hour all 24 oblasts have the same `now`. `freq4w` (2026-09-03 to 09-19): 9,760 of 9,792 rows equal, the others differ by at most 0.25 (one of the four weekly lags differs).
- Continuity: the daily means of the main features run smoothly through 08-29 (the table in the check file). `starts_7d` and `share_7d` change more across T than most neighbouring 48 h blocks, because they are 7-day windows of a series whose alert rate was rising from 08-27 on; the two checks above show the combined
  series equals the official series before T and the API series after T, so that change is in the data, not made by the splice. The number of oblast episodes per day is steady across T (113 on 08-28, 107 on 08-29).
- Leakage: features at 24 origins around T rebuilt from combined rows cut at t equal the full-data features (22,464 values, 0 mismatches).

## The live forecast log and its scorer

- **The log:** every run of `python scripts/predict.py --now` appends its whole forecast (24 oblasts x H = 1, 3, 6) to `data/predictions/log.csv`, whatever `--oblast` shows: `origin_utc, oblast, h, probability, above_threshold, threshold, model_version, run_time_utc`. Append only: the file is opened for appending, nothing in it is ever rewritten,
  and nothing is written if an existing file has a different header. `model_version` is `frozen-r13-` plus 12 hex digits of the SHA-256 of the three LightGBM files and `models/frozen.json`. Whether to commit the log is the user's call.
- **The scorer:** `python scripts/score_predictions.py` (offline, no token; `--write` also writes `results/live_forecast_scores.md`). It scores the forecasts whose horizon has fully passed against the API archive with the same target and metrics as the forward test (within-oblast AUC, Brier, calibration in the large, precision/recall/F1 at the logged
  decision), next to the three baselines on the same rows. A forecast is scored only if both day files that its window (t, t+H] touches were fetched at least 5 minutes after t+H (from `data/api_archive/log.csv`); the others are counted as not scoreable yet, never guessed. If one origin/oblast/H was logged twice, the first run is scored. The log is only read.
- **When the sample is too small** (my choice of lines, stated in the output): fewer than 3 scored dates is "far too small to mean anything" (no interval computed); 3 to 13 dates is "too small to mean anything yet" (the day-block interval is shown and is very wide); 14 or more is "a start", still short of the forward test's 41 days. The report always says how many forecasts, origin hours and which dates were scored,
  and warns if the scored forecasts come from more than one model version.
- **Tested offline:** a synthetic log with the frozen model's probabilities for every hour of the forward test (2026-09-07 to 10-17) is scored to exactly the forward test's table (60 cells: AUC, Brier, precision, recall, F1 for LightGBM and the three baselines); the edge cases (an origin whose horizon has not passed, one beyond the archive, a duplicate run, a mixed header, an empty log) behave as described.

## v2: LightGBM trained on the combined dataset

Round 16. **The design, with the decision rule, is in `PROCESS_LOG.md` ("Round 16 ... DESIGN, fixed before any test number is seen"), committed (4e0c628) before the training script existed and before any v2 number was computed.** Script: `scripts/train_v2.py`; results: `results/v2/`; production model: `models/v2/` (not committed; `python scripts/build_combined.py` then `python scripts/train_v2.py` rebuilds it, deterministically: a second run gave byte-identical results and model files).

- **Data:** the combined dataset (official to 2026-08-28, API from 08-29, the Aug 19-20 patch), cut at 2026-10-18 00:00 UTC; no outage mask (features with `outages=[]`, rows split with `outages=()`).
- **Split, per H, as v1's `split()` with test_start = 2026-09-28:** train = windows closing by 09-28 (950,400 / 950,352 / 950,280 rows at H = 1 / 3 / 6); validation fit = windows closing by 09-21; validation week 09-21 to 09-27 for early stopping and the F1 threshold; final fit on all train rows with the early-stopped tree count (194 / 181 / 149 trees); test = 09-28 to 10-17, 20 days (11,520 / 11,472 / 11,400 rows). Thresholds come from the validation fit (v1's known approximation).
- **Model:** v1's features and hyperparameters, nothing tuned. **Predictors on the same test rows:** v2; v2 with Platt scaling fitted on the validation week only (secondary); frozen v1; a logistic regression refit on the v2 rows; same as now; same hour yesterday; train frequency (fitted on the v2 train rows); rolling 4-week frequency.
- **v1 was already scored on these days in the forward test.** It is 20 days from one source; the intervals are wide.

### Results (within-oblast AUC, Brier, precision, recall, F1 at the validation-week threshold)

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

### Intervals (day-block bootstrap: whole test days resampled, 1,000 resamples, seed 0, 95% percentile intervals)
Each predictor:

| H | predictor | auc | auc_lo | auc_hi | brier | brier_lo | brier_hi |
|---|---|---|---|---|---|---|---|
| 1 | v2 LightGBM | 0.692 | 0.650 | 0.722 | 0.127 | 0.117 | 0.136 |
| 1 | v2 + Platt (secondary) | 0.692 | 0.650 | 0.722 | 0.127 | 0.117 | 0.136 |
| 1 | frozen v1 LightGBM | 0.686 | 0.644 | 0.714 | 0.129 | 0.118 | 0.139 |
| 1 | logistic (refit on the v2 rows) | 0.531 | 0.501 | 0.563 | 0.147 | 0.133 | 0.160 |
| 1 | same as now | 0.400 | 0.380 | 0.417 | 0.421 | 0.382 | 0.458 |
| 1 | same hour yesterday | 0.517 | 0.506 | 0.528 | 0.269 | 0.247 | 0.289 |
| 1 | train frequency | 0.513 | 0.492 | 0.528 | 0.165 | 0.148 | 0.181 |
| 1 | rolling 4-week frequency | 0.509 | 0.499 | 0.520 | 0.172 | 0.158 | 0.185 |
| 3 | v2 LightGBM | 0.663 | 0.622 | 0.693 | 0.166 | 0.155 | 0.176 |
| 3 | v2 + Platt (secondary) | 0.663 | 0.622 | 0.693 | 0.165 | 0.155 | 0.176 |
| 3 | frozen v1 LightGBM | 0.660 | 0.620 | 0.689 | 0.170 | 0.159 | 0.180 |
| 3 | logistic (refit on the v2 rows) | 0.547 | 0.510 | 0.575 | 0.187 | 0.172 | 0.202 |
| 3 | same as now | 0.459 | 0.438 | 0.477 | 0.438 | 0.408 | 0.465 |
| 3 | same hour yesterday | 0.541 | 0.525 | 0.553 | 0.316 | 0.297 | 0.334 |
| 3 | train frequency | 0.516 | 0.485 | 0.546 | 0.278 | 0.250 | 0.304 |
| 3 | rolling 4-week frequency | 0.521 | 0.507 | 0.538 | 0.225 | 0.211 | 0.239 |
| 6 | v2 LightGBM | 0.664 | 0.616 | 0.696 | 0.131 | 0.119 | 0.143 |
| 6 | v2 + Platt (secondary) | 0.664 | 0.616 | 0.696 | 0.131 | 0.118 | 0.144 |
| 6 | frozen v1 LightGBM | 0.654 | 0.606 | 0.684 | 0.135 | 0.124 | 0.146 |
| 6 | logistic (refit on the v2 rows) | 0.569 | 0.522 | 0.600 | 0.144 | 0.131 | 0.156 |
| 6 | same as now | 0.478 | 0.458 | 0.496 | 0.443 | 0.420 | 0.466 |
| 6 | same hour yesterday | 0.543 | 0.523 | 0.559 | 0.238 | 0.213 | 0.264 |
| 6 | train frequency | 0.507 | 0.471 | 0.542 | 0.271 | 0.247 | 0.294 |
| 6 | rolling 4-week frequency | 0.502 | 0.475 | 0.534 | 0.187 | 0.173 | 0.200 |

v2 minus each other predictor (AUC: positive = v2 ahead; Brier: negative = v2 ahead; `share_*_ahead` = share of resamples in which v2 is ahead; the Platt variant has the same within-oblast AUC by construction):

| H | predictor | d_auc | d_auc_lo | d_auc_hi | share_auc_ahead | d_brier | d_brier_lo | d_brier_hi | share_brier_ahead |
|---|---|---|---|---|---|---|---|---|---|
| 1 | v2 + Platt (secondary) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -0.001 | 0.001 | 0.494 |
| 1 | frozen v1 LightGBM | 0.006 | -0.001 | 0.014 | 0.946 | -0.002 | -0.003 | -0.001 | 1.000 |
| 1 | logistic (refit on the v2 rows) | 0.160 | 0.121 | 0.181 | 1.000 | -0.020 | -0.024 | -0.015 | 1.000 |
| 1 | same as now | 0.291 | 0.242 | 0.327 | 1.000 | -0.294 | -0.325 | -0.263 | 1.000 |
| 1 | same hour yesterday | 0.175 | 0.130 | 0.205 | 1.000 | -0.142 | -0.156 | -0.129 | 1.000 |
| 1 | train frequency | 0.179 | 0.135 | 0.212 | 1.000 | -0.038 | -0.046 | -0.031 | 1.000 |
| 1 | rolling 4-week frequency | 0.183 | 0.138 | 0.214 | 1.000 | -0.045 | -0.051 | -0.040 | 1.000 |
| 3 | v2 + Platt (secondary) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -0.000 | 0.001 | 0.224 |
| 3 | frozen v1 LightGBM | 0.004 | -0.003 | 0.010 | 0.879 | -0.004 | -0.006 | -0.002 | 1.000 |
| 3 | logistic (refit on the v2 rows) | 0.117 | 0.082 | 0.146 | 1.000 | -0.021 | -0.028 | -0.015 | 1.000 |
| 3 | same as now | 0.204 | 0.158 | 0.243 | 1.000 | -0.272 | -0.297 | -0.247 | 1.000 |
| 3 | same hour yesterday | 0.123 | 0.083 | 0.158 | 1.000 | -0.150 | -0.170 | -0.132 | 1.000 |
| 3 | train frequency | 0.148 | 0.102 | 0.187 | 1.000 | -0.112 | -0.136 | -0.090 | 1.000 |
| 3 | rolling 4-week frequency | 0.142 | 0.098 | 0.173 | 1.000 | -0.059 | -0.068 | -0.049 | 1.000 |
| 6 | v2 + Platt (secondary) | 0.000 | 0.000 | 0.000 | 0.000 | -0.000 | -0.001 | 0.001 | 0.635 |
| 6 | frozen v1 LightGBM | 0.011 | 0.000 | 0.020 | 0.975 | -0.004 | -0.006 | -0.002 | 1.000 |
| 6 | logistic (refit on the v2 rows) | 0.096 | 0.055 | 0.143 | 1.000 | -0.013 | -0.017 | -0.008 | 1.000 |
| 6 | same as now | 0.186 | 0.140 | 0.221 | 1.000 | -0.312 | -0.341 | -0.283 | 1.000 |
| 6 | same hour yesterday | 0.122 | 0.080 | 0.151 | 1.000 | -0.107 | -0.129 | -0.087 | 1.000 |
| 6 | train frequency | 0.157 | 0.096 | 0.201 | 1.000 | -0.140 | -0.168 | -0.111 | 1.000 |
| 6 | rolling 4-week frequency | 0.163 | 0.111 | 0.198 | 1.000 | -0.055 | -0.068 | -0.044 | 1.000 |

### Calibration in the large, and the Platt variant (secondary)
Mean predicted against observed; Brier = bias^2 + Var(p - y). The full decomposition, the Platt coefficients and the reliability tables are in `results/v2/calibration.md`.

| H | predictor | mean_predicted | observed | bias | bias^2 | brier |
|---|---|---|---|---|---|---|
| 1 | v2 LightGBM | 0.1762 | 0.1957 | -0.0195 | 0.0004 | 0.1269 |
| 1 | v2 + Platt (secondary) | 0.1826 | 0.1957 | -0.0132 | 0.0002 | 0.1269 |
| 1 | frozen v1 LightGBM | 0.1611 | 0.1957 | -0.0347 | 0.0012 | 0.1292 |
| 1 | logistic (refit on the v2 rows) | 0.1692 | 0.1957 | -0.0265 | 0.0007 | 0.1466 |
| 1 | train frequency | 0.0878 | 0.1957 | -0.1080 | 0.0117 | 0.1653 |
| 1 | rolling 4-week frequency | 0.1669 | 0.1957 | -0.0288 | 0.0008 | 0.1723 |
| 3 | v2 LightGBM | 0.4114 | 0.4426 | -0.0311 | 0.0010 | 0.1656 |
| 3 | v2 + Platt (secondary) | 0.4182 | 0.4426 | -0.0244 | 0.0006 | 0.1653 |
| 3 | frozen v1 LightGBM | 0.3882 | 0.4426 | -0.0543 | 0.0030 | 0.1696 |
| 3 | logistic (refit on the v2 rows) | 0.3999 | 0.4426 | -0.0427 | 0.0018 | 0.1869 |
| 3 | train frequency | 0.2302 | 0.4426 | -0.2123 | 0.0451 | 0.2780 |
| 3 | rolling 4-week frequency | 0.3909 | 0.4426 | -0.0516 | 0.0027 | 0.2247 |
| 6 | v2 LightGBM | 0.5758 | 0.5954 | -0.0196 | 0.0004 | 0.1311 |
| 6 | v2 + Platt (secondary) | 0.5751 | 0.5954 | -0.0203 | 0.0004 | 0.1312 |
| 6 | frozen v1 LightGBM | 0.5551 | 0.5954 | -0.0403 | 0.0016 | 0.1348 |
| 6 | logistic (refit on the v2 rows) | 0.5685 | 0.5954 | -0.0270 | 0.0007 | 0.1436 |
| 6 | train frequency | 0.3743 | 0.5954 | -0.2211 | 0.0489 | 0.2713 |
| 6 | rolling 4-week frequency | 0.5469 | 0.5954 | -0.0486 | 0.0024 | 0.1866 |

### The decision rule, applied
"v2 becomes the default of `predict.py --now` only if its within-oblast AUC is not worse than v1's at all three horizons and its Brier is better at least at H=1" (point values, plain v2 against frozen v1, the same rows; intervals and the Platt variant play no part). Result: AUC 0.6916 / 0.6633 / 0.6645 against 0.6856 / 0.6598 / 0.6536 (v2 / v1 at H = 1 / 3 / 6), Brier at H=1 0.1269 against 0.1292: **v2 is the default** (`results/v2/decision.json`; `predict.py --now --model v1` keeps the old model).
The production model was refit on every origin whose window closes by the cut (961,920 / 961,872 / 961,800 rows) with the same tree counts and the validation-fit thresholds, saved in `models/v2/`; `model_version` in the prediction log reads `frozen-v2-...` (v1: `frozen-r13-...`).

### Caveats
- The AUC edge over v1 is small and its intervals include zero at H=1 and H=3 (and touch it at H=6): v2 is not shown to rank better. The Brier edge is consistent and is mostly the level (v1 predicted lower than what happened in this busier period). The rule was fixed before the numbers; it selects v2 on point values, which is a weaker statement than "v2 is better".
- One 20-day period from one source, with v1 already scored on it; the test days are the most recent ones. v2's training data include the 2026-09-07 to 09-27 days that were v1's forward-test days.
- The held-out numbers are for the model trained to 09-27; the model `--now` uses is the same model refit on the 20 test days too, which has no held-out score.

## The forecast map

Round 17. `scripts/predict.py --now` and `--at` write `output/forecast_map.html` (git-ignored) after printing their table; `scripts/forecast_map.py` builds it from the same probabilities (all 24 oblasts, whatever `--oblast` shows). One file, no script, no font, no image, no request when it is opened: the outlines are inline SVG, the 1 h / 3 h / 6 h switch is CSS only (radio buttons), and the colours are CSS variables with a light and a dark set (`prefers-color-scheme`). If the page cannot be written, the forecast is still printed and one line on stderr says "Map not written"; a refused forecast writes nothing.

- **On each oblast:** the probability in text (so the colour is never the only carrier), a filled triangle if it is at or above the frozen threshold of the model that made it and an open one if below, and a red "!" badge if an alert is running **at the origin hour** (the model's own "now": at least half of the raions under alert; the origin is the last completed hour, so this can be up to an hour older than the moment the page is made). The details of an oblast (status, the three probabilities with their thresholds) appear in a **fixed panel above the map** when the pointer is on the oblast or it has keyboard focus: there is no tooltip, because a tooltip is drawn by the browser wherever it likes and covered neighbouring labels (round 18; it hid Kharkivska's number). The panel is CSS only (`:has()`: Chrome 105, Safari 15.4, Firefox 121 and later; in an older browser it says to use the table). Under the map: a table with the same numbers and the words above / below.
- **Kyiv City** is a small outline inside Kyivska oblast, so it also has a call-out box in the empty corner above the north-west (a leader line to the city), with the same three probabilities, triangles and badge.
- **Crimea (with Sevastopol) and Luhansk** are grey and hatched, labelled "no data": the alert data do not cover Crimea, and Luhansk is the permanent-alert oblast the model leaves out.
- **Header:** origin hour in UTC and in Kyiv time, when the page was made, the model (v1 or v2) with the fingerprint that is also in the prediction log, the freshness line (live runs) or the "replay of a past hour" text and the training-period warning (`--at`), and the calibration note of that model. Footer: "A study model, not for safety decisions: follow the official alerts."
- **Colours:** five probability bins (under 10%, 10 to 25%, 25 to 50%, 50 to 75%, 75% and over), the same for all three horizons so colours compare across the switch. One blue family, lightness-monotone: light mode darker = more probable (`#61b9ff`, `#2f8ad4`, `#005da2`, `#003465`, `#00112b`), dark mode lighter = more probable (`#374991`, `#5173bc`, `#6ea0e8`, `#a0cdff`, `#edf6ff`). Round 18 replaced the round-17 ramps (steps of the reference blue ramp, neighbouring bins only about 10 apart in OKLab x100, which in dark mode read as one navy): the new ones have the lightness range stretched to what the page colour allows and a slight hue drift from violet-blue (dark end) to sky blue (light end), so neighbouring bins are at least 14.5 (light) and 13.5 (dark) apart, and at least 14.5 / 13.3 as seen with protanopia and deuteranopia (Machado et al. 2009, severity 1). Checked by `scripts/check_forecast_map.py` (monotone in OKLab lightness, steps at least 0.13 apart, neighbours at least 12 apart under normal, protan and deutan vision, text at least 4.5:1 on every fill, the faintest fill 2:1 on the page, outlines 3:1, hue spread within one family) and by the dataviz skill's ordinal validator (all four checks pass in both modes). Lightness alone survives every colour-vision deficiency; the numbers and triangles do not depend on colour at all. On a phone the oblast names are hidden and the percentages enlarged; the table carries the rest.
- **Outlines:** Natural Earth admin-1 (public domain), simplified, committed as `data/geo/ukraine_oblasts.geojson` with the source commit, its SHA-256, the licence text and every change in `data/geo/README.md` (rebuilt by `scripts/build_geo.py`). Natural Earth's default file lists Crimea and Sevastopol under Russia; they are taken by their Ukrainian ISO codes, as Ukraine's units. The 24 units are matched by ISO 3166-2 code; `python scripts/check_forecast_map.py` checks that match against the feature names, completeness and duplicates, and that our 24 are the 24 units in the alert data.
- **Checks:** `scripts/check_forecast_map.py` (names and geometry, shared borders identical in both neighbours, the page's colour class / percentage / triangle / badge for every oblast and horizon, self-contained, header facts, colours, and `predict.py --at` writing the page); and, offline against the fake API (a day cut at 2026-10-10 12:37 UTC), `predict.py --now` with the default model, `--model v1`, `--model v2` and `--oblast Kyivska`: every probability, above / below flag and alert state in the page equals the model's own output on the forward-test features, the model fingerprint and times are right, and a refused forecast leaves no page. Round 18 added: the freshness wording, the Ukrainian names against the API's own, the language tables, the fixed panel (one block per unit, a hover and a focus rule each), and both languages for every page check; and in headless Chromium: no request at all when the page is opened, no title element in the map, the panel shows the right block when the pointer is on Kharkivska, Luhansk, Crimea, the Kyiv call-out or when Lvivska has focus, and the label under the pointer is still the oblast's own.
- **Freshness wording (round 18):** anything under one minute old, and anything *ahead* of our clock (the API's clock may run a minute or two ahead; the page used to say "-2 min before now"), is shown as "just now"; then "N min before now" up to 3 hours, then "N.N h before now". The same text is in the terminal and on the page (`live_api.ago`).
- **Language (round 18):** `predict.py --lang uk` (for `--now` and `--at`) writes the terminal output and the map in Ukrainian; English is the default and its output is unchanged (the nine fixed commands of the round were compared line by line before and after: identical except the "just now" wording). All texts are in `src/i18n.py`, one English and one Ukrainian version per text, checked to have the same placeholders. **Oblast names are a hand-written list, not a translation**, in the spelling the Ukraine Alarm API itself uses; `check_forecast_map.py` checks every name against `UK_TO_OURS` (the table the data pipeline maps the API's state names to our names with, so a wrong name would also have broken the data), against the state-level names in the saved API files, and for capitalisation; tables are in Ukrainian alphabetical order (`і`, `ї`, `є` where the alphabet puts them). Not translated: error messages and refusals that name a command, `--help`, the model fingerprint, the file paths, the column names in `data/predictions/log.csv`. `--oblast` still takes the English names. The Ukrainian wording of the sentences was written by hand (by the assistant) and has not been reviewed by a native speaker; the Crimea and Sevastopol names are the official ones but appear in none of our data, so the check cannot verify them (they are only in the hover panel and, for Crimea, on the grey area).
- **Not in the map:** what happened afterwards (the replay shows no outcome), baselines, uncertainty. It is a display of the model's probabilities, which are slightly low on average (the calibration note says by how much).

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
pip install translitua
python scripts/source_check.py
python scripts/api_check.py
python scripts/sensitivity_aug19.py
python scripts/forward_test.py --selftest
python scripts/forward_test.py --diagnose
python scripts/check_live_replay.py
python scripts/build_combined.py
python scripts/check_combined.py
python scripts/train_v2.py
python scripts/build_geo.py PATH_TO_ne_10m_admin_1_states_provinces.geojson
python scripts/check_forecast_map.py
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
- `python scripts/check_live_replay.py`: the live forecast replayed as of 2026-10-10 12:00 (and 12:37) from an archive cut to what the API would have said then must give the forward test's features and probabilities for that hour exactly (offline; two negative controls)
- `python scripts/build_combined.py`: official data to 2026-08-28 + the API archive from 08-29 + the Aug 19-20 patch -> data/combined/alerts_combined.csv (not committed) and MANIFEST.md (needs translitua)
- `python scripts/check_combined.py`: features at the splice against official-only and API-only, continuity, leakage -> results/combined_splice_check.md
- `python scripts/train_v2.py`: v2 on the combined dataset, compared with frozen v1 on 2026-09-28 to 10-17, the decision rule applied -> results/v2/ and models/v2/ (the design is in PROCESS_LOG.md, Round 16; takes a few minutes)
- `python scripts/build_geo.py FILE`: Natural Earth admin-1 -> data/geo/ukraine_oblasts.geojson (source, licence and pinned SHA-256 in data/geo/README.md; the output is committed, so this is only needed to rebuild it)
- `python scripts/check_forecast_map.py`: the oblast name match, the geometry, the page and its colours (offline, seconds)
- `python scripts/score_predictions.py`: the live forecasts in data/predictions/log.csv against the API archive (`--write` -> results/live_forecast_scores.md); every `predict.py --now` run appends to that log
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
- `python scripts/predict.py --now`: the live forecast for the last completed hour from the API (tops up data/api_archive/, needs `UA_ALARM_TOKEN` and `pip install translitua`; see the README, "Try it"); `--force` on archive_api.py refetches saved days

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
src/i18n.py          texts for --lang en/uk and the Ukrainian oblast names (checked against the API's own spelling)
src/telegram_*.py     Telegram post parser (oblasts, threat types) and per-oblast features (the Telegram experiment)
data/neighbours.csv  hand-written oblast adjacency (land borders), used by the neighbour features
data/news/           GDELT hourly aggregate + pull record (the news experiment)
data/source_check/    public posts of the official alert channel for Aug 13–18 (compressed), for results/source_check.md
data/api_archive/      Ukraine Alarm API history saved by scripts/archive_api.py (the forward test and the API check read it)
data/predictions/      the live forecast log (data/predictions/log.csv, appended by scripts/predict.py --now)
data/combined/         the combined official + API dataset (MANIFEST.md committed, the csv is built by scripts/build_combined.py)
models/v2/             the v2 production model (written by scripts/train_v2.py, not committed)
results/v2/            v2 against frozen v1: tables, bootstrap, calibration, decision.json
data/geo/             oblast outlines for the forecast map (Natural Earth, public domain; README.md has the source and licence)
output/               forecast_map.html, written by scripts/predict.py (not committed)
docs/api/             the API's swagger json
data/telegram/       public posts of t.me/s/kpszsu (the Telegram experiment)
models/              fitted by scripts/evaluate.py for scripts/predict.py (gitignored)
scripts/             one script per step, run from the repo root
results/             evaluation tables
figures/             plots and the tables behind them
PROCESS_LOG.md       lab notebook
CLAUDE.md            working rules for this repo
```
