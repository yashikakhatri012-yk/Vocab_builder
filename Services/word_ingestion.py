import json
import os
import time
from datetime import datetime, timedelta

import requests


DATAMUSE_URL = "https://api.datamuse.com/words"
DICTIONARY_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
MAX_UPSTREAM_CALLS_PER_HOUR = int(os.getenv("WORD_API_CALLS_PER_HOUR", "30"))
REQUEST_TIMEOUT = float(os.getenv("WORD_API_TIMEOUT", "5"))


def _http_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "VocabBuilder/2.0 educational vocabulary app",
        "Accept": "application/json",
    })
    return session


def _within_budget(cur):
    cutoff = datetime.utcnow() - timedelta(hours=1)
    cur.execute("SELECT COUNT(*) AS total FROM api_request_log WHERE requested_at >= %s", (cutoff,))
    return int(cur.fetchone()["total"] or 0) < MAX_UPSTREAM_CALLS_PER_HOUR


def _record_call(cur, provider, endpoint):
    cur.execute(
        "INSERT INTO api_request_log (provider, endpoint, requested_at) VALUES (%s,%s,NOW())",
        (provider, endpoint),
    )


def _get_json(cur, session, provider, endpoint, url, params=None):
    if not _within_budget(cur):
        return None
    try:
        response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        _record_call(cur, provider, endpoint)
        if response.ok:
            return response.json()
    except requests.RequestException:
        _record_call(cur, provider, endpoint)
    return None


def discover_candidates(cur, session, limit=20):
    anchors = [
        "academic vocabulary", "education", "critical thinking",
        "communication", "science", "technology", "literature", "business", "culture",
    ]
    query = anchors[int(time.time() // 86400) % len(anchors)]
    data = _get_json(cur, session, "datamuse", "words", DATAMUSE_URL, {"ml": query, "max": limit})
    if not data:
        return []
    candidates = []
    for item in data:
        word = (item.get("word") or "").strip().lower()
        if word and word.replace("-", "").replace("'", "").isalpha() and 4 <= len(word) <= 30:
            candidates.append(word)
    return list(dict.fromkeys(candidates))


def fetch_definition(cur, session, word):
    cur.execute(
        "SELECT payload_json FROM dictionary_cache WHERE word=%s AND expires_at > NOW()",
        (word,),
    )
    row = cur.fetchone()
    if row:
        return json.loads(row["payload_json"])

    data = _get_json(
        cur, session, "dictionaryapi", "definition",
        DICTIONARY_URL.format(word=word),
    )
    if data:
        cur.execute(
            """
            INSERT INTO dictionary_cache (word, payload_json, fetched_at, expires_at)
            VALUES (%s,%s,NOW(),DATE_ADD(NOW(), INTERVAL 30 DAY))
            ON DUPLICATE KEY UPDATE
                payload_json=VALUES(payload_json), fetched_at=NOW(),
                expires_at=DATE_ADD(NOW(), INTERVAL 30 DAY)
            """,
            (word, json.dumps(data, ensure_ascii=False)),
        )
    return data


def normalize_entry(payload, default_level="B1"):
    if not payload or not isinstance(payload, list):
        return None
    entry = payload[0] or {}
    word = (entry.get("word") or "").strip().lower()
    phonetic = entry.get("phonetic") or ""
    audio = ""
    example = ""
    meanings = entry.get("meanings") or []
    definitions, synonyms, antonyms = [], [], []
    part_of_speech = ""

    for meaning in meanings:
        part_of_speech = part_of_speech or (meaning.get("partOfSpeech") or "")
        synonyms.extend(meaning.get("synonyms") or [])
        antonyms.extend(meaning.get("antonyms") or [])
        for item in meaning.get("definitions") or []:
            if item.get("definition"):
                definitions.append(item["definition"])
            if not example and item.get("example"):
                example = item["example"]
            synonyms.extend(item.get("synonyms") or [])
            antonyms.extend(item.get("antonyms") or [])

    for phon in entry.get("phonetics") or []:
        phonetic = phon.get("text") or phonetic
        audio = phon.get("audio") or audio

    if not word or not definitions:
        return None
    return {
        "word": word,
        "meaning": definitions[0],
        "part_of_speech": part_of_speech or "word",
        "synonym": ", ".join(dict.fromkeys(synonyms))[:500],
        "antonym": ", ".join(dict.fromkeys(antonyms))[:500],
        "example": example,
        "level": default_level,
        "phonetic": phonetic,
        "audio_url": audio,
        "source": "Free Dictionary API / Wiktionary",
    }


def lookup_word(mysql, word):
    word = " ".join((word or "").strip().lower().split())
    if not word or len(word) > 60:
        return None
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            """
            SELECT id, word, eng_meaning AS meaning, part_of_speech,
                   synonym, antonym, example, level, phonetic, audio_url, source
            FROM words WHERE LOWER(word)=LOWER(%s) LIMIT 1
            """,
            (word,),
        )
        local = cur.fetchone()
        if local:
            return dict(local)
        entry = normalize_entry(fetch_definition(cur, _http_session(), word))
        mysql.connection.commit()
        return entry
    finally:
        cur.close()


def replenish_library(mysql, target_new_words=10):
    cur = mysql.connection.cursor()
    session = _http_session()
    inserted = 0
    try:
        candidates = discover_candidates(cur, session, limit=max(20, target_new_words * 2))
        for word in candidates:
            if inserted >= target_new_words:
                break
            cur.execute("SELECT id FROM words WHERE LOWER(word)=LOWER(%s) LIMIT 1", (word,))
            if cur.fetchone():
                continue
            entry = normalize_entry(fetch_definition(cur, session, word))
            if not entry:
                continue
            cur.execute(
                """
                INSERT INTO words
                    (word, eng_meaning, part_of_speech, synonym, antonym, example,
                     level, phonetic, audio_url, source)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    entry["word"], entry["meaning"], entry["part_of_speech"],
                    entry["synonym"], entry["antonym"], entry["example"],
                    entry["level"], entry["phonetic"], entry["audio_url"], entry["source"],
                ),
            )
            inserted += 1
        mysql.connection.commit()
        return inserted
    finally:
        cur.close()
