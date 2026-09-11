import os
import random
from datetime import date, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mysqldb import MySQL
from werkzeug.security import check_password_hash, generate_password_hash

from Services.Spaced_repetition import update_spaced_repetition
from Services.word_ingestion import lookup_word, replenish_library


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me-in-production")

# ---------------- DATABASE ----------------
app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST", "localhost")
app.config["MYSQL_USER"] = os.getenv("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD", "")
app.config["MYSQL_DB"] = os.getenv("MYSQL_DB", "vocabulary")
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
mysql = MySQL(app)

# ---------------- LOGIN ----------------
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.password = row["password"]
        self.name = row.get("name") or "Learner"
        self.exam = row.get("exam") or "English Proficiency"
        self.word_limit = int(row.get("word_limit") or 10)
        self.start_date = row.get("start_date")
        self.end_date = row.get("end_date")


@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT id, username, password, name, exam, word_limit, start_date, end_date
        FROM users WHERE id=%s
        """,
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    return User(row) if row else None


# ---------------- HELPERS ----------------
def get_today():
    return date.today()


def clamp_word_limit(value, default=10):
    try:
        return max(3, min(50, int(value)))
    except (TypeError, ValueError):
        return default


def update_streak(user_id):
    today = get_today()
    cur = mysql.connection.cursor()
    cur.execute("SELECT last_active, streak FROM user_streak WHERE user_id=%s", (user_id,))
    row = cur.fetchone()

    if not row:
        cur.execute(
            "INSERT INTO user_streak (user_id, last_active, streak) VALUES (%s, %s, 1)",
            (user_id, today),
        )
        streak = 1
    else:
        last_active = row["last_active"]
        streak = int(row["streak"] or 0)
        if last_active == today:
            pass
        elif last_active == today - timedelta(days=1):
            streak += 1
        else:
            streak = 1
        cur.execute(
            "UPDATE user_streak SET streak=%s, last_active=%s WHERE user_id=%s",
            (streak, today, user_id),
        )

    mysql.connection.commit()
    cur.close()
    return streak


def get_daily_words(user_id, limit):
    """Return due review words first, then fill remaining slots with unseen words."""
    today = get_today()
    limit = clamp_word_limit(limit)
    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT w.id, w.word, w.eng_meaning, w.part_of_speech,
               w.synonym, w.antonym, w.example, w.level,
               w.phonetic, w.audio_url, w.source,
               uw.status, uw.interval_days, uw.ease, uw.last_review
        FROM user_words uw
        JOIN words w ON uw.word_id = w.id
        WHERE uw.user_id = %s
          AND (
                (uw.status IN ('new','unknown')
                 AND (uw.last_review IS NULL OR uw.last_review <= %s))
                OR
                (uw.status = 'known'
                 AND uw.last_review IS NOT NULL
                 AND uw.last_review <= %s)
              )
        ORDER BY
            CASE WHEN uw.status='unknown' THEN 0 ELSE 1 END,
            COALESCE(uw.last_review, %s),
            w.id
        LIMIT %s
        """,
        (user_id, today, today, today, limit),
    )
    words = list(cur.fetchall())

    remaining = limit - len(words)
    if remaining > 0:
        cur.execute(
            """
            SELECT id, word, eng_meaning, part_of_speech,
                   synonym, antonym, example, level,
                   phonetic, audio_url, source,
                   'new' AS status, 1 AS interval_days, 2.5 AS ease,
                   NULL AS last_review
            FROM words
            WHERE id NOT IN (SELECT word_id FROM user_words WHERE user_id=%s)
            ORDER BY RAND()
            LIMIT %s
            """,
            (user_id, remaining),
        )
        new_words = list(cur.fetchall())
        words.extend(new_words)
        for word in new_words:
            cur.execute(
                """
                INSERT INTO user_words
                    (user_id, word_id, status, learned_on, last_review,
                     interval_days, known, unknown, ease)
                VALUES (%s, %s, 'new', %s, %s, 1, 0, 0, 2.5)
                """,
                (user_id, word["id"], today, today),
            )

    mysql.connection.commit()
    cur.close()
    return words


