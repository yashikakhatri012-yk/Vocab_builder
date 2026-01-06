CREATE DATABASE IF NOT EXISTS vocabulary;
USE vocabulary;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    exam VARCHAR(50),
    word_limit INT DEFAULT 10,
    start_date DATE DEFAULT CURRENT_DATE,
    end_date DATE
);
CREATE TABLE words (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word VARCHAR(100) NOT NULL,
    eng_meaning TEXT NOT NULL,
    part_of_speech VARCHAR(50),
    synonym TEXT,
    antonym TEXT,
    example TEXT,
    level ENUM('A1','A2','B1','B2','C1','C2')
);
CREATE TABLE user_words (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    word_id INT NOT NULL,

    status ENUM('new','known','unknown') DEFAULT 'new',

    learned_on DATE,
    last_review DATE,
    interval_days INT DEFAULT 1,

    known TINYINT(1) DEFAULT 0,
    unknown TINYINT(1) DEFAULT 0,

    ease FLOAT DEFAULT 2.5,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,

    UNIQUE (user_id, word_id)
);
CREATE TABLE user_streak (
    user_id INT PRIMARY KEY,
    last_active DATE,
    streak INT DEFAULT 1,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- Table: test_result
CREATE TABLE test_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    score INT NOT NULL,
    total INT NOT NULL,
    level VARCHAR(10),
    test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: daily_words
CREATE TABLE daily_words (
    user_id INT NOT NULL,
    word_id INT NOT NULL,
    word_date DATE NOT NULL,
    PRIMARY KEY (user_id, word_id, word_date)
);

-- Table: tests
CREATE TABLE tests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    score INT NOT NULL,
    date_taken DATE NOT NULL,
    streak INT DEFAULT 0
);
-- mcq_options table
CREATE TABLE mcq_options (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word_id INT NOT NULL,
    option_text VARCHAR(255) NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);
