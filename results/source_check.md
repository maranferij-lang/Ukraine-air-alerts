# Source check: does the official channel reproduce our official csv?

We re-derived the official alerts from their source, the public Telegram channel `air_alert_ua`, with the **unmodified upstream parser** (Vadimkin/ukrainian-air-raid-sirens-dataset at commit `7ccd436`, the commit of our snapshot), and compared them with `data/raw/official_data_en.csv` after our cleaning (`src/load.py`: exact duplicates dropped, hromada = raion rows relabelled).

Produced by `scripts/source_check.py` (offline apart from downloading the four upstream files; no Telegram access, no token).

## What was run
- Posts: `data/source_check/channel_posts_aug13_18.csv.gz`, 3280 public posts, 2026-08-12 23:57 to 2026-08-18 18:57 UTC.
- Parser: upstream `OfficialAirAlertProcessor.process_message` (hashtags to oblast / raion / hromada through `states.json`, 🔴 starts, 🟢 / "Відбій" ends, the 3-hour rule for alerts without an end). Only the Telethon import is stubbed; the class is not edited. Posts are fed in id order, shaped like Telethon's messages (text, UTC date, id).
- Upstream files, SHA-256:
  - `official_channel_processor.py`: `cbc62a1c52b73f0be6ec51648af55accc8e2d4e47a689c23b31400f51f79cd51`
  - `legacy_states.py`: `6d211bf2e56d44b933e12ce36641707467ad86825e03a77a8c426ea4fc5e2c51`
  - `tg_dataclasses.py`: `fb75b1cca647e5216094f428c986da87e82df07d2e79b71e409c57b81e9961ae`
  - `states.json`: `ede0fafce9c1794878c44d54f6072e28d50c7164331e1eeb5a61edeff128705a`
- Compared: alerts that **start** in [2026-08-14, 2026-08-17) UTC, i.e. Aug 14–16 (the day before is warm-up for alerts already running; the days after let the alerts end).

## Alert rows (oblast, raion, hromada, level, start, end)

| | rows |
|---|---|
| our csv (cleaned) | 855 (hromada 60, oblast 5, raion 790) |
| channel, upstream parser | 854 (hromada 59, oblast 5, raion 790) |
| same place and start in both | 854 |
| of those, identical end too | **854** |
| only in our csv | 1 |
| only in the channel | 0 |

So **854 of 855** rows of our csv are reproduced to the second, and nothing in the channel is missing from the csv.

The row only in our csv:

| oblast | raion | hromada | level | start | end |
|---|---|---|---|---|---|
| Dnipropetrovska oblast | Nikopolskyi raion | m. Marhanets ta Marhanetska terytorialna hromada | hromada | 2026-08-14 05:35:50 | 2026-08-19 05:26:54 |

1 of 1 only-in-csv rows end after the last post in the file (2026-08-18 18:57 UTC): the alert was still running when the posts stop, so the parser has no end for it yet. That is an edge of this slice, not a difference between the sources.

## The level the model uses: hours with the oblast under alert
Oblast under alert = at least half of its raions (same fixed raion list), 24 oblasts, 2026-08-14 06:00 to 2026-08-16 18:00 UTC.

| | |
|---|---|
| oblast-hours compared | 1440 |
| share under alert, our csv / channel | 0.2625 / 0.2625 |
| oblast-hours where they disagree | **0** |
| alert starts, our csv / channel | 139 / 139 |

## Posts the parser skips
321 of 3280 posts are skipped (not an alert state): 298 are 🟠 warnings and the rest other notices (for example evacuation). Hashtags the parser did not know: 0. The same skips happen in the upstream run that made our csv, which is why the rows match.

## The channel stopped on 2026-09-07 (recorded by hand)
On 2026-10-11 the newest post in `t.me/s/air_alert_ua` was number 338380, from **2026-09-07 06:09:04 UTC**, in the middle of an alert wave with no all-clear after it. Three checks agreed: `?after=338380` returned no posts; `?before=999999` returned the same last page; a direct link to post 338381 answered "Post not found". The same method returned fresh posts of another channel (`kpszsu`) from that day, so the preview was not stale. The message format did not change before the stop (the same templates on Aug 6, Sep 2 and Sep 7). So there is no newer official data to add, and `scripts/predict.py --now` re-checks the channel every time it runs.
