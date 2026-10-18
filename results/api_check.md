# API check: does the Ukraine Alarm API history agree with our official data?

Source compared against our official data: **the Ukraine Alarm API** (`api.ukrainealarm.com`, `GET /api/v3/alerts/dateHistory`, a different source from the official Telegram channel behind our csv). Produced by `scripts/api_check.py`, offline, from the saved API answers.

## What was compared
- API days saved: 1 (2026-08-15 to 2026-08-15 UTC), 0 missing in between; SHA-256 prefix of the files in date order: `78a97f09bb58012f`.
- Hours compared: the UTC days with a file, minus the official feed's outage [2026-08-29, 2026-09-03) and everything from 2026-09-06 00:00 UTC (the official data's trusted end): 24 hours x 24 oblasts = 576 oblast-hours.
- Rules applied to the API alerts: only alertType `AIR`; district (`... район`) -> raion row (name transliterated, must be one of our 118 raions); `м. Київ` and `... область` -> oblast-level row; hromada-level rows are dropped, as `src/panel.py` does; oblast under alert when at least half of its raions are (the same fixed raion list); restarts within 5 minutes joined. The official side goes through the same code.

## What the API rows were turned into
- api rows: 399
- after joining the days' files: 399
- not AIR (dropped): 3
- still open or without an end (dropped): 0
- raion rows: 369
- oblast-level rows: 2
- hromada-level rows dropped: 25
- oblast-level rows for oblasts not in our data: 0
- districts not in our raion list (dropped): 0 rows, 0 names
- other names (dropped): 0 rows

## Oblast-hours (the series the model uses)

| | oblast-hours |
|---|---|
| compared | 576 |
| same "under alert" in both | 576 of 576 (100.0%) |
| under alert only in the official data | 0 |
| under alert only in the API | 0 |
| same "a new alert starts in this hour" in both | 576 of 576 (100.0%) |
| a start in the official data only / in the API only / in both | 0 / 0 / 66 |

Per oblast:

| oblast | hours | "under alert" differs | official only | API only | "new alert starts" differs |
|---|---|---|---|---|---|
| Cherkaska oblast | 24 | 0 | 0 | 0 | 0 |
| Chernihivska oblast | 24 | 0 | 0 | 0 | 0 |
| Chernivetska oblast | 24 | 0 | 0 | 0 | 0 |
| Dnipropetrovska oblast | 24 | 0 | 0 | 0 | 0 |
| Donetska oblast | 24 | 0 | 0 | 0 | 0 |
| Ivano-Frankivska oblast | 24 | 0 | 0 | 0 | 0 |
| Kharkivska oblast | 24 | 0 | 0 | 0 | 0 |
| Khersonska oblast | 24 | 0 | 0 | 0 | 0 |
| Khmelnytska oblast | 24 | 0 | 0 | 0 | 0 |
| Kirovohradska oblast | 24 | 0 | 0 | 0 | 0 |
| Kyiv City | 24 | 0 | 0 | 0 | 0 |
| Kyivska oblast | 24 | 0 | 0 | 0 | 0 |
| Lvivska oblast | 24 | 0 | 0 | 0 | 0 |
| Mykolaivska oblast | 24 | 0 | 0 | 0 | 0 |
| Odeska oblast | 24 | 0 | 0 | 0 | 0 |
| Poltavska oblast | 24 | 0 | 0 | 0 | 0 |
| Rivnenska oblast | 24 | 0 | 0 | 0 | 0 |
| Sumska oblast | 24 | 0 | 0 | 0 | 0 |
| Ternopilska oblast | 24 | 0 | 0 | 0 | 0 |
| Vinnytska oblast | 24 | 0 | 0 | 0 | 0 |
| Volynska oblast | 24 | 0 | 0 | 0 | 0 |
| Zakarpatska oblast | 24 | 0 | 0 | 0 | 0 |
| Zaporizka oblast | 24 | 0 | 0 | 0 | 0 |
| Zhytomyrska oblast | 24 | 0 | 0 | 0 | 0 |

## Oblast episodes (alerts after the half-of-raions rule and the 5-minute join)

| | official episodes | API episodes |
|---|---|---|
| starting on the compared hours | 67 | 67 |
| with a start of the other source within 1 minute | 66 of 67 | 66 of 67 |
| with a start of the other source within 5 minutes | 67 of 67 | 67 of 67 |
| with a start of the other source within 1 hour | 67 of 67 | 67 of 67 |

## Raion alert rows

| | official | API |
|---|---|---|
| raion-level rows starting on the compared hours | 336 | 336 |
| with a row of the other source, same raion, start within 5 s | 330 of 336 | 330 of 336 |
| with a row of the other source, same raion, start within 60 s | 330 of 336 | 330 of 336 |
| of the official rows matched within 60 s, end also within 60 s | 327 of 330 | |

