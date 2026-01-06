# import csv

# with open("words.csv", newline="", encoding="latin-1") as file:
#     reader = csv.DictReader(file)
#     print("FIELDNAMES:", reader.fieldnames)

#     for row in reader:
#         print("ROW KEYS:", row.keys())
#         break




import csv
import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="fighter@2749",
    database="vocabulary"
)

cursor = conn.cursor()

with open("words.csv", newline="", encoding="latin-1") as file:
    reader = csv.DictReader(file)

    print("CSV Columns:", reader.fieldnames)  # ✅ YAHAN OK

    for row in reader:
        cursor.execute(
            """
            INSERT INTO words
            (word, part_of_speech, eng_meaning, synonym, antonym, example, level)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row["word"],
                row["part_of_speech"],
                row["eng_meaning"],
                row["synonym"],
                row["antonym"],
                row["example"],
                row["level"]
            )
        )

conn.commit()
conn.close()

print("Words imported successfully")
















