import os
import re
import sqlite3
from datetime import datetime
from difflib import SequenceMatcher
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import pathlib
_HERE = pathlib.Path(__file__).parent.resolve()
app = Flask(__name__,
            template_folder=str(_HERE / "templates"),
            static_folder=str(_HERE / "static"))
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

# ── Database path comes from the environment ───────────────────────────────────
DB_PATH = os.environ.get("POEM_DB", "poem.db")


# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    """Create the application-specific tables if they don't exist yet."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- One row per practice run of a chapter
        CREATE TABLE IF NOT EXISTS memorization_sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id),
            chapter_id   INTEGER NOT NULL REFERENCES chapters(id),
            started_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            total_score  REAL,          -- 0-100 average similarity
            grade        TEXT           -- letter grade
        );

        -- One row per verse attempt within a session
        CREATE TABLE IF NOT EXISTS verse_attempts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL REFERENCES memorization_sessions(id),
            verse_id     INTEGER NOT NULL REFERENCES verses(id),
            user_input   TEXT    NOT NULL,
            similarity   REAL    NOT NULL,  -- 0.0-1.0
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()


# ── Auth helpers ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def current_user():
    if "user_id" not in session:
        return None
    return get_db().execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()


# ── Text comparison helpers ────────────────────────────────────────────────────

def normalize_arabic_text(text):
    # Step 1: Replace Alef Wasla (ٱ) with regular Alif (ا)
    text = text.replace('\u0671', '\u0627')
    # Step 2: Remove Arabic diacritics (U+064B to U+0655)
    arabic_diacritics = re.compile(r'[\u064B-\u0655]')
    text = arabic_diacritics.sub('', text)
    return text

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_arabic_text(text.strip()))


def similarity_score(expected: str, user_input: str) -> float:
    """Returns 0.0–1.0 similarity (word-level, case-insensitive)."""
    a = normalize(expected).lower().split()
    b = normalize(user_input).lower().split()
    if not a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def build_diff_html(expected: str, user_input: str) -> str:
    """
    Returns an HTML snippet where:
      • correct words  → green
      • missing words  → red   (what was expected but not typed)
      • extra words    → amber (what was typed but not expected)
    """
    a = normalize(expected).split()
    b = normalize(user_input).split()
    parts = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None,
                                                 [w.lower() for w in a],
                                                 [w.lower() for w in b]).get_opcodes():
        if tag == "equal":
            parts += [f'<span class="diff-ok">{w}</span>' for w in a[i1:i2]]
        elif tag == "replace":
            parts += [f'<span class="diff-missing">{w}</span>' for w in a[i1:i2]]
            parts += [f'<span class="diff-extra">{w}</span>'   for w in b[j1:j2]]
        elif tag == "delete":
            parts += [f'<span class="diff-missing">{w}</span>' for w in a[i1:i2]]
        elif tag == "insert":
            parts += [f'<span class="diff-extra">{w}</span>'   for w in b[j1:j2]]
    return " ".join(parts)


def score_to_grade(score: float) -> str:
    """Convert 0-100 score to letter grade."""
    if score >= 97: return "A+"
    if score >= 93: return "A"
    if score >= 90: return "A−"
    if score >= 87: return "B+"
    if score >= 83: return "B"
    if score >= 80: return "B−"
    if score >= 77: return "C+"
    if score >= 73: return "C"
    if score >= 70: return "C−"
    if score >= 60: return "D"
    return "F"


def grade_color(grade: str) -> str:
    if grade.startswith("A"): return "success"
    if grade.startswith("B"): return "primary"
    if grade.startswith("C"): return "warning"
    return "danger"


# ── Routes: auth ───────────────────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        if not username or not password:
            flash("Username and password are required.", "danger")
        elif db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
            flash("Username already taken.", "danger")
        else:
            db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            db.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ── Routes: chapter selection ──────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    db = get_db()
    chapters = db.execute(
        'SELECT * FROM chapters ORDER BY id'
    ).fetchall()
    return render_template("index.html", chapters=chapters)


# ── Routes: memorization ───────────────────────────────────────────────────────

@app.route("/start/<int:chapter_id>")
@login_required
def start_session(chapter_id):
    db = get_db()
    chapter = db.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
    if not chapter:
        flash("Chapter not found.", "danger")
        return redirect(url_for("index"))

    # Create a new memorization session
    cur = db.execute(
        "INSERT INTO memorization_sessions (user_id, chapter_id) VALUES (?, ?)",
        (session["user_id"], chapter_id),
    )
    db.commit()
    mem_session_id = cur.lastrowid

    # Store progress in Flask session
    session["mem_session_id"] = mem_session_id
    session["chapter_id"]     = chapter_id
    session["verse_index"]    = 0          # index into the ordered verse list

    return redirect(url_for("verse_page"))


