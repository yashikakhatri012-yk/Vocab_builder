# Vocab Builder

A focused vocabulary learning app built with Flask and MySQL. V2 combines daily vocabulary, spaced repetition, practice tests, progress tracking, and a cached live dictionary lookup in one minimal learning workspace.

## What V2 adds

- Minimal, responsive dashboard and mobile navigation
- Daily learning queue with difficult/review words prioritized
- Spaced repetition with interval + ease-factor scheduling
- 10-question, 10-minute practice tests with A1–A2 / B1–B2 / C1–C2 filters
- Score history and learning statistics
- Live dictionary lookup with phonetics, examples, synonyms, antonyms, and optional pronunciation audio
- Local dictionary cache so repeated lookups do not repeatedly hit third-party APIs
- Controlled vocabulary ingestion from external lexical data into the local MySQL library
- Application-side upstream API budget (`WORD_API_CALLS_PER_HOUR`, default 30 calls/hour)
- Environment-based secrets/configuration instead of hard-coded database credentials
- Basic account validation and duplicate-account handling

## Architecture

```text
Flask routes / Jinja templates
        |
        +-- MySQL learning state
        |
        +-- Services/Spaced_repetition.py
        |
        +-- Services/word_ingestion.py
                |
                +-- Datamuse: candidate word discovery
                +-- Free Dictionary API: definitions / phonetics / audio
                +-- MySQL cache + request budget
```

Datamuse is used for lexical discovery. The Free Dictionary API exposes English dictionary data and phonetic/audio information. The V2 application never exposes those third-party endpoints directly to the browser for normal dictionary lookups; the server fetches and caches results. citeturn987020search0turn949228search0

## Setup

### 1. Clone

```bash
git clone https://github.com/new-experimental/Vocab_builder.git
cd Vocab_builder
```

### 2. Environment

Create environment variables for your deployment:

```text
SECRET_KEY=replace-with-a-long-random-secret
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DB=vocabulary
WORD_API_CALLS_PER_HOUR=30
WORD_API_TIMEOUT=5
MAINTENANCE_TOKEN=replace-with-a-private-token
```

### 3. Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Database migration

Start with the existing `db.sql`, then run:

```bash
mysql -u root -p < migrations/001_vocab_v2.sql
```

The migration adds optional word metadata, a dictionary cache, API request accounting, and indexes for growing word/review tables.

### 5. Run

```bash
python app.py
```

Open `http://127.0.0.1:5000/`.

## Keeping the word library growing

The repository includes:

```bash
python scripts/replenish_words.py --count 10
```

For production, run this periodically with cron or the equivalent scheduler. The ingestion service discovers candidate vocabulary, checks for duplicates, fetches definitions, stores normalized data locally, and respects the application-wide upstream request budget.

Example cron schedule:

```cron
0 */8 * * * cd /path/to/Vocab_builder && /path/to/venv/bin/python scripts/replenish_words.py --count 10 >> /var/log/vocab-builder-replenish.log 2>&1
```

The web app also exposes a protected maintenance endpoint for hosted schedulers:

```bash
curl -X POST \
  -H "X-Maintenance-Token: $MAINTENANCE_TOKEN" \
  -d "count=10" \
  https://your-domain.example/maintenance/replenish
```

## API behavior

The dictionary lookup is deliberately server-side and cache-first. A cached word can be served without an upstream call. Uncached calls are counted in `api_request_log`, and once the configured hourly budget is reached, the application stops making more upstream requests until the budget window moves.

The external dictionary source does **not** provide a verified CEFR level in the returned data, so newly ingested words use a conservative `B1` default rather than inventing a CEFR classification. They can be reclassified later when a trusted level source is introduced.

## Security notes

Never commit real database passwords, API credentials, or `MAINTENANCE_TOKEN` values. The V2 application reads secrets from environment variables and the maintenance endpoint requires a secret request header.

## Project status

V2 is under active development. Test against the actual production MySQL schema before merging the upgrade branch into `master`.
