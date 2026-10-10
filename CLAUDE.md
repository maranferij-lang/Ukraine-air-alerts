# CLAUDE.md

forecasting air raid alerts per oblast, hourly, from the official alert history. test task for a course, deadline monday.

rules. dont break these without asking me first:
- no leakage. every feature for origin t uses only what is known at t. neighbours = the last completed hour [t-1h, t). static tables (the frequency baseline) are fitted on train only, rolling features may use anything already observed by t
- chronological split only. test = last 30 full days of official data. no random splits, no k-fold
- the test window is the last 30 full days of official data. if a feature, a mask or anything else shrinks it, ask me before running, logging it after is not enough
- every model number goes next to the three baselines (persistence, same hour yesterday, train frequency). a number without baselines does not go in the README
- no plain accuracy. brier, auc within oblast, precision/recall at a threshold chosen on the last train week, never on test. 0/1 baselines are reported raw, no threshold search
- oblast is under alert when at least half of its raions are. dont change it
- never edit data/raw by hand. re-pull with scripts/fetch_data.py only
- everything you decide, find or break goes in PROCESS_LOG.md in the same round, before the commit
- one commit per round, at the end of the round
- if something i ask for looks wrong, say so before doing it. id rather be told
- volunteer feed: lviv and volyn are mislabelled upstream (substring bug in the parser). never compare western oblasts with volunteer numbers
- rows after the outage use 7-day features scaled from the observed hours. always report them separately next to the pooled numbers
