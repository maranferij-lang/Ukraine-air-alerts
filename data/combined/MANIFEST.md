# Manifest: the combined alert dataset

Produced by `scripts/build_combined.py` (offline, deterministic). `alerts_combined.csv` is not committed (about 30 MB); rebuild it with the script and check the SHA-256 below. The rules and every splice point are in `docs/DETAILS.md`, "The combined dataset"; `results/combined_splice_check.md` has the checks.

- splice instant T: 2026-08-29 00:00:00 UTC (official before, API after)
- patch: API raion rows of Chernihivska oblast, Kyivska oblast starting 2026-08-19 19:00 to 2026-08-20 12:00 UTC
- the cut: 2026-10-18 00:00 UTC (rows that start later are not in the file; ends are clipped to it)
- rows: 210440; first start 2022-03-15 16:10:34+00:00; last start 2026-10-17 23:53:11.987023+00:00; last end 2026-10-18 00:00:00+00:00
- `alerts_combined.csv`: 22034606 bytes, SHA-256 `721cf7755726c9cc38b06ea116fe0750a76f0fb2b45de67d9a34748feb1f8c14`
- inputs (SHA-256 prefix):
  - `data/raw/official_data_en.csv`: `b396f87696243069`
  - `data/api_archive/date_history/ (all day files, in date order)`: `16c8ce13d0fb4860`

## What each rule did

- official rows (cleaned, without Luhansk): 185363
- official rows kept (end at or before the splice): 183292
- official rows dropped, spanning the splice (start before, end after): 46
- official rows dropped, started at or after the splice: 2025
- api rows (AIR, our oblasts) that start before the cut: 35367
- api rows ignored, start at or after the cut: 534
- api rows whose end was clipped to the cut (running or ending after it): 47
- api rows kept (end after the splice): 27130
- api rows not used (end at or before the splice: the official side has them): 8237
- api_patch rows: 18
- official rows of the two patch oblasts starting in the patch window (kept as they are): 6
- api days read: 74

## Rows by source and level

| source | hromada | oblast | raion |
|---|---|---|---|
| api | 0 | 367 | 26763 |
| api_patch | 0 | 0 | 18 |
| official | 20653 | 65289 | 97350 |
