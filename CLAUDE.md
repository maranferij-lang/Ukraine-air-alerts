# CLAUDE.md

forecasting air raid alerts per oblast, hourly, from the official alert history. test task for a course, deadline monday.

rules. dont break these without asking me first:
- no leakage. every feature for origin t uses only what is known at t. neighbours lagged one hour. frequency tables and any encodings fitted on train only
- chronological split only. test = last 30 full days of official data. no random splits, no k-fold
- every model number goes next to the three baselines (persistence, same hour yesterday, train frequency). a number without baselines does not go in the README
- no plain accuracy. brier, auc within oblast, precision/recall at a threshold chosen on the last train week, never on test
- oblast is under alert when at least half of its raions are. dont change it
- never edit data/raw by hand. re-pull with scripts/fetch_data.py only
- everything you decide, find or break goes in PROCESS_LOG.md in the same round, before the commit
- one commit per round, at the end of the round
- if something i ask for looks wrong, say so before doing it. id rather be told
