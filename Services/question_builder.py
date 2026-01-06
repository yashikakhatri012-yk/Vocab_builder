import csv
import random

CSV_FILE = "words.csv"

def load_words():
    words = []
    with open(CSV_FILE, newline='', encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            words.append(row)
    return words


def generate_questions(limit=10):
    words = load_words()
    selected = random.sample(words, limit)

    questions = []

    for w in selected:
        options = [w["eng_meaning"]]

        # take random wrong options
        while len(options) < 4:
            opt = random.choice(words)["eng_meaning"]
            if opt not in options:
                options.append(opt)

        random.shuffle(options)

        questions.append({
            "word": w["word"],
            "options": options,
            "answer": w["eng_meaning"]
        })

    return questions
