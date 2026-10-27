"""
db.py — SQLite storage layer.

We use SQLite because it needs zero setup: the whole database is one file
(mockinterview.db). When you outgrow it, swap these functions for Postgres.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "mockinterview.db")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT NOT NULL,
    round       TEXT NOT NULL,
    text        TEXT NOT NULL,
    ideal       TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '',
    difficulty  INTEGER NOT NULL DEFAULT 2
);

CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name    TEXT NOT NULL,
    company         TEXT NOT NULL,
    round           TEXT NOT NULL,
    difficulty_felt INTEGER NOT NULL,
    rating          INTEGER NOT NULL,
    text            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name TEXT NOT NULL,
    company      TEXT NOT NULL,
    round        TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    finished     INTEGER NOT NULL DEFAULT 0,
    total_questions INTEGER NOT NULL DEFAULT 4,
    current_qid  INTEGER,
    report_json  TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,
    question_id   INTEGER,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    score_json    TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS question_stats (
    question_id   INTEGER PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
    times_asked   INTEGER NOT NULL DEFAULT 0,
    avg_score     REAL NOT NULL DEFAULT 0,
    last_asked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_questions_company ON questions(company, round);
CREATE INDEX IF NOT EXISTS idx_reviews_company   ON reviews(company, round);
CREATE INDEX IF NOT EXISTS idx_turns_session     ON turns(session_id);
"""


def is_initialized():
    """
    True when the schema is actually present.

    Guards a real failure we hit: if the .db file is deleted (or truncated)
    while the server is running, SQLite silently re-creates a 0-byte file on
    the next connect and every query fails with "no such table". The process
    stays up and returns 500s, which looks like a dead app with a live port.
    """
    try:
        conn = connect()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='questions'"
        ).fetchone()
        conn.close()
        return bool(row)
    except sqlite3.Error:
        return False


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(force_reseed=False):
    """Create tables and load the seed question bank + seed reviews."""
    conn = connect()
    conn.executescript(SCHEMA)

    # Tiny migration helper: add columns that older DB files lack.
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    if "total_questions" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN total_questions INTEGER NOT NULL DEFAULT 4")
    if "current_qid" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN current_qid INTEGER")
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
    if count == 0 or force_reseed:
        if force_reseed:
            conn.execute("DELETE FROM questions")
            conn.execute("DELETE FROM question_stats")
        with open(os.path.join(DATA_DIR, "questions.json"), encoding="utf-8") as f:
            bank = json.load(f)
        for q in bank["questions"]:
            conn.execute(
                "INSERT INTO questions (company, round, text, ideal, tags, difficulty) "
                "VALUES (?,?,?,?,?,?)",
                (
                    q.get("company") or "Generic Fresher",
                    q["round"],
                    q["text"],
                    q["ideal"],
                    ",".join(q.get("tags", [])),
                    int(q.get("difficulty", 2)),
                ),
            )
        conn.commit()

    rcount = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]
    if rcount == 0:
        with open(os.path.join(DATA_DIR, "seed_reviews.json"), encoding="utf-8") as f:
            reviews = json.load(f)
        for r in reviews:
            created = datetime.now(timezone.utc) - timedelta(days=int(r.get("days_ago", 0)))
            conn.execute(
                "INSERT INTO reviews (student_name, company, round, difficulty_felt, "
                "rating, text, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    r["student_name"],
                    r["company"],
                    r["round"],
                    int(r["difficulty_felt"]),
                    int(r["rating"]),
                    r["text"],
                    created.isoformat(timespec="seconds"),
                ),
            )
        conn.commit()

    conn.close()


# ---------------------------------------------------------------- questions

def get_companies():
    """Company catalogue with review-derived metadata."""
    conn = connect()
    with open(os.path.join(DATA_DIR, "questions.json"), encoding="utf-8") as f:
        bank = json.load(f)

    rows = conn.execute(
        "SELECT company, COUNT(*) AS n FROM questions GROUP BY company"
    ).fetchall()
    qcounts = {r["company"]: r["n"] for r in rows}

    rev = conn.execute(
        "SELECT company, COUNT(*) AS n, AVG(difficulty_felt) AS d, AVG(rating) AS r "
        "FROM reviews GROUP BY company"
    ).fetchall()
    revmap = {r["company"]: r for r in rev}
    conn.close()

    out = []
    for c in bank["companies"]:
        name = c["name"]
        rv = revmap.get(name)
        # Only advertise rounds we can actually run. Showing a round with an
        # empty question pool was a real bug: clicking "Cognizant + aptitude"
        # returned a 400 with no explanation in the UI.
        available = [r for r in c["rounds"] if len(questions_for(name, r)) > 0]
        out.append(
            {
                "name": name,
                "type": c["type"],
                "about": c["about"],
                "rounds": available or c["rounds"],
                "question_count": qcounts.get(name, 0),
                "review_count": rv["n"] if rv else 0,
                "avg_difficulty_felt": round(rv["d"], 2) if rv else None,
                "avg_rating": round(rv["r"], 2) if rv else None,
            }
        )
    return out