def get_dashboard_stats(user_id):
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT COUNT(*) AS tracked,
               COALESCE(SUM(known),0) AS known,
               COALESCE(SUM(unknown),0) AS unknown,
               COALESCE(SUM(CASE WHEN status='unknown' AND last_review <= %s THEN 1 ELSE 0 END),0) AS due
        FROM user_words WHERE user_id=%s
        """,
        (get_today(), user_id),
    )
    row = cur.fetchone()
    known = int(row["known"] or 0)
    unknown = int(row["unknown"] or 0)
    attempted = known + unknown

    cur.execute("SELECT COUNT(*) AS total FROM words")
    library_size = int(cur.fetchone()["total"] or 0)

    cur.execute(
        """
        SELECT id, score, total, level, test_date
        FROM test_result WHERE user_id=%s
        ORDER BY test_date DESC LIMIT 5
        """,
        (user_id,),
    )
    tests = cur.fetchall()
    cur.close()

    return {
        "tracked": int(row["tracked"] or 0),
        "known": known,
        "unknown": unknown,
        "due": int(row["due"] or 0),
        "accuracy": round((known / attempted) * 100) if attempted else 0,
        "library_size": library_size,
        "tests": tests,
    }


def build_questions(user_id, level_filter=None, limit=10):
    cur = mysql.connection.cursor()
    params = [user_id]
    where_level = ""
    levels = []

    if level_filter:
        levels = [x.strip().upper() for x in level_filter.split(",") if x.strip()]
        valid = {"A1", "A2", "B1", "B2", "C1", "C2"}
        levels = [x for x in levels if x in valid]
        if levels:
            placeholders = ",".join(["%s"] * len(levels))
            where_level = f" AND w.level IN ({placeholders})"
            params.extend(levels)

    cur.execute(
        f"""
        SELECT w.id, w.word, w.eng_meaning, w.level
        FROM user_words uw JOIN words w ON uw.word_id=w.id
        WHERE uw.user_id=%s AND uw.status IN ('unknown','new') {where_level}
        ORDER BY RAND() LIMIT %s
        """,
        (*params, limit),
    )
    candidates = list(cur.fetchall())

    if len(candidates) < limit:
        level_clause = ""
        if levels:
            placeholders = ",".join(["%s"] * len(levels))
            level_clause = f" AND level IN ({placeholders})"
        cur.execute(
            f"""
            SELECT id, word, eng_meaning, level FROM words
            WHERE id NOT IN (SELECT word_id FROM user_words WHERE user_id=%s)
            {level_clause}
            ORDER BY RAND() LIMIT %s
            """,
            (user_id, *levels, limit - len(candidates)),
        )
        candidates.extend(cur.fetchall())

    questions = []
    for item in candidates[:limit]:
        cur.execute(
            "SELECT eng_meaning FROM words WHERE level=%s AND id!=%s ORDER BY RAND() LIMIT 6",
            (item["level"], item["id"]),
        )
        distractors = [r["eng_meaning"] for r in cur.fetchall()]
        options = []
        for option in distractors + [item["eng_meaning"]]:
            if option not in options:
                options.append(option)
            if len(options) == 4:
                break
        while len(options) < 4:
            cur.execute("SELECT eng_meaning FROM words WHERE id!=%s ORDER BY RAND() LIMIT 1", (item["id"],))
            row = cur.fetchone()
            if not row or row["eng_meaning"] in options:
                break
            options.append(row["eng_meaning"])

        random.shuffle(options)
        questions.append({
            "id": item["id"],
            "word": item["word"],
            "meaning": item["eng_meaning"],
            "level": item["level"],
            "options": options,
        })

    cur.close()
    return questions


# ---------------- AUTH ----------------
@app.route("/")
def home():
    return redirect(url_for("Dashboard" if current_user.is_authenticated else "login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("Dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        exam = request.form.get("exam", "English Proficiency")
        word_limit = clamp_word_limit(request.form.get("word_limit"))
        start_date = request.form.get("start_date") or None
        end_date = request.form.get("end_date") or None

        if len(name) < 2 or not username or len(password) < 6:
            flash("Use a name, valid email, and a password with at least 6 characters.", "error")
            return render_template("signup.html")

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            cur.close()
            flash("An account with that email already exists.", "error")
            return render_template("signup.html")

        cur.execute(
            """
            INSERT INTO users (name, username, password, exam, word_limit, start_date, end_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (name, username, generate_password_hash(password), exam, word_limit, start_date, end_date),
        )
        mysql.connection.commit()
        cur.close()
        flash("Account created. Welcome to Vocab Builder!", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("Dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, username, password, name, exam, word_limit, start_date, end_date FROM users WHERE username=%s",
            (username,),
        )
        row = cur.fetchone()
        cur.close()

        if row and check_password_hash(row["password"], password):
            login_user(User(row))
            return redirect(url_for("Dashboard"))

        flash("Email or password is incorrect.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------------- DASHBOARD ----------------
@app.route("/Dashboard")
@login_required
def Dashboard():
    streak = update_streak(current_user.id)
    words = get_daily_words(current_user.id, current_user.word_limit)
    stats = get_dashboard_stats(current_user.id)
    return render_template("Dashboard.html", words=words, streak=streak, today=get_today(), stats=stats)


# ---------------- LIVE WORD LOOKUP ----------------
@app.route("/lookup")
@login_required
def lookup():
    query = request.args.get("word", "").strip()
    result = lookup_word(mysql, query) if query else None
    return render_template("lookup.html", query=query, result=result)


@app.route("/api/lookup")
@login_required
def api_lookup():
    query = request.args.get("word", "").strip()
    result = lookup_word(mysql, query) if query else None
    if not result:
        return jsonify({"ok": False, "error": "Word not found"}), 404
    return jsonify({"ok": True, "word": result})


# ---------------- WORD REVIEW ----------------
@app.route("/update-word", methods=["POST"])
@login_required
def update_word():
    try:
        word_id = int(request.form.get("word_id", "0"))
    except ValueError:
        flash("Invalid word.", "error")
        return redirect(url_for("Dashboard"))

    status = request.form.get("status", "unknown")
    if status not in {"known", "unknown"}:
        status = "unknown"

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT interval_days, ease FROM user_words WHERE user_id=%s AND word_id=%s",
        (current_user.id, word_id),
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        flash("That word is no longer available.", "error")
        return redirect(url_for("Dashboard"))

    old_interval = int(row["interval_days"] or 1)
    old_ease = float(row["ease"] or 2.5)
    quality = 5 if status == "known" else 2
    interval, ease = update_spaced_repetition(quality, old_interval, old_ease)
    next_review = get_today() + timedelta(days=max(1, interval))

    cur.execute(
        """
        UPDATE user_words
        SET status=%s, last_review=%s, interval_days=%s, ease=%s,
            known=%s, unknown=%s, learned_on=COALESCE(learned_on, %s)
        WHERE user_id=%s AND word_id=%s
        """,
        (
            status, next_review, interval, ease,
            1 if status == "known" else 0,
            1 if status == "unknown" else 0,
            get_today(), current_user.id, word_id,
        ),
    )
    mysql.connection.commit()
    cur.close()

    flash(
        "Marked as learned. Nice work!" if status == "known" else "Added to your review queue.",
        "success",
    )
    return redirect(url_for("Dashboard"))


# ---------------- TEST ZONE ----------------
@app.route("/test")
@login_required
def test():
    level_filter = request.args.get("level", "A1,A2")
    questions = build_questions(current_user.id, level_filter=level_filter, limit=10)
    return render_template("test.html", questions=questions, level_filter=level_filter)


@app.route("/submit-mcq", methods=["POST"])
@login_required
def submit_mcq():
    answers = {}
    for key, value in request.form.items():
        if key.startswith("q_"):
            try:
                answers[int(key[2:])] = value
            except ValueError:
                continue

    if not answers:
        flash("No answers were submitted. Start the test again.", "error")
        return redirect(url_for("test"))

    ids = list(answers.keys())
    placeholders = ",".join(["%s"] * len(ids))
    cur = mysql.connection.cursor()
    cur.execute(
        f"SELECT id, word, eng_meaning, level FROM words WHERE id IN ({placeholders})",
        tuple(ids),
    )
    rows = {row["id"]: row for row in cur.fetchall()}

    results = []
    score = 0
    for word_id in ids:
        word = rows.get(word_id)
        if not word:
            continue
        selected = answers[word_id]
        is_correct = selected == word["eng_meaning"]
        score += int(is_correct)
        results.append({
            "word": word["word"],
            "selected": selected,
            "correct": word["eng_meaning"],
            "is_correct": is_correct,
            "level": word["level"],
        })

        quality = 5 if is_correct else 2
        cur.execute(
            "SELECT interval_days, ease FROM user_words WHERE user_id=%s AND word_id=%s",
            (current_user.id, word_id),
        )
        progress = cur.fetchone()
        old_interval = int(progress["interval_days"] or 1) if progress else 1
        old_ease = float(progress["ease"] or 2.5) if progress else 2.5
        interval, ease = update_spaced_repetition(quality, old_interval, old_ease)
        next_review = get_today() + timedelta(days=max(1, interval))
        status = "known" if is_correct else "unknown"

        cur.execute(
            """
            INSERT INTO user_words
                (user_id, word_id, status, learned_on, last_review,
                 interval_days, known, unknown, ease)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                status=VALUES(status), last_review=VALUES(last_review),
                interval_days=VALUES(interval_days), known=VALUES(known),
                unknown=VALUES(unknown), ease=VALUES(ease)
            """,
            (
                current_user.id, word_id, status,
                get_today(), next_review, interval,
                1 if is_correct else 0, 0 if is_correct else 1, ease,
            ),
        )

    total = len(results)
    level = request.form.get("test_level", "Mixed")
    cur.execute(
        "INSERT INTO test_result (user_id, score, total, level) VALUES (%s,%s,%s,%s)",
        (current_user.id, score, total, level[:10]),
    )
    mysql.connection.commit()
    cur.close()

    streak = update_streak(current_user.id)
    percentage = round((score / total) * 100) if total else 0
    return render_template(
        "result.html",
        results=results,
        score=score,
        total=total,
        percentage=percentage,
        streak=streak,
    )


# ---------------- MAINTENANCE ----------------
@app.route("/maintenance/replenish", methods=["POST"])
def maintenance_replenish():
    expected = os.getenv("MAINTENANCE_TOKEN", "")
    provided = request.headers.get("X-Maintenance-Token", "")
    if not expected or provided != expected:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    try:
        requested = max(1, min(20, int(request.form.get("count", 10))))
    except (TypeError, ValueError):
        requested = 10

    try:
        inserted = replenish_library(mysql, requested)
    except Exception:
        mysql.connection.rollback()
        return jsonify({"ok": False, "error": "Library refresh failed"}), 503

    return jsonify({"ok": True, "inserted": inserted})


# ---------------- SETTINGS ----------------
@app.route("/setting", methods=["GET", "POST"])
@login_required
def setting():
    if request.method == "POST":
        name = request.form.get("name", current_user.name).strip() or current_user.name
        exam = request.form.get("exam", current_user.exam)
        word_limit = clamp_word_limit(request.form.get("word_limit"), current_user.word_limit)
        start_date = request.form.get("start_date") or None
        end_date = request.form.get("end_date") or None

        cur = mysql.connection.cursor()
        cur.execute(
            """
            UPDATE users
            SET name=%s, exam=%s, word_limit=%s, start_date=%s, end_date=%s
            WHERE id=%s
            """,
            (name, exam, word_limit, start_date, end_date, current_user.id),
        )

        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password or confirm_password or current_password:
            if not check_password_hash(current_user.password, current_password):
                cur.close()
                flash("Current password is incorrect.", "error")
                return render_template("setting.html", user=current_user)
            if len(new_password) < 6 or new_password != confirm_password:
                cur.close()
                flash("New passwords must match and be at least 6 characters.", "error")
                return render_template("setting.html", user=current_user)
            cur.execute(
                "UPDATE users SET password=%s WHERE id=%s",
                (generate_password_hash(new_password), current_user.id),
            )

        mysql.connection.commit()
        cur.close()
        current_user.name = name
        current_user.exam = exam
        current_user.word_limit = word_limit
        current_user.start_date = start_date
        current_user.end_date = end_date
        flash("Settings saved successfully.", "success")
        return redirect(url_for("setting"))

    return render_template("setting.html", user=current_user)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
