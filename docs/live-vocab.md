# Live vocabulary

The V2 follow-up adds a cache-first dictionary layer and scheduled vocabulary ingestion.

Datamuse supplies candidate words. Free Dictionary API supplies English definition data and phonetics/audio where available. External traffic is routed through the server, cached locally, and bounded by an application-wide hourly request budget.

Use `python scripts/replenish_words.py --count 10` or a scheduler against `/maintenance/replenish` with `X-Maintenance-Token` configured.