@app.route("/verse", methods=["GET", "POST"])
@login_required
def verse_page():
    if "mem_session_id" not in session:
        flash("No active session.", "warning")
        return redirect(url_for("index"))

    db        = get_db()
    chapter   = db.execute("SELECT * FROM chapters WHERE id = ?", (session["chapter_id"],)).fetchone()
    verses    = db.execute(
        "SELECT * FROM verses WHERE chapter_id = ? ORDER BY number",
        (session["chapter_id"],),
    ).fetchall()
    idx       = session["verse_index"]

    # All verses done → go to report
    if idx >= len(verses):
        return redirect(url_for("report"))

    verse     = verses[idx]
    prev_verse = verses[idx - 1] if idx > 0 else None

    diff_html  = None
    verse_score = None

    if request.method == "POST":
        user_input = request.form.get("user_input", "")
        sim        = similarity_score(verse["content"], user_input)
        score_pct  = round(sim * 100, 1)

        # Save attempt
        db.execute(
            """INSERT INTO verse_attempts (session_id, verse_id, user_input, similarity)
               VALUES (?, ?, ?, ?)""",
            (session["mem_session_id"], verse["id"], user_input, sim),
        )
        db.commit()

        diff_html   = build_diff_html(verse["content"], user_input)
        verse_score = score_pct

        # Advance on "next" button press (second submit)
        if "next" in request.form:
            session["verse_index"] = idx + 1
            session.modified = True
            return redirect(url_for("verse_page"))

        # First submit: show feedback
        return render_template(
            "verse.html",
            chapter=chapter,
            verse=verse,
            verses=verses,
            idx=idx,
            prev_verse=prev_verse,
            diff_html=diff_html,
            verse_score=verse_score,
            user_input=user_input,
        )

    return render_template(
        "verse.html",
        chapter=chapter,
        verse=verse,
        verses=verses,
        idx=idx,
        prev_verse=prev_verse,
        diff_html=diff_html,
        verse_score=verse_score,
        user_input=None,
    )


# ── Routes: report ─────────────────────────────────────────────────────────────

@app.route("/report")
@login_required
def report():
    if "mem_session_id" not in session:
        return redirect(url_for("index"))

    db         = get_db()
    mem_sid    = session["mem_session_id"]
    chapter    = db.execute("SELECT * FROM chapters WHERE id = ?", (session["chapter_id"],)).fetchone()

    attempts = db.execute(
        """SELECT va.*, v.content AS expected, v.number
           FROM verse_attempts va
           JOIN verses v ON v.id = va.verse_id
           WHERE va.session_id = ?
           ORDER BY v.number""",
        (mem_sid,),
    ).fetchall()

    if not attempts:
        flash("No attempts found.", "warning")
        return redirect(url_for("index"))

    avg_score = round(sum(a["similarity"] for a in attempts) / len(attempts) * 100, 1)
    grade     = score_to_grade(avg_score)

    # Finalise the session row
    db.execute(
        """UPDATE memorization_sessions
           SET completed_at = ?, total_score = ?, grade = ?
           WHERE id = ?""",
        (datetime.utcnow(), avg_score, grade, mem_sid),
    )
    db.commit()

    # Build per-verse diff
    diffs = [
        {
            "number":     a["number"],
            "expected":   a["expected"],
            "user_input": a["user_input"],
            "score":      round(a["similarity"] * 100, 1),
            "diff_html":  build_diff_html(a["expected"], a["user_input"]),
        }
        for a in attempts
    ]

    # History for this user / chapter
    history = db.execute(
        """SELECT ms.completed_at, ms.total_score, ms.grade
           FROM memorization_sessions ms
           WHERE ms.user_id = ? AND ms.chapter_id = ? AND ms.completed_at IS NOT NULL
           ORDER BY ms.completed_at DESC
           LIMIT 10""",
        (session["user_id"], session["chapter_id"]),
    ).fetchall()

    # Clear session state
    for key in ("mem_session_id", "chapter_id", "verse_index"):
        session.pop(key, None)

    return render_template(
        "report.html",
        chapter=chapter,
        diffs=diffs,
        avg_score=avg_score,
        grade=grade,
        grade_color=grade_color(grade),
        history=history,
    )


# ── Bootstrap ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
