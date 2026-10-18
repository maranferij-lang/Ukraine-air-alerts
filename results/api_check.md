# API check: does the Ukraine Alarm API history agree with our official data?

Source compared against our official data: **the Ukraine Alarm API** (`api.ukrainealarm.com`, `GET /api/v3/alerts/dateHistory`, a different source from the official Telegram channel behind our csv). Produced by `scripts/api_check.py`, offline, from the saved API answers.

## What was compared
- API days saved: 74 (2026-08-06 to 2026-10-18 UTC), 0 missing in between; SHA-256 prefix of the files in date order: `82fd45046b0459af`.
- Hours compared: the UTC days with a file, minus the official feed's outage [2026-08-29, 2026-09-03) and everything from 2026-09-06 00:00 UTC (the official data's trusted end): 624 hours x 24 oblasts = 14976 oblast-hours.
- Rules applied to the API alerts: only alertType `AIR`; district (`... район`) -> raion row (name transliterated, must be one of our 118 raions; one known rename: Sheptytskyi = our Chervonohradskyi); `м. Київ` and `... область` -> oblast-level row; hromada-level rows are dropped, as `src/panel.py` does; oblast under alert when at least half of its raions are (the same fixed raion list); restarts within 5 minutes joined. The official side goes through the same code.

## What the API rows were turned into
- api rows: 40527
- after joining the days' files: 37380
- not AIR (dropped): 312
- still open or without an end (dropped): 80
- raion rows: 35289
- oblast-level rows: 445
- hromada-level rows dropped: 1254
- oblast-level rows for oblasts not in our data: 0
- districts not in our raion list (dropped): 0 rows, 0 names
- other names (dropped): 0 rows

## Oblast-hours (the series the model uses)

| | oblast-hours |
|---|---|
| compared | 14976 |
| same "under alert" in both | 14942 of 14976 (99.8%) |
| under alert only in the official data | 0 |
| under alert only in the API | 34 |
| same "a new alert starts in this hour" in both | 14954 of 14976 (99.9%) |
| a start in the official data only / in the API only / in both | 7 / 15 / 1824 |

Per oblast:

| oblast | hours | "under alert" differs | official only | API only | "new alert starts" differs |
|---|---|---|---|---|---|
| Cherkaska oblast | 624 | 1 | 0 | 1 | 2 |
| Chernihivska oblast | 624 | 14 | 0 | 14 | 2 |
| Chernivetska oblast | 624 | 0 | 0 | 0 | 0 |
| Dnipropetrovska oblast | 624 | 0 | 0 | 0 | 1 |
| Donetska oblast | 624 | 0 | 0 | 0 | 0 |
| Ivano-Frankivska oblast | 624 | 0 | 0 | 0 | 0 |
| Kharkivska oblast | 624 | 1 | 0 | 1 | 2 |
| Khersonska oblast | 624 | 0 | 0 | 0 | 0 |
| Khmelnytska oblast | 624 | 0 | 0 | 0 | 0 |
| Kirovohradska oblast | 624 | 0 | 0 | 0 | 0 |
| Kyiv City | 624 | 1 | 0 | 1 | 2 |
| Kyivska oblast | 624 | 11 | 0 | 11 | 2 |
| Lvivska oblast | 624 | 0 | 0 | 0 | 0 |
| Mykolaivska oblast | 624 | 1 | 0 | 1 | 1 |
| Odeska oblast | 624 | 0 | 0 | 0 | 0 |
| Poltavska oblast | 624 | 2 | 0 | 2 | 3 |
| Rivnenska oblast | 624 | 0 | 0 | 0 | 0 |
| Sumska oblast | 624 | 1 | 0 | 1 | 2 |
| Ternopilska oblast | 624 | 0 | 0 | 0 | 0 |
| Vinnytska oblast | 624 | 1 | 0 | 1 | 2 |
| Volynska oblast | 624 | 0 | 0 | 0 | 0 |
| Zakarpatska oblast | 624 | 0 | 0 | 0 | 0 |
| Zaporizka oblast | 624 | 0 | 0 | 0 | 1 |
| Zhytomyrska oblast | 624 | 1 | 0 | 1 | 2 |

Days with the most disagreeing oblast-hours (top 5):

| day (UTC) | "under alert" differs | "new alert starts" differs | oblasts involved |
|---|---|---|---|
| 2026-08-20 | 17 | 2 | 2 |
| 2026-08-19 | 16 | 18 | 11 |
| 2026-09-05 | 1 | 2 | 2 |

## Oblast episodes (alerts after the half-of-raions rule and the 5-minute join)

| | official episodes | API episodes |
|---|---|---|
| starting on the compared hours | 1882 | 1890 |
| with a start of the other source within 1 minute | 1866 of 1882 | 1866 of 1890 |
| with a start of the other source within 5 minutes | 1875 of 1882 | 1875 of 1890 |
| with a start of the other source within 1 hour | 1882 of 1882 | 1882 of 1890 |

## Raion alert rows

| | official | API |
|---|---|---|
| raion-level rows starting on the compared hours | 9360 | 9395 |
| with a row of the other source, same raion, start within 5 s | 9263 of 9360 | 9263 of 9395 |
| with a row of the other source, same raion, start within 60 s | 9301 of 9360 | 9301 of 9395 |
| of the official rows matched within 60 s, end also within 60 s | 9219 of 9301 | |

## The official feed's outage

- The official data has nothing in [2026-08-29, 2026-09-03). The API days saved for that window give 521 oblast episodes starting in it, in 22 oblasts. They are not compared with anything here.

