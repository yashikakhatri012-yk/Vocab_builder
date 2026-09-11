# Database migrations

Run the original schema first with `db.sql`, then apply `001_vocab_v2.sql` once.

The migration is additive: it adds optional word metadata, dictionary caching, API request accounting, and lookup indexes. Existing learner progress is preserved.
