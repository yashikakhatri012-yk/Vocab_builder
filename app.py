from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta
import random

app = Flask(__name__)
app.secret_key = "vocab_secret"

# ---------------- MYSQL ----------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'fighter@2749'
app.config['MYSQL_DB'] = 'vocabulary'
mysql = MySQL(app)

# ---------------- LOGIN ----------------
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password, name, exam, word_limit, start_date, end_date):
        self.id = id
        self.username = username
        self.password = password
        self.name = name
        self.exam = exam
        self.word_limit = word_limit
        self.start_date = start_date
        self.end_date = end_date

@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, username, password, name, exam, word_limit, start_date, end_date
        FROM users WHERE id=%s
    """, (user_id,))
    u = cur.fetchone()
    cur.close()
    return User(*u) if u else None

# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        password = generate_password_hash(request.form['password'])
        cur.execute("""
            INSERT INTO users (name, username, password, exam, word_limit)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            request.form['name'],
            request.form['username'],
            password,
            request.form.get('exam'),
            request.form.get('word_limit', 10)
        ))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('login'))
    return render_template('signup.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, username, password, name, exam, word_limit, start_date, end_date
            FROM users WHERE username=%s
        """, (request.form['username'],))
        u = cur.fetchone()
        cur.close()

        if u and check_password_hash(u[2], request.form['password']):
            login_user(User(*u))
            return redirect(url_for('Dashboard'))
        flash("Invalid login")
    return render_template('login.html')

@app.route('/')
def home():
    return redirect(url_for('Dashboard'))

# ---------------- STREAK ----------------
def update_streak(user_id):
    cur = mysql.connection.cursor()
    today = date.today()

    cur.execute("SELECT last_active, streak FROM user_streak WHERE user_id=%s", (user_id,))
    row = cur.fetchone()

    if not row:
        cur.execute("""
            INSERT INTO user_streak (user_id,last_active,streak)
            VALUES (%s,%s,1)
        """, (user_id, today))
    else:
        last, streak = row
        if last == today - timedelta(days=1):
            streak += 1
        elif last != today:
            streak = 1
        cur.execute("""
            UPDATE user_streak SET streak=%s,last_active=%s WHERE user_id=%s
        """, (streak, today, user_id))

    mysql.connection.commit()
    cur.close()

# ---------------- SPACED REPETITION ENGINE ----------------
from datetime import date

def get_daily_words(user_id, limit):
    cur = mysql.connection.cursor()
    today = date.today()

    # 🟢 FINAL LIST (always return list)
    words = []

    # 1️⃣ FETCH UNKNOWN / DUE WORDS
    cur.execute("""
        SELECT w.id, w.word, w.eng_meaning, w.part_of_speech,
               w.synonym, w.antonym, w.example, w.level
        FROM user_words uw
        JOIN words w ON uw.word_id = w.id
        WHERE uw.user_id = %s
        AND uw.status IN ('new','unknown')
        AND (uw.last_review IS NULL OR uw.last_review <= %s)
        LIMIT %s
    """, (user_id, today, limit))

    repeat_words = list(cur.fetchall())   # 🔥 convert tuple → list
    words.extend(repeat_words)

    remaining = limit - len(repeat_words)

    # 2️⃣ FETCH BRAND NEW WORDS (IF NEEDED)
    if remaining > 0:
        cur.execute("""
            SELECT id, word, eng_meaning, part_of_speech,
                   synonym, antonym, example, level
            FROM words
            WHERE id NOT IN (
                SELECT word_id FROM user_words WHERE user_id = %s
            )
            ORDER BY RAND()
            LIMIT %s
        """, (user_id, remaining))

        new_words = list(cur.fetchall())   # 🔥 convert tuple → list
        words.extend(new_words)

        # 3️⃣ INSERT NEW WORDS INTO user_words
        for w in new_words:
           cur.execute("""
                 INSERT INTO user_words
                 (user_id, word_id, status, learned_on, last_review,
                 interval_days, known, unknown, ease)
                 VALUES (%s, %s, 'new', %s, %s, 1, 0, 0, 2.5)""",
                 (user_id, w[0], today, today))

    mysql.connection.commit()
    cur.close()

    return words   # ✅ ALWAYS A LIST


# ---------------- DASHBOARD ----------------
@app.route('/Dashboard')
@login_required
def Dashboard():
    update_streak(current_user.id)

    cur = mysql.connection.cursor()
    cur.execute("SELECT streak FROM user_streak WHERE user_id=%s", (current_user.id,))
    streak = cur.fetchone()[0]
    cur.close()

    words = get_daily_words(current_user.id, current_user.word_limit)
    total = len(words)
    cur = mysql.connection.cursor()
    # Known count (clicked)
    cur.execute("""
    SELECT COUNT(*) FROM user_words
    WHERE user_id = %s AND known = 1
""", (current_user.id,))
    known = cur.fetchone()[0]

    # Unknown count (clicked)
    cur.execute("""
    SELECT COUNT(*) FROM user_words
    WHERE user_id = %s AND unknown = 1
""", (current_user.id,))
    unknown = cur.fetchone()[0]

    attempted = known + unknown
    accuracy = int((known / attempted) * 100) if attempted > 0 else 0
    
    cur.close()

    return render_template(
        "Dashboard.html",
        words=words,
        streak=streak,
        today=date.today(),
        total=total,
        known=known,
        unknown=unknown,
        accuracy=accuracy
    )

# ---------------- WORD STATUS UPDATE ----------------
@app.route('/update-word', methods=['POST'])
@login_required
def update_word():
    word_id = request.form['word_id']
    status = request.form['status']
    today = date.today()

    next_review = today + timedelta(days=1) if status == 'unknown' else None

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE user_words
        SET status=%s, last_review=%s,
            known=%s, unknown=%s
        WHERE user_id=%s AND word_id=%s
    """, (
        status,
        next_review,
        1 if status == 'known' else 0,
        1 if status == 'unknown' else 0,
        current_user.id,
        word_id
    ))
    mysql.connection.commit()
    cur.close()
    return "OK"

