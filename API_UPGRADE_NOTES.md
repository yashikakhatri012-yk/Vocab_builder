# Live vocabulary pipeline

The V2 follow-up adds a cache-first dictionary integration and scheduled library replenishment.

- Datamuse is used only for candidate discovery.
- Free Dictionary API is used for English definitions, phonetics, examples, synonyms/antonyms where available, and pronunciation audio.
- `dictionary_cache` prevents repeated upstream dictionary calls for 30 days.
- `api_request_log` tracks upstream calls and enforces the server-side hourly budget.
- `scripts/replenish_words.py` is the scheduler-friendly worker.
- `/maintenance/replenish` is protected by `MAINTENANCE_TOKEN` for hosted schedulers.

The application keeps the external service behind the Flask server rather than exposing third-party endpoints directly to normal browser clients.
