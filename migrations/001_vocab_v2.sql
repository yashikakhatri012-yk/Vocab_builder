USE vocabulary;

-- Run once against an existing Vocab Builder database.
-- These ALTER statements add optional metadata; learning data is preserved.
ALTER TABLE words ADD COLUMN phonetic VARCHAR(150) NULL;
ALTER TABLE words ADD COLUMN audio_url TEXT NULL;
ALTER TABLE words ADD COLUMN source VARCHAR(255) NULL;

CREATE TABLE IF NOT EXISTS dictionary_cache (
    word VARCHAR(100) PRIMARY KEY,
    payload_json LONGTEXT NOT NULL,
    fetched_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    INDEX idx_dictionary_cache_expiry (expires_at)
);

CREATE TABLE IF NOT EXISTS api_request_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    endpoint VARCHAR(120) NOT NULL,
    requested_at DATETIME NOT NULL,
    INDEX idx_api_request_log_time (requested_at)
);

-- Optional: make lookups fast as the library grows.
CREATE INDEX idx_words_level ON words(level);
CREATE INDEX idx_user_words_due ON user_words(user_id, status, last_review);
