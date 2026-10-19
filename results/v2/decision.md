# The decision rule, applied

Fixed in advance (`PROCESS_LOG.md`, Round 16): `predict.py --now` switches to v2 only if the within-oblast AUC of plain v2 is not worse than frozen v1's at all three horizons and its Brier is better at least at H = 1 (point values at full precision, the same test rows; intervals and the Platt variant play no part).

- H=1: AUC v2 0.6916 against v1 0.6856: not worse
- H=3: AUC v2 0.6633 against v1 0.6598: not worse
- H=6: AUC v2 0.6645 against v1 0.6536: not worse
- Brier at H=1: v2 0.1269 against v1 0.1292: better

**Result: `predict.py --now` uses v2 by default.**

## Training record

| H | train rows | validation-fit rows | validation-week rows | test rows | trees (early stopping on the validation week) | logistic iterations | train windows close by | validation-fit windows close by | frozen v1 threshold | v2 threshold |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 950400 | 946368 | 4032 | 11520 | 194 | 8 | 2026-09-28 00:00 | 2026-09-21 00:00 | 0.1872 | 0.2519 |
| 3 | 950352 | 946320 | 3984 | 11472 | 181 | 7 | 2026-09-28 00:00 | 2026-09-21 00:00 | 0.2429 | 0.4270 |
| 6 | 950280 | 946248 | 3912 | 11400 | 149 | 6 | 2026-09-28 00:00 | 2026-09-21 00:00 | 0.3141 | 0.4268 |