# ---------------- WEEKEND TEST (DAY 7) ----------------
@app.route('/test')
@login_required
def test():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT w.id, w.word, w.eng_meaning, w.level
        FROM user_words uw
        JOIN words w ON uw.word_id=w.id
        WHERE uw.user_id=%s
        AND uw.status='unknown'
    """, (current_user.id,))

    questions = []
    for wid, word, correct, level in cur.fetchall():
        cur.execute("""
            SELECT eng_meaning FROM words
            WHERE level=%s AND id!=%s
            ORDER BY RAND() LIMIT 3
        """, (level, wid))
        options = [o[0] for o in cur.fetchall()] + [correct]
        random.shuffle(options)

        questions.append({
            "id": wid,
            "word": word,
            "options": options,
            "correct": correct
        })
    cur.close()
    return render_template(
        "test.html",
        questions=questions,    
    )


# ---------------- SUBMIT MCQ ----------------
@app.route('/submit-mcq', methods=['POST'])
@login_required
def submit_mcq():
    cur = mysql.connection.cursor()
    score = 0

    for word_id, ans in request.form.items():
        cur.execute("SELECT eng_meaning FROM words WHERE id=%s", (word_id,))
        correct = cur.fetchone()[0]

        if ans == correct:
            score += 1
            cur.execute("""
                UPDATE user_words SET status='known', known=1, unknown=0
                WHERE user_id=%s AND word_id=%s
            """, (current_user.id, word_id))

    mysql.connection.commit()
    cur.close()
    return render_template("result.html", score=score)

# ---------------- SETTINGS ----------------
@app.route('/setting', methods=['GET','POST'])
@login_required
def setting():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE users SET name=%s, exam=%s, word_limit=%s
            WHERE id=%s
        """, (
            request.form['name'],
            request.form['exam'],
            request.form['word_limit'],
            current_user.id
        ))
        mysql.connection.commit()
        cur.close()
        flash("Settings updated")
    return render_template("setting.html", user=current_user)

# ---------------- LOGOUT ----------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
