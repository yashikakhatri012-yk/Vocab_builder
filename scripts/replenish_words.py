"""Populate the local vocabulary library from the free dictionary providers.

Run from the repository root, for example:
    python scripts/replenish_words.py --count 10

Recommended production setup: run this with cron every 6-12 hours.
"""

import argparse

from app import mysql
from Services.word_ingestion import replenish_library


def main():
    parser = argparse.ArgumentParser(description="Replenish Vocab Builder's word library")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()

    count = max(1, min(20, args.count))
    inserted = replenish_library(mysql, count)
    print(f"Inserted {inserted} new word(s).")


if __name__ == "__main__":
    main()