def questions_for(company, round_name):
    """
    Question pool for a company+round: the company's own questions FIRST,
    then shared 'Generic Fresher' questions for that round as filler so a
    round never runs out of material. Company questions naturally rank higher
    because of the review-topic weighting.
    """
    conn = connect()
    base = (
        "SELECT q.*, COALESCE(s.times_asked,0) AS times_asked, "
        "COALESCE(s.avg_score,0) AS avg_score "
        "FROM questions q LEFT JOIN question_stats s ON s.question_id = q.id "
    )
    own = conn.execute(base + "WHERE q.company = ? AND q.round = ?", (company, round_name)).fetchall()
    generic = []
    if company != "Generic Fresher":
        generic = conn.execute(
            base + "WHERE q.company = 'Generic Fresher' AND q.round = ?", (round_name,)
        ).fetchall()
    conn.close()

    seen, out = set(), []
    for r in list(own) + list(generic):
        d = dict(r)
        if d["text"] in seen:
            continue
        seen.add(d["text"])
        d["is_generic"] = d["company"] == "Generic Fresher"
        out.append(d)
    return out


def company_questions_only(company, round_name):
    """Strict company pool — used for coverage-gap analysis."""
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM questions WHERE company = ? AND round = ?", (company, round_name)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def all_questions():
    conn = connect()
    rows = conn.execute("SELECT * FROM questions").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_question_stats(question_id, score):
    conn = connect()
    row = conn.execute(
        "SELECT times_asked, avg_score FROM question_stats WHERE question_id = ?",
        (question_id,),
    ).fetchone()
    if row:
        n = row["times_asked"] + 1
        avg = (row["avg_score"] * row["times_asked"] + score) / n
        conn.execute(
            "UPDATE question_stats SET times_asked=?, avg_score=?, last_asked_at=? "
            "WHERE question_id=?",
            (n, avg, now(), question_id),
        )
    else:
        conn.execute(
            "INSERT INTO question_stats (question_id, times_asked, avg_score, last_asked_at) "
            "VALUES (?,1,?,?)",
            (question_id, score, now()),
        )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------ reviews

def add_review(student_name, company, round_name, difficulty_felt, rating, text):
    conn = connect()
    cur = conn.execute(
        "INSERT INTO reviews (student_name, company, round, difficulty_felt, rating, "
        "text, created_at) VALUES (?,?,?,?,?,?,?)",
        (student_name, company, round_name, int(difficulty_felt), int(rating), text, now()),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def reviews_for(company=None, round_name=None, limit=200):
    conn = connect()
    sql = "SELECT * FROM reviews WHERE 1=1"
    params = []
    if company:
        sql += " AND company = ?"
        params.append(company)
    if round_name:
        sql += " AND round = ?"
        params.append(round_name)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------- sessions

def create_session(student_name, company, round_name, total_questions=4):
    conn = connect()
    cur = conn.execute(
        "INSERT INTO sessions (student_name, company, round, created_at, total_questions) "
        "VALUES (?,?,?,?,?)",
        (student_name, company, round_name, now(), int(total_questions)),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def set_current_question(session_id, question_id):
    conn = connect()
    conn.execute("UPDATE sessions SET current_qid=? WHERE id=?", (question_id, session_id))
    conn.commit()
    conn.close()


def get_session(session_id):
    conn = connect()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_session(session_id, finished=None, report=None):
    conn = connect()
    if finished is not None:
        conn.execute("UPDATE sessions SET finished=? WHERE id=?", (int(finished), session_id))
    if report is not None:
        conn.execute(
            "UPDATE sessions SET report_json=? WHERE id=?",
            (json.dumps(report, ensure_ascii=False), session_id),
        )
    conn.commit()
    conn.close()


def add_turn(session_id, seq, question_id, question, answer, score):
    conn = connect()
    conn.execute(
        "INSERT INTO turns (session_id, seq, question_id, question, answer, score_json, "
        "created_at) VALUES (?,?,?,?,?,?,?)",
        (session_id, seq, question_id, question, answer, json.dumps(score, ensure_ascii=False), now()),
    )
    conn.commit()
    conn.close()


def set_turn_score(turn_id, score):
    conn = connect()
    conn.execute(
        "UPDATE turns SET score_json=? WHERE id=?",
        (json.dumps(score, ensure_ascii=False), turn_id),
    )
    conn.commit()
    conn.close()


def turns_for(session_id):
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM turns WHERE session_id = ? ORDER BY seq", (session_id,)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["score"] = json.loads(d.pop("score_json"))
        out.append(d)
    return out


def student_history(student_name, limit=20):
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE student_name = ? ORDER BY id DESC LIMIT ?",
        (student_name, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db(force_reseed=True)
    print(f"Seeded database at {DB_PATH}")
    print(f"  questions: {len(all_questions())}")
    print(f"  reviews  : {len(reviews_for())}")
