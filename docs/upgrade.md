# V2 follow-up

This release layers live vocabulary infrastructure onto the V2 product shell.

## Included

- Server-side dictionary lookup and JSON endpoint
- Persistent dictionary cache
- Upstream request accounting and application-side hourly budget
- External candidate discovery for controlled library growth
- Pronunciation metadata support
- Protected maintenance refresh endpoint
- Scheduler-friendly replenishment script
- Database migration and setup documentation

## Recommended deployment order

1. Deploy code.
2. Apply `migrations/001_vocab_v2.sql` once.
3. Set `WORD_API_CALLS_PER_HOUR`, `WORD_API_TIMEOUT`, and `MAINTENANCE_TOKEN`.
4. Run the replenishment script manually once and verify inserted words.
5. Schedule the script every 8–12 hours.
6. Test dashboard review, dictionary lookup, tests, and result history against the production database.
