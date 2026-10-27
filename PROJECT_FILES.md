# InterviewLoop — complete source, one file

Every source file in the project, in copy-paste order. Reconstruction is **lossless**: the generator verifies a rebuild matches the original byte-for-byte.

## How to use this

**Option A — rebuild the server app (recommended)**

1. Create the folders shown in the tree below.
2. Create each file and paste the matching block.
3. Then run:

```bash
pip install -r requirements.txt
python -m app.db                       # creates the database, seeds 65 questions
python -m uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000> in Chrome or Edge.

**Option B — just want the demo, no Python**

You only need `standalone/` plus `data/`, then:

```bash
python standalone/build.py     # produces standalone.html
```

Double-click the resulting `standalone.html`. Whole app, one file, no server.

## Not included (generated, not hand-written)

| File | How to generate |
|---|---|
| `standalone.html` | `python standalone/build.py` |
| `mockinterview.db` | `python -m app.db` |
| `screenshot-*.png` | binary images — download from the project workspace |

**31 files · 357 KB of text.**

## Directory structure

```text
mockinterview/
├── .github/
│   └── workflows/
│       └── ci.yml
├── app/
│   ├── __init__.py
│   ├── db.py
│   ├── engine.py
│   ├── feedback.py
│   ├── llm.py
│   ├── main.py
│   └── scoring.py
├── data/
│   ├── questions.json
│   └── seed_reviews.json
├── standalone/
│   ├── build.py
│   ├── engine.js
│   ├── local_api.js
│   └── template.html
├── static/
│   ├── index.html
│   ├── voice.html
│   └── voice.js
├── tests/
│   └── test_scoring.py
├── tools/
│   └── file_bundle.py
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── GO_LIVE.md
├── PUSH_TO_GITHUB.md
├── Procfile
├── README.md
├── SETUP.md
├── render.yaml
├── requirements.txt
└── run.sh
```

---

## Files

<!-- FILE: requirements.txt -->

<sub>43 bytes</sub>

```
fastapi>=0.110
uvicorn>=0.27
pydantic>=2.0

```

---

<!-- FILE: run.sh -->

<sub>547 bytes</sub>

```bash
#!/usr/bin/env bash
# One-command start: seeds the DB if missing/empty, then serves the app.
set -euo pipefail
cd "$(dirname "$0")"

needs_seed=0
if [ ! -f mockinterview.db ]; then
  needs_seed=1
elif [ ! -s mockinterview.db ]; then
  # A 0-byte file is worse than no file: the server starts, then 500s everywhere.
  echo "Found an empty mockinterview.db — reseeding."
  needs_seed=1
fi

if [ "$needs_seed" = "1" ]; then
  rm -f mockinterview.db
  python3 -m app.db
fi

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

```

---

<!-- FILE: .gitignore -->

<sub>258 bytes</sub>

```
# Python
__pycache__/
*.py[cod]
.venv/
venv/
env/
*.egg-info/

# App data (generated at runtime, not source)
mockinterview.db
*.db
*.sqlite3

# Secrets — never commit these
.env
.env.*
!.env.example

# OS / editor
.DS_Store
Thumbs.db
.idea/
.vscode/
*.swp

```

---

<!-- FILE: .env.example -->

<sub>478 bytes</sub>

```bash
# Copy to .env and fill in only what you need. The app runs fine with none of these.

# Optional: turns on generative follow-ups and richer coaching feedback.
# Works with any OpenAI-compatible endpoint (OpenAI, Groq, Together, OpenRouter, Ollama).
# OPENAI_API_KEY=sk-...
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-mini

# For Ollama locally (free, private, no key needed):
# LLM_BASE_URL=http://localhost:11434/v1
# LLM_MODEL=llama3.1
# OPENAI_API_KEY=ollama

```

---

<!-- FILE: app/__init__.py -->

<sub>0 bytes</sub>

```python

```

---

<!-- FILE: app/db.py -->

<sub>13205 bytes</sub>

```python
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

```

---

<!-- FILE: app/scoring.py -->

<sub>19356 bytes</sub>

```python
"""
scoring.py — rubric-based answer evaluation.

WHY A RUBRIC AND NOT JUST "ASK THE LLM IF IT'S GOOD":
  A score from an LLM alone is unreproducible — the same answer can get 6/10
  today and 8/10 tomorrow, which destroys student trust. So we always compute
  a deterministic rubric score over explicit dimensions. The LLM (when you add
  a key) is used for the *narrative* feedback, and its score is blended in as
  one weighted signal rather than being the whole answer.

Dimensions (each 0-10, then weighted):
  coverage   35%  - did the answer hit the key concepts in the ideal answer?
  structure  20%  - is there a beginning/middle/end (STAR for behavioural)?
  specificity 20% - concrete details: numbers, names, examples, code terms
  depth      15%  - length appropriate, no filler-only rambling
  confidence 10%  - hedging words ("maybe", "I think", "not sure")
"""

import re
from difflib import SequenceMatcher

from .feedback import STOPWORDS, _tokens

# Technical answers are graded mostly on correctness (coverage) — a correct
# answer delivered plainly is still correct. Behavioural answers are graded
# mostly on whether the story is complete and well-told, so structure carries
# more weight there.
WEIGHTS_TECHNICAL = {
    "coverage": 0.40,
    "specificity": 0.20,
    "structure": 0.15,
    "depth": 0.15,
    "confidence": 0.10,
}
WEIGHTS_BEHAVIOURAL = {
    "coverage": 0.30,
    "structure": 0.25,
    "specificity": 0.20,
    "depth": 0.15,
    "confidence": 0.10,
}
WEIGHTS = WEIGHTS_TECHNICAL   # default for external callers

STAR_MARKERS = [
    "situation", "task", "action", "result", "when i", "at that time",
    "i decided", "i built", "i led", "so i", "as a result", "finally",
    "the outcome", "we achieved", "i learned",
]
STRUCTURE_MARKERS = [
    "first", "second", "third", "then", "next", "finally", "because",
    "for example", "however", "on the other hand", "in short", "to summarise",
    "to summarize", "in conclusion", "so that",
]
HEDGES = [
    "maybe", "i think", "i guess", "not sure", "i don't know", "dont know",
    "kind of", "sort of", "probably", "somewhat", "i believe", "umm", "uhh",
    "actually i", "i'm not", "im not", "no idea", "not really",
]
FILLERS = ["basically", "actually", "you know", "like i said", "stuff", "things like that", "etc"]

# Common technical vocabulary worth a specificity bump when used.
TECH_TERMS = set(
    """o(n) o(1) o(log n) time complexity space complexity hash map hashmap array
    string pointer recursion iterative query index join primary key foreign key
    normalization class object interface inheritance polymorphism thread process
    memory cache api endpoint latency throughput scalable trade-off tradeoff
    buffer queue stack tree graph heap algorithm function variable parameter
    request response server client database table row column schema
    acid transaction commit rollback idempotent concurrency lock mutex""".split()
)


def _lexical_overlap(answer, ideal):
    """Content-word overlap between the answer and the model answer."""
    a = set(_tokens(answer))
    i = set(_tokens(ideal))
    if not i:
        return 0.0
    hit = len(a & i)
    return min(1.0, hit / max(1, min(len(i), 14)))


def _key_concepts(ideal, limit=12):
    """The distinct content words of the reference answer, in order."""
    out = []
    for t in _tokens(ideal):
        if len(t) > 2 and t not in out:
            out.append(t)
    return out[:limit]


def _concept_coverage(answer, ideal):
    """
    Fraction of the reference answer's key concepts the candidate touched.

    Deliberately forgiving: a candidate who says 'hashmap' where the reference
    says 'hash map', or 'combine the tables' where it says 'join', should not
    be punished for vocabulary. Prefix matching handles simple morphology.
    """
    concepts = _key_concepts(ideal)
    if not concepts:
        return 0.0
    a_tokens = set(_tokens(answer))
    a_flat = " ".join(_tokens(answer))
    hits = 0
    for c in concepts:
        if c in a_tokens or c in a_flat:
            hits += 1
        elif len(c) >= 5 and any(t.startswith(c[:5]) for t in a_tokens):
            hits += 1
    return hits / len(concepts)


def _fuzzy_overlap(answer, ideal):
    """Catches paraphrases the exact-match metric misses."""
    a = " ".join(_tokens(answer))
    i = " ".join(_tokens(ideal))
    if not a or not i:
        return 0.0
    return SequenceMatcher(None, a, i).ratio()


def _count(answer, markers):
    low = answer.lower()
    return sum(1 for m in markers if m in low)


# Causal / justification language. A direct HR answer needs a *reason*, and
# people rarely say "because" — they say "so", "since", "which means".
REASON_RE = (r"\b(because|since|so that|so i|so I|so my|the reason|due to|which means|"
             r"my goal|therefore|hence|thus|as a result|supportive|comfortable with|"
             r"that is why|for that reason)\b")
# Concrete detail: digits OR spelled-out numbers ("four years", "two projects").
NUMBER_RE = (r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
             r"for example|for instance|such as|in my college|during my|last year|"
             r"at my|in my hostel)\b")

STORY_CUES = [
    "tell me about a time", "describe a time", "tell me about a situation",
    "describe a situation", "give me an example", "have you ever",
    "how did you handle", "share an experience", "tell me about an incident",
    "describe an incident", "when was a time",
]


def question_kind(question_text):
    """
    'story'   -> an experience question, graded as a STAR narrative
    'direct'  -> a factual/opinion question ("are you okay relocating?",
                 "why this company?", "what is your weakness?")
                 graded on a clear answer + a reason, NOT on STAR.

    Without this split, a perfectly good answer to a yes/no HR question gets
    marked down for having no Situation-Task-Action-Result. That was a real
    bug: a strong relocation answer scored 4.8/10 'Weak'.
    """
    q = (question_text or "").lower()
    return "story" if any(c in q for c in STORY_CUES) else "direct"


def score_answer(answer, ideal, tags="", round_name="technical", difficulty=2, question=""):
    answer = (answer or "").strip()
    words = answer.split()
    n = len(words)
    low = answer.lower()

    if n == 0:
        return {
            "overall": 0.0,
            "dimensions": {k: 0.0 for k in WEIGHTS_TECHNICAL},
            "flags": ["empty"],
            "tags": tags,
            "strengths": [],
            "improvements": ["You did not answer. In a real interview, say what you do know and think aloud — silence is scored worse than an imperfect attempt."],
            "band": "No answer",
            "verdict": "No answer recorded.",
        }

    # --- structure (computed first: behavioural coverage depends on it) ---
    star_hits = _count(answer, STAR_MARKERS)
    struct_hits = _count(answer, STRUCTURE_MARKERS)
    behavioural = round_name in ("hr", "behavioral")
    kind = question_kind(question) if question else "story"

    # --- coverage -------------------------------------------------------
    concept = _concept_coverage(answer, ideal)
    lex = _lexical_overlap(answer, ideal)
    fuzz = _fuzzy_overlap(answer, ideal)
    word_coverage = min(10.0, (0.70 * concept + 0.20 * lex + 0.10 * fuzz) * 14.0)
    # A very short answer cannot really cover the concept, however wordy it is.
    if n < 8:
        word_coverage *= 0.5
    # Graceful floor: a substantiated, well-structured answer that simply uses
    # different words than the reference must not be graded as "missing concepts".
    if n >= 30 and struct_hits >= 1 and word_coverage < 4.0:
        word_coverage = 4.0

    if behavioural and kind == "story":
        # Experience questions: matching the reference WORDING is the wrong
        # test. Grade whether it is a complete story: specific incident,
        # your actions, a result.
        numbers_b = 1 if re.search(r"\b\d+", answer) else 0
        result_b = 1 if re.search(
            r"\b(result|outcome|so we|which led|impact|reduced|increased|learned|finally)\b", low
        ) else 0
        ownership = 1 if re.search(r"\bi (decided|built|led|fixed|proposed|owned|took|asked|changed)\b", low) else 0
        story = min(10.0, 2.5 + 1.3 * min(star_hits, 4) + 2.0 * numbers_b + 2.0 * result_b + 1.5 * ownership)
        coverage = round(0.65 * story + 0.35 * word_coverage, 2)
    elif behavioural:
        # Direct HR questions: a clear position + a stated reason + something
        # concrete is a complete answer. No narrative structure required.
        direct = 0
        if re.match(r"^\s*(yes|no|definitely|absolutely|i am|i would|i have|i do|i will|i prefer|i believe)", low):
            direct = 1
        elif re.search(r"\b(yes|no|comfortable|willing|open to|ready to|i am not)\b", low):
            direct = 1
        reason = 1 if re.search(REASON_RE, answer, re.IGNORECASE) else 0
        concrete = 1 if re.search(NUMBER_RE, answer, re.IGNORECASE) else 0
        filler_only = 1 if n < 12 else 0
        pos = min(10.0, 2.0 + 2.6 * direct + 2.4 * reason + 2.4 * concrete - 2.0 * filler_only)
        # For HR questions the reference is *guidance*, not content to match,
        # so lexical overlap barely counts. Position + reason + concreteness is
        # the real signal.
        coverage = round(0.86 * pos + 0.14 * word_coverage, 2)
    else:
        coverage = word_coverage
    if behavioural and kind == "story":
        structure = min(10.0, 3.0 + 1.6 * star_hits + 1.1 * struct_hits)
    elif behavioural:
        # Direct answers are short by nature; reward signposting and a reason,
        # not a missing narrative arc.
        structure = min(10.0, 6.0 + 1.1 * struct_hits + 1.0 * star_hits)
    else:
        # Technical: a plain but correct answer starts at a fair baseline.
        # Explicit signposting and stating complexity/trade-offs earn more.
        tradeoff = 1 if re.search(r"\b(trade-?off|however|but |whereas|O\(|complexity|downside)\b", low) else 0
        structure = min(10.0, 5.0 + 1.4 * struct_hits + 1.2 * star_hits + 1.0 * tradeoff)

    # --- specificity ----------------------------------------------------
    numbers = len(re.findall(r"\b\d+(?:\.\d+)?\b", answer))
    tech = sum(1 for t in TECH_TERMS if t in low)
    examples = 1 if re.search(r"\b(for example|e\.g\.|such as|instance|say)\b", low) else 0
    specificity = min(10.0, 2.0 + 1.5 * numbers + 1.0 * min(tech, 4) + 2.0 * examples)

    # --- depth ----------------------------------------------------------
    if behavioural and kind == "story":
        ideal_len, span = 70, 130        # STAR stories need length
    elif behavioural:
        ideal_len, span = 45, 90         # direct answers should be crisp
    else:
        ideal_len, span = 55, 110
    depth = 10.0 - min(8.0, abs(n - ideal_len) / span * 6.0)
    depth = max(2.0, depth)

    # --- confidence -----------------------------------------------------
    hedges = _count(answer, HEDGES)
    fillers = _count(answer, FILLERS)
    confidence = max(1.0, 10.0 - 2.2 * hedges - 1.2 * fillers)

    dims = {
        "coverage": round(coverage, 1),
        "structure": round(structure, 1),
        "specificity": round(specificity, 1),
        "depth": round(depth, 1),
        "confidence": round(confidence, 1),
    }
    weights = WEIGHTS_BEHAVIOURAL if behavioural else WEIGHTS_TECHNICAL
    overall = sum(dims[k] * w for k, w in weights.items())
    if difficulty >= 4:
        overall *= 0.95   # slightly tougher grading on hard questions
    overall = round(max(0.0, min(10.0, overall)), 1)

    # --- human-readable narrative --------------------------------------
    strengths, improvements = [], []

    if behavioural and kind == "direct":
        if dims["coverage"] >= 7:
            strengths.append("Clear position, a reason, and something concrete — exactly what this round scores.")
        else:
            improvements.append("Answer in three beats: your position ('Yes, I am'), your reason, and one concrete detail from your life.")
    else:
        if dims["coverage"] >= 7:
            strengths.append("You hit most of the concepts the interviewer was listening for.")
        elif dims["coverage"] <= 4:
            improvements.append("Key concepts were missing. Say the definition first, then one concrete example.")
        else:
            improvements.append("You touched the right idea but left out part of it — being complete is what separates a 6 from an 8.")

    if behavioural and kind == "story":
        if star_hits >= 3:
            strengths.append("Your answer had a clear Situation-Action-Result flow.")
        else:
            improvements.append("Use STAR explicitly: Situation (1 line), Task, the Actions *you* took, then the Result with a number.")
    elif behavioural:
        has_reason = re.search(REASON_RE, answer, re.IGNORECASE)
        if not has_reason:
            improvements.append("Give your answer, then a reason. 'Yes, and here is why' is what makes it credible.")
        elif dims["specificity"] < 6:
            improvements.append("Back the reason with something concrete — a number, a city, a past experience.")
        else:
            strengths.append("Clear position with a reason — exactly what an HR round scores.")
    else:
        if dims["structure"] >= 7:
            strengths.append("Logical, easy-to-follow progression.")
        else:
            improvements.append("Structure the answer: definition, then how it works, then an example, then the trade-off.")

    if dims["specificity"] >= 7:
        strengths.append("Concrete details and technical vocabulary — interviewers can tell you have used this.")
    else:
        improvements.append("Add specifics: a number, a real example, or the exact term the interviewer expects.")

    if n < 25:
        improvements.append("Too short. Aim for 30-60 seconds; a one-line answer reads as unprepared.")
    if n > 260:
        improvements.append("Too long — you will lose the interviewer. Cut to the core and offer detail if asked.")

    if hedges >= 2:
        improvements.append("You hedged several times ('maybe', 'I think'). State your answer, then qualify it if needed.")

    if not strengths:
        strengths.append("You engaged with the question — that is the right instinct to build on.")

    band, verdict = _band(overall)

    return {
        "overall": overall,
        "dimensions": dims,
        "flags": _flags(dims, n, hedges),
        "tags": tags,
        "strengths": strengths[:3],
        "improvements": improvements[:3],
        "band": band,
        "verdict": verdict,
        "word_count": n,
    }


def _band(score):
    if score >= 8.5:
        return "Strong hire signal", "This would land well in a real interview."
    if score >= 7.0:
        return "Good", "Solid answer. A little more structure would make it memorable."
    if score >= 5.5:
        return "Borderline", "The idea is there but the delivery needs work."
    if score >= 3.5:
        return "Weak", "The interviewer would likely move on. Revisit the fundamentals here."
    return "Needs work", "This needs rebuilding before you take a real interview."


def _flags(dims, n, hedges):
    flags = []
    if dims["coverage"] <= 4:
        flags.append("missing_concepts")
    if n < 25:
        flags.append("too_short")
    if n > 260:
        flags.append("rambling")
    if hedges >= 2:
        flags.append("hedging")
    if dims["specificity"] <= 4:
        flags.append("no_specifics")
    if dims["structure"] <= 4:
        flags.append("no_structure")
    return flags


def _dedupe(rows, max_per_score=1):
    """
    Sibling tags (oop / fundamentals / java / abstraction) all come from the
    same question and carry the same score, so listing all four is noise.
    Keep at most one tag per distinct score.
    """
    seen, out = {}, []
    for r in rows:
        key = round(r["score"], 1)
        if seen.get(key, 0) >= max_per_score:
            continue
        seen[key] = seen.get(key, 0) + 1
        out.append(r)
    return out


def summarise_session(turns):
    """Roll individual turns into a session report."""
    if not turns:
        return {"overall": 0.0, "dimensions": {}, "band": "No answers", "turns": 0}

    dims = {}
    for k in WEIGHTS_TECHNICAL:
        vals = [t["score"]["dimensions"].get(k, 0.0) for t in turns]
        dims[k] = round(sum(vals) / len(vals), 1)

    overall = round(sum(t["score"]["overall"] for t in turns) / len(turns), 1)
    band, verdict = _band(overall)

    weakest = min(dims.items(), key=lambda kv: kv[1])
    strongest = max(dims.items(), key=lambda kv: kv[1])

    tag_totals = {}
    for t in turns:
        for tag in [x for x in (t["score"].get("tags") or "").split(",") if x]:
            tag_totals.setdefault(tag, []).append(t["score"]["overall"])
    tag_avgs = sorted(
        ({t: round(sum(v) / len(v), 1) for t, v in tag_totals.items()}).items(),
        key=lambda kv: kv[1],
    )

    return {
        "overall": overall,
        "band": band,
        "verdict": verdict,
        "turns": len(turns),
        "dimensions": dims,
        "strongest_dimension": strongest[0],
        "weakest_dimension": weakest[0],
        "weak_topics": _dedupe([{"topic": t, "score": sc} for t, sc in tag_avgs if sc < 6.5])[:3],
        "strong_topics": _dedupe([{"topic": t, "score": sc} for t, sc in tag_avgs[::-1] if sc >= 7.0])[:3],
        "per_turn": [
            {
                "seq": t["seq"],
                "question": t["question"],
                "answer": t["answer"],
                "overall": t["score"]["overall"],
                "verdict": t["score"].get("verdict", ""),
                "improvements": t["score"].get("improvements", []),
            }
            for t in turns
        ],
        "next_actions": _next_actions(dims, tag_avgs),
    }


def _next_actions(dims, tag_avgs):
    actions = []
    wd = min(dims.items(), key=lambda kv: kv[1])[0] if dims else None
    tips = {
        "coverage": "Build a one-page cheat sheet per topic: definition, mechanism, example, trade-off. Cover all four in every answer.",
        "structure": "Answer with a fixed template: what it is, how it works, an example, the trade-off. Rehearse it 5 times.",
        "specificity": "Attach a number or a named example to every claim. 'Improved latency from 800ms to 200ms' beats 'it was faster'.",
        "depth": "Time yourself: 45-75 seconds for technical, 90-120 seconds for behavioural. Cut anything that is not evidence.",
        "confidence": "Remove 'maybe', 'I think', 'sort of'. Say the answer, then add a condition if you must.",
    }
    if wd in tips:
        actions.append(tips[wd])
    seen_scores = set()
    for tag, sc in tag_avgs:
        if sc >= 6.5 or round(sc, 1) in seen_scores:
            continue
        if sum(1 for a in actions if "Weak area" in a) >= 2:
            break
        seen_scores.add(round(sc, 1))
        actions.append(f"Weak area '{tag}' scored {sc}/10 — do 3 short written answers on it before your next mock.")
    if not actions:
        actions.append("Good baseline. Next session, attempt the same company at a harder difficulty.")
    return actions[:4]

```

---

<!-- FILE: app/feedback.py -->

<sub>16644 bytes</sub>

```python
"""
feedback.py — THE DIFFERENTIATOR of this project.

Two learning loops live here:

  LOOP 1 (community -> bot)
    Past students write reviews ("they drilled SQL joins for 20 minutes").
    We mine those reviews into a *company profile*: which topics are hot,
    how hard the round really feels, and what advice repeats.
    The question selector uses that profile to re-weight the question bank,
    so the bot asks what that company ACTUALLY asks — not what a generic
    syllabus says.

  LOOP 2 (student -> bot)
    Every answer is scored. Weak tags are tracked per student, so the next
    session for that student leans into their weak areas, and the report
    tells them exactly what to fix.

Nothing here is hard-coded to a company: add reviews and the behaviour shifts.
"""

import math
import re
from collections import Counter
from datetime import datetime, timezone

from . import db

# Words that carry no topical signal.
STOPWORDS = set(
    """a an the and or but if then than that this those these i me my we our you your
    he she it they them was were is are am be been being do does did doing have has had
    having will would should could can may might must not no nor so very too also just
    about after again all any as at before both by during each few for from further how
    into more most other out over same some such through to under until up what when where
    which while who whom why with would asked ask asking question questions interview
    interviewer panel round told tell said say says like really pretty totally got get
    went go came come one two three four five minute minutes time day days make made
    them there their they're we're i'm don't didn't it's he's she's very much lot lots
    know knew think thought want wanted need needed give gave take took""".split()
)

# Mapping of common review phrasings -> canonical topic tags.
# This is the "dictionary" version of what an LLM would infer.
TOPIC_SYNONYMS = {
    "sql": ["sql", "query", "queries", "join", "joins", "select", "database query"],
    "dbms": ["dbms", "database", "normalization", "normalisation", "normal form", "3nf", "2nf", "acid"],
    "joins": ["join", "joins", "left join", "inner join"],
    "index": ["index", "indexing", "indexes", "b-tree", "btree"],
    "oop": ["oop", "oops", "object oriented", "class", "inheritance", "polymorphism"],
    "overloading": ["overloading", "overload", "overriding", "override"],
    "abstract": ["abstract class", "interface"],
    "dsa": ["dsa", "algorithm", "algorithms", "coding", "code", "problem solving", "leetcode"],
    "arrays": ["array", "arrays", "subarray", "sliding window"],
    "strings": ["string", "strings", "palindrome", "anagram", "reverse a string"],
    "linked-list": ["linked list", "linkedlist", "pointer manipulation"],
    "trees": ["tree", "binary tree", "bst", "traversal", "level order"],
    "heaps": ["heap", "heaps", "median", "priority queue"],
    "hashing": ["hash", "hashing", "hashmap", "hash map", "dictionary"],
    "recursion": ["recursion", "recursive", "backtracking"],
    "binary-search": ["binary search", "searching"],
    "dp": ["dynamic programming", "dp", "kadane", "memoization"],
    "system-design": ["system design", "design a", "hld", "lld", "scalability", "scaling"],
    "caching": ["cache", "caching", "redis", "cdn"],
    "concurrency": ["concurrency", "concurrent", "thread", "threads", "lock", "locking", "race condition"],
    "os": ["os", "operating system", "process", "thread", "deadlock", "memory management", "stack vs heap"],
    "networking": ["networking", "network", "tcp", "udp", "dns", "http", "url", "tls"],
    "api": ["api", "rest", "endpoint", "idempotency", "idempotent", "microservice"],
    "java": ["java", "jvm", "jre", "equals", "string pool"],
    "python": ["python", "tuple", "list comprehension", "pandas"],
    "c": ["c language", "c programming", "struct", "union", "malloc", "pointer arithmetic"],
    "pointers": ["pointer", "pointers", "pointer arithmetic"],
    "project": ["project", "projects", "final year project", "capstone", "resume project"],
    "resume": ["resume", "cv", "resume walkthrough"],
    "internship": ["internship", "intern", "training"],
    "intro": ["tell me about yourself", "introduce yourself", "introduction", "about yourself"],
    "why-company": ["why tcs", "why infosys", "why wipro", "why our company", "why do you want to join"],
    "relocation": ["relocate", "relocation", "any location", "another city", "shift", "rotational", "night shift"],
    "bond": ["bond", "service agreement", "service bond", "contract"],
    "salary": ["salary", "ctc", "package", "compensation"],
    "star": ["star", "situation task action result", "situation", "situation-based", "situational"],
    "behavioral": ["behavioural", "behavioral", "situational", "scenario", "hypothetical"],
    "conflict": ["conflict", "disagree", "disagreement", "argument", "teammate", "team member"],
    "teamwork": ["teamwork", "team", "group", "collaboration"],
    "leadership-principle": ["leadership principle", "leadership principles", "lp", "ownership", "customer obsession"],
    "ownership": ["ownership", "own the", "responsibility", "not my job"],
    "deadline": ["deadline", "tight deadline", "delay", "delayed", "miss the deadline", "pressure"],
    "failure": ["fail", "failure", "failed", "mistake", "went wrong"],
    "self-awareness": ["weakness", "strength", "improve", "feedback", "rejected", "not selected"],
    "career": ["five years", "5 years", "career", "future", "growth", "promotion"],
    "communication": ["communication", "english", "speak", "speaking", "confidence", "confident", "fluency"],
    "pseudo-code": ["pseudo code", "pseudocode", "pseudo-code", "dry run", "trace"],
    "aptitude": ["aptitude", "quantitative", "reasoning", "logical", "puzzle"],
    "complexity": ["complexity", "time complexity", "space complexity", "big o", "o(n)"],
    "edge-cases": ["edge case", "edge cases", "corner case"],
    "core": ["core java", "fundamentals", "basics", "theory"],
}

# Advice-ish phrases worth surfacing verbatim in the bot's hints.
ADVICE_MARKERS = [
    "my advice", "advice", "prepare", "revise", "be ready", "keep ready",
    "important", "make sure", "do mention", "do not", "don't", "always",
    "must", "remember", "practice", "focus on",
]


def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9+#\-']+", text.lower()) if t not in STOPWORDS]


def extract_topics(text):
    """Map free-text review language onto canonical topic tags."""
    low = " " + text.lower() + " "
    found = set()
    for tag, phrases in TOPIC_SYNONYMS.items():
        for p in phrases:
            if re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", low):
                found.add(tag)
                break
    return found


def _recency_weight(created_at, half_life_days=90):
    """Newer reviews matter more. Exponential decay with a 90-day half-life."""
    try:
        ts = datetime.fromisoformat(created_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - ts).total_seconds() / 86400)
    except Exception:
        age_days = 0.0
    return math.pow(0.5, age_days / half_life_days)


# --------------------------------------------------------------- LOOP 1

def company_profile(company, round_name=None):
    """
    Mine reviews into an actionable profile.

    Returns hot topics ranked by recency-weighted mention count, the real
    felt difficulty, repeated advice lines, and coverage gaps (topics students
    mention that our current question bank does not cover).
    """
    reviews = db.reviews_for(company=company, round_name=round_name, limit=500)
    blended = False
    # Cold-start guard: 1-2 reviews for a specific round is not a signal, it is
    # noise. Fall back to all of that company's reviews, down-weighted.
    if round_name and len(reviews) < 3:
        company_wide = db.reviews_for(company=company, limit=500)
        if len(company_wide) > len(reviews):
            reviews = company_wide
            blended = True

    topic_score = Counter()
    topic_examples = {}
    advice = Counter()
    diffs, ratings = [], []

    for r in reviews:
        w = _recency_weight(r["created_at"])
        diffs.append((r["difficulty_felt"], w))
        ratings.append((r["rating"], w))
        for tag in extract_topics(r["text"]):
            topic_score[tag] += w
            topic_examples.setdefault(tag, r["text"])

        for sentence in re.split(r"(?<=[.!?])\s+", r["text"]):
            s = sentence.strip()
            if len(s) < 15:
                continue
            low = s.lower()
            if any(m in low for m in ADVICE_MARKERS):
                advice[s] += 1

    total_w = sum(w for _, w in diffs) or 1.0
    felt = round(sum(d * w for d, w in diffs) / total_w, 2) if diffs else None
    rating = round(sum(v * w for v, w in ratings) / total_w, 2) if ratings else None

    ranked = [
        {"topic": t, "mentions": round(s, 2)}
        for t, s in topic_score.most_common(12)
    ]

    # Coverage gaps: hot topics the bank has no question for.
    if round_name:
        bank_subset = db.company_questions_only(company, round_name)
    else:
        bank_subset = [q for q in db.all_questions() if q["company"] == company]
    covered = set()
    for q in bank_subset:
        covered.update(t for t in q["tags"].split(",") if t)
    gaps = [t for t in ranked if t["topic"] not in covered][:5]

    return {
        "company": company,
        "round": round_name,
        "review_count": len(reviews),
        "blended_company_wide": blended,
        "avg_difficulty_felt": felt,
        "avg_rating": rating,
        "hot_topics": ranked,
        "advice": [a for a, _ in advice.most_common(5)],
        "coverage_gaps": [g["topic"] for g in gaps],
        "sample_quotes": [r["text"] for r in reviews[:3]],
    }


def topic_weights(company, round_name=None):
    """Normalised 0..1 weight per topic, for biasing question selection."""
    prof = company_profile(company, round_name)
    if not prof["hot_topics"]:
        return {}
    top = prof["hot_topics"][0]["mentions"] or 1.0
    return {h["topic"]: h["mentions"] / top for h in prof["hot_topics"]}


# --------------------------------------------------------------- LOOP 2

def student_weak_tags(student_name, last_n=5):
    """Average score per tag across the student's recent sessions."""
    sessions = db.student_history(student_name, limit=last_n)
    tag_scores = {}
    tag_counts = Counter()
    for s in sessions:
        for turn in db.turns_for(s["id"]):
            tags = (turn["score"].get("tags") or "")
            score = turn["score"].get("overall", 0)
            for t in [x for x in tags.split(",") if x]:
                tag_scores[t] = tag_scores.get(t, 0.0) + score
                tag_counts[t] += 1
    return {
        t: round(tag_scores[t] / tag_counts[t], 2)
        for t in tag_scores
        if tag_counts[t] > 0
    }


def rank_questions(questions, company, round_name, target_difficulty=2.5,
                   weak_tags=None, asked_ids=(), rng=None):
    """
    Score and order the candidate questions.

    score = 0.45 * review_topic_match      <- LOOP 1
          + 0.25 * weak_area_match         <- LOOP 2
          + 0.20 * difficulty_fit
          + 0.10 * freshness (less-asked questions first)
    """
    tw = topic_weights(company, round_name)
    weak = weak_tags or {}

    ranked = []
    for q in questions:
        if q["id"] in asked_ids:
            continue
        tags = [t for t in q["tags"].split(",") if t]

        review_match = max([tw.get(t, 0.0) for t in tags], default=0.0)
        weak_match = 0.0
        if weak:
            lows = [max(0.0, (6.0 - weak[t]) / 6.0) for t in tags if t in weak]
            weak_match = max(lows, default=0.0)

        diff_fit = max(0.0, 1.0 - abs(q["difficulty"] - target_difficulty) / 3.0)
        freshness = 1.0 / (1.0 + q["times_asked"])

        score = (
            0.45 * review_match
            + 0.25 * weak_match
            + 0.20 * diff_fit
            + 0.10 * freshness
        )
        ranked.append((score, q, {
            "review_match": round(review_match, 2),
            "weak_area_match": round(weak_match, 2),
            "difficulty_fit": round(diff_fit, 2),
            "freshness": round(freshness, 2),
        }))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked


def next_target_difficulty(history_scores, start=2.5):
    """
    Adaptive difficulty: do well -> go harder; struggle -> consolidate.
    This is the mini 'item response theory' loop every good assessment tool has.
    """
    if not history_scores:
        return start
    recent = history_scores[-2:]
    avg = sum(recent) / len(recent)
    if avg >= 7.5:
        return min(5.0, start + 1.0)
    if avg >= 5.5:
        return start
    return max(1.0, start - 0.75)


def focus_plan(student_name, company=None):
    """Turn weak tags into a concrete study plan shown in the report."""
    weak = student_weak_tags(student_name)
    if not weak:
        return []
    ordered = sorted(weak.items(), key=lambda kv: kv[1])
    plan, seen_scores = [], set()
    for tag, sc in ordered:
        if sc >= 6.5 or round(sc, 1) in seen_scores:
            continue
        seen_scores.add(round(sc, 1))
        if len(plan) >= 3:
            break
        hint = TOPIC_HINTS.get(tag, "Revise the fundamentals and practise explaining this aloud in two minutes.")
        plan.append({"topic": tag, "avg_score": sc, "why": hint})
    return plan


TOPIC_HINTS = {
    "sql": "Write 10 queries by hand: joins, GROUP BY with HAVING, subqueries, window functions. Say the query aloud as you write it.",
    "dbms": "Be able to draw 1NF -> 2NF -> 3NF on a whiteboard with a concrete table and name the anomaly each form removes.",
    "joins": "Practise the LEFT JOIN 'find rows with no match' pattern — it is the most commonly asked follow-up.",
    "index": "Explain the B-tree lookup and then immediately state the write cost and low-cardinality caveat.",
    "oop": "Prepare one running example (e.g. Payment/PaymentMethod) and explain all four pillars through it.",
    "dsa": "Solve 3 problems a day out loud. Always state brute force, then optimise, then complexity.",
    "complexity": "For every answer, end with 'time is O(...) because ..., space is O(...) because ...'.",
    "system-design": "Use a fixed skeleton: requirements -> scale estimate -> API -> data model -> components -> bottlenecks.",
    "concurrency": "Learn lock ordering, atomic operations and optimistic vs pessimistic concurrency with one example each.",
    "os": "Revise process vs thread, deadlock's four conditions, and stack vs heap with diagrams.",
    "networking": "Trace a URL request end to end until you can do it in 60 seconds without notes.",
    "project": "Rehearse a 90-second project pitch: problem, your exact modules, hardest bug, measurable result.",
    "relocation": "Decide your honest answer now and say it in one confident sentence. Hesitation is what gets marked down.",
    "bond": "Know your stance on the service agreement and state it without hedging.",
    "star": "Write 5 STAR stories (conflict, failure, leadership, deadline, learning) with numbers, and reuse them.",
    "behavioral": "Prepare stories, not adjectives. Every claim needs a specific incident behind it.",
    "communication": "Record yourself answering 'tell me about yourself' and cut every filler word.",
    "self-awareness": "Have a real weakness with the concrete action you took and the evidence it improved.",
    "pseudo-code": "Practise dry-running loops on paper with a variable table — write each iteration down.",
    "core": "Revise definitions until you can give a one-line answer plus a one-line example.",
}


def aggregate_insights():
    """Dashboard numbers for the home page."""
    conn = db.connect()
    q = conn.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"]
    r = conn.execute("SELECT COUNT(*) c FROM reviews").fetchone()["c"]
    s = conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
    t = conn.execute("SELECT COUNT(*) c FROM turns").fetchone()["c"]
    conn.close()
    return {
        "questions": q,
        "reviews": r,
        "sessions": s,
        "answers_scored": t,
        "learning_loops": [
            "reviews -> hot-topic weighting",
            "answers -> per-student weak-area focus",
            "answers -> adaptive difficulty",
        ],
    }

```

---

<!-- FILE: app/llm.py -->

<sub>9153 bytes</sub>

```python
"""
llm.py — the pluggable brain.

The app works with ZERO API keys (offline mode). That matters: you can demo
this in a college lab with no internet and no billing.

Set one env var to switch on a real LLM:
    export OPENAI_API_KEY=sk-...          # OpenAI, Groq, Together, OpenRouter...
    export LLM_BASE_URL=https://api.openai.com/v1   # optional, any OpenAI-compatible
    export LLM_MODEL=gpt-4o-mini                    # optional

Then the SAME functions below start returning richer, generative feedback,
follow-up questions and evaluations. Nothing else in the codebase changes —
that is the whole point of putting it behind one seam.

Interview-question *content* stays curated in data/questions.json on purpose:
you never want a hallucinated SQL question in an interview.
"""

import json
import os
import urllib.request

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or ""


def is_enabled():
    return bool(API_KEY)


def status():
    return {
        "mode": "llm" if is_enabled() else "offline",
        "model": MODEL if is_enabled() else "rule-based rubric engine",
        "note": (
            "Add OPENAI_API_KEY to enable generative follow-ups and richer feedback."
            if not is_enabled()
            else "LLM enabled. Scores are still rubric-anchored for consistency."
        ),
    }


def _chat(messages, temperature=0.5, max_tokens=500, timeout=40):
    """Minimal OpenAI-compatible chat call using only the stdlib."""
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"].strip()


# ------------------------------------------------------------------ prompts

INTERVIEWER_SYSTEM = """You are a senior technical interviewer at {company} conducting a real
{round_name} round for a fresher candidate. You are professional, warm but efficient.
Rules:
- Ask ONE question at a time. Never list multiple questions.
- Keep your turn under 45 spoken words. This is spoken aloud, so no markdown, no bullets, no emoji.
- You may give at most one short follow-up probe on the previous answer before moving on.
- Do not reveal the model answer. Do not coach the candidate mid-interview.
- Stay in character as an interviewer, not a chatbot."""

FEEDBACK_SYSTEM = """You are an interview coach. You are given a question, the candidate's
answer, the reference answer, and a deterministic rubric score. Write feedback that is
specific, kind and actionable. Cite the candidate's own words. Do not inflate: if the
rubric score is low, say so plainly. Max 90 words. Return plain text, no markdown."""


# --------------------------------------------------------------- behaviours

ROUND_LABELS = {
    "aptitude": "aptitude",
    "technical": "technical",
    "hr": "HR",
    "behavioral": "behavioural",
    "dsa": "DSA",
    "system_design": "system design",
}


def round_label(round_name):
    """A round name you would actually say out loud ('dsa' -> 'DSA')."""
    key = str(round_name or "").strip().lower()
    return ROUND_LABELS.get(key, key.replace("_", " "))


def interviewer_intro(company, round_name, student_name, n_questions):
    spoken_round = round_label(round_name)
    """Opening line of the interview (the first question is sent separately)."""
    if is_enabled():
        try:
            return _chat(
                [
                    {"role": "system", "content": INTERVIEWER_SYSTEM.format(
                        company=company, round_name=spoken_round)},
                    {"role": "user", "content": (
                        f"Greet {student_name} in one sentence, say this is a {spoken_round} "
                        f"round for {company}, mention there are {n_questions} questions, and "
                        f"ask them to think aloud. Do not ask a question yet. Max 40 words."
                    )},
                ],
                temperature=0.6,
                max_tokens=120,
            )
        except Exception:
            pass
    return (
        f"Hi {student_name}, thanks for joining. I will be running your {spoken_round} round "
        f"for {company} today — {n_questions} questions, and I would like you to think aloud. "
        f"Take your time and answer in your own words."
    )


def feedback_narrative(question, answer, ideal, rubric, round_name):
    """Richer coaching text; falls back to the rubric wording."""
    if is_enabled():
        try:
            return _chat(
                [
                    {"role": "system", "content": FEEDBACK_SYSTEM},
                    {"role": "user", "content": (
                        f"Round: {round_name}\nQuestion: {question}\n"
                        f"Candidate answer: {answer}\nReference answer: {ideal}\n"
                        f"Rubric score: {rubric['overall']}/10 "
                        f"(coverage {rubric['dimensions']['coverage']}, "
                        f"structure {rubric['dimensions']['structure']}, "
                        f"specificity {rubric['dimensions']['specificity']})\n"
                        f"Rubric flagged: {', '.join(rubric.get('flags') or ['nothing'])}"
                    )},
                ],
                temperature=0.4,
                max_tokens=220,
            )
        except Exception:
            pass
    return " ".join(rubric["improvements"][:2])


def followup_probe(question, answer, ideal, rubric):
    """One smart follow-up, or None to move on."""
    if rubric["overall"] < 4.5:
        return None   # answer was too weak; a probe would just pile on
    if is_enabled():
        try:
            txt = _chat(
                [
                    {"role": "system", "content": (
                        "You are an interviewer. Given a question, an answer and the reference, "
                        "produce ONE short probing follow-up (max 18 words) that tests depth or an "
                        "edge case. If no probe is warranted reply exactly: NONE")},
                    {"role": "user", "content": f"Q: {question}\nA: {answer}\nRef: {ideal}"},
                ],
                temperature=0.7,
                max_tokens=60,
            )
            if txt.upper().startswith("NONE"):
                return None
            return txt
        except Exception:
            pass

    # Offline probe templates, chosen from the rubric's weakest signal.
    if "no_specifics" in rubric["flags"]:
        return "Can you give me a concrete example where that mattered?"
    if "missing_concepts" in rubric["flags"]:
        return "What is the trade-off of that approach?"
    if rubric["dimensions"]["coverage"] >= 7.5:
        return "How would that change if you had to scale it ten times?"
    return None


def question_hint(question, ideal):
    """A nudge WITHOUT giving away the answer — used by the hint button."""
    if is_enabled():
        try:
            return _chat(
                [
                    {"role": "system", "content": (
                        "Give ONE short hint (max 20 words) that nudges the candidate toward the "
                        "answer without revealing it. Plain text only.")},
                    {"role": "user", "content": f"Question: {question}\nReference: {ideal}"},
                ],
                temperature=0.6,
                max_tokens=60,
            )
        except Exception:
            pass
    first = ideal.split(".")[0]
    return "Start with: " + " ".join(first.split()[:12]) + "... (now complete it in your own words)"


def closing(company, overall_score):
    if is_enabled():
        try:
            return _chat(
                [
                    {"role": "system", "content": (
                        "You are an interviewer closing a fresher mock interview. Two sentences max, "
                        "warm and honest about the score shown. No markdown.")},
                    {"role": "user", "content": f"Company: {company}. Rubric average: {overall_score}/10."},
                ],
                temperature=0.7,
                max_tokens=90,
            )
        except Exception:
            pass
    if overall_score >= 7:
        tail = "That was a confident round — keep this level and work on the small details."
    elif overall_score >= 5:
        tail = "You have the right instincts; structure and specificity are what to fix next."
    else:
        tail = "You are early in preparation, which is fine. Fix the fundamentals topic by topic."
    return f"That is the end of the round. {tail}"

```

---

<!-- FILE: app/engine.py -->

<sub>8884 bytes</sub>

```python
"""
engine.py — interview orchestration.

The engine owns the conversation state machine:

  start -> (ask question -> score answer -> optional probe -> next question)* -> report

It pulls three levers that together make this feel "company specific":
  1. the question pool comes from that company's round (generic filler behind it)
  2. ordering is biased by mined review topics      (feedback.LOOP 1)
  3. target difficulty shifts with the student      (adaptive)
plus the student's historical weak tags               (feedback.LOOP 2)

Design note: the question currently in play is stored on the session (as
`current_qid`) so the server never has to guess what the candidate is
answering. Guessing was the source of a real bug in an earlier draft.
"""

from . import db, feedback, llm, scoring

QUESTIONS_PER_ROUND = {"aptitude": 3, "technical": 4, "dsa": 3,
                       "system_design": 3, "hr": 4, "behavioral": 3}


def start_session(student_name, company, round_name, limit=None):
    limit = limit or QUESTIONS_PER_ROUND.get(round_name, 4)

    pool = db.questions_for(company, round_name)
    if not pool:
        raise ValueError(
            f"No questions for {company} / {round_name}. Try a different round."
        )

    weak = feedback.student_weak_tags(student_name)
    profile = feedback.company_profile(company, round_name)
    target = feedback.next_target_difficulty([], start=2.5)

    ranked = feedback.rank_questions(
        pool, company, round_name,
        target_difficulty=target,
        weak_tags=weak,
        asked_ids=(),
    )
    if not ranked:
        raise ValueError("No eligible questions for this round.")

    first_q, first_why = ranked[0][1], ranked[0][2]
    sid = db.create_session(student_name, company, round_name, total_questions=limit)
    db.set_current_question(sid, first_q["id"])

    intro = llm.interviewer_intro(company, round_name, student_name, limit)

    return {
        "session_id": sid,
        "student_name": student_name,
        "company": company,
        "round": round_name,
        "total_questions": limit,
        "pool_size": len(pool),
        "profile": profile,
        "weak_areas": weak,
        "intro": intro,
        "llm": llm.status(),
        "why_selected": first_why,
        "first": _ask(first_q, 1, limit),
    }


def _ask(q, index, total):
    return {
        "seq": index,
        "of": total,
        "question_id": q["id"],
        "text": q["text"],
        "round": q["round"],
        "difficulty": q["difficulty"],
        "tags": q["tags"],
        "is_generic": q.get("is_generic", False),
        "speak": f"Question {index}. {q['text']}",
    }


def _current_question(session, pool):
    """Fetch the question the candidate is currently answering."""
    by_id = {q["id"]: q for q in pool}
    qid = session.get("current_qid")
    if qid and qid in by_id:
        return by_id[qid]
    if qid:  # question lives in another round's pool — fetch directly
        for cand in db.all_questions():
            if cand["id"] == qid:
                return cand
    return pool[0]


def submit_answer(session_id, answer_text, followup_answer=None):
    """
    Score the answer, record it, and decide what happens next.

    1. Score the answer against the rubric.
    2. If this is a first attempt and the answer deserves a probe, ask ONE
       follow-up (it does not consume a question slot).
    3. Otherwise advance: mark the question done, pick the next question
       adaptively, or finish with the report.
    """
    s = db.get_session(session_id)
    if not s:
        raise ValueError("Session not found")
    if s["finished"]:
        raise ValueError("This session is already finished.")

    pool = db.questions_for(s["company"], s["round"])
    q = _current_question(s, pool)

    turns = db.turns_for(session_id)
    seq = len(turns) + 1
    limit = s["total_questions"] or QUESTIONS_PER_ROUND.get(s["round"], 4)
    is_followup = bool(followup_answer)

    rubric = scoring.score_answer(
        answer_text, q["ideal"], tags=q["tags"],
        round_name=s["round"], difficulty=q["difficulty"],
        question=q["text"],
    )
    rubric["coaching"] = llm.feedback_narrative(
        q["text"], answer_text, q["ideal"], rubric, s["round"]
    )
    rubric["is_followup"] = is_followup

    if is_followup and turns:
        # Attach the probe reply to the SAME question instead of double counting.
        prev = turns[-1]
        prev["score"]["probe_answer"] = answer_text
        prev["score"]["probe_score"] = rubric["overall"]
        prev["score"]["probe_coaching"] = rubric["coaching"]
        db.set_turn_score(prev["id"], prev["score"])
        done = len(turns)
    else:
        probe = llm.followup_probe(q["text"], answer_text, q["ideal"], rubric)
        db.add_turn(session_id, seq, q["id"], q["text"], answer_text, rubric)
        db.record_question_stats(q["id"], rubric["overall"])
        if probe:
            return {
                "type": "probe",
                "seq": seq,
                "of": limit,
                "score": rubric,
                "probe": probe,
                "speak": probe,
            }
        done = seq

    # ---------------------------------------------------------- advance
    if done >= limit:
        return _finish(session_id, s, rubric)

    history = [t["score"]["overall"] for t in db.turns_for(session_id)]
    asked_ids = {t["question_id"] for t in db.turns_for(session_id) if t["question_id"]}
    weak = feedback.student_weak_tags(s["student_name"])
    target = feedback.next_target_difficulty(history)

    ranked = feedback.rank_questions(
        pool, s["company"], s["round"],
        target_difficulty=target,
        weak_tags=weak,
        asked_ids=asked_ids,
    )
    if not ranked:
        return _finish(session_id, s, rubric)

    _, nxt, why = ranked[0]
    db.set_current_question(session_id, nxt["id"])
    return {
        "type": "next",
        "score": rubric,
        "next": _ask(nxt, done + 1, limit),
        "why_selected": why,
        "target_difficulty": round(target, 2),
        "speak": f"Moving on. {nxt['text']}",
    }


def hint(session_id):
    s = db.get_session(session_id)
    if not s:
        raise ValueError("Session not found")
    pool = db.questions_for(s["company"], s["round"])
    q = _current_question(s, pool)
    notes = feedback.company_profile(s["company"], s["round"])["advice"]
    return {
        "hint": llm.question_hint(q["text"], q["ideal"]),
        "peer_advice": notes,
    }


def skip(session_id):
    """Skip the current question without scoring it (tests honesty of the flow)."""
    s = db.get_session(session_id)
    if not s:
        raise ValueError("Session not found")
    pool = db.questions_for(s["company"], s["round"])
    turns = db.turns_for(session_id)
    limit = s["total_questions"] or 4
    if len(turns) + 1 >= limit:
        return _finish(session_id, s, None)
    q = _current_question(s, pool)
    asked_ids = {t["question_id"] for t in db.turns_for(session_id) if t["question_id"]}
    asked_ids.add(q["id"])
    ranked = feedback.rank_questions(
        pool, s["company"], s["round"],
        target_difficulty=feedback.next_target_difficulty([t["score"]["overall"] for t in turns]),
        weak_tags=feedback.student_weak_tags(s["student_name"]),
        asked_ids=asked_ids,
    )
    if not ranked:
        return _finish(session_id, s, None)
    _, nxt, why = ranked[0]
    db.set_current_question(session_id, nxt["id"])
    return {
        "type": "next",
        "skipped": q["text"],
        "next": _ask(nxt, len(turns) + 1, limit),
        "why_selected": why,
        "speak": f"No problem, moving on. {nxt['text']}",
    }


def _finish(session_id, s, last_rubric=None):
    turns = db.turns_for(session_id)
    report = scoring.summarise_session(turns)
    report["student_name"] = s["student_name"]
    report["company"] = s["company"]
    report["round"] = s["round"]
    report["focus_plan"] = feedback.focus_plan(s["student_name"], s["company"])
    report["closing"] = llm.closing(s["company"], report["overall"])
    report["company_profile"] = feedback.company_profile(s["company"], s["round"])
    report["llm"] = llm.status()
    db.update_session(session_id, finished=1, report=report)
    return {
        "type": "report",
        "score": last_rubric,
        "report": report,
        "speak": report["closing"],
    }


def finish_now(session_id):
    s = db.get_session(session_id)
    if not s:
        raise ValueError("Session not found")
    return _finish(session_id, s)


def get_report(session_id):
    import json
    s = db.get_session(session_id)
    if not s:
        raise ValueError("Session not found")
    if s["report_json"]:
        return json.loads(s["report_json"])
    return scoring.summarise_session(db.turns_for(session_id))

```

---

<!-- FILE: app/main.py -->

<sub>6489 bytes</sub>

```python
"""
main.py — FastAPI server.

Run:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Every endpoint is listed in /docs (FastAPI gives you a free interactive API
explorer). That is also how you will wire a React frontend later.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, engine, feedback, llm, scoring

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Mock Interview Bot",
    description="Company-specific mock interviews that learn from past student reviews.",
    version="1.0.0",
)


@app.on_event("startup")
def _startup():
    # init_db() is idempotent (CREATE TABLE IF NOT EXISTS) and re-seeds when the
    # bank is empty, so it also self-heals a missing or truncated database file.
    db.init_db()
    if not db.is_initialized():
        print("WARNING: database schema missing after init_db()")


# ------------------------------------------------------------------ schemas

class StartRequest(BaseModel):
    student_name: str = Field(..., min_length=1, max_length=60)
    company: str
    round: str
    limit: int | None = Field(default=None, ge=1, le=10)


class AnswerRequest(BaseModel):
    answer: str = ""
    followup_answer: str | None = None


class ReviewRequest(BaseModel):
    student_name: str = Field(..., min_length=1, max_length=60)
    company: str
    round: str
    difficulty_felt: int = Field(..., ge=1, le=5)
    rating: int = Field(..., ge=1, le=5)
    text: str = Field(..., min_length=10, max_length=2000)


# -------------------------------------------------------------------- pages

@app.get("/", include_in_schema=False)
def index():
    """Voice-first experience is the default. Text chat lives at /text."""
    response = FileResponse(STATIC_DIR / "voice.html")
    response.headers["Permissions-Policy"] = "microphone=(self)"
    return response


@app.get("/text", include_in_schema=False)
def text_mode():
    """The original text-chat interface, kept as an accessible fallback."""
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------------- api

@app.get("/api/health")
def health():
    """
    Health check that reports a broken database instead of raising a 500.

    A 500 from /api/health is indistinguishable from "server is down", which
    makes debugging much harder than it needs to be.
    """
    if not db.is_initialized():
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "reason": "database not initialised",
                "fix": "stop the server, delete mockinterview.db, run `python -m app.db`, restart",
                "llm": llm.status(),
            },
        )
    return {"ok": True, "llm": llm.status(), "insights": feedback.aggregate_insights()}


@app.get("/api/companies")
def companies():
    return {"companies": db.get_companies()}


@app.get("/api/companies/{company}/profile")
def company_profile(company: str, round: str | None = None):
    prof = feedback.company_profile(company, round)
    prof["reviews"] = db.reviews_for(company=company, round_name=round, limit=20)
    return prof


@app.get("/api/questions")
def questions(company: str | None = None, round: str | None = None):
    if company and round:
        return {"questions": db.questions_for(company, round)}
    rows = db.all_questions()
    if company:
        rows = [r for r in rows if r["company"] == company]
    if round:
        rows = [r for r in rows if r["round"] == round]
    return {"questions": rows}


@app.post("/api/sessions")
def start_session(req: StartRequest):
    try:
        return engine.start_session(req.student_name, req.company, req.round, req.limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/{session_id}/answer")
def answer(session_id: int, req: AnswerRequest):
    try:
        return engine.submit_answer(
            session_id, req.answer, followup_answer=req.followup_answer
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/{session_id}/hint")
def hint(session_id: int):
    try:
        return engine.hint(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/{session_id}/skip")
def skip(session_id: int):
    try:
        return engine.skip(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/{session_id}/finish")
def finish(session_id: int):
    try:
        return engine.finish_now(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/sessions/{session_id}/report")
def report(session_id: int):
    try:
        return engine.get_report(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/students/{student_name}/history")
def history(student_name: str):
    sessions = db.student_history(student_name)
    return {
        "sessions": sessions,
        "weak_areas": feedback.student_weak_tags(student_name),
        "focus_plan": feedback.focus_plan(student_name),
    }


@app.get("/api/reviews")
def reviews(company: str | None = None, round: str | None = None):
    return {"reviews": db.reviews_for(company=company, round_name=round)}


@app.post("/api/reviews")
def create_review(req: ReviewRequest):
    rid = db.add_review(
        req.student_name, req.company, req.round,
        req.difficulty_felt, req.rating, req.text,
    )
    # The loop closes here: the new review immediately changes the
    # company profile and therefore future question selection.
    return {
        "id": rid,
        "profile_after": feedback.company_profile(req.company, req.round),
        "message": "Thanks! This review now influences future mock interviews.",
    }


@app.get("/api/insights")
def insights():
    return feedback.aggregate_insights()


@app.exception_handler(404)
def _nf(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Not found"})


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

```

---

<!-- FILE: data/questions.json -->

<sub>36429 bytes</sub>

```json
{
  "companies": [
    {
      "name": "TCS",
      "type": "service",
      "about": "Mass hiring via TCS NQT. Expect aptitude + technical + HR. Interviewers are usually friendly, focus on basics and willingness to relocate / work in any shift.",
      "rounds": [
        "aptitude",
        "technical",
        "hr"
      ]
    },
    {
      "name": "Infosys",
      "type": "service",
      "about": "Infosys online test + technical + HR. Heavy emphasis on projects, DBMS and OOP. Certification questions (Infosys Springboard) come up often.",
      "rounds": [
        "aptitude",
        "technical",
        "hr"
      ]
    },
    {
      "name": "Wipro",
      "type": "service",
      "about": "Wipro Elite NTH. Aptitude + coding (2 questions) + technical + HR. Panel often checks communication and bond/relocation comfort.",
      "rounds": [
        "aptitude",
        "technical",
        "hr"
      ]
    },
    {
      "name": "Cognizant",
      "type": "service",
      "about": "GenC / GenC Elevate. Aptitude + coding + technical + HR. Interviewers probe SQL joins and one language deeply.",
      "rounds": [
        "aptitude",
        "technical",
        "hr"
      ]
    },
    {
      "name": "Accenture",
      "type": "service",
      "about": "Cognitive + technical assessment, then a combined technical-cum-HR round. Behavioural questions (situation based) carry a lot of weight.",
      "rounds": [
        "aptitude",
        "technical",
        "hr",
        "behavioral"
      ]
    },
    {
      "name": "Capgemini",
      "type": "service",
      "about": "Pseudo code + English communication test, then technical + HR. Pseudo-code reading is a distinct section.",
      "rounds": [
        "aptitude",
        "technical",
        "hr"
      ]
    },
    {
      "name": "Amazon",
      "type": "product",
      "about": "Online assessment (2 DSA) + 3-4 technical loops. Every round has 2 Leadership Principle questions. Expect deep follow-ups on trade-offs and complexity.",
      "rounds": [
        "dsa",
        "system_design",
        "behavioral",
        "technical"
      ]
    },
    {
      "name": "Google",
      "type": "product",
      "about": "Phone screen + 4-5 onsite rounds. Pure problem solving and coding on a shared doc, plus Googleyness. No trivia - they want optimal complexity.",
      "rounds": [
        "dsa",
        "system_design",
        "behavioral"
      ]
    },
    {
      "name": "Microsoft",
      "type": "product",
      "about": "Codility test then 3-4 rounds. Mix of DSA, CS fundamentals (OS/DBMS) and behavioural. Strong focus on clarifying questions first.",
      "rounds": [
        "dsa",
        "technical",
        "system_design",
        "behavioral"
      ]
    },
    {
      "name": "Flipkart",
      "type": "product",
      "about": "Machine coding + DSA + design + hiring manager. Machine coding round (working code in 90 min) is the filter.",
      "rounds": [
        "dsa",
        "system_design",
        "behavioral",
        "technical"
      ]
    },
    {
      "name": "Zoho",
      "type": "product",
      "about": "Written aptitude + C/C++ coding on paper, then multiple technical rounds. Very fundamentals-heavy, low tolerance for vague answers.",
      "rounds": [
        "aptitude",
        "technical",
        "dsa",
        "hr"
      ]
    },
    {
      "name": "Generic Fresher",
      "type": "both",
      "about": "A balanced fresher interview: technical fundamentals, one coding question, one HR/behavioural question. Use this when the company is not listed.",
      "rounds": [
        "technical",
        "dsa",
        "hr",
        "behavioral"
      ]
    }
  ],
  "questions": [
    {
      "company": "TCS",
      "round": "aptitude",
      "text": "A train covers 240 km in 4 hours. If it increases its speed by 20 km/h, how long will it take to cover the same distance?",
      "ideal": "Original speed is 60 km/h. New speed is 80 km/h. Time = 240/80 = 3 hours. State the steps and the final answer clearly.",
      "tags": [
        "speed",
        "time",
        "distance",
        "quantitative"
      ],
      "difficulty": 2
    },
    {
      "company": "TCS",
      "round": "technical",
      "text": "Explain the difference between a primary key and a unique key in SQL.",
      "ideal": "A primary key uniquely identifies each row and cannot be NULL; a table has only one primary key. A unique key also enforces uniqueness but allows one NULL and a table may have several. Example: employee_id as primary key, email as unique key.",
      "tags": [
        "sql",
        "dbms",
        "keys",
        "constraints"
      ],
      "difficulty": 2
    },
    {
      "company": "TCS",
      "round": "technical",
      "text": "What is the difference between method overloading and method overriding?",
      "ideal": "Overloading is compile-time polymorphism: same method name, different parameter list, in the same class. Overriding is runtime polymorphism: a subclass redefines a superclass method with the same signature, resolved via dynamic dispatch.",
      "tags": [
        "oop",
        "polymorphism",
        "java",
        "c++"
      ],
      "difficulty": 2
    },
    {
      "company": "TCS",
      "round": "hr",
      "text": "Are you comfortable relocating to any city or working in rotational shifts?",
      "ideal": "Give a clear yes/specific condition, then a reason. 'Yes, I am open to relocating anywhere in India; I have already discussed it with my family. I have lived in a hostel for four years so adjusting to a new city is not a problem.' Avoid a vague 'I can manage'.",
      "tags": [
        "relocation",
        "flexibility",
        "shift",
        "commitment"
      ],
      "difficulty": 1
    },
    {
      "company": "TCS",
      "round": "hr",
      "text": "Why do you want to join TCS when you could join a startup?",
      "ideal": "Show research and a concrete reason: structured training (Initial Learning Program), scale of projects, exposure to multiple domains. Tie it to your own goal, e.g. wanting a strong foundation in enterprise software delivery. Do not say 'because TCS is a big company'.",
      "tags": [
        "why-company",
        "motivation",
        "research"
      ],
      "difficulty": 2
    },
    {
      "company": "TCS",
      "round": "hr",
      "text": "Tell me about yourself.",
      "ideal": "30-60 second STRUCTURE: present state (degree, college, key skill), one proof point (project or internship with a result), then why this role. Avoid reciting your resume chronology or your family details.",
      "tags": [
        "intro",
        "communication",
        "structure"
      ],
      "difficulty": 1
    },
    {
      "company": "Infosys",
      "round": "technical",
      "text": "Explain normalization. Why do we need 3NF?",
      "ideal": "Normalization organizes tables to reduce redundancy and update anomalies. 1NF: atomic values. 2NF: no partial dependency on part of a composite key. 3NF: no transitive dependency of a non-key attribute on the key. Trade-off: more joins, so sometimes denormalize for read performance.",
      "tags": [
        "dbms",
        "normalization",
        "3nf",
        "design"
      ],
      "difficulty": 3
    },
    {
      "company": "Infosys",
      "round": "technical",
      "text": "What happens internally when you type a URL in the browser and press Enter?",
      "ideal": "DNS resolution to get the IP, TCP handshake, TLS handshake for HTTPS, HTTP request to the server, server responds, browser parses HTML and fetches sub-resources, builds the DOM and renders. Mention DNS cache and CDN briefly.",
      "tags": [
        "networking",
        "dns",
        "http",
        "browser"
      ],
      "difficulty": 3
    },
    {
      "company": "Infosys",
      "round": "technical",
      "text": "Pick one project from your resume and explain your exact contribution.",
      "ideal": "Name the project, the problem, your specific modules and the stack. Use 'I' not 'we'. Give one measurable outcome (users, latency, marks, accuracy) and one hard bug you fixed and how.",
      "tags": [
        "project",
        "resume",
        "ownership",
        "depth"
      ],
      "difficulty": 2
    },
    {
      "company": "Infosys",
      "round": "hr",
      "text": "You are assigned a technology you have never worked on. What will you do in the first week?",
      "ideal": "Concrete plan: read official documentation and a small tutorial, build a throwaway sample, find a mentor/teammate, ask for existing code to read, then take a small ticket. Show you are self-driven but also know when to ask for help.",
      "tags": [
        "learning",
        "adaptability",
        "situational"
      ],
      "difficulty": 2
    },
    {
      "company": "Wipro",
      "round": "technical",
      "text": "Write the logic to reverse a string without using a built-in reverse function.",
      "ideal": "Two-pointer swap: i=0, j=n-1, swap characters and move inward until i>=j. O(n) time, O(1) space for a mutable array; O(n) space if you build a new string. Say the complexity and one edge case (empty string, unicode).",
      "tags": [
        "coding",
        "strings",
        "two-pointer",
        "complexity"
      ],
      "difficulty": 2
    },
    {
      "company": "Wipro",
      "round": "technical",
      "text": "What is the difference between == and .equals() in Java?",
      "ideal": "== compares references (memory addresses) for objects and values for primitives. .equals() compares content and can be overridden. String interning causes surprises: new String(\"a\") == \"a\" is false but .equals is true.",
      "tags": [
        "java",
        "strings",
        "equality",
        "core"
      ],
      "difficulty": 2
    },
    {
      "company": "Wipro",
      "round": "hr",
      "text": "Are you willing to sign a service agreement / bond?",
      "ideal": "Answer honestly and directly, then show commitment reasoning. If yes say yes without hesitation - hesitation is what gets marked down. If no, say no politely with a reason.",
      "tags": [
        "bond",
        "commitment",
        "honesty"
      ],
      "difficulty": 1
    },
    {
      "company": "Cognizant",
      "round": "technical",
      "text": "Write a SQL query to find the second highest salary from an Employee table.",
      "ideal": "Options: SELECT MAX(salary) FROM Employee WHERE salary < (SELECT MAX(salary) FROM Employee); or use LIMIT/OFFSET; or DENSE_RANK() over salary. Mention NULL handling and duplicate salaries. Naming the trade-off is what earns marks.",
      "tags": [
        "sql",
        "query",
        "subquery",
        "window-function"
      ],
      "difficulty": 3
    },
    {
      "company": "Cognizant",
      "round": "technical",
      "text": "Explain the different types of JOINs with an example.",
      "ideal": "INNER (matching rows only), LEFT (all left + matches), RIGHT, FULL OUTER, CROSS. Give a small students/courses example and say when you would use LEFT JOIN (e.g. find students with no course).",
      "tags": [
        "sql",
        "joins",
        "dbms"
      ],
      "difficulty": 2
    },
    {
      "company": "Cognizant",
      "round": "hr",
      "text": "You and a teammate disagree on the approach to a task. What did you do?",
      "ideal": "Use STAR. Situation, your task, the action (listened, wrote down both options, compared using a criterion like effort vs accuracy, escalated if needed), and the result. Show that you disagree on ideas, not on people.",
      "tags": [
        "teamwork",
        "conflict",
        "star",
        "behavioural"
      ],
      "difficulty": 2
    },
    {
      "company": "Accenture",
      "round": "behavioral",
      "text": "You realise two days before the deadline that you will miss it. What do you do?",
      "ideal": "STAR-style and proactive: raise it immediately, quantify the gap, propose options (cut scope, add help, phased delivery), commit to a revised date you can meet. The interviewer is testing ownership and early escalation, not perfection.",
      "tags": [
        "situational",
        "ownership",
        "communication",
        "deadline"
      ],
      "difficulty": 2
    },
    {
      "company": "Accenture",
      "round": "hr",
      "text": "Where do you see yourself in five years?",
      "ideal": "Show a growth path inside the role: strong individual contributor in 1-2 years, owning modules and mentoring juniors by year 3-4, moving toward technical leadership or domain expertise. Avoid 'doing MBA and leaving' or 'in your seat'.",
      "tags": [
        "career",
        "ambition",
        "retention"
      ],
      "difficulty": 1
    },
    {
      "company": "Capgemini",
      "round": "technical",
      "text": "Read this pseudo-code and tell the output: set x = 5; while x > 0 { print x; x = x - 2 }",
      "ideal": "Prints 5, 3, 1 then the loop ends because x becomes -1 which is not > 0. Explain the trace step by step and confirm the condition is checked before each iteration.",
      "tags": [
        "pseudo-code",
        "loops",
        "trace",
        "logic"
      ],
      "difficulty": 2
    },
    {
      "company": "Capgemini",
      "round": "technical",
      "text": "What is the difference between GET and POST?",
      "ideal": "GET requests data in the URL, is idempotent, cacheable and length-limited; POST sends data in the body, is not idempotent and is used to create resources. Mention that GET is not secure for secrets because it lands in logs/history.",
      "tags": [
        "http",
        "rest",
        "web",
        "api"
      ],
      "difficulty": 2
    },
    {
      "company": "Amazon",
      "round": "behavioral",
      "text": "Tell me about a time you took ownership of something outside your responsibility.",
      "ideal": "STAR + Leadership Principle 'Ownership'. Pick a real incident: what was broken or missing, why nobody was assigned to it, what you specifically did, the measurable outcome, and what you learned. Long-term thinking and 'never say it's not my job' should be visible.",
      "tags": [
        "star",
        "ownership",
        "leadership-principle",
        "behavioural"
      ],
      "difficulty": 3
    },
    {
      "company": "Amazon",
      "round": "behavioral",
      "text": "Describe a time you had to make a decision with incomplete data.",
      "ideal": "Amazon LP: 'Bias for Action' and 'Dive Deep'. Show that you identified what data was missing, what risk was acceptable, what reversible decision you made, and how you validated it afterwards. Quantify the impact.",
      "tags": [
        "star",
        "bias-for-action",
        "decision",
        "ambiguity"
      ],
      "difficulty": 4
    },
    {
      "company": "Amazon",
      "round": "behavioral",
      "text": "Tell me about a time you disagreed with your manager or a senior. How did you handle it?",
      "ideal": "LP: 'Have Backbone; Disagree and Commit'. Show that you raised the concern with data, listened, and if overruled committed fully rather than quietly disengaging. Do not tell a story where you were simply right and the manager was stupid.",
      "tags": [
        "star",
        "backbone",
        "conflict",
        "leadership-principle"
      ],
      "difficulty": 4
    },
    {
      "company": "Amazon",
      "round": "dsa",
      "text": "Given an array of integers and a target, return the indices of two numbers that add up to the target. Explain the optimal approach.",
      "ideal": "Hash map from value to index, iterate once, for each element check if target - x is in the map. O(n) time, O(n) space. Mention the brute force O(n^2) first to show you can see the trade-off, then optimize. Confirm behaviour with duplicates and no-solution case.",
      "tags": [
        "hashing",
        "arrays",
        "two-sum",
        "complexity"
      ],
      "difficulty": 3
    },
    {
      "company": "Amazon",
      "round": "dsa",
      "text": "Find the maximum sum of any contiguous subarray of an array of integers.",
      "ideal": "Kadane's algorithm: running sum = max(x, running + x), track global max. O(n) time, O(1) space. Explain why discarding a negative running sum is safe, and handle an all-negative array.",
      "tags": [
        "dp",
        "kadane",
        "arrays",
        "complexity"
      ],
      "difficulty": 4
    },
    {
      "company": "Amazon",
      "round": "system_design",
      "text": "Design a URL shortener like amzn.to. What are the key components?",
      "ideal": "Clarify scale (reads vs writes), then: API layer, ID generation (base62 of a counter or hash), key-value store for mapping, cache for hot links, 301 vs 302 redirect choice, analytics pipeline, and collision handling. State the read-heavy caching strategy explicitly.",
      "tags": [
        "system-design",
        "hld",
        "hashing",
        "caching",
        "scale"
      ],
      "difficulty": 4
    },
    {
      "company": "Amazon",
      "round": "technical",
      "text": "What is the difference between a process and a thread?",
      "ideal": "A process has its own memory space; threads share the process's heap and code but have separate stacks and registers. Context switching between threads is cheaper. Mention races and locks, and that Python has the GIL as a real-world caveat.",
      "tags": [
        "os",
        "process",
        "thread",
        "concurrency"
      ],
      "difficulty": 3
    },
    {
      "company": "Google",
      "round": "dsa",
      "text": "Given a binary tree, return its level-order traversal.",
      "ideal": "BFS with a queue; process one level at a time by recording the queue size before the inner loop. O(n) time, O(width) space. Mention DFS-with-depth as an alternative and why BFS is natural here.",
      "tags": [
        "trees",
        "bfs",
        "queue",
        "traversal"
      ],
      "difficulty": 3
    },
    {
      "company": "Google",
      "round": "dsa",
      "text": "You are given a stream of numbers. Design a structure that returns the median at any time.",
      "ideal": "Two heaps: a max-heap for the lower half and a min-heap for the upper half, rebalanced so their sizes differ by at most one. Median is the top of the larger heap or the average of both tops. Insert O(log n), median O(1).",
      "tags": [
        "heaps",
        "stream",
        "median",
        "design"
      ],
      "difficulty": 4
    },
    {
      "company": "Google",
      "round": "dsa",
      "text": "Explain how you would find the longest substring without repeating characters.",
      "ideal": "Sliding window with a map of last-seen index. Move the right pointer, on repeat jump the left pointer to max(left, last_seen+1). O(n) time, O(min(n, alphabet)) space. Trace a small example like 'abcabcbb'.",
      "tags": [
        "sliding-window",
        "strings",
        "hashmap",
        "complexity"
      ],
      "difficulty": 4
    },
    {
      "company": "Google",
      "round": "system_design",
      "text": "Design a rate limiter for an API.",
      "ideal": "Clarify per-user vs global, and hard vs soft limits. Compare fixed window, sliding window log, token bucket (allows bursts) and leaky bucket. Token bucket in a Redis-like store with atomic increment is the usual answer. Discuss distributed edge cases and response code 429 + Retry-After.",
      "tags": [
        "system-design",
        "rate-limiting",
        "token-bucket",
        "distributed"
      ],
      "difficulty": 4
    },
    {
      "company": "Google",
      "round": "behavioral",
      "text": "Tell me about a technical project you are most proud of and what you would do differently.",
      "ideal": "Pick one project with real depth, explain the hardest technical decision, then genuinely critique it (design debt, missing tests, scale limit) and say what you would change. Self-awareness is the scored trait here.",
      "tags": [
        "project",
        "reflection",
        "googleyness",
        "depth"
      ],
      "difficulty": 3
    },
    {
      "company": "Microsoft",
      "round": "dsa",
      "text": "Reverse a linked list. Which approach do you choose and why?",
      "ideal": "Iterative with three pointers (prev, curr, next) is O(n) time and O(1) space. Recursive is O(n) stack space. Walk the pointer updates aloud and state the new head. Handle empty and single-node lists.",
      "tags": [
        "linked-list",
        "pointers",
        "iteration",
        "complexity"
      ],
      "difficulty": 3
    },
    {
      "company": "Microsoft",
      "round": "technical",
      "text": "What is the difference between a stack and a heap memory?",
      "ideal": "Stack holds function frames and local values, is fast, LIFO and size-limited; heap holds dynamically allocated objects, is larger and freed by GC or manually. Mention that the stack is per-thread while the heap is shared.",
      "tags": [
        "os",
        "memory",
        "stack",
        "heap"
      ],
      "difficulty": 3
    },
    {
      "company": "Microsoft",
      "round": "technical",
      "text": "How does an index improve SQL query performance, and when can it hurt?",
      "ideal": "An index is a B-tree keyed on the column, turning a full scan into a logarithmic lookup. It hurts writes (extra maintenance), consumes space, and is ignored for low-cardinality columns or when leading columns of a composite index are not used.",
      "tags": [
        "dbms",
        "index",
        "b-tree",
        "performance"
      ],
      "difficulty": 3
    },
    {
      "company": "Microsoft",
      "round": "behavioral",
      "text": "Describe a bug you shipped and how you found it.",
      "ideal": "STAR with real debugging detail: the symptom, the hypothesis list, the tool you used (logs, debugger, bisect), the root cause, the fix, and the test or alert you added so it cannot recur. Owning the mistake scores higher than blaming.",
      "tags": [
        "star",
        "debugging",
        "ownership",
        "learning"
      ],
      "difficulty": 3
    },
    {
      "company": "Flipkart",
      "round": "dsa",
      "text": "Design an LRU cache with get and put in O(1).",
      "ideal": "Hash map from key to node plus a doubly linked list for recency order. get moves the node to the front; put evicts the tail when capacity is exceeded. Explain each operation's O(1) guarantee and the eviction boundary case.",
      "tags": [
        "design",
        "lru",
        "hashmap",
        "linked-list"
      ],
      "difficulty": 4
    },
    {
      "company": "Flipkart",
      "round": "system_design",
      "text": "How would you design the inventory system for a flash sale?",
      "ideal": "Clarify oversell tolerance first. Then: pre-warm inventory in a fast store, atomic decrement or reservation with TTL, queue-based order intake, idempotency keys, and a reconciliation job. Discuss contention, locking vs optimistic concurrency, and graceful 'sold out' UX.",
      "tags": [
        "system-design",
        "inventory",
        "concurrency",
        "e-commerce"
      ],
      "difficulty": 5
    },
    {
      "company": "Flipkart",
      "round": "technical",
      "text": "What is idempotency and why does it matter in payments?",
      "ideal": "An operation that gives the same result when repeated. In payments, retries with an idempotency key prevent double debits. Explain the server-side unique key + stored response pattern.",
      "tags": [
        "api",
        "idempotency",
        "payments",
        "reliability"
      ],
      "difficulty": 4
    },
    {
      "company": "Flipkart",
      "round": "behavioral",
      "text": "Tell me about a time you had to learn something very fast to finish a task.",
      "ideal": "STAR, but emphasise method: what you read, what you skipped, how you validated understanding with a small prototype, and the deadline you met. Name the specific resource you used.",
      "tags": [
        "star",
        "learning",
        "velocity",
        "ownership"
      ],
      "difficulty": 3
    },
    {
      "company": "Zoho",
      "round": "technical",
      "text": "What is the difference between a structure and a union in C?",
      "ideal": "A struct allocates space for all members simultaneously; a union allocates space for the largest member and members share it. Struct size is roughly the sum with padding; union size is the max member. Unions are for memory reuse and type punning.",
      "tags": [
        "c",
        "struct",
        "union",
        "memory"
      ],
      "difficulty": 2
    },
    {
      "company": "Zoho",
      "round": "technical",
      "text": "Explain pointer arithmetic with an example.",
      "ideal": "Incrementing a pointer moves it by sizeof(type) bytes; subtracting two pointers of the same array yields the element count. Show int *p; p+1 advances 4 bytes. Mention that void* arithmetic is illegal and out-of-bounds arithmetic is undefined behaviour.",
      "tags": [
        "c",
        "pointers",
        "memory",
        "undefined-behaviour"
      ],
      "difficulty": 3
    },
    {
      "company": "Zoho",
      "round": "dsa",
      "text": "Check whether a given string is a palindrome, ignoring case and spaces.",
      "ideal": "Two pointers from both ends, skipping non-alphanumerics, compare lowercase characters. O(n) time, O(1) space. Say why you avoid building a cleaned copy of the string.",
      "tags": [
        "strings",
        "two-pointer",
        "coding",
        "edge-cases"
      ],
      "difficulty": 2
    },
    {
      "company": "Zoho",
      "round": "hr",
      "text": "You were not selected in a previous interview. What did you change afterwards?",
      "ideal": "Be honest and specific about the gap (e.g. 'I froze on recursion') and name the concrete action and proof of improvement (50 problems solved, a project rewritten). Shows coachability, which Zoho weights heavily.",
      "tags": [
        "self-awareness",
        "coachability",
        "honesty"
      ],
      "difficulty": 2
    },
    {
      "company": "Generic Fresher",
      "round": "technical",
      "text": "Explain the four pillars of object-oriented programming with one example each.",
      "ideal": "Encapsulation (private fields + getters), Abstraction (interface hiding detail), Inheritance (Dog extends Animal), Polymorphism (same call, different behaviour - overloading/overriding). Use one running example like a Payment class across the four pillars.",
      "tags": [
        "oop",
        "fundamentals",
        "java",
        "abstraction"
      ],
      "difficulty": 2
    },
    {
      "company": "Generic Fresher",
      "round": "technical",
      "text": "What is the difference between a list and a tuple in Python, and when would you use each?",
      "ideal": "Lists are mutable, tuples immutable. Tuples are hashable so they can be dict keys, slightly faster and signal intent. Use tuples for fixed records (coordinates) and lists for collections that change.",
      "tags": [
        "python",
        "data-structures",
        "immutability"
      ],
      "difficulty": 2
    },
    {
      "company": "Generic Fresher",
      "round": "technical",
      "text": "Explain the difference between TCP and UDP.",
      "ideal": "TCP is connection-oriented, ordered, reliable, with congestion control; UDP is connectionless, unordered, unreliable but low latency. Examples: HTTP/file transfer on TCP, DNS/video/gaming on UDP.",
      "tags": [
        "networking",
        "tcp",
        "udp",
        "fundamentals"
      ],
      "difficulty": 3
    },
    {
      "company": "Generic Fresher",
      "round": "technical",
      "text": "What is a deadlock and how can you prevent it?",
      "ideal": "Two or more processes each hold a resource and wait for one held by another. Four conditions: mutual exclusion, hold and wait, no preemption, circular wait. Prevent by consistent lock ordering, timeouts, or a single global lock.",
      "tags": [
        "os",
        "deadlock",
        "concurrency",
        "fundamentals"
      ],
      "difficulty": 3
    },
    {
      "company": "Generic Fresher",
      "round": "dsa",
      "text": "How would you check if two strings are anagrams of each other?",
      "ideal": "Count character frequencies in a hash map (or a 26-size array) for the first string, decrement for the second; all zeros means anagram. O(n) time. Mention the sort-and-compare alternative at O(n log n) and the length pre-check.",
      "tags": [
        "strings",
        "hashmap",
        "counting",
        "complexity"
      ],
      "difficulty": 2
    },
    {
      "company": "Generic Fresher",
      "round": "dsa",
      "text": "Write an algorithm to find the factorial of a number iteratively and recursively. Compare them.",
      "ideal": "Iterative: multiply 1..n, O(n) time O(1) space. Recursive: n * fact(n-1) with base case n<=1, O(n) stack space. Mention integer overflow for large n and the case n=0 returning 1.",
      "tags": [
        "recursion",
        "iteration",
        "coding",
        "overflow"
      ],
      "difficulty": 2
    },
    {
      "company": "Generic Fresher",
      "round": "dsa",
      "text": "Given a sorted array, find the index of a target element efficiently.",
      "ideal": "Binary search: low=0, high=n-1, mid=(low+high)//2, compare and halve the range. O(log n) time. Mention the sorted precondition and off-by-one care, and return -1 when not found.",
      "tags": [
        "binary-search",
        "arrays",
        "complexity",
        "sorted"
      ],
      "difficulty": 3
    },
    {
      "company": "Generic Fresher",
      "round": "hr",
      "text": "What is your biggest weakness?",
      "ideal": "Pick a real, non-fatal weakness with the concrete step you are taking and evidence of progress. 'I used to go silent when stuck; now I timebox to 20 minutes then ask' beats 'I am a perfectionist'.",
      "tags": [
        "self-awareness",
        "honesty",
        "growth"
      ],
      "difficulty": 2
    },
    {
      "company": "Generic Fresher",
      "round": "hr",
      "text": "Why should we hire you over other candidates with the same degree?",
      "ideal": "One differentiator with proof: a shipped project, an internship outcome, an open-source contribution, a certification with a working demo. Then tie it to the role's needs. Never say 'I am hardworking'.",
      "tags": [
        "differentiation",
        "value",
        "proof"
      ],
      "difficulty": 2
    },
    {
      "company": "Generic Fresher",
      "round": "hr",
      "text": "Do you have any questions for us?",
      "ideal": "Always have two questions ready: one about the team/tech stack and one about what success looks like in the first six months. Avoid questions answered on the website or about salary in round one.",
      "tags": [
        "closing",
        "curiosity",
        "preparation"
      ],
      "difficulty": 1
    },
    {
      "company": "Generic Fresher",
      "round": "behavioral",
      "text": "Tell me about a time you failed and what you learned.",
      "ideal": "STAR with a genuine failure (not a humble-brag), your specific contribution to the failure, the fix, and a changed behaviour you can prove later. The learning must be verifiable, not 'I learned to be careful'.",
      "tags": [
        "star",
        "failure",
        "learning",
        "self-awareness"
      ],
      "difficulty": 2
    },
    {
      "company": "Generic Fresher",
      "round": "behavioral",
      "text": "Describe a time you worked in a team where someone was not contributing.",
      "ideal": "STAR: what you observed, whether you spoke to them privately first, what you redistributed, whether you escalated, and the outcome. Show empathy plus delivery focus.",
      "tags": [
        "teamwork",
        "conflict",
        "star",
        "delivery"
      ],
      "difficulty": 2
    },
    {
      "company": null,
      "round": "hr",
      "text": "Walk me through your resume in 60 seconds.",
      "ideal": "Chronological but selective: education, strongest technical skill with proof, one project or internship with a result, and a closing line on why this role. Do not list every subject you studied.",
      "tags": [
        "intro",
        "resume",
        "communication"
      ],
      "difficulty": 1
    },
    {
      "company": null,
      "round": "technical",
      "text": "What is the difference between an abstract class and an interface?",
      "ideal": "An abstract class can hold state and concrete methods and is extended once; an interface declares a contract, supports multiple implementation, and has no state (default methods aside). Choose an abstract class for shared code, an interface for capability.",
      "tags": [
        "oop",
        "interfaces",
        "abstraction",
        "design"
      ],
      "difficulty": 3
    },
    {
      "company": null,
      "round": "hr",
      "text": "How do you handle pressure or a very tight deadline?",
      "ideal": "Give your actual method: prioritise by impact, break work into chunks, communicate status early, cut scope not quality. Back it with one short example. Vague answers like 'I stay calm' score poorly.",
      "tags": [
        "pressure",
        "prioritisation",
        "method"
      ],
      "difficulty": 2
    },
    {
      "company": null,
      "round": "behavioral",
      "text": "Tell me about a time you had to convince someone to accept your idea.",
      "ideal": "STAR with the resistance, the evidence you brought, how you adapted your argument to their concern, and the outcome. Listening to the objection is the part interviewers score.",
      "tags": [
        "star",
        "persuasion",
        "influence",
        "communication"
      ],
      "difficulty": 3
    },
    {
      "company": null,
      "round": "aptitude",
      "text": "A shopkeeper marks an item 40% above cost and then gives a 25% discount. What is his profit percentage?",
      "ideal": "Let cost be 100. Marked price = 140. Selling price after 25% discount = 140 x 0.75 = 105. Profit = 5 on 100, so 5%. Show the base-100 shortcut explicitly - it avoids algebra errors.",
      "tags": [
        "aptitude",
        "percentage",
        "profit-loss"
      ],
      "difficulty": 2
    },
    {
      "company": null,
      "round": "aptitude",
      "text": "If 6 workers can finish a task in 12 days, how many days will 9 workers take, working at the same rate?",
      "ideal": "Work is constant: 6 x 12 = 72 worker-days. With 9 workers, 72/9 = 8 days. State the inverse proportion explicitly.",
      "tags": [
        "aptitude",
        "time-work",
        "ratio"
      ],
      "difficulty": 1
    },
    {
      "company": null,
      "round": "aptitude",
      "text": "Complete the series: 2, 6, 12, 20, 30, ?",
      "ideal": "Differences are 4, 6, 8, 10 - increasing by 2. Next difference is 12, so 30 + 12 = 42. Alternatively n(n+1): 6x7 = 42. Give the rule, not just the number.",
      "tags": [
        "aptitude",
        "series",
        "reasoning"
      ],
      "difficulty": 2
    },
    {
      "company": null,
      "round": "aptitude",
      "text": "In a class of 40 students, 60% passed maths and 50% passed science. 25% passed both. How many failed both subjects?",
      "ideal": "Passed at least one = 60 + 50 - 25 = 85%. Failed both = 15% of 40 = 6 students. Use inclusion-exclusion and state each step.",
      "tags": [
        "aptitude",
        "sets",
        "venn",
        "percentage"
      ],
      "difficulty": 3
    },
    {
      "company": null,
      "round": "aptitude",
      "text": "A sum doubles in 8 years at simple interest. In how many years will it become four times itself?",
      "ideal": "Doubling means SI = P in 8 years, so rate = 12.5% per year. For 4x, SI must be 3P, which takes 8 x 3 = 24 years. Emphasise that SI grows linearly.",
      "tags": [
        "aptitude",
        "simple-interest",
        "quantitative"
      ],
      "difficulty": 2
    }
  ]
}
```

---

<!-- FILE: data/seed_reviews.json -->

<sub>7386 bytes</sub>

```json
[
  {
    "student_name": "Aarav",
    "company": "TCS",
    "round": "hr",
    "difficulty_felt": 2,
    "rating": 4,
    "text": "Very friendly panel. They asked a lot about relocation and shift and whether I would sign the bond. No deep technical questions at all, mostly about my final year project.",
    "days_ago": 40
  },
  {
    "student_name": "Meera",
    "company": "TCS",
    "round": "technical",
    "difficulty_felt": 3,
    "rating": 3,
    "text": "Asked me to write SQL query for second highest salary and then kept asking about joins. Also asked about primary key vs unique key. My advice: revise SQL properly.",
    "days_ago": 22
  },
  {
    "student_name": "Rohit",
    "company": "TCS",
    "round": "hr",
    "difficulty_felt": 1,
    "rating": 5,
    "text": "Total 15 minutes. Tell me about yourself, why TCS, relocation, and if I know what TCS does. They really want to hear that you are okay with any location.",
    "days_ago": 12
  },
  {
    "student_name": "Sneha",
    "company": "Infosys",
    "round": "technical",
    "difficulty_felt": 3,
    "rating": 4,
    "text": "70 percent of my interview was my project. They asked why I chose that database and made me explain the architecture on paper. Then normalization questions, 3NF specifically.",
    "days_ago": 30
  },
  {
    "student_name": "Karthik",
    "company": "Infosys",
    "round": "technical",
    "difficulty_felt": 4,
    "rating": 2,
    "text": "Panel drilled me on OOP for 20 minutes - overloading vs overriding, abstract class vs interface, then asked about ACID properties. Felt underprepared on theory.",
    "days_ago": 18
  },
  {
    "student_name": "Divya",
    "company": "Infosys",
    "round": "hr",
    "difficulty_felt": 2,
    "rating": 4,
    "text": "Standard HR round. They asked what I would do if given a technology I do not know. Also asked about my Infosys Springboard certification, so do mention it.",
    "days_ago": 9
  },
  {
    "student_name": "Imran",
    "company": "Wipro",
    "round": "technical",
    "difficulty_felt": 2,
    "rating": 4,
    "text": "Asked me to reverse a string and check palindrome in Java. Also difference between == and equals. Pretty basic, they mainly checked if I could explain my code.",
    "days_ago": 25
  },
  {
    "student_name": "Priya",
    "company": "Wipro",
    "round": "hr",
    "difficulty_felt": 1,
    "rating": 3,
    "text": "HR asked about the service agreement and relocation straight away. Be very clear and do not hesitate on the bond question, they mark you down for that.",
    "days_ago": 15
  },
  {
    "student_name": "Nikhil",
    "company": "Cognizant",
    "round": "technical",
    "difficulty_felt": 3,
    "rating": 4,
    "text": "SQL heavy. Second highest salary, types of joins, then a question on when to use left join. They also asked me to pick one language and go deep.",
    "days_ago": 20
  },
  {
    "student_name": "Ananya",
    "company": "Cognizant",
    "round": "technical",
    "difficulty_felt": 4,
    "rating": 3,
    "text": "Started from DBMS normalization and went into indexing. Asked why an index slows down inserts. I had read it but could not explain it well.",
    "days_ago": 7
  },
  {
    "student_name": "Vikram",
    "company": "Accenture",
    "round": "behavioral",
    "difficulty_felt": 2,
    "rating": 5,
    "text": "Almost entirely situational questions - missed deadline, team conflict, disagreeing with a senior. They want STAR format, that is it. Prepare 5 stories and you are set.",
    "days_ago": 35
  },
  {
    "student_name": "Riya",
    "company": "Accenture",
    "round": "hr",
    "difficulty_felt": 1,
    "rating": 4,
    "text": "Very conversational. Asked where I see myself in 5 years and about my hobbies. Very important to look confident and smile, they judge communication a lot.",
    "days_ago": 11
  },
  {
    "student_name": "Aditya",
    "company": "Amazon",
    "round": "behavioral",
    "difficulty_felt": 5,
    "rating": 4,
    "text": "Every single round had two leadership principle questions. They dig for 4-5 follow ups on the same story - what exactly did YOU do, what was the metric. One story about ownership is not enough.",
    "days_ago": 45
  },
  {
    "student_name": "Pooja",
    "company": "Amazon",
    "round": "dsa",
    "difficulty_felt": 4,
    "rating": 5,
    "text": "Two sum variant followed by a sliding window problem. They cared more about me stating complexity and edge cases than finishing the code. Always ask clarifying questions first.",
    "days_ago": 28
  },
  {
    "student_name": "Sameer",
    "company": "Amazon",
    "round": "system_design",
    "difficulty_felt": 5,
    "rating": 3,
    "text": "Asked to design a URL shortener and then went very deep on how I generate the unique id and how I handle collisions. Also asked about caching and analytics. I underestimated this round.",
    "days_ago": 14
  },
  {
    "student_name": "Tanvi",
    "company": "Google",
    "round": "dsa",
    "difficulty_felt": 5,
    "rating": 4,
    "text": "No small talk, straight to the problem. They gave a hint only after I was stuck for a while. Very focused on optimal complexity, brute force was not accepted.",
    "days_ago": 50
  },
  {
    "student_name": "Arjun",
    "company": "Google",
    "round": "system_design",
    "difficulty_felt": 5,
    "rating": 3,
    "text": "Rate limiter design. They expected me to compare token bucket vs sliding window and talk about distributed state. Tough round, prepare properly.",
    "days_ago": 16
  },
  {
    "student_name": "Neha",
    "company": "Microsoft",
    "round": "dsa",
    "difficulty_felt": 4,
    "rating": 5,
    "text": "Reverse linked list and a tree question. The interviewer was helpful and wanted me to think aloud. They also asked one OS question about process vs thread.",
    "days_ago": 21
  },
  {
    "student_name": "Harsh",
    "company": "Microsoft",
    "round": "technical",
    "difficulty_felt": 3,
    "rating": 4,
    "text": "Indexing and stack vs heap were asked. Also a debugging story from my project. Be ready to admit a bug you shipped, they like honesty there.",
    "days_ago": 6
  },
  {
    "student_name": "Ishita",
    "company": "Flipkart",
    "round": "system_design",
    "difficulty_felt": 5,
    "rating": 3,
    "text": "Flash sale inventory design. They kept pushing on how to avoid overselling. Concurrency and idempotency came up again and again.",
    "days_ago": 19
  },
  {
    "student_name": "Siddharth",
    "company": "Zoho",
    "round": "technical",
    "difficulty_felt": 4,
    "rating": 4,
    "text": "C fundamentals and pointers. Nothing about frameworks. They also asked me why I was rejected somewhere before, so keep an honest answer ready.",
    "days_ago": 24
  },
  {
    "student_name": "Kavya",
    "company": "Generic Fresher",
    "round": "hr",
    "difficulty_felt": 2,
    "rating": 4,
    "text": "Weakness, why should we hire you, and any questions for us. Having two good questions at the end changed the tone of the interview completely.",
    "days_ago": 5
  },
  {
    "student_name": "Rahul",
    "company": "Generic Fresher",
    "round": "technical",
    "difficulty_felt": 3,
    "rating": 3,
    "text": "OOP four pillars, TCP vs UDP, and one binary search question. Mixed round, tested breadth over depth.",
    "days_ago": 3
  }
]

```

---

<!-- FILE: static/index.html -->

<sub>38492 bytes</sub>

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>InterviewLoop — Company-Specific Mock Interviews</title>
<style>
  :root{
    --bg:#0b1020; --panel:#131a30; --panel2:#1a2340; --line:#26304f;
    --text:#e8ecf8; --muted:#93a0c2; --accent:#6c8cff; --accent2:#22d3a6;
    --warn:#ffb020; --bad:#ff5c7a; --good:#22d3a6; --radius:16px;
  }
  *{box-sizing:border-box}
  body{
    margin:0; background:radial-gradient(1200px 600px at 80% -10%,#1c2a55 0%,var(--bg) 55%);
    color:var(--text); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;
    min-height:100vh;
  }
  .wrap{max-width:1120px; margin:0 auto; padding:22px 18px 70px}
  header{display:flex; align-items:center; justify-content:space-between; gap:14px; padding:6px 0 20px; flex-wrap:wrap}
  .brand{display:flex; align-items:center; gap:11px}
  .logo{
    width:38px;height:38px;border-radius:11px;
    background:linear-gradient(135deg,var(--accent),var(--accent2));
    display:grid;place-items:center;font-weight:800;font-size:17px;color:#08102a;
  }
  .brand h1{font-size:17px;margin:0;letter-spacing:.2px}
  .brand p{margin:0;font-size:12px;color:var(--muted)}
  .pill{font-size:11.5px;padding:5px 11px;border-radius:999px;border:1px solid var(--line);
        background:var(--panel);color:var(--muted);display:inline-flex;align-items:center;gap:7px}
  .dot{width:7px;height:7px;border-radius:50%;background:var(--good);box-shadow:0 0 9px var(--good)}
  .dot.off{background:var(--warn);box-shadow:0 0 9px var(--warn)}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:20px}
  .grid{display:grid;gap:16px}
  .cols-2{grid-template-columns:1.15fr .85fr}
  @media(max-width:880px){.cols-2{grid-template-columns:1fr}}
  h2{font-size:15px;margin:0 0 4px;letter-spacing:.3px}
  .sub{color:var(--muted);font-size:12.5px;margin:0 0 15px}
  label{display:block;font-size:12px;color:var(--muted);margin:0 0 6px;font-weight:600;letter-spacing:.3px}
  input,select,textarea{
    width:100%;background:var(--panel2);border:1px solid var(--line);color:var(--text);
    border-radius:10px;padding:11px 12px;font:inherit;outline:none;transition:border .15s
  }
  input:focus,select:focus,textarea:focus{border-color:var(--accent)}
  textarea{resize:vertical;min-height:96px;line-height:1.55}
  button{
    font:inherit;font-weight:650;border-radius:10px;border:1px solid transparent;cursor:pointer;
    padding:11px 17px;transition:transform .12s,filter .15s;color:#08102a;
    background:linear-gradient(135deg,var(--accent),#8aa2ff)
  }
  button:hover{transform:translateY(-1px);filter:brightness(1.07)}
  button:disabled{opacity:.45;cursor:not-allowed;transform:none}
  button.ghost{background:transparent;color:var(--text);border-color:var(--line)}
  button.good{background:linear-gradient(135deg,var(--accent2),#4ee0bb)}
  button.small{padding:7px 12px;font-size:12.5px;border-radius:9px}
  .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  .chips{display:flex;gap:8px;flex-wrap:wrap}
  .chip{
    font-size:12px;padding:6px 11px;border-radius:999px;border:1px solid var(--line);
    background:var(--panel2);color:var(--muted);cursor:pointer;user-select:none
  }
  .chip.on{border-color:var(--accent);color:#cdd8ff;background:#1e2a52}
  .chip.static{cursor:default}
  .company-card{
    border:1px solid var(--line);background:var(--panel2);border-radius:13px;padding:13px;
    cursor:pointer;transition:.15s
  }
  .company-card:hover{border-color:#3a4880;transform:translateY(-1px)}
  .company-card.on{border-color:var(--accent);background:#1b2650;box-shadow:0 0 0 1px var(--accent) inset}
  .company-card .nm{font-weight:700;font-size:13.5px;display:flex;justify-content:space-between;gap:8px}
  .company-card .meta{font-size:11.5px;color:var(--muted);margin-top:5px}
  .tag{font-size:10.5px;padding:2px 8px;border-radius:999px;background:#233060;color:#a9baff}
  .tag.prod{background:#123f34;color:#6ee7c0}
  .score-ring{width:64px;height:64px;flex:0 0 auto}
  .stat{display:flex;justify-content:space-between;font-size:12.5px;padding:7px 0;border-bottom:1px dashed #222c4a}
  .stat:last-child{border:0}
  .stat b{color:var(--text);font-weight:650}
  .muted{color:var(--muted)}
  .chat{display:flex;flex-direction:column;gap:13px;max-height:52vh;overflow-y:auto;padding-right:5px}
  .msg{display:flex;gap:10px;animation:in .25s ease}
  @keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
  .msg .av{width:29px;height:29px;border-radius:9px;flex:0 0 auto;display:grid;place-items:center;font-size:12px;font-weight:800}
  .msg.bot .av{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#08102a}
  .msg.me .av{background:#2b3766;color:#c6d2f7}
  .bubble{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:11px 14px;font-size:14px;max-width:94%}
  .msg.me .bubble{background:#1d2a52;border-color:#2c3a66}
  .msg.me{align-self:flex-end;flex-direction:row-reverse}
  .scorebox{border-radius:12px;padding:13px 15px;border:1px solid var(--line);background:var(--panel2);margin-top:12px}
  .scorebox .top{display:flex;align-items:center;gap:14px}
  .scorebox .n{font-size:26px;font-weight:800;line-height:1}
  .bars{display:grid;gap:6px;margin-top:11px}
  .bar{display:grid;grid-template-columns:96px 1fr 34px;gap:9px;align-items:center;font-size:11.5px;color:var(--muted)}
  .track{display:block;height:6px;background:#212c4d;border-radius:99px;overflow:hidden}
  .fill{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
  .list{margin:7px 0 0;padding-left:17px;font-size:12.8px;color:#c3cde9}
  .list li{margin:4px 0}
  .banner{border-radius:11px;padding:11px 13px;font-size:12.6px;border:1px solid var(--line);background:var(--panel2)}
  .banner.hot{border-color:#3a4a86;background:#1a2350;color:#c3d1ff}
  .banner.warn{border-color:#5a4520;background:#2a2214;color:#ffd591}
  .mic{position:relative}
  .mic.rec{background:linear-gradient(135deg,var(--bad),#ff8aa0);animation:pulse 1.4s infinite}
  @keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,92,122,.5)}50%{box-shadow:0 0 0 12px rgba(255,92,122,0)}}
  .hide{display:none!important}
  .kbd{font-size:11px;border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:1px 6px;color:var(--muted)}
  .foot{color:var(--muted);font-size:11.5px;text-align:center;margin-top:26px;line-height:1.7}
  .advice{font-size:12.4px;color:#b9c6e8;border-left:3px solid var(--accent);padding-left:11px;margin:9px 0}
  .review{border-bottom:1px dashed #222c4a;padding:9px 0;font-size:12.6px}
  .review:last-child{border:0}
  .stars{color:var(--warn);letter-spacing:1px;font-size:11px}
  .progress{height:4px;background:#212c4d;border-radius:99px;overflow:hidden;margin:12px 0}
  .progress i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .3s}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#1d2a52;border:1px solid var(--line);
    padding:10px 16px;border-radius:10px;font-size:13px;z-index:99;animation:in .2s}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">
      <div class="logo">IL</div>
      <div>
        <h1>InterviewLoop</h1>
        <p>Company-specific mock interviews that learn from every review</p>
      </div>
    </div>
    <div class="row">
      <span class="pill" id="enginePill"><span class="dot"></span> engine</span>
      <span class="pill" id="voicePill"><span class="dot off"></span> voice off</span>
    </div>
  </header>

  <!-- ================= SETUP ================= -->
  <section id="setup">
    <div class="grid cols-2">
      <div class="card">
        <h2>Start a mock interview</h2>
        <p class="sub">Pick a company. The bot weights questions by what past students reported — not a generic syllabus.</p>

        <div style="margin-bottom:14px">
          <label for="studentName">Your name</label>
          <input id="studentName" placeholder="e.g. Ananya" autocomplete="off" />
        </div>

        <label>Choose a company</label>
        <div id="companyGrid" class="grid" style="grid-template-columns:1fr 1fr;gap:9px;margin-bottom:15px"></div>

        <div class="row" style="justify-content:space-between;align-items:flex-end">
          <div style="flex:1;min-width:170px">
            <label for="roundSel">Round</label>
            <select id="roundSel"></select>
          </div>
          <div style="flex:0 0 118px">
            <label for="lenSel">Length</label>
            <select id="lenSel">
              <option value="3">3 questions</option>
              <option value="4" selected>4 questions</option>
              <option value="5">5 questions</option>
            </select>
          </div>
        </div>

        <div class="row" style="margin-top:16px">
          <button id="startBtn" class="good">Start interview →</button>
          <button class="ghost small" id="voiceToggle">🎙 Voice mode: off</button>
        </div>
        <p class="sub" style="margin:12px 0 0" id="modeNote"></p>
      </div>

      <div class="card">
        <h2 id="profTitle">Company intel</h2>
        <p class="sub">Mined live from student reviews.</p>
        <div id="profBody" class="muted" style="font-size:13px">Select a company to see what recent candidates reported.</div>
      </div>
    </div>

    <div class="grid cols-2" style="margin-top:16px">
      <div class="card">
        <h2>Add your review</h2>
        <p class="sub">This is the learning loop. Your review immediately reshapes how this company's interviews are generated.</p>
        <div class="row" style="margin-bottom:10px">
          <div style="flex:1;min-width:120px">
            <label for="rvCompany">Company</label>
            <select id="rvCompany"></select>
          </div>
          <div style="flex:0 0 130px">
            <label for="rvRound">Round</label>
            <select id="rvRound"></select>
          </div>
        </div>
        <div class="row" style="margin-bottom:10px">
          <div style="flex:1">
            <label>How hard did it feel?</label>
            <div class="chips" id="rvDiff"></div>
          </div>
          <div style="flex:1">
            <label>Your rating</label>
            <div class="chips" id="rvRate"></div>
          </div>
        </div>
        <label for="rvText">What did they actually ask?</label>
        <textarea id="rvText" placeholder="They drilled SQL joins for 20 minutes, then asked about my project. Advice: revise DBMS properly."></textarea>
        <div class="row" style="margin-top:11px">
          <button id="rvSubmit">Submit review</button>
          <span class="muted" style="font-size:12px">Anonymous-friendly · no login needed</span>
        </div>
      </div>

      <div class="card">
        <h2>Recent reviews</h2>
        <p class="sub" id="rvSub">What candidates said</p>
        <div id="rvList" style="max-height:270px;overflow-y:auto"></div>
      </div>
    </div>
  </section>

  <!-- ================= INTERVIEW ================= -->
  <section id="interview" class="hide">
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <div>
          <h2 id="ivTitle">Interview</h2>
          <p class="sub" id="ivSub" style="margin:2px 0 0"></p>
        </div>
        <div class="row">
          <button class="ghost small" id="hintBtn">💡 Hint</button>
          <button class="ghost small" id="skipBtn">Skip</button>
          <button class="ghost small" id="endBtn">End & see report</button>
        </div>
      </div>
      <div class="progress"><i id="progBar" style="width:0%"></i></div>
      <div class="chat" id="chat"></div>

      <div style="margin-top:14px">
        <label for="answerBox">Your answer <span class="muted" id="answerHint">— speak or type. Think aloud.</span></label>
        <textarea id="answerBox" placeholder="Type your answer, or press the mic and speak…"></textarea>
        <div class="row" style="margin-top:10px;justify-content:space-between">
          <div class="row">
            <button class="mic" id="micBtn">🎙 Speak</button>
            <button class="good" id="sendBtn">Send answer</button>
          </div>
          <span class="muted" style="font-size:11.5px"><span class="kbd">Ctrl</span> + <span class="kbd">Enter</span> to send</span>
        </div>
      </div>
    </div>
  </section>

  <!-- ================= REPORT ================= -->
  <section id="report" class="hide"></section>

  <p class="foot">
    InterviewLoop · curated question bank + rubric scoring + two learning loops<br>
    Offline engine by default. Set <code>OPENAI_API_KEY</code> to upgrade feedback quality — scores stay rubric-anchored.
  </p>
</div>

<script>
/* ============================================================
   STATE
   ============================================================ */
const S = {
  companies: [],
  company: null,
  sessionId: null,
  seq: 0,
  of: 0,
  answeringProbe: false,
  probeText: null,
  voiceOn: false,
  listening: false,
  voicePersona: 'female',
};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function toast(msg, ms = 2600) {
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

/* ============================================================
   VOICE — Web Speech API (no keys, no cost, runs in the browser)
   ============================================================ */
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;

function voiceSupported() { return !!SpeechRec && 'speechSynthesis' in window; }

function initVoice() {
  if (!SpeechRec) return;
  recognizer = new SpeechRec();
  recognizer.continuous = true;
  recognizer.interimResults = true;
  recognizer.lang = 'en-IN';

  let finalText = '';
  recognizer.onstart = () => { S.listening = true; finalText = $('answerBox').value; syncMic(); };
  recognizer.onresult = (e) => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += (finalText ? ' ' : '') + t.trim();
      else interim += t;
    }
    $('answerBox').value = (finalText + ' ' + interim).replace(/\s+/g, ' ').trim();
  };
  recognizer.onerror = (e) => {
    S.listening = false; syncMic();
    if (e.error === 'not-allowed') toast('Microphone blocked. Allow mic access in your browser.');
    else if (e.error !== 'aborted') toast('Voice error: ' + e.error);
  };
  recognizer.onend = () => { S.listening = false; syncMic(); };
}

function syncMic() {
  const b = $('micBtn');
  if (!b) return;
  b.classList.toggle('rec', S.listening);
  b.textContent = S.listening ? '⏹ Stop' : '🎙 Speak';
}

function toggleMic() {
  if (!recognizer) { toast('Speech recognition needs Chrome/Edge (or a supported browser).'); return; }
  if (S.listening) { recognizer.stop(); }
  else {
    try { recognizer.start(); }
    catch (e) { toast('Could not start the mic. Try again.'); }
  }
}

let voicesCache = [];
function loadVoices() { voicesCache = window.speechSynthesis ? speechSynthesis.getVoices() : []; }
if ('speechSynthesis' in window) {
  loadVoices();
  speechSynthesis.onvoiceschanged = loadVoices;
}

function speak(text, done) {
  if (!S.voiceOn || !('speechSynthesis' in window) || !text) { if (done) done(); return; }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(String(text).replace(/[*#`_]/g, ''));
  const want = S.voicePersona === 'male' ? ['male'] : ['female'];
  const en = voicesCache.filter(v => /^en/i.test(v.lang));
  const pick = en.find(v => want.some(w => v.name.toLowerCase().includes(w))) || en[0] || voicesCache[0];
  if (pick) u.voice = pick;
  u.lang = (pick && pick.lang) || 'en-IN';
  u.rate = 0.97; u.pitch = 1.02;
  u.onend = () => { if (done) done(); };
  u.onerror = () => { if (done) done(); };
  speechSynthesis.speak(u);
  // Some engines never fire onend if cancelled — fail safe.
  setTimeout(() => { if (done) done(); }, Math.min(22000, 2600 + String(text).length * 68));
}

function toggleVoiceMode() {
  if (!voiceSupported()) { toast('This browser has no speech support. Chrome or Edge works best.'); return; }
  S.voiceOn = !S.voiceOn;
  $('voiceToggle').textContent = `🎙 Voice mode: ${S.voiceOn ? 'on' : 'off'}`;
  $('voiceToggle').classList.toggle('good', S.voiceOn);
  $('voicePill').innerHTML = `<span class="dot ${S.voiceOn ? '' : 'off'}"></span> voice ${S.voiceOn ? 'on' : 'off'}`;
  if (!S.voiceOn && 'speechSynthesis' in window) speechSynthesis.cancel();
  toast(S.voiceOn
    ? 'Voice mode on — the interviewer will speak and you can answer by mic.'
    : 'Voice mode off — text only.');
}

/* ============================================================
   SETUP SCREEN
   ============================================================ */
async function loadCompanies() {
  const data = await api('/api/companies');
  S.companies = data.companies;

  const grid = $('companyGrid');
  grid.innerHTML = S.companies.map(c => `
    <div class="company-card" data-co="${esc(c.name)}">
      <div class="nm"><span>${esc(c.name)}</span>
        <span class="tag ${c.type === 'product' ? 'prod' : ''}">${c.type === 'product' ? 'product' : c.type === 'service' ? 'service' : 'general'}</span>
      </div>
      <div class="meta">${c.question_count} Qs${c.review_count ? ` · ${c.review_count} reviews` : ''}${c.avg_difficulty_felt ? ` · feels ${c.avg_difficulty_felt}/5` : ''}</div>
    </div>`).join('');

  grid.querySelectorAll('.company-card').forEach(el => {
    el.onclick = () => selectCompany(el.dataset.co);
  });

  const rvCo = $('rvCompany');
  rvCo.innerHTML = S.companies.map(c => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('');
  rvCo.onchange = () => { fillRounds($('rvRound'), rvCo.value); loadReviews(); };

  selectCompany(S.companies[0].name);
}

function selectCompany(name) {
  S.company = S.companies.find(c => c.name === name);
  document.querySelectorAll('.company-card').forEach(el =>
    el.classList.toggle('on', el.dataset.co === name));
  fillRounds($('roundSel'), name);
  $('rvCompany').value = name;
  fillRounds($('rvRound'), name);
  loadProfile(name, $('roundSel').value);
  loadReviews();
}

function fillRounds(sel, company) {
  const c = S.companies.find(x => x.name === company);
  if (!c) return;
  sel.innerHTML = c.rounds.map(r =>
    `<option value="${esc(r)}">${esc(prettyRound(r))}</option>`).join('');
}

const prettyRound = (r) => ({
  aptitude: 'Aptitude', technical: 'Technical', hr: 'HR / Behavioural',
  behavioral: 'Behavioural (STAR)', dsa: 'DSA / Coding',
  system_design: 'System Design',
}[r] || r);

async function loadProfile(company, round) {
  const el = $('profBody');
  el.innerHTML = '<span class="muted">Mining reviews…</span>';
  try {
    const url = `/api/companies/${encodeURIComponent(company)}/profile` + (round ? `?round=${encodeURIComponent(round)}` : '');
    const p = await api(url);
    const hot = (p.hot_topics || []).slice(0, 7);
    const max = hot.length ? hot[0].mentions : 1;
    el.innerHTML = `
      ${p.review_count === 0
        ? '<div class="banner warn">No reviews yet for this company. Be the first — your review will shape the questions.</div>'
        : `<div class="banner hot">
             <b>${p.review_count}</b> review${p.review_count > 1 ? 's' : ''} mined${p.blended_company_wide ? ' (blended for this round)' : ''} ·
             felt difficulty <b>${p.avg_difficulty_felt ?? '—'}/5</b> ·
             rating <b>${p.avg_rating ?? '—'}/5</b>
           </div>`}
      ${hot.length ? `
        <div style="margin-top:13px">
          <div class="muted" style="font-size:11.5px;margin-bottom:7px;letter-spacing:.4px">WHAT THEY ACTUALLY ASKED (weighted by recency)</div>
          ${hot.map(h => `
            <div class="bar" style="grid-template-columns:118px 1fr 28px">
              <span style="color:#c3cde9">${esc(h.topic)}</span>
              <span class="track"><span class="fill" style="width:${Math.max(8, (h.mentions / max) * 100)}%"></span></span>
              <span>${h.mentions}</span>
            </div>`).join('')}
        </div>` : ''}
      ${p.advice && p.advice.length ? `
        <div style="margin-top:14px">
          <div class="muted" style="font-size:11.5px;margin-bottom:5px;letter-spacing:.4px">REPEATED ADVICE FROM PEERS</div>
          ${p.advice.map(a => `<div class="advice">“${esc(a)}”</div>`).join('')}
        </div>` : ''}
      ${p.coverage_gaps && p.coverage_gaps.length ? `
        <div class="banner" style="margin-top:13px;font-size:12px">
          <b>Gap detected:</b> students mention ${p.coverage_gaps.slice(0, 3).map(esc).join(', ')} but our bank has no question on it yet.
          <span class="muted">→ add questions here to improve the bot.</span>
        </div>` : ''}
    `;
  } catch (e) {
    el.innerHTML = `<span class="muted">Could not load intel: ${esc(e.message)}</span>`;
  }
}

async function loadReviews() {
  const co = $('rvCompany').value;
  const list = $('rvList');
  list.innerHTML = '<span class="muted">Loading…</span>';
  try {
    const data = await api('/api/reviews?company=' + encodeURIComponent(co));
    $('rvSub').textContent = `${data.reviews.length} review${data.reviews.length === 1 ? '' : 's'} for ${co}`;
    list.innerHTML = data.reviews.length ? data.reviews.map(r => `
      <div class="review">
        <div class="row" style="justify-content:space-between">
          <b style="font-size:12.5px">${esc(r.student_name)} · ${esc(prettyRound(r.round))}</b>
          <span class="stars">${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</span>
        </div>
        <div style="margin-top:3px">${esc(r.text)}</div>
        <div class="muted" style="font-size:11px;margin-top:3px">felt ${r.difficulty_felt}/5</div>
      </div>`).join('') : '<span class="muted">No reviews yet.</span>';
  } catch (e) { list.innerHTML = `<span class="muted">${esc(e.message)}</span>`; }
}

/* rating chips */
function buildChips(el, max, selected) {
  el.innerHTML = Array.from({ length: max }, (_, i) =>
    `<span class="chip ${i + 1 === selected ? 'on' : ''}" data-v="${i + 1}">${i + 1}</span>`).join('');
  el.querySelectorAll('.chip').forEach(c => {
    c.onclick = () => {
      el.querySelectorAll('.chip').forEach(x => x.classList.remove('on'));
      c.classList.add('on');
      el.dataset.value = c.dataset.v;
    };
  });
  el.dataset.value = selected;
}

async function submitReview() {
  const text = $('rvText').value.trim();
  if (text.length < 10) return toast('Please write a little more (at least 10 characters).');
  const name = ($('studentName').value.trim() || 'Anonymous');
  const btn = $('rvSubmit');
  btn.disabled = true; btn.textContent = 'Submitting…';
  try {
    const res = await api('/api/reviews', {
      method: 'POST',
      body: JSON.stringify({
        student_name: name,
        company: $('rvCompany').value,
        round: $('rvRound').value,
        difficulty_felt: Number($('rvDiff').dataset.value || 3),
        rating: Number($('rvRate').dataset.value || 4),
        text,
      }),
    });
    $('rvText').value = '';
    toast('Review saved — future interviews now weight these topics.');
    loadReviews();
    if (S.company && S.company.name === $('rvCompany').value) {
      loadProfile(S.company.name, $('roundSel').value);
    }
  } catch (e) { toast(e.message); }
  finally { btn.disabled = false; btn.textContent = 'Submit review'; }
}

/* ============================================================
   INTERVIEW
   ============================================================ */
async function startInterview() {
  const name = $('studentName').value.trim();
  if (!name) { toast('Enter your name first — it keeps your progress across sessions.'); $('studentName').focus(); return; }

  const btn = $('startBtn');
  btn.disabled = true; btn.textContent = 'Preparing…';
  try {
    const data = await api('/api/sessions', {
      method: 'POST',
      body: JSON.stringify({
        student_name: name,
        company: $('companyGrid').querySelector('.company-card.on').dataset.co,
        round: $('roundSel').value,
        limit: Number($('lenSel').value),
      }),
    });

    S.sessionId = data.session_id;
    S.seq = 1; S.of = data.total_questions;
    S.answeringProbe = false; S.probeText = null;

    $('setup').classList.add('hide');
    $('report').classList.add('hide');
    $('interview').classList.remove('hide');
    $('ivTitle').textContent = `${data.company} · ${prettyRound(data.round)}`;
    $('ivSub').textContent = `${data.total_questions} questions · ${data.pool_size} questions in pool · personalised from ${data.profile.review_count} reviews`;

    $('chat').innerHTML = '';
    addMsg('bot', data.intro);

    const weakKeys = Object.keys(data.weak_areas || {});
    if (weakKeys.length) {
      const weakest = weakKeys.sort((a, b) => data.weak_areas[a] - data.weak_areas[b]).slice(0, 3);
      addBanner(`Focusing on your weak areas from past sessions: <b>${weakest.map(esc).join(', ')}</b>`);
    }
    if (data.why_selected && data.why_selected.review_match >= 0.5) {
      addBanner(`Selected because past candidates reported this topic for ${esc(data.company)}.`, 'hot');
    }

    updateProgress(1);
    addMsg('bot', data.first.text, { speak: data.first.speak });
    $('answerBox').value = '';
    $('answerBox').focus();
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Start interview →';
  }
}

function addMsg(who, text, opts = {}) {
  const c = $('chat');
  const d = document.createElement('div');
  d.className = 'msg ' + who;
  d.innerHTML = `<div class="av">${who === 'bot' ? 'AI' : 'You'}</div>
                 <div class="bubble">${esc(text).replace(/\n/g, '<br>')}</div>`;
  c.appendChild(d);
  c.scrollTop = c.scrollHeight;
  if (opts.speak) speak(opts.speak);
}

function addBanner(html, kind = '') {
  const c = $('chat');
  const d = document.createElement('div');
  d.className = 'banner ' + kind;
  d.style.fontSize = '12.2px';
  d.innerHTML = html;
  c.appendChild(d);
  c.scrollTop = c.scrollHeight;
}

function updateProgress(seq) {
  $('progBar').style.width = Math.min(100, (seq / S.of) * 100) + '%';
}

const BAND_COLOR = (s) => s >= 7 ? 'var(--good)' : s >= 5.5 ? 'var(--warn)' : 'var(--bad)';

function addScoreCard(sc) {
  const d = document.createElement('div');
  d.className = 'scorebox';
  const dims = sc.dimensions || {};
  const order = ['coverage', 'structure', 'specificity', 'depth', 'confidence'];
  d.innerHTML = `
    <div class="top">
      <div style="text-align:center">
        <div class="n" style="color:${BAND_COLOR(sc.overall)}">${sc.overall}</div>
        <div class="muted" style="font-size:10.5px">/10</div>
      </div>
      <div style="flex:1">
        <b style="font-size:13px">${esc(sc.band || '')}</b>
        <div class="muted" style="font-size:12px;margin-top:2px">${esc(sc.verdict || '')}</div>
        ${sc.coaching ? `<div style="font-size:12.6px;margin-top:7px;color:#cdd8f5">${esc(sc.coaching)}</div>` : ''}
      </div>
    </div>
    <div class="bars">
      ${order.filter(k => dims[k] !== undefined).map(k => `
        <div class="bar"><span>${k}</span>
          <span class="track"><span class="fill" style="width:${dims[k] * 10}%"></span></span>
          <span>${dims[k]}</span></div>`).join('')}
    </div>
    ${sc.strengths && sc.strengths.length ? `<ul class="list">${sc.strengths.map(s => `<li>✅ ${esc(s)}</li>`).join('')}</ul>` : ''}
    ${sc.improvements && sc.improvements.length ? `<ul class="list">${sc.improvements.map(s => `<li>🔧 ${esc(s)}</li>`).join('')}</ul>` : ''}
  `;
  $('chat').appendChild(d);
  $('chat').scrollTop = $('chat').scrollHeight;
}

async function sendAnswer() {
  const text = $('answerBox').value.trim();
  if (!text) return toast('Write or speak an answer first.');
  if (S.listening) { try { recognizer.stop(); } catch (e) {} }

  const btn = $('sendBtn');
  btn.disabled = true; btn.textContent = 'Scoring…';
  addMsg('me', text);
  $('answerBox').value = '';

  try {
    const body = S.answeringProbe
      ? { answer: text, followup_answer: S.probeText }
      : { answer: text };
    const data = await api(`/api/sessions/${S.sessionId}/answer`, {
      method: 'POST', body: JSON.stringify(body),
    });

    if (data.score) addScoreCard(data.score);

    if (data.type === 'probe') {
      S.answeringProbe = true;
      S.probeText = data.probe;
      $('answerHint').textContent = '— follow-up question. Answer briefly.';
      setTimeout(() => addMsg('bot', data.probe, { speak: data.speak }), 320);
    } else if (data.type === 'next') {
      S.answeringProbe = false; S.probeText = null;
      $('answerHint').textContent = '— speak or type. Think aloud.';
      S.seq = data.next.seq;
      updateProgress(S.seq);
      setTimeout(() => {
        if (data.why_selected && data.why_selected.weak_area_match >= 0.5) {
          addBanner('This question targets a topic you scored low on previously.', '');
        }
        addMsg('bot', data.next.text, { speak: data.next.speak });
        $('answerBox').focus();
      }, 420);
    } else if (data.type === 'report') {
      setTimeout(() => renderReport(data.report), 380);
    }
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false; btn.textContent = 'Send answer';
  }
}

async function getHint() {
  try {
    const data = await api(`/api/sessions/${S.sessionId}/hint`, { method: 'POST' });
    addBanner(`💡 <b>Hint:</b> ${esc(data.hint)}`);
    if (data.peer_advice && data.peer_advice.length) {
      addBanner(`📣 <b>Peer advice:</b> “${esc(data.peer_advice[0])}”`);
    }
  } catch (e) { toast(e.message); }
}

async function skipQuestion() {
  try {
    const data = await api(`/api/sessions/${S.sessionId}/skip`, { method: 'POST' });
    if (data.type === 'report') return renderReport(data.report);
    addBanner('Question skipped — not counted.', 'warn');
    S.answeringProbe = false; S.probeText = null;
    S.seq = data.next.seq;
    updateProgress(S.seq);
    addMsg('bot', data.next.text, { speak: data.speak });
  } catch (e) { toast(e.message); }
}

async function endInterview() {
  if (!confirm('End the interview and see your report?')) return;
  try {
    const data = await api(`/api/sessions/${S.sessionId}/finish`, { method: 'POST' });
    renderReport(data.report);
  } catch (e) { toast(e.message); }
}

/* ============================================================
   REPORT
   ============================================================ */
function renderReport(r) {
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  $('interview').classList.add('hide');
  $('report').classList.remove('hide');

  const dims = r.dimensions || {};
  const order = ['coverage', 'structure', 'specificity', 'depth', 'confidence'];
  const prof = r.company_profile || {};

  $('report').innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div class="row" style="justify-content:space-between;align-items:flex-start">
        <div>
          <h2>Session report — ${esc(r.company)} · ${esc(prettyRound(r.round))}</h2>
          <p class="sub">${esc(r.student_name)} · ${r.turns} scored answer${r.turns === 1 ? '' : 's'}</p>
        </div>
        <div class="row">
          <button class="ghost small" onclick="location.reload()">New session</button>
        </div>
      </div>
      <div class="row" style="align-items:center;gap:20px;margin-top:6px">
        <svg class="score-ring" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="#212c4d" stroke-width="3.4"/>
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="${BAND_COLOR(r.overall)}" stroke-width="3.4"
            stroke-linecap="round" stroke-dasharray="${(r.overall / 10) * 97.4} 97.4"
            transform="rotate(-90 18 18)"/>
          <text x="18" y="20.8" text-anchor="middle" font-size="9.5" font-weight="800"
            fill="#e8ecf8" font-family="sans-serif">${r.overall}</text>
        </svg>
        <div>
          <b style="font-size:15px">${esc(r.band)}</b>
          <div class="muted" style="font-size:12.5px">${esc(r.verdict)}</div>
          <div class="muted" style="font-size:12px;margin-top:5px">
            strongest: <b>${esc(r.strongest_dimension || '—')}</b> ·
            weakest: <b>${esc(r.weakest_dimension || '—')}</b>
          </div>
        </div>
      </div>
      <div class="bars" style="margin-top:16px">
        ${order.filter(k => dims[k] !== undefined).map(k => `
          <div class="bar"><span>${k}</span>
            <span class="track"><span class="fill" style="width:${dims[k] * 10}%"></span></span>
            <span>${dims[k]}</span></div>`).join('')}
      </div>
      ${r.closing ? `<div class="banner" style="margin-top:14px">${esc(r.closing)}</div>` : ''}
    </div>

    <div class="grid cols-2">
      <div class="card">
        <h2>What to fix next</h2>
        <p class="sub">Generated from this session and your answer history.</p>
        <ul class="list">${(r.next_actions || []).map(a => `<li>${esc(a)}</li>`).join('')}</ul>
        ${(r.focus_plan || []).length ? `
          <div style="margin-top:14px">
            <div class="muted" style="font-size:11.5px;letter-spacing:.4px;margin-bottom:6px">FOCUS PLAN</div>
            ${r.focus_plan.map(f => `
              <div class="advice"><b>${esc(f.topic)}</b> (${f.avg_score}/10)<br>${esc(f.why)}</div>`).join('')}
          </div>` : ''}
      </div>

      <div class="card">
        <h2>Topic breakdown</h2>
        <p class="sub">Averaged from your scored answers.</p>
        ${(r.weak_topics || []).length ? `
          <div class="muted" style="font-size:11.5px;margin-bottom:5px">WEAK</div>
          ${r.weak_topics.map(t => `<div class="stat"><span>${esc(t.topic)}</span><b style="color:var(--bad)">${t.score}/10</b></div>`).join('')}` : ''}
        ${(r.strong_topics || []).length ? `
          <div class="muted" style="font-size:11.5px;margin:12px 0 5px">STRONG</div>
          ${r.strong_topics.map(t => `<div class="stat"><span>${esc(t.topic)}</span><b style="color:var(--good)">${t.score}/10</b></div>`).join('')}` : ''}
        ${!(r.weak_topics || []).length && !(r.strong_topics || []).length ? '<span class="muted">Not enough data yet.</span>' : ''}
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h2>Answer by answer</h2>
      <p class="sub">Every question, your answer, and what to change.</p>
      ${(r.per_turn || []).map(t => `
        <div style="border-top:1px solid var(--line);padding:13px 0">
          <div class="row" style="justify-content:space-between">
            <b style="font-size:13px">Q${t.seq}. ${esc(t.question)}</b>
            <b style="color:${BAND_COLOR(t.overall)}">${t.overall}/10</b>
          </div>
          <div class="muted" style="font-size:12.4px;margin:6px 0">Your answer: ${esc(t.answer)}</div>
          <ul class="list">${(t.improvements || []).map(i => `<li>${esc(i)}</li>`).join('')}</ul>
        </div>`).join('')}
    </div>

    <div class="card" style="margin-top:16px">
      <h2>Company intel used for this session</h2>
      <p class="sub">${prof.review_count || 0} reviews mined · felt difficulty ${prof.avg_difficulty_felt ?? '—'}/5</p>
      <div class="chips">
        ${(prof.hot_topics || []).slice(0, 9).map(h => `<span class="chip static">${esc(h.topic)} · ${h.mentions}</span>`).join('')}
      </div>
      ${(prof.advice || []).length ? `
        <div style="margin-top:12px">
          ${prof.advice.map(a => `<div class="advice">“${esc(a)}”</div>`).join('')}
        </div>` : ''}
      <div class="banner" style="margin-top:13px;font-size:12px">
        <b>The loop continues:</b> add a review for ${esc(r.company)} and the next student's mock will be weighted differently.
      </div>
    </div>
  `;
  window.scrollTo({ top: 0, behavior: 'smooth' });
  speak(r.closing);
}

/* ============================================================
   WIRING
   ============================================================ */
(async function boot() {
  initVoice();
  $('voicePill').innerHTML = `<span class="dot ${voiceSupported() ? '' : 'off'}"></span> voice ${voiceSupported() ? 'ready' : 'unsupported'}`;

  try {
    const h = await api('/api/health');
    $('enginePill').innerHTML = `<span class="dot ${h.llm.mode === 'llm' ? '' : 'off'}"></span> ${h.llm.mode === 'llm' ? esc(h.llm.model) : 'offline rubric engine'}`;
    $('modeNote').textContent = h.llm.mode === 'llm'
      ? 'LLM enabled: generative follow-ups and richer coaching.'
      : 'Running offline with a deterministic rubric engine — no API key needed. Set OPENAI_API_KEY to upgrade feedback.';
  } catch (e) { /* health is optional */ }

  $('voiceToggle').onclick = toggleVoiceMode;
  $('startBtn').onclick = startInterview;
  $('sendBtn').onclick = sendAnswer;
  $('micBtn').onclick = toggleMic;
  $('hintBtn').onclick = getHint;
  $('skipBtn').onclick = skipQuestion;
  $('endBtn').onclick = endInterview;
  $('rvSubmit').onclick = submitReview;
  $('rvDiff').dataset.value = 3;
  $('rvRate').dataset.value = 4;
  buildChips($('rvDiff'), 5, 3);
  buildChips($('rvRate'), 5, 4);

  $('answerBox').addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); sendAnswer(); }
  });
  $('roundSel').addEventListener('change', () => {
    if (S.company) loadProfile(S.company.name, $('roundSel').value);
  });

  try { await loadCompanies(); }
  catch (e) { toast('Could not reach the API: ' + e.message); }
})();
</script>
</body>
</html>

```

---

<!-- FILE: standalone/engine.js -->

<sub>30433 bytes</sub>

```javascript
/**
 * engine.js — the InterviewLoop engine, ported to plain JavaScript.
 *
 * This is a faithful port of app/scoring.py, app/feedback.py and app/engine.py
 * so the app can run with NO server and NO network (see standalone.html).
 * Keep the two in sync if you change scoring rules — the Python version is the
 * source of truth for the production API, this one powers the offline demo.
 *
 * Everything below is deliberately dependency-free.
 */

/* ============================== text utils ============================== */

const STOPWORDS = new Set(("a an the and or but if then than that this those these i me my we our you your " +
  "he she it they them was were is are am be been being do does did doing have has had " +
  "having will would should could can may might must not no nor so very too also just " +
  "about after again all any as at before both by during each few for from further how " +
  "into more most other out over same some such through to under until up what when where " +
  "which while who whom why with would asked ask asking question questions interview " +
  "interviewer panel round told tell said say says like really pretty totally got get " +
  "went go came come one two three four five minute minutes time day days make made " +
  "them there their they're we're i'm don't didn't it's he's she's very much lot lots " +
  "know knew think thought want wanted need needed give gave take took").split(" "));

function tokens(text) {
  return (String(text).toLowerCase().match(/[a-z0-9+#\-']+/g) || [])
    .filter(t => !STOPWORDS.has(t));
}

function keyConcepts(ideal, limit = 12) {
  const out = [];
  for (const t of tokens(ideal)) {
    if (t.length > 2 && !out.includes(t)) out.push(t);
  }
  return out.slice(0, limit);
}

function conceptCoverage(answer, ideal) {
  const concepts = keyConcepts(ideal);
  if (!concepts.length) return 0;
  const aTok = new Set(tokens(answer));
  const aFlat = tokens(answer).join(" ");
  let hits = 0;
  for (const c of concepts) {
    if (aTok.has(c) || aFlat.includes(c)) hits++;
    else if (c.length >= 5 && [...aTok].some(t => t.startsWith(c.slice(0, 5)))) hits++;
  }
  return hits / concepts.length;
}

function lexicalOverlap(answer, ideal) {
  const a = new Set(tokens(answer));
  const i = new Set(tokens(ideal));
  if (!i.size) return 0;
  let hit = 0;
  for (const t of a) if (i.has(t)) hit++;
  return Math.min(1, hit / Math.max(1, Math.min(i.size, 14)));
}

/** Approximation of Python's difflib.SequenceMatcher.ratio() via LCS. */
function lcsRatio(a, b) {
  if (!a.length || !b.length) return 0;
  const m = a.length, n = b.length;
  let prev = new Array(n + 1).fill(0);
  for (let i = 1; i <= m; i++) {
    const cur = new Array(n + 1).fill(0);
    for (let j = 1; j <= n; j++) {
      cur[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : Math.max(prev[j], cur[j - 1]);
    }
    prev = cur;
  }
  return (2 * prev[n]) / (m + n);
}

const REASON_RE = new RegExp(
  "\\b(because|since|so that|so i|so my|the reason|due to|which means|my goal|therefore|" +
  "hence|thus|as a result|supportive|comfortable with|that is why|for that reason)\\b", "i");
const NUMBER_RE = new RegExp(
  "\\b(\\d+|one|two|three|four|five|six|seven|eight|nine|ten|for example|for instance|" +
  "such as|in my college|during my|last year|at my|in my hostel)\\b", "i");

const STAR_MARKERS = ["situation", "task", "action", "result", "when i", "at that time",
  "i decided", "i built", "i led", "so i", "as a result", "finally", "the outcome",
  "we achieved", "i learned"];

const STRUCTURE_MARKERS = ["first", "second", "third", "then", "next", "finally", "because",
  "for example", "however", "on the other hand", "in short", "to summarise", "to summarize",
  "in conclusion", "so that"];

const HEDGES = ["maybe", "i think", "i guess", "not sure", "i don't know", "dont know",
  "kind of", "sort of", "probably", "somewhat", "i believe", "umm", "uhh", "actually i",
  "i'm not", "im not", "no idea", "not really"];

const FILLERS = ["basically", "actually", "you know", "like i said", "stuff",
  "things like that", "etc"];

const TECH_TERMS = new Set(("o(n) o(1) o(log n) time complexity space complexity hash map hashmap array " +
  "string pointer recursion iterative query index join primary key foreign key " +
  "normalization class object interface inheritance polymorphism thread process " +
  "memory cache api endpoint latency throughput scalable trade-off tradeoff " +
  "buffer queue stack tree graph heap algorithm function variable parameter " +
  "request response server client database table row column schema " +
  "acid transaction commit rollback idempotent concurrency lock mutex").split(" "));

const STORY_CUES = ["tell me about a time", "describe a time", "tell me about a situation",
  "describe a situation", "give me an example", "have you ever", "how did you handle",
  "share an experience", "tell me about an incident", "describe an incident",
  "when was a time"];

function questionKind(questionText) {
  const q = String(questionText || "").toLowerCase();
  return STORY_CUES.some(c => q.includes(c)) ? "story" : "direct";
}

function countMarkers(answer, markers) {
  const low = answer.toLowerCase();
  return markers.filter(m => low.includes(m)).length;
}

/* ============================== scoring ============================== */

const WEIGHTS_TECHNICAL = { coverage: 0.40, specificity: 0.20, structure: 0.15, depth: 0.15, confidence: 0.10 };
const WEIGHTS_BEHAVIOURAL = { coverage: 0.30, structure: 0.25, specificity: 0.20, depth: 0.15, confidence: 0.10 };

function band(score) {
  if (score >= 8.5) return ["Strong hire signal", "This would land well in a real interview."];
  if (score >= 7.0) return ["Good", "Solid answer. A little more structure would make it memorable."];
  if (score >= 5.5) return ["Borderline", "The idea is there but the delivery needs work."];
  if (score >= 3.5) return ["Weak", "The interviewer would likely move on. Revisit the fundamentals here."];
  return ["Needs work", "This needs rebuilding before you take a real interview."];
}

function scoreAnswer(answer, ideal, tags, roundName, difficulty, question) {
  answer = String(answer || "").trim();
  const words = answer ? answer.split(/\s+/) : [];
  const n = words.length;
  const low = answer.toLowerCase();

  if (n === 0) {
    return {
      overall: 0, dimensions: { coverage: 0, structure: 0, specificity: 0, depth: 0, confidence: 0 },
      flags: ["empty"], tags, strengths: [],
      improvements: ["You did not answer. In a real interview, say what you do know and think aloud — silence is scored worse than an imperfect attempt."],
      band: "No answer", verdict: "No answer recorded.", word_count: 0,
    };
  }

  const behavioural = roundName === "hr" || roundName === "behavioral";
  const kind = questionKind(question);

  const starHits = countMarkers(answer, STAR_MARKERS);
  const structHits = countMarkers(answer, STRUCTURE_MARKERS);

  // ---- coverage
  const concept = conceptCoverage(answer, ideal);
  const lex = lexicalOverlap(answer, ideal);
  const fuzz = lcsRatio(tokens(answer), tokens(ideal));
  let wordCoverage = Math.min(10, (0.70 * concept + 0.20 * lex + 0.10 * fuzz) * 14);
  if (n < 8) wordCoverage *= 0.5;
  if (n >= 30 && structHits >= 1 && wordCoverage < 4) wordCoverage = 4;

  let coverage;
  if (behavioural && kind === "story") {
    const numbersB = /\b\d+/.test(answer) ? 1 : 0;
    const resultB = /\b(result|outcome|so we|which led|impact|reduced|increased|learned|finally)\b/.test(low) ? 1 : 0;
    const ownership = /\bi (decided|built|led|fixed|proposed|owned|took|asked|changed)\b/.test(low) ? 1 : 0;
    const story = Math.min(10, 2.5 + 1.3 * Math.min(starHits, 4) + 2.0 * numbersB + 2.0 * resultB + 1.5 * ownership);
    coverage = round2(0.65 * story + 0.35 * wordCoverage);
  } else if (behavioural) {
    let direct = 0;
    if (/^\s*(yes|no|definitely|absolutely|i am|i would|i have|i do|i will|i prefer|i believe)/.test(low)) direct = 1;
    else if (/\b(yes|no|comfortable|willing|open to|ready to|i am not)\b/.test(low)) direct = 1;
    const reason = REASON_RE.test(answer) ? 1 : 0;
    const concrete = NUMBER_RE.test(answer) ? 1 : 0;
    const fillerOnly = n < 12 ? 1 : 0;
    const pos = Math.min(10, 2.0 + 2.6 * direct + 2.4 * reason + 2.4 * concrete - 2.0 * fillerOnly);
    coverage = round2(0.86 * pos + 0.14 * wordCoverage);
  } else {
    coverage = wordCoverage;
  }

  // ---- structure
  let structure;
  if (behavioural && kind === "story") {
    structure = Math.min(10, 3.0 + 1.6 * starHits + 1.1 * structHits);
  } else if (behavioural) {
    structure = Math.min(10, 6.0 + 1.1 * structHits + 1.0 * starHits);
  } else {
    const tradeoff = /\b(trade-?off|however|but |whereas|o\(|complexity|downside)\b/.test(low) ? 1 : 0;
    structure = Math.min(10, 5.0 + 1.4 * structHits + 1.2 * starHits + 1.0 * tradeoff);
  }

  // ---- specificity
  const numbers = (answer.match(/\b\d+(?:\.\d+)?\b/g) || []).length;
  const tech = [...TECH_TERMS].filter(t => low.includes(t)).length;
  const examples = /\b(for example|e\.g\.|such as|instance|say)\b/.test(low) ? 1 : 0;
  const specificity = Math.min(10, 2.0 + 1.5 * numbers + 1.0 * Math.min(tech, 4) + 2.0 * examples);

  // ---- depth
  let idealLen, span;
  if (behavioural && kind === "story") { idealLen = 70; span = 130; }
  else if (behavioural) { idealLen = 45; span = 90; }
  else { idealLen = 55; span = 110; }
  let depth = 10 - Math.min(8, Math.abs(n - idealLen) / span * 6);
  depth = Math.max(2, depth);

  // ---- confidence
  const hedges = countMarkers(answer, HEDGES);
  const fillers = countMarkers(answer, FILLERS);
  const confidence = Math.max(1, 10 - 2.2 * hedges - 1.2 * fillers);

  const dims = {
    coverage: round1(coverage), structure: round1(structure),
    specificity: round1(specificity), depth: round1(depth), confidence: round1(confidence),
  };
  const weights = behavioural ? WEIGHTS_BEHAVIOURAL : WEIGHTS_TECHNICAL;
  let overall = Object.keys(dims).reduce((s, k) => s + dims[k] * weights[k], 0);
  if (difficulty >= 4) overall *= 0.95;
  overall = round1(Math.max(0, Math.min(10, overall)));

  // ---- narrative
  const strengths = [], improvements = [];

  if (behavioural && kind === "direct") {
    if (dims.coverage >= 7) strengths.push("Clear position, a reason, and something concrete — exactly what this round scores.");
    else improvements.push("Answer in three beats: your position ('Yes, I am'), your reason, and one concrete detail from your life.");
  } else {
    if (dims.coverage >= 7) strengths.push("You hit most of the concepts the interviewer was listening for.");
    else if (dims.coverage <= 4) improvements.push("Key concepts were missing. Say the definition first, then one concrete example.");
    else improvements.push("You touched the right idea but left out part of it — being complete is what separates a 6 from an 8.");
  }

  if (behavioural && kind === "story") {
    if (starHits >= 3) strengths.push("Your answer had a clear Situation-Action-Result flow.");
    else improvements.push("Use STAR explicitly: Situation (1 line), Task, the Actions *you* took, then the Result with a number.");
  } else if (behavioural) {
    if (!REASON_RE.test(answer)) improvements.push("Give your answer, then a reason. 'Yes, and here is why' is what makes it credible.");
    else if (dims.specificity < 6) improvements.push("Back the reason with something concrete — a number, a city, a past experience.");
    else strengths.push("Clear position with a reason — exactly what an HR round scores.");
  } else {
    if (dims.structure >= 7) strengths.push("Logical, easy-to-follow progression.");
    else improvements.push("Structure the answer: definition, then how it works, then an example, then the trade-off.");
  }

  if (dims.specificity >= 7) strengths.push("Concrete details and technical vocabulary — interviewers can tell you have used this.");
  else improvements.push("Add specifics: a number, a real example, or the exact term the interviewer expects.");

  if (n < 25) improvements.push("Too short. Aim for 30-60 seconds; a one-line answer reads as unprepared.");
  if (n > 260) improvements.push("Too long — you will lose the interviewer. Cut to the core and offer detail if asked.");
  if (hedges >= 2) improvements.push("You hedged several times ('maybe', 'I think'). State your answer, then qualify it if needed.");
  if (!strengths.length) strengths.push("You engaged with the question — that is the right instinct to build on.");

  const flags = [];
  if (dims.coverage <= 4) flags.push("missing_concepts");
  if (n < 25) flags.push("too_short");
  if (n > 260) flags.push("rambling");
  if (hedges >= 2) flags.push("hedging");
  if (dims.specificity <= 4) flags.push("no_specifics");
  if (dims.structure <= 4) flags.push("no_structure");

  const [bnd, verdict] = band(overall);
  return {
    overall, dimensions: dims, flags, tags, strengths: strengths.slice(0, 3),
    improvements: improvements.slice(0, 3), band: bnd, verdict, word_count: n,
  };
}

const round1 = x => Math.round(x * 10) / 10;
const round2 = x => Math.round(x * 100) / 100;

/* ======================= review mining (loop 1) ======================= */

const TOPIC_SYNONYMS = {
  "sql": ["sql", "query", "queries", "select", "database query"],
  "joins": ["join", "joins", "left join", "inner join"],
  "dbms": ["dbms", "database", "normalization", "normalisation", "normal form", "3nf", "2nf", "acid"],
  "index": ["index", "indexing", "indexes", "b-tree", "btree"],
  "oop": ["oop", "oops", "object oriented", "class", "inheritance", "polymorphism"],
  "dsa": ["dsa", "algorithm", "algorithms", "coding", "code", "problem solving", "leetcode"],
  "arrays": ["array", "arrays", "subarray", "sliding window"],
  "strings": ["string", "strings", "palindrome", "anagram", "reverse a string"],
  "linked-list": ["linked list", "linkedlist"],
  "trees": ["tree", "binary tree", "bst", "traversal", "level order"],
  "heaps": ["heap", "heaps", "median", "priority queue"],
  "hashing": ["hash", "hashing", "hashmap", "hash map"],
  "recursion": ["recursion", "recursive", "backtracking"],
  "binary-search": ["binary search", "searching"],
  "dp": ["dynamic programming", "kadane", "memoization"],
  "system-design": ["system design", "design a", "hld", "lld", "scalability", "scaling"],
  "caching": ["cache", "caching", "redis", "cdn"],
  "concurrency": ["concurrency", "concurrent", "thread", "threads", "lock", "locking", "race condition"],
  "os": ["os", "operating system", "process", "deadlock", "memory management", "stack vs heap"],
  "networking": ["networking", "network", "tcp", "udp", "dns", "http", "url", "tls"],
  "api": ["api", "rest", "endpoint", "idempotency", "idempotent", "microservice"],
  "java": ["java", "jvm", "jre", "equals", "string pool"],
  "python": ["python", "tuple", "list comprehension"],
  "c": ["c language", "c programming", "struct", "union", "pointer arithmetic"],
  "pointers": ["pointer", "pointers"],
  "project": ["project", "projects", "final year project", "capstone", "resume project"],
  "resume": ["resume", "cv"],
  "intro": ["tell me about yourself", "introduce yourself", "introduction", "about yourself"],
  "why-company": ["why tcs", "why infosys", "why wipro", "why our company", "why do you want to join"],
  "relocation": ["relocate", "relocation", "any location", "another city", "shift", "rotational", "night shift"],
  "bond": ["bond", "service agreement", "service bond", "contract"],
  "star": ["star", "situation task action result", "situation", "situational"],
  "behavioral": ["behavioural", "behavioral", "situational", "scenario"],
  "conflict": ["conflict", "disagree", "disagreement", "argument", "teammate"],
  "teamwork": ["teamwork", "team", "group", "collaboration"],
  "leadership-principle": ["leadership principle", "leadership principles", "ownership", "customer obsession"],
  "ownership": ["ownership", "own the", "responsibility", "not my job"],
  "deadline": ["deadline", "tight deadline", "delay", "delayed", "pressure"],
  "failure": ["fail", "failure", "failed", "mistake", "went wrong"],
  "self-awareness": ["weakness", "strength", "improve", "feedback", "rejected", "not selected"],
  "career": ["five years", "5 years", "career", "future", "growth", "promotion"],
  "communication": ["communication", "english", "speak", "speaking", "confidence", "confident", "fluency"],
  "pseudo-code": ["pseudo code", "pseudocode", "pseudo-code", "dry run", "trace"],
  "aptitude": ["aptitude", "quantitative", "reasoning", "logical", "puzzle"],
  "complexity": ["complexity", "time complexity", "space complexity", "big o"],
  "edge-cases": ["edge case", "edge cases", "corner case"],
  "core": ["core java", "fundamentals", "basics", "theory"],
};

function extractTopics(text) {
  const low = " " + String(text).toLowerCase() + " ";
  const found = new Set();
  for (const [tag, phrases] of Object.entries(TOPIC_SYNONYMS)) {
    for (const p of phrases) {
      const esc = p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      if (new RegExp("(?<![a-z0-9])" + esc + "(?![a-z0-9])").test(low)) { found.add(tag); break; }
    }
  }
  return found;
}

const ADVICE_MARKERS = ["my advice", "advice", "prepare", "revise", "be ready", "keep ready",
  "important", "make sure", "do mention", "do not", "don't", "always", "must", "remember",
  "practice", "focus on"];

function recencyWeight(createdAt, halfLifeDays = 90) {
  const t = new Date(createdAt).getTime();
  if (isNaN(t)) return 1;
  const ageDays = Math.max(0, (Date.now() - t) / 86400000);
  return Math.pow(0.5, ageDays / halfLifeDays);
}

/** Mine reviews into a company profile. Mirrors feedback.company_profile(). */
function companyProfile(state, company, roundName) {
  let reviews = state.reviews.filter(r => r.company === company && (!roundName || r.round === roundName));
  let blended = false;
  if (roundName && reviews.length < 3) {
    const wide = state.reviews.filter(r => r.company === company);
    if (wide.length > reviews.length) { reviews = wide; blended = true; }
  }

  const topicScore = {}, advice = {}, diffs = [], ratings = [];
  for (const r of reviews) {
    const w = recencyWeight(r.created_at);
    diffs.push([r.difficulty_felt, w]);
    ratings.push([r.rating, w]);
    for (const tag of extractTopics(r.text)) topicScore[tag] = (topicScore[tag] || 0) + w;
    for (const sentence of r.text.split(/(?<=[.!?])\s+/)) {
      const s = sentence.trim();
      if (s.length < 15) continue;
      if (ADVICE_MARKERS.some(m => s.toLowerCase().includes(m))) {
        advice[s] = (advice[s] || 0) + 1;
      }
    }
  }

  const totalW = diffs.reduce((s, [, w]) => s + w, 0) || 1;
  const felt = diffs.length ? round2(diffs.reduce((s, [d, w]) => s + d * w, 0) / totalW) : null;
  const rating = ratings.length ? round2(ratings.reduce((s, [v, w]) => s + v * w, 0) / totalW) : null;

  const hotTopics = Object.entries(topicScore)
    .sort((a, b) => b[1] - a[1]).slice(0, 12)
    .map(([topic, mentions]) => ({ topic, mentions: round2(mentions) }));

  const covered = new Set();
  for (const q of state.questions) {
    if (q.company === company && (!roundName || q.round === roundName)) {
      String(q.tags || "").split(",").filter(Boolean).forEach(t => covered.add(t));
    }
  }
  const gaps = hotTopics.filter(h => !covered.has(h.topic)).slice(0, 5).map(h => h.topic);

  const adviceList = Object.entries(advice).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([a]) => a);

  return {
    company, round: roundName || null, review_count: reviews.length, blended_company_wide: blended,
    avg_difficulty_felt: felt, avg_rating: rating, hot_topics: hotTopics,
    advice: adviceList, coverage_gaps: gaps, sample_quotes: reviews.slice(0, 3).map(r => r.text),
  };
}

function topicWeights(state, company, roundName) {
  const prof = companyProfile(state, company, roundName);
  if (!prof.hot_topics.length) return {};
  const top = prof.hot_topics[0].mentions || 1;
  const out = {};
  for (const h of prof.hot_topics) out[h.topic] = h.mentions / top;
  return out;
}

/* ==================== student profile (loop 2) ==================== */

function studentWeakTags(state, studentName, lastN = 5) {
  const sessions = state.sessions.filter(s => s.student_name === studentName).slice(-lastN);
  const totals = {}, counts = {};
  for (const s of sessions) {
    for (const t of s.turns) {
      const tags = String(t.score.tags || "").split(",").filter(Boolean);
      for (const tag of tags) {
        totals[tag] = (totals[tag] || 0) + t.score.overall;
        counts[tag] = (counts[tag] || 0) + 1;
      }
    }
  }
  const out = {};
  for (const tag of Object.keys(totals)) out[tag] = round2(totals[tag] / counts[tag]);
  return out;
}

const TOPIC_HINTS = {
  "sql": "Write 10 queries by hand: joins, GROUP BY with HAVING, subqueries, window functions. Say the query aloud as you write it.",
  "dbms": "Be able to draw 1NF -> 2NF -> 3NF on a whiteboard with a concrete table and name the anomaly each form removes.",
  "joins": "Practise the LEFT JOIN 'find rows with no match' pattern — it is the most commonly asked follow-up.",
  "index": "Explain the B-tree lookup and then immediately state the write cost and low-cardinality caveat.",
  "oop": "Prepare one running example (e.g. Payment/PaymentMethod) and explain all four pillars through it.",
  "dsa": "Solve 3 problems a day out loud. Always state brute force, then optimise, then complexity.",
  "complexity": "For every answer, end with 'time is O(...) because ..., space is O(...) because ...'.",
  "system-design": "Use a fixed skeleton: requirements -> scale estimate -> API -> data model -> components -> bottlenecks.",
  "concurrency": "Learn lock ordering, atomic operations and optimistic vs pessimistic concurrency with one example each.",
  "os": "Revise process vs thread, deadlock's four conditions, and stack vs heap with diagrams.",
  "networking": "Trace a URL request end to end until you can do it in 60 seconds without notes.",
  "project": "Rehearse a 90-second project pitch: problem, your exact modules, hardest bug, measurable result.",
  "relocation": "Decide your honest answer now and say it in one confident sentence. Hesitation is what gets marked down.",
  "bond": "Know your stance on the service agreement and state it without hedging.",
  "star": "Write 5 STAR stories (conflict, failure, leadership, deadline, learning) with numbers, and reuse them.",
  "behavioral": "Prepare stories, not adjectives. Every claim needs a specific incident behind it.",
  "communication": "Record yourself answering 'tell me about yourself' and cut every filler word.",
  "self-awareness": "Have a real weakness with the concrete action you took and the evidence it improved.",
  "pseudo-code": "Practise dry-running loops on paper with a variable table — write each iteration down.",
  "core": "Revise definitions until you can give a one-line answer plus a one-line example.",
};

function focusPlan(state, studentName) {
  const weak = studentWeakTags(state, studentName);
  const ordered = Object.entries(weak).sort((a, b) => a[1] - b[1]);
  const plan = [], seen = new Set();
  for (const [tag, sc] of ordered) {
    if (sc >= 6.5 || seen.has(round1(sc))) continue;
    seen.add(round1(sc));
    if (plan.length >= 3) break;
    plan.push({ topic: tag, avg_score: sc,
      why: TOPIC_HINTS[tag] || "Revise the fundamentals and practise explaining this aloud in two minutes." });
  }
  return plan;
}

/* ======================== selection & adaptivity ======================== */

function nextTargetDifficulty(historyScores, start = 2.5) {
  if (!historyScores.length) return start;
  const recent = historyScores.slice(-2);
  const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
  if (avg >= 7.5) return Math.min(5, start + 1);
  if (avg >= 5.5) return start;
  return Math.max(1, start - 0.75);
}

function questionsFor(state, company, roundName) {
  const own = state.questions.filter(q => q.company === company && q.round === roundName);
  const generic = company !== "Generic Fresher"
    ? state.questions.filter(q => q.company === "Generic Fresher" && q.round === roundName) : [];
  const seen = new Set(), out = [];
  for (const q of [...own, ...generic]) {
    if (seen.has(q.text)) continue;
    seen.add(q.text);
    out.push({ ...q, is_generic: q.company === "Generic Fresher" });
  }
  return out;
}

function rankQuestions(state, questions, company, roundName, targetDifficulty, weakTags, askedIds) {
  const tw = topicWeights(state, company, roundName);
  const weak = weakTags || {};
  const ranked = [];
  for (const q of questions) {
    if (askedIds && askedIds.has(q.id)) continue;
    const tags = String(q.tags || "").split(",").filter(Boolean);
    const reviewMatch = Math.max(0, ...tags.map(t => tw[t] || 0));
    let weakMatch = 0;
    if (Object.keys(weak).length) {
      weakMatch = Math.max(0, ...tags.filter(t => weak[t] !== undefined).map(t => Math.max(0, (6 - weak[t]) / 6)));
    }
    const diffFit = Math.max(0, 1 - Math.abs(q.difficulty - targetDifficulty) / 3);
    const freshness = 1 / (1 + (q.times_asked || 0));
    const score = 0.45 * reviewMatch + 0.25 * weakMatch + 0.20 * diffFit + 0.10 * freshness;
    ranked.push({ score, q, why: {
      review_match: round2(reviewMatch), weak_area_match: round2(weakMatch),
      difficulty_fit: round2(diffFit), freshness: round2(freshness) } });
  }
  ranked.sort((a, b) => b.score - a.score);
  return ranked;
}

/* ========================== session summary ========================== */

function dedupe(rows) {
  const seen = {}, out = [];
  for (const r of rows) {
    const k = round1(r.score);
    if (seen[k]) continue;
    seen[k] = 1;
    out.push(r);
  }
  return out;
}

function summariseSession(turns) {
  if (!turns.length) return { overall: 0, dimensions: {}, band: "No answers", turns: 0, verdict: "" };

  const dims = {};
  for (const k of Object.keys(WEIGHTS_TECHNICAL)) {
    dims[k] = round1(turns.reduce((s, t) => s + (t.score.dimensions[k] || 0), 0) / turns.length);
  }
  const overall = round1(turns.reduce((s, t) => s + t.score.overall, 0) / turns.length);
  const [bnd, verdict] = band(overall);

  const entries = Object.entries(dims).sort((a, b) => b[1] - a[1]);
  const strongest = entries[0][0], weakest = entries[entries.length - 1][0];

  const tagTotals = {};
  for (const t of turns) {
    for (const tag of String(t.score.tags || "").split(",").filter(Boolean)) {
      (tagTotals[tag] = tagTotals[tag] || []).push(t.score.overall);
    }
  }
  const tagAvgs = Object.entries(tagTotals)
    .map(([t, v]) => [t, round1(v.reduce((a, b) => a + b, 0) / v.length)])
    .sort((a, b) => a[1] - b[1]);

  const weakTopics = dedupe(tagAvgs.filter(([, s]) => s < 6.5).map(([t, s]) => ({ topic: t, score: s }))).slice(0, 3);
  const strongTopics = dedupe([...tagAvgs].reverse().filter(([, s]) => s >= 7).map(([t, s]) => ({ topic: t, score: s }))).slice(0, 3);

  const nextActions = [];
  const tips = {
    coverage: "Build a one-page cheat sheet per topic: definition, mechanism, example, trade-off. Cover all four in every answer.",
    structure: "Answer with a fixed template: what it is, how it works, an example, the trade-off. Rehearse it 5 times.",
    specificity: "Attach a number or a named example to every claim. 'Improved latency from 800ms to 200ms' beats 'it was faster'.",
    depth: "Time yourself: 45-75 seconds for technical, 90-120 seconds for behavioural. Cut anything that is not evidence.",
    confidence: "Remove 'maybe', 'I think', 'sort of'. Say the answer, then add a condition if you must.",
  };
  if (tips[weakest]) nextActions.push(tips[weakest]);
  const seenScores = new Set();
  for (const [tag, sc] of tagAvgs) {
    if (sc >= 6.5 || seenScores.has(round1(sc))) continue;
    if (nextActions.filter(a => a.includes("Weak area")).length >= 2) break;
    seenScores.add(round1(sc));
    nextActions.push(`Weak area '${tag}' scored ${sc}/10 — do 3 short written answers on it before your next mock.`);
  }
  if (!nextActions.length) nextActions.push("Good baseline. Next session, attempt the same company at a harder difficulty.");

  return {
    overall, band: bnd, verdict, turns: turns.length, dimensions: dims,
    strongest_dimension: strongest, weakest_dimension: weakest,
    weak_topics: weakTopics, strong_topics: strongTopics,
    per_turn: turns.map(t => ({
      seq: t.seq, question: t.question, answer: t.answer,
      overall: t.score.overall, verdict: t.score.verdict, improvements: t.score.improvements,
    })),
    next_actions: nextActions.slice(0, 4),
  };
}

/* ============================ offline "LLM" ============================ */

const ROUND_LABELS = {
  aptitude: "aptitude", technical: "technical", hr: "HR",
  behavioral: "behavioural", dsa: "DSA", system_design: "system design",
};
const roundLabel = r => ROUND_LABELS[String(r || "").toLowerCase()] || String(r || "").replace(/_/g, " ");

const Offline = {
  intro(company, roundName, studentName, n) {
    return `Hi ${studentName}, thanks for joining. I will be running your ${roundLabel(roundName)} round for ${company} today — ${n} questions, and I would like you to think aloud. Take your time and answer in your own words.`;
  },
  coaching(score) {
    return (score.improvements || []).slice(0, 2).join(" ");
  },
  probe(score) {
    if (score.overall < 4.5) return null;
    if (score.flags.includes("no_specifics")) return "Can you give me a concrete example where that mattered?";
    if (score.flags.includes("missing_concepts")) return "What is the trade-off of that approach?";
    if (score.dimensions.coverage >= 7.5) return "How would that change if you had to scale it ten times?";
    return null;
  },
  hint(ideal) {
    const first = String(ideal).split(".")[0];
    return "Start with: " + first.split(/\s+/).slice(0, 12).join(" ") + "... (now complete it in your own words)";
  },
  closing(overall) {
    let tail;
    if (overall >= 7) tail = "That was a confident round — keep this level and work on the small details.";
    else if (overall >= 5) tail = "You have the right instincts; structure and specificity are what to fix next.";
    else tail = "You are early in preparation, which is fine. Fix the fundamentals topic by topic.";
    return `That is the end of the round. ${tail}`;
  },
};

```

---

<!-- FILE: standalone/template.html -->

<sub>39277 bytes</sub>

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>InterviewLoop — Company-Specific Mock Interviews</title>
<style>
  :root{
    --bg:#0b1020; --panel:#131a30; --panel2:#1a2340; --line:#26304f;
    --text:#e8ecf8; --muted:#93a0c2; --accent:#6c8cff; --accent2:#22d3a6;
    --warn:#ffb020; --bad:#ff5c7a; --good:#22d3a6; --radius:16px;
  }
  *{box-sizing:border-box}
  body{margin:0;background:radial-gradient(1200px 600px at 80% -10%,#1c2a55 0%,var(--bg) 55%);
    color:var(--text);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;min-height:100vh}
  .wrap{max-width:1120px;margin:0 auto;padding:22px 18px 70px}
  header{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:6px 0 20px;flex-wrap:wrap}
  .brand{display:flex;align-items:center;gap:11px}
  .logo{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,var(--accent),var(--accent2));
    display:grid;place-items:center;font-weight:800;font-size:17px;color:#08102a}
  .brand h1{font-size:17px;margin:0;letter-spacing:.2px}
  .brand p{margin:0;font-size:12px;color:var(--muted)}
  .pill{font-size:11.5px;padding:5px 11px;border-radius:999px;border:1px solid var(--line);
    background:var(--panel);color:var(--muted);display:inline-flex;align-items:center;gap:7px}
  .dot{width:7px;height:7px;border-radius:50%;background:var(--good);box-shadow:0 0 9px var(--good)}
  .dot.off{background:var(--warn);box-shadow:0 0 9px var(--warn)}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:20px}
  .grid{display:grid;gap:16px}
  .cols-2{grid-template-columns:1.15fr .85fr}
  @media(max-width:880px){.cols-2{grid-template-columns:1fr}}
  h2{font-size:15px;margin:0 0 4px;letter-spacing:.3px}
  .sub{color:var(--muted);font-size:12.5px;margin:0 0 15px}
  label{display:block;font-size:12px;color:var(--muted);margin:0 0 6px;font-weight:600;letter-spacing:.3px}
  input,select,textarea{width:100%;background:var(--panel2);border:1px solid var(--line);color:var(--text);
    border-radius:10px;padding:11px 12px;font:inherit;outline:none;transition:border .15s}
  input:focus,select:focus,textarea:focus{border-color:var(--accent)}
  textarea{resize:vertical;min-height:96px;line-height:1.55}
  button{font:inherit;font-weight:650;border-radius:10px;border:1px solid transparent;cursor:pointer;
    padding:11px 17px;transition:transform .12s,filter .15s;color:#08102a;
    background:linear-gradient(135deg,var(--accent),#8aa2ff)}
  button:hover{transform:translateY(-1px);filter:brightness(1.07)}
  button:disabled{opacity:.45;cursor:not-allowed;transform:none}
  button.ghost{background:transparent;color:var(--text);border-color:var(--line)}
  button.good{background:linear-gradient(135deg,var(--accent2),#4ee0bb)}
  button.small{padding:7px 12px;font-size:12.5px;border-radius:9px}
  .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  .chips{display:flex;gap:8px;flex-wrap:wrap}
  .chip{font-size:12px;padding:6px 11px;border-radius:999px;border:1px solid var(--line);
    background:var(--panel2);color:var(--muted);cursor:pointer;user-select:none}
  .chip.on{border-color:var(--accent);color:#cdd8ff;background:#1e2a52}
  .chip.static{cursor:default}
  .company-card{border:1px solid var(--line);background:var(--panel2);border-radius:13px;padding:13px;
    cursor:pointer;transition:.15s}
  .company-card:hover{border-color:#3a4880;transform:translateY(-1px)}
  .company-card.on{border-color:var(--accent);background:#1b2650;box-shadow:0 0 0 1px var(--accent) inset}
  .company-card .nm{font-weight:700;font-size:13.5px;display:flex;justify-content:space-between;gap:8px}
  .company-card .meta{font-size:11.5px;color:var(--muted);margin-top:5px}
  .tag{font-size:10.5px;padding:2px 8px;border-radius:999px;background:#233060;color:#a9baff}
  .tag.prod{background:#123f34;color:#6ee7c0}
  .score-ring{width:64px;height:64px;flex:0 0 auto}
  .stat{display:flex;justify-content:space-between;font-size:12.5px;padding:7px 0;border-bottom:1px dashed #222c4a}
  .stat:last-child{border:0}
  .muted{color:var(--muted)}
  .chat{display:flex;flex-direction:column;gap:13px;max-height:52vh;overflow-y:auto;padding-right:5px}
  .msg{display:flex;gap:10px;animation:in .25s ease}
  @keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
  .msg .av{width:29px;height:29px;border-radius:9px;flex:0 0 auto;display:grid;place-items:center;font-size:12px;font-weight:800}
  .msg.bot .av{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#08102a}
  .msg.me .av{background:#2b3766;color:#c6d2f7}
  .bubble{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:11px 14px;font-size:14px;max-width:94%}
  .msg.me .bubble{background:#1d2a52;border-color:#2c3a66}
  .msg.me{align-self:flex-end;flex-direction:row-reverse}
  .scorebox{border-radius:12px;padding:13px 15px;border:1px solid var(--line);background:var(--panel2);margin-top:12px}
  .scorebox .top{display:flex;align-items:center;gap:14px}
  .scorebox .n{font-size:26px;font-weight:800;line-height:1}
  .bars{display:grid;gap:6px;margin-top:11px}
  .bar{display:grid;grid-template-columns:96px 1fr 34px;gap:9px;align-items:center;font-size:11.5px;color:var(--muted)}
  .track{display:block;height:6px;background:#212c4d;border-radius:99px;overflow:hidden}
  .fill{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
  .list{margin:7px 0 0;padding-left:17px;font-size:12.8px;color:#c3cde9}
  .list li{margin:4px 0}
  .banner{border-radius:11px;padding:11px 13px;font-size:12.6px;border:1px solid var(--line);background:var(--panel2)}
  .banner.hot{border-color:#3a4a86;background:#1a2350;color:#c3d1ff}
  .banner.warn{border-color:#5a4520;background:#2a2214;color:#ffd591}
  .mic{position:relative}
  .mic.rec{background:linear-gradient(135deg,var(--bad),#ff8aa0);animation:pulse 1.4s infinite}
  @keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,92,122,.5)}50%{box-shadow:0 0 0 12px rgba(255,92,122,0)}}
  .hide{display:none!important}
  .kbd{font-size:11px;border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:1px 6px;color:var(--muted)}
  .foot{color:var(--muted);font-size:11.5px;text-align:center;margin-top:26px;line-height:1.7}
  .advice{font-size:12.4px;color:#b9c6e8;border-left:3px solid var(--accent);padding-left:11px;margin:9px 0}
  .review{border-bottom:1px dashed #222c4a;padding:9px 0;font-size:12.6px}
  .review:last-child{border:0}
  .stars{color:var(--warn);letter-spacing:1px;font-size:11px}
  .progress{height:4px;background:#212c4d;border-radius:99px;overflow:hidden;margin:12px 0}
  .progress i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .3s}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#1d2a52;border:1px solid var(--line);
    padding:10px 16px;border-radius:10px;font-size:13px;z-index:99;animation:in .2s;max-width:90vw;text-align:center}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand">
      <div class="logo">IL</div>
      <div>
        <h1>InterviewLoop</h1>
        <p>Company-specific mock interviews that learn from every review</p>
      </div>
    </div>
    <div class="row">
      <span class="pill"><span class="dot"></span> offline engine</span>
      <span class="pill" id="voicePill"><span class="dot off"></span> voice off</span>
    </div>
  </header>

  <section id="setup">
    <div class="grid cols-2">
      <div class="card">
        <h2>Start a mock interview</h2>
        <p class="sub">Pick a company. The bot weights questions by what past students reported — not a generic syllabus.</p>
        <div style="margin-bottom:14px">
          <label for="studentName">Your name</label>
          <input id="studentName" placeholder="e.g. Ananya" autocomplete="off" />
        </div>
        <label>Choose a company</label>
        <div id="companyGrid" class="grid" style="grid-template-columns:1fr 1fr;gap:9px;margin-bottom:15px"></div>
        <div class="row" style="justify-content:space-between;align-items:flex-end">
          <div style="flex:1;min-width:170px">
            <label for="roundSel">Round</label>
            <select id="roundSel"></select>
          </div>
          <div style="flex:0 0 118px">
            <label for="lenSel">Length</label>
            <select id="lenSel">
              <option value="3">3 questions</option>
              <option value="4" selected>4 questions</option>
              <option value="5">5 questions</option>
            </select>
          </div>
        </div>
        <div class="row" style="margin-top:16px">
          <button id="startBtn" class="good">Start interview →</button>
          <button class="ghost small" id="voiceToggle">🎙 Voice mode: off</button>
        </div>
        <p class="sub" style="margin:12px 0 0" id="modeNote"></p>
      </div>

      <div class="card">
        <h2>Company intel</h2>
        <p class="sub">Mined live from student reviews.</p>
        <div id="profBody" class="muted" style="font-size:13px">Select a company to see what recent candidates reported.</div>
      </div>
    </div>

    <div class="grid cols-2" style="margin-top:16px">
      <div class="card">
        <h2>Add your review</h2>
        <p class="sub">This is the learning loop. Your review immediately reshapes how this company's interviews are generated.</p>
        <div class="row" style="margin-bottom:10px">
          <div style="flex:1;min-width:120px">
            <label for="rvCompany">Company</label>
            <select id="rvCompany"></select>
          </div>
          <div style="flex:0 0 130px">
            <label for="rvRound">Round</label>
            <select id="rvRound"></select>
          </div>
        </div>
        <div class="row" style="margin-bottom:10px">
          <div style="flex:1">
            <label>How hard did it feel?</label>
            <div class="chips" id="rvDiff"></div>
          </div>
          <div style="flex:1">
            <label>Your rating</label>
            <div class="chips" id="rvRate"></div>
          </div>
        </div>
        <label for="rvText">What did they actually ask?</label>
        <textarea id="rvText" placeholder="They drilled SQL joins for 20 minutes, then asked about my project. Advice: revise DBMS properly."></textarea>
        <div class="row" style="margin-top:11px">
          <button id="rvSubmit">Submit review</button>
          <span class="muted" style="font-size:12px">Saved in this browser only</span>
        </div>
      </div>

      <div class="card">
        <h2>Recent reviews</h2>
        <p class="sub" id="rvSub">What candidates said</p>
        <div id="rvList" style="max-height:270px;overflow-y:auto"></div>
        <div class="row" style="margin-top:12px">
          <button class="ghost small" id="resetBtn">Reset demo data</button>
        </div>
      </div>
    </div>
  </section>

  <section id="interview" class="hide">
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <div>
          <h2 id="ivTitle">Interview</h2>
          <p class="sub" id="ivSub" style="margin:2px 0 0"></p>
        </div>
        <div class="row">
          <button class="ghost small" id="hintBtn">💡 Hint</button>
          <button class="ghost small" id="skipBtn">Skip</button>
          <button class="ghost small" id="endBtn">End & see report</button>
        </div>
      </div>
      <div class="progress"><i id="progBar" style="width:0%"></i></div>
      <div class="chat" id="chat"></div>
      <div style="margin-top:14px">
        <label for="answerBox">Your answer <span class="muted" id="answerHint">— speak or type. Think aloud.</span></label>
        <textarea id="answerBox" placeholder="Type your answer, or press the mic and speak…"></textarea>
        <div class="row" style="margin-top:10px;justify-content:space-between">
          <div class="row">
            <button class="mic" id="micBtn">🎙 Speak</button>
            <button class="good" id="sendBtn">Send answer</button>
          </div>
          <span class="muted" style="font-size:11.5px"><span class="kbd">Ctrl</span> + <span class="kbd">Enter</span> to send</span>
        </div>
      </div>
    </div>
  </section>

  <section id="report" class="hide"></section>

  <p class="foot">
    InterviewLoop · single-file offline edition · curated question bank + rubric scoring + two learning loops<br>
    No server, no API key, no network. All data stays in this browser.
  </p>
</div>

<script>
/* ===================== VOICE ENGINE (inlined at build time) ===================== */
__VOICE_JS__
</script>
<script>
/* ===================== DATA (inlined at build time) ===================== */
const QUESTIONS = __QUESTIONS__;
const SEED_REVIEWS = __REVIEWS__;
const COMPANIES = __COMPANIES__;

/* ===================== ENGINE (inlined at build time) ==================== */
__ENGINE__

/* ============================== STATE ============================== */
const STORE_KEY = 'interviewloop_state_v1';

function freshState() {
  return {
    questions: QUESTIONS.map((q, i) => ({
      id: i + 1,
      company: q.company || 'Generic Fresher',
      round: q.round,
      text: q.text,
      ideal: q.ideal,
      tags: (q.tags || []).join(','),
      difficulty: q.difficulty || 2,
      times_asked: 0,
    })),
    reviews: SEED_REVIEWS.map((r, i) => ({
      id: i + 1,
      student_name: r.student_name,
      company: r.company,
      round: r.round,
      difficulty_felt: r.difficulty_felt,
      rating: r.rating,
      text: r.text,
      created_at: new Date(Date.now() - (r.days_ago || 0) * 86400000).toISOString(),
    })),
    sessions: [],
    sessionSeq: 0,
  };
}

let state;
try {
  const raw = localStorage.getItem(STORE_KEY);
  state = raw ? JSON.parse(raw) : freshState();
  if (!state.questions || !state.questions.length) state = freshState();
} catch (e) { state = freshState(); }

function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) {}
}

/* ============================== HELPERS ============================== */
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const prettyRound = r => ({ aptitude:'Aptitude', technical:'Technical', hr:'HR / Behavioural',
  behavioral:'Behavioural (STAR)', dsa:'DSA / Coding', system_design:'System Design' }[r] || r);
const BAND_COLOR = s => s >= 7 ? 'var(--good)' : s >= 5.5 ? 'var(--warn)' : 'var(--bad)';

function toast(msg, ms = 2600) {
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

const S = { company: null, sessionId: null, seq: 0, of: 0, answeringProbe: false,
  probeText: null, voiceOn: false, listening: false };

/* ============================== VOICE ============================== */
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
const voiceSupported = () => !!SpeechRec && 'speechSynthesis' in window;

function initVoice() {
  if (!SpeechRec) return;
  recognizer = new SpeechRec();
  recognizer.continuous = true;
  recognizer.interimResults = true;
  recognizer.lang = 'en-IN';
  let finalText = '';
  recognizer.onstart = () => { S.listening = true; finalText = $('answerBox').value; syncMic(); };
  recognizer.onresult = e => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += (finalText ? ' ' : '') + t.trim();
      else interim += t;
    }
    $('answerBox').value = (finalText + ' ' + interim).replace(/\s+/g, ' ').trim();
  };
  recognizer.onerror = e => {
    S.listening = false; syncMic();
    if (e.error === 'not-allowed') toast('Microphone blocked. Allow mic access in your browser.');
    else if (e.error !== 'aborted') toast('Voice error: ' + e.error);
  };
  recognizer.onend = () => { S.listening = false; syncMic(); };
}

function syncMic() {
  const b = $('micBtn'); if (!b) return;
  b.classList.toggle('rec', S.listening);
  b.textContent = S.listening ? '⏹ Stop' : '🎙 Speak';
}

function toggleMic() {
  if (!recognizer) { toast('Speech recognition needs Chrome or Edge.'); return; }
  if (S.listening) recognizer.stop();
  else { try { recognizer.start(); } catch (e) { toast('Could not start the mic. Try again.'); } }
}

let voicesCache = [];
const loadVoices = () => { voicesCache = window.speechSynthesis ? speechSynthesis.getVoices() : []; };
if ('speechSynthesis' in window) { loadVoices(); speechSynthesis.onvoiceschanged = loadVoices; }

function speak(text, done) {
  if (!S.voiceOn || !('speechSynthesis' in window) || !text) { if (done) done(); return; }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(String(text).replace(/[*#`_]/g, ''));
  const en = voicesCache.filter(v => /^en/i.test(v.lang));
  const pick = en.find(v => /female|woman/i.test(v.name)) || en[0] || voicesCache[0];
  if (pick) u.voice = pick;
  u.lang = (pick && pick.lang) || 'en-IN';
  u.rate = 0.97; u.pitch = 1.02;
  u.onend = () => { if (done) done(); };
  u.onerror = () => { if (done) done(); };
  speechSynthesis.speak(u);
  setTimeout(() => { if (done) done(); }, Math.min(22000, 2600 + String(text).length * 68));
}

function toggleVoiceMode() {
  if (!voiceSupported()) { toast('This browser has no speech support. Chrome or Edge works best.'); return; }
  S.voiceOn = !S.voiceOn;
  $('voiceToggle').textContent = `🎙 Voice mode: ${S.voiceOn ? 'on' : 'off'}`;
  $('voiceToggle').classList.toggle('good', S.voiceOn);
  $('voicePill').innerHTML = `<span class="dot ${S.voiceOn ? '' : 'off'}"></span> voice ${S.voiceOn ? 'on' : 'off'}`;
  if (!S.voiceOn && 'speechSynthesis' in window) speechSynthesis.cancel();
  toast(S.voiceOn ? 'Voice mode on — the interviewer will speak and you can answer by mic.'
                  : 'Voice mode off — text only.');
}

/* ============================== SETUP ============================== */
function roundsFor(company) {
  const base = (COMPANIES.find(c => c.name === company) || { rounds: [] }).rounds || [];
  return base.filter(r => state.questions.some(q => q.company === company && q.round === r));
}

function buildCompanyGrid() {
  const grid = $('companyGrid');
  grid.innerHTML = COMPANIES.map(c => {
    const qn = state.questions.filter(q => q.company === c.name).length;
    const rv = state.reviews.filter(r => r.company === c.name);
    const felt = rv.length ? (rv.reduce((s, r) => s + r.difficulty_felt, 0) / rv.length).toFixed(1) : null;
    return `<div class="company-card" data-co="${esc(c.name)}">
      <div class="nm"><span>${esc(c.name)}</span>
        <span class="tag ${c.type === 'product' ? 'prod' : ''}">${c.type === 'product' ? 'product' : c.type === 'service' ? 'service' : 'general'}</span>
      </div>
      <div class="meta">${qn} Qs${rv.length ? ` · ${rv.length} reviews` : ''}${felt ? ` · feels ${felt}/5` : ''}</div>
    </div>`;
  }).join('');
  grid.querySelectorAll('.company-card').forEach(el => {
    el.onclick = () => selectCompany(el.dataset.co);
  });
  $('rvCompany').innerHTML = COMPANIES.map(c => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('');
  $('rvCompany').onchange = () => { fillRounds($('rvRound'), $('rvCompany').value); loadReviews(); };
}

function selectCompany(name) {
  S.company = name;
  document.querySelectorAll('.company-card').forEach(el => el.classList.toggle('on', el.dataset.co === name));
  fillRounds($('roundSel'), name);
  $('rvCompany').value = name;
  fillRounds($('rvRound'), name);
  loadProfile(name, $('roundSel').value);
  loadReviews();
}

function fillRounds(sel, company) {
  const rs = roundsFor(company);
  sel.innerHTML = rs.map(r => `<option value="${esc(r)}">${esc(prettyRound(r))}</option>`).join('');
}

function loadProfile(company, round) {
  const el = $('profBody');
  const p = companyProfile(state, company, round);
  const hot = (p.hot_topics || []).slice(0, 7);
  const max = hot.length ? hot[0].mentions : 1;

  el.innerHTML = `
    ${p.review_count === 0
      ? '<div class="banner warn">No reviews yet for this company. Be the first — your review will shape the questions.</div>'
      : `<div class="banner hot"><b>${p.review_count}</b> review${p.review_count > 1 ? 's' : ''} mined${p.blended_company_wide ? ' (blended for this round)' : ''} ·
         felt difficulty <b>${p.avg_difficulty_felt ?? '—'}/5</b> · rating <b>${p.avg_rating ?? '—'}/5</b></div>`}
    ${hot.length ? `<div style="margin-top:13px">
      <div class="muted" style="font-size:11.5px;margin-bottom:7px;letter-spacing:.4px">WHAT THEY ACTUALLY ASKED (weighted by recency)</div>
      ${hot.map(h => `<div class="bar" style="grid-template-columns:118px 1fr 28px">
        <span style="color:#c3cde9">${esc(h.topic)}</span>
        <span class="track"><span class="fill" style="width:${Math.max(8, (h.mentions / max) * 100)}%"></span></span>
        <span>${h.mentions}</span></div>`).join('')}
    </div>` : ''}
    ${p.advice.length ? `<div style="margin-top:14px">
      <div class="muted" style="font-size:11.5px;margin-bottom:5px;letter-spacing:.4px">REPEATED ADVICE FROM PEERS</div>
      ${p.advice.map(a => `<div class="advice">“${esc(a)}”</div>`).join('')}
    </div>` : ''}
    ${p.coverage_gaps.length ? `<div class="banner" style="margin-top:13px;font-size:12px">
      <b>Gap detected:</b> students mention ${p.coverage_gaps.slice(0, 3).map(esc).join(', ')} but our bank has no question on it yet.
      <span class="muted">→ add questions here to improve the bot.</span></div>` : ''}
  `;
}

function loadReviews() {
  const co = $('rvCompany').value;
  const rv = state.reviews.filter(r => r.company === co)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  $('rvSub').textContent = `${rv.length} review${rv.length === 1 ? '' : 's'} for ${co}`;
  $('rvList').innerHTML = rv.length ? rv.map(r => `
    <div class="review">
      <div class="row" style="justify-content:space-between">
        <b style="font-size:12.5px">${esc(r.student_name)} · ${esc(prettyRound(r.round))}</b>
        <span class="stars">${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</span>
      </div>
      <div style="margin-top:3px">${esc(r.text)}</div>
      <div class="muted" style="font-size:11px;margin-top:3px">felt ${r.difficulty_felt}/5</div>
    </div>`).join('') : '<span class="muted">No reviews yet.</span>';
}

function buildChips(el, max, selected) {
  el.innerHTML = Array.from({ length: max }, (_, i) =>
    `<span class="chip ${i + 1 === selected ? 'on' : ''}" data-v="${i + 1}">${i + 1}</span>`).join('');
  el.querySelectorAll('.chip').forEach(c => {
    c.onclick = () => {
      el.querySelectorAll('.chip').forEach(x => x.classList.remove('on'));
      c.classList.add('on');
      el.dataset.value = c.dataset.v;
    };
  });
  el.dataset.value = selected;
}

function submitReview() {
  const text = $('rvText').value.trim();
  if (text.length < 10) return toast('Please write a little more (at least 10 characters).');
  const company = $('rvCompany').value;
  const round = $('rvRound').value;
  state.reviews.push({
    id: (state.reviews.at(-1)?.id || 0) + 1,
    student_name: ($('studentName').value.trim() || 'Anonymous'),
    company, round,
    difficulty_felt: Number($('rvDiff').dataset.value || 3),
    rating: Number($('rvRate').dataset.value || 4),
    text,
    created_at: new Date().toISOString(),
  });
  save();
  $('rvText').value = '';
  toast('Review saved — future interviews now weight these topics.');
  loadReviews();
  if (S.company === company) loadProfile(S.company, $('roundSel').value);
  buildCompanyGrid();
  selectCompany(S.company);
}

/* ============================== INTERVIEW ============================== */
function startInterview() {
  const name = $('studentName').value.trim();
  if (!name) { toast('Enter your name first.'); $('studentName').focus(); return; }

  const company = document.querySelector('.company-card.on')?.dataset.co || COMPANIES[0].name;
  const round = $('roundSel').value;
  const limit = Number($('lenSel').value);

  const pool = questionsFor(state, company, round);
  if (!pool.length) return toast('No questions for that round yet.');

  const weak = studentWeakTags(state, name);
  const profile = companyProfile(state, company, round);
  const target = nextTargetDifficulty([], 2.5);
  const ranked = rankQuestions(state, pool, company, round, target, weak, new Set());
  const first = ranked[0];

  state.sessionSeq += 1;
  const sid = state.sessionSeq;
  state.sessions.push({
    id: sid, student_name: name, company, round,
    created_at: new Date().toISOString(),
    total_questions: limit, current_qid: first.q.id, turns: [], finished: false, report: null,
  });
  save();

  S.sessionId = sid; S.seq = 1; S.of = limit; S.answeringProbe = false; S.probeText = null;

  $('setup').classList.add('hide');
  $('report').classList.add('hide');
  $('interview').classList.remove('hide');
  $('ivTitle').textContent = `${company} · ${prettyRound(round)}`;
  $('ivSub').textContent = `${limit} questions · ${pool.length} questions in pool · personalised from ${profile.review_count} reviews`;

  $('chat').innerHTML = '';
  addMsg('bot', Offline.intro(company, prettyRound(round), name, limit));

  const weakKeys = Object.keys(weak);
  if (weakKeys.length) {
    const weakest = weakKeys.sort((a, b) => weak[a] - weak[b]).slice(0, 3);
    addBanner(`Focusing on your weak areas from past sessions: <b>${weakest.map(esc).join(', ')}</b>`);
  }
  if (first.why.review_match >= 0.5) {
    addBanner(`Selected because past candidates reported this topic for ${esc(company)}.`, 'hot');
  }

  updateProgress(1);
  addMsg('bot', first.q.text, { speak: `Question 1. ${first.q.text}` });
  $('answerBox').value = '';
  $('answerBox').focus();
}

const currentSession = () => state.sessions.find(s => s.id === S.sessionId);
const currentQuestion = () => {
  const s = currentSession();
  return s ? state.questions.find(q => q.id === s.current_qid) : null;
};

function addMsg(who, text, opts = {}) {
  const c = $('chat');
  const d = document.createElement('div');
  d.className = 'msg ' + who;
  d.innerHTML = `<div class="av">${who === 'bot' ? 'AI' : 'You'}</div>
                 <div class="bubble">${esc(text).replace(/\n/g, '<br>')}</div>`;
  c.appendChild(d);
  c.scrollTop = c.scrollHeight;
  if (opts.speak) speak(opts.speak);
}

function addBanner(html, kind = '') {
  const c = $('chat');
  const d = document.createElement('div');
  d.className = 'banner ' + kind;
  d.style.fontSize = '12.2px';
  d.innerHTML = html;
  c.appendChild(d);
  c.scrollTop = c.scrollHeight;
}

function updateProgress(seq) { $('progBar').style.width = Math.min(100, (seq / S.of) * 100) + '%'; }

function addScoreCard(sc) {
  const d = document.createElement('div');
  d.className = 'scorebox';
  const dims = sc.dimensions || {};
  const order = ['coverage', 'structure', 'specificity', 'depth', 'confidence'];
  d.innerHTML = `
    <div class="top">
      <div style="text-align:center">
        <div class="n" style="color:${BAND_COLOR(sc.overall)}">${sc.overall}</div>
        <div class="muted" style="font-size:10.5px">/10</div>
      </div>
      <div style="flex:1">
        <b style="font-size:13px">${esc(sc.band || '')}</b>
        <div class="muted" style="font-size:12px;margin-top:2px">${esc(sc.verdict || '')}</div>
        ${sc.coaching ? `<div style="font-size:12.6px;margin-top:7px;color:#cdd8f5">${esc(sc.coaching)}</div>` : ''}
      </div>
    </div>
    <div class="bars">
      ${order.filter(k => dims[k] !== undefined).map(k => `
        <div class="bar"><span>${k}</span>
          <span class="track"><span class="fill" style="width:${dims[k] * 10}%"></span></span>
          <span>${dims[k]}</span></div>`).join('')}
    </div>
    ${sc.strengths && sc.strengths.length ? `<ul class="list">${sc.strengths.map(s => `<li>✅ ${esc(s)}</li>`).join('')}</ul>` : ''}
    ${sc.improvements && sc.improvements.length ? `<ul class="list">${sc.improvements.map(s => `<li>🔧 ${esc(s)}</li>`).join('')}</ul>` : ''}
  `;
  $('chat').appendChild(d);
  $('chat').scrollTop = $('chat').scrollHeight;
}

function sendAnswer() {
  const text = $('answerBox').value.trim();
  if (!text) return toast('Write or speak an answer first.');
  if (S.listening) { try { recognizer.stop(); } catch (e) {} }

  const s = currentSession();
  const q = currentQuestion();
  if (!s || !q) return toast('Session lost. Please start again.');

  addMsg('me', text);
  $('answerBox').value = '';

  const sc = scoreAnswer(text, q.ideal, q.tags, s.round, q.difficulty, q.text);
  sc.coaching = Offline.coaching(sc);
  addScoreCard(sc);

  if (S.answeringProbe) {
    // Attach the probe reply to the same question rather than double counting.
    const prev = s.turns.at(-1);
    if (prev) { prev.score.probe_answer = text; prev.score.probe_score = sc.overall; }
    S.answeringProbe = false; S.probeText = null;
    $('answerHint').textContent = '— speak or type. Think aloud.';
    save();
    return advance(s, q);
  }

  const probe = Offline.probe(sc);
  s.turns.push({ seq: s.turns.length + 1, question_id: q.id, question: q.text, answer: text, score: sc });
  q.times_asked = (q.times_asked || 0) + 1;
  save();

  if (probe) {
    S.answeringProbe = true; S.probeText = probe;
    $('answerHint').textContent = '— follow-up question. Answer briefly.';
    setTimeout(() => addMsg('bot', probe, { speak: probe }), 320);
    return;
  }
  advance(s, q);
}

function advance(s, q) {
  const limit = s.total_questions;
  const done = s.turns.length;

  if (done >= limit) return finish(s);

  const history = s.turns.map(t => t.score.overall);
  const asked = new Set(s.turns.map(t => t.question_id));
  asked.add(q.id);
  const weak = studentWeakTags(state, s.student_name);
  const target = nextTargetDifficulty(history);
  const pool = questionsFor(state, s.company, s.round);
  const ranked = rankQuestions(state, pool, s.company, s.round, target, weak, asked);

  if (!ranked.length) return finish(s);

  const nxt = ranked[0];
  s.current_qid = nxt.q.id;
  save();
  S.seq = done + 1;
  updateProgress(S.seq);

  setTimeout(() => {
    if (nxt.why.weak_area_match >= 0.5) addBanner('This question targets a topic you scored low on previously.');
    addMsg('bot', nxt.q.text, { speak: `Question ${done + 1}. ${nxt.q.text}` });
    $('answerBox').focus();
  }, 420);
}

function getHint() {
  const q = currentQuestion();
  if (!q) return;
  addBanner(`💡 <b>Hint:</b> ${esc(Offline.hint(q.ideal))}`);
  const advice = companyProfile(state, currentSession().company, currentSession().round).advice;
  if (advice.length) addBanner(`📣 <b>Peer advice:</b> “${esc(advice[0])}”`);
}

function skipQuestion() {
  const s = currentSession(); const q = currentQuestion();
  if (!s || !q) return;
  addBanner('Question skipped — not counted.', 'warn');
  S.answeringProbe = false; S.probeText = null;
  advance(s, q);
}

function finish(s) {
  const report = summariseSession(s.turns.map(t => ({ seq: t.seq, question: t.question, answer: t.answer, score: t.score })));
  report.student_name = s.student_name;
  report.company = s.company;
  report.round = s.round;
  report.focus_plan = focusPlan(state, s.student_name);
  report.closing = Offline.closing(report.overall);
  report.company_profile = companyProfile(state, s.company, s.round);
  s.finished = true;
  s.report = report;
  save();
  renderReport(report);
}

function endInterview() {
  const s = currentSession();
  if (!s) return;
  if (s.turns.length && !confirm('End the interview and see your report?')) return;
  if (!s.turns.length) return toast('Answer at least one question first.');
  finish(s);
}

/* ============================== REPORT ============================== */
function renderReport(r) {
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  $('interview').classList.add('hide');
  $('report').classList.remove('hide');

  const dims = r.dimensions || {};
  const order = ['coverage', 'structure', 'specificity', 'depth', 'confidence'];
  const prof = r.company_profile || {};

  $('report').innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div class="row" style="justify-content:space-between;align-items:flex-start">
        <div>
          <h2>Session report — ${esc(r.company)} · ${esc(prettyRound(r.round))}</h2>
          <p class="sub">${esc(r.student_name)} · ${r.turns} scored answer${r.turns === 1 ? '' : 's'}</p>
        </div>
        <button class="ghost small" id="newSession">New session</button>
      </div>
      <div class="row" style="align-items:center;gap:20px;margin-top:6px">
        <svg class="score-ring" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="#212c4d" stroke-width="3.4"/>
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="${BAND_COLOR(r.overall)}" stroke-width="3.4"
            stroke-linecap="round" stroke-dasharray="${(r.overall / 10) * 97.4} 97.4" transform="rotate(-90 18 18)"/>
          <text x="18" y="20.8" text-anchor="middle" font-size="9.5" font-weight="800" fill="#e8ecf8"
            font-family="sans-serif">${r.overall}</text>
        </svg>
        <div>
          <b style="font-size:15px">${esc(r.band)}</b>
          <div class="muted" style="font-size:12.5px">${esc(r.verdict)}</div>
          <div class="muted" style="font-size:12px;margin-top:5px">
            strongest: <b>${esc(r.strongest_dimension || '—')}</b> · weakest: <b>${esc(r.weakest_dimension || '—')}</b>
          </div>
        </div>
      </div>
      <div class="bars" style="margin-top:16px">
        ${order.filter(k => dims[k] !== undefined).map(k => `
          <div class="bar"><span>${k}</span>
            <span class="track"><span class="fill" style="width:${dims[k] * 10}%"></span></span>
            <span>${dims[k]}</span></div>`).join('')}
      </div>
      ${r.closing ? `<div class="banner" style="margin-top:14px">${esc(r.closing)}</div>` : ''}
    </div>

    <div class="grid cols-2">
      <div class="card">
        <h2>What to fix next</h2>
        <p class="sub">Generated from this session and your answer history.</p>
        <ul class="list">${(r.next_actions || []).map(a => `<li>${esc(a)}</li>`).join('')}</ul>
        ${(r.focus_plan || []).length ? `<div style="margin-top:14px">
          <div class="muted" style="font-size:11.5px;letter-spacing:.4px;margin-bottom:6px">FOCUS PLAN</div>
          ${r.focus_plan.map(f => `<div class="advice"><b>${esc(f.topic)}</b> (${f.avg_score}/10)<br>${esc(f.why)}</div>`).join('')}
        </div>` : ''}
      </div>
      <div class="card">
        <h2>Topic breakdown</h2>
        <p class="sub">Averaged from your scored answers.</p>
        ${(r.weak_topics || []).length ? `<div class="muted" style="font-size:11.5px;margin-bottom:5px">WEAK</div>
          ${r.weak_topics.map(t => `<div class="stat"><span>${esc(t.topic)}</span><b style="color:var(--bad)">${t.score}/10</b></div>`).join('')}` : ''}
        ${(r.strong_topics || []).length ? `<div class="muted" style="font-size:11.5px;margin:12px 0 5px">STRONG</div>
          ${r.strong_topics.map(t => `<div class="stat"><span>${esc(t.topic)}</span><b style="color:var(--good)">${t.score}/10</b></div>`).join('')}` : ''}
        ${!(r.weak_topics || []).length && !(r.strong_topics || []).length ? '<span class="muted">Not enough data yet.</span>' : ''}
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h2>Answer by answer</h2>
      <p class="sub">Every question, your answer, and what to change.</p>
      ${(r.per_turn || []).map(t => `
        <div style="border-top:1px solid var(--line);padding:13px 0">
          <div class="row" style="justify-content:space-between">
            <b style="font-size:13px">Q${t.seq}. ${esc(t.question)}</b>
            <b style="color:${BAND_COLOR(t.overall)}">${t.overall}/10</b>
          </div>
          <div class="muted" style="font-size:12.4px;margin:6px 0">Your answer: ${esc(t.answer)}</div>
          <ul class="list">${(t.improvements || []).map(i => `<li>${esc(i)}</li>`).join('')}</ul>
        </div>`).join('')}
    </div>

    <div class="card" style="margin-top:16px">
      <h2>Company intel used for this session</h2>
      <p class="sub">${prof.review_count || 0} reviews mined · felt difficulty ${prof.avg_difficulty_felt ?? '—'}/5</p>
      <div class="chips">${(prof.hot_topics || []).slice(0, 9).map(h => `<span class="chip static">${esc(h.topic)} · ${h.mentions}</span>`).join('')}</div>
      ${(prof.advice || []).length ? `<div style="margin-top:12px">${prof.advice.map(a => `<div class="advice">“${esc(a)}”</div>`).join('')}</div>` : ''}
      <div class="banner" style="margin-top:13px;font-size:12px">
        <b>The loop continues:</b> add a review for ${esc(r.company)} and the next student's mock will be weighted differently.
      </div>
    </div>
  `;
  $('newSession').onclick = resetToSetup;
  window.scrollTo({ top: 0, behavior: 'smooth' });
  speak(r.closing);
}

function resetToSetup() {
  $('report').classList.add('hide');
  $('interview').classList.add('hide');
  $('setup').classList.remove('hide');
  buildCompanyGrid();
  selectCompany(S.company || COMPANIES[0].name);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ============================== WIRING ============================== */
(function boot() {
  initVoice();
  $('voicePill').innerHTML = `<span class="dot ${voiceSupported() ? '' : 'off'}"></span> voice ${voiceSupported() ? 'ready' : 'unsupported'}`;
  $('modeNote').textContent = 'Fully offline: rubric engine + curated bank + review mining run in this page. No API key, no network.';

  $('voiceToggle').onclick = toggleVoiceMode;
  $('startBtn').onclick = startInterview;
  $('sendBtn').onclick = sendAnswer;
  $('micBtn').onclick = toggleMic;
  $('hintBtn').onclick = getHint;
  $('skipBtn').onclick = skipQuestion;
  $('endBtn').onclick = endInterview;
  $('rvSubmit').onclick = submitReview;
  $('resetBtn').onclick = () => {
    if (!confirm('Reset all demo data (reviews you added, sessions) back to the seeded state?')) return;
    localStorage.removeItem(STORE_KEY);
    state = freshState();
    save();
    buildCompanyGrid();
    selectCompany(COMPANIES[0].name);
    toast('Demo data reset.');
  };
  $('roundSel').addEventListener('change', () => {
    if (S.company) loadProfile(S.company, $('roundSel').value);
  });
  $('answerBox').addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); sendAnswer(); }
  });

  buildChips($('rvDiff'), 5, 3);
  buildChips($('rvRate'), 5, 4);
  buildCompanyGrid();
  selectCompany(COMPANIES[0].name);
})();
</script>
</body>
</html>

```

---

<!-- FILE: standalone/build.py -->

<sub>3823 bytes</sub>

```python
#!/usr/bin/env python3
"""
build.py — inline the question bank + JS engine into ONE portable HTML file.

    python3 standalone/build.py

Output: standalone.html (~100 KB) — the entire app, no server needed.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "standalone.html"

bank = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
reviews = json.loads((ROOT / "data" / "seed_reviews.json").read_text(encoding="utf-8"))
engine = (ROOT / "standalone" / "engine.js").read_text(encoding="utf-8")
voice = (ROOT / "static" / "voice.js").read_text(encoding="utf-8")
template = (ROOT / "standalone" / "template.html").read_text(encoding="utf-8")
voice_html = (ROOT / "static" / "voice.html").read_text(encoding="utf-8")
local_api = (ROOT / "standalone" / "local_api.js").read_text(encoding="utf-8")

# Bootstrap for the offline edition: localStorage-backed state plus the globals
# that local_api.js expects (state, save, COMPANIES, Offline, engine fns).
LOCAL_STATE_JS = """
const STORE_KEY = 'interviewloop_voice_state_v1';

function freshState() {
  return {
    questions: QUESTIONS.map((q, i) => ({
      id: i + 1,
      company: q.company || 'Generic Fresher',
      round: q.round,
      text: q.text,
      ideal: q.ideal,
      tags: (q.tags || []).join(','),
      difficulty: q.difficulty || 2,
      times_asked: 0,
    })),
    reviews: SEED_REVIEWS.map((r, i) => ({
      id: i + 1,
      student_name: r.student_name,
      company: r.company,
      round: r.round,
      difficulty_felt: r.difficulty_felt,
      rating: r.rating,
      text: r.text,
      created_at: new Date(Date.now() - (r.days_ago || 0) * 86400000).toISOString(),
    })),
    sessions: [],
    sessionSeq: 0,
  };
}

let state;
try {
  const raw = localStorage.getItem(STORE_KEY);
  state = raw ? JSON.parse(raw) : freshState();
  if (!state || !state.questions || !state.questions.length) state = freshState();
} catch (e) { state = freshState(); }

function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) {}
}
"""


def _script(js, label):
    """Wrap inline JS in a script tag, guarding against stray </script>."""
    return f"<script>\n/* {label} */\n{js.replace('</script>', '<\\/script>')}\n</script>"


# The offline edition is built FROM the real voice-first page, so the two UIs can
# never drift apart. Only the data source and the two adapter scripts differ.
html = voice_html

# Replace the external script tag with the inlined dependencies.
html = html.replace(
    '<script src="/static/voice.js"></script>',
    "\n".join([
        _script(engine, "engine.js — scoring, review mining, ranking (inlined)"),
        _script(local_api, "local_api.js — server REST shape over local state"),
        _script(voice, "voice.js — hands-free turn engine (inlined)"),
        "<script>",
        "/* ---- local data ---- */",
        "const QUESTIONS = " + json.dumps(bank["questions"], ensure_ascii=False) + ";",
        "const SEED_REVIEWS = " + json.dumps(reviews, ensure_ascii=False) + ";",
        "const SEED_COMPANIES = " + json.dumps(bank["companies"], ensure_ascii=False) + ";",
        "</script>",
        "<script>",
        "/* ---- persistence + local bootstrap ---- */",
        LOCAL_STATE_JS,
        "</script>",
    ]),
)

# Guard against accidental CDN/external references — the preview iframe has no network.
external = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)', html)
OUT.write_text(html, encoding="utf-8")

print(f"built {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
print(f"  questions: {len(bank['questions'])}  companies: {len(bank['companies'])}  reviews: {len(reviews)}")
print(f"  external references: {external if external else 'none (fully self-contained)'}")

```

---

<!-- FILE: tests/test_scoring.py -->

<sub>10342 bytes</sub>

```python
"""
tests/test_scoring.py — offline sanity tests for the rubric and learning loops.

Run:  python tests/test_scoring.py
No server, no API key, no network needed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import feedback, scoring  # noqa: E402

PASS, FAIL = 0, 0
FAILURES = []


def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILURES.append(f"{label} {detail}")
        print(f"  ✗ {label}  {detail}")


IDEAL_JOINS = ("INNER (matching rows only), LEFT (all left + matches), RIGHT, FULL OUTER, "
               "CROSS. Give a small students/courses example and say when you would use "
               "LEFT JOIN (e.g. find students with no course).")
IDEAL_STAR = ("STAR + Leadership Principle 'Ownership'. Pick a real incident, what you "
              "specifically did, the measurable outcome, and what you learned.")
IDEAL_RELOC = "Give a clear yes/specific condition, then a reason."

STRONG_JOINS = ("Inner join returns only matching rows; left join keeps all rows from the "
                "left table and fills NULL where there is no match, which is the right "
                "trade-off when you need to find students with no course. Time is O(n log n) "
                "with an index on the join key.")
GOOD_JOINS = ("An inner join returns only matching rows, a left join keeps all rows from "
              "the left table and fills nulls where there is no match.")
VAGUE_JOINS = ("I think maybe joins are used to combine tables and there are inner and outer "
               "joins, I don't know all details exactly.")

STRONG_STAR = ("Situation: our registration portal crashed with 400 concurrent users before "
               "launch. Task: I owned the backend fix although load testing was not my "
               "module. Action: I profiled the endpoint, found an N+1 query doing 120 "
               "lookups per request, added a compound index and a 60-second cache, then load "
               "tested to 2000 users. Result: p95 latency dropped from 4.1s to 210ms and "
               "registration opened on time. I learned to treat load testing as ownership.")
WEAK_STAR = ("I think maybe we did a project and it was good. I don't know exactly but we "
             "worked as a team and it was fine.")

GOOD_RELOC = ("Yes sir I am comfortable relocating anywhere in India. I have lived in a "
              "hostel for four years so adjusting to a new city is not a problem, and my "
              "family is supportive of it.")
VAGUE_RELOC = "I can manage sir."


def test_technical_scoring():
    print("\n[1] Technical scoring")
    strong = scoring.score_answer(STRONG_JOINS, IDEAL_JOINS, "sql,joins", "technical", 2,
                                  question="Explain the different types of JOINs.")
    good = scoring.score_answer(GOOD_JOINS, IDEAL_JOINS, "sql,joins", "technical", 2,
                                question="Explain the different types of JOINs.")
    vague = scoring.score_answer(VAGUE_JOINS, IDEAL_JOINS, "sql,joins", "technical", 2,
                                 question="Explain the different types of JOINs.")

    check("strong answer >= 7.5", strong["overall"] >= 7.5, f"got {strong['overall']}")
    check("strong outranks good", strong["overall"] > good["overall"],
          f"{strong['overall']} vs {good['overall']}")
    check("good paraphrase >= 5.5 (no vocab penalty)", good["overall"] >= 5.5,
          f"got {good['overall']}")
    check("vague answer < 5", vague["overall"] < 5.0, f"got {vague['overall']}")
    check("vague flagged hedging", "hedging" in vague["flags"])
    check("vague flagged missing concepts", "missing_concepts" in vague["flags"])
    check("strong answer has no 'too_short' flag", "too_short" not in strong["flags"])
    check("score bounded 0..10", all(0 <= t["overall"] <= 10 for t in (strong, good, vague)))


def test_behavioural_story():
    print("\n[2] Behavioural (STAR story) scoring")
    strong = scoring.score_answer(STRONG_STAR, IDEAL_STAR, "star,ownership", "behavioral", 3,
                                  question="Tell me about a time you took ownership.")
    weak = scoring.score_answer(WEAK_STAR, IDEAL_STAR, "star,ownership", "behavioral", 3,
                                question="Tell me about a time you took ownership.")
    check("STAR story scores high", strong["overall"] >= 7.5, f"got {strong['overall']}")
    check("STAR story >= 9 on structure", strong["dimensions"]["structure"] >= 9.0,
          f"got {strong['dimensions']['structure']}")
    check("vague story scores low", weak["overall"] <= 5.0, f"got {weak['overall']}")
    check("vague story flagged no_structure", "no_structure" in weak["flags"])


def test_hr_direct():
    """Regression: a good relocation answer must NOT be graded as a failed STAR story."""
    print("\n[3] HR direct-question scoring (regression test)")
    good = scoring.score_answer(GOOD_RELOC, IDEAL_RELOC, "relocation", "hr", 1,
                                question="Are you comfortable relocating to any city?")
    vague = scoring.score_answer(VAGUE_RELOC, IDEAL_RELOC, "relocation", "hr", 1,
                                 question="Are you comfortable relocating to any city?")

    check("kind detected as 'direct'",
          scoring.question_kind("Are you comfortable relocating to any city?") == "direct")
    check("kind detected as 'story'",
          scoring.question_kind("Tell me about a time you took ownership.") == "story")
    # This exact case scored 4.8/10 'Weak' before the fix.
    check("good HR answer >= 6.5", good["overall"] >= 6.5, f"got {good['overall']}")
    check("good HR answer beats vague", good["overall"] > vague["overall"],
          f"{good['overall']} vs {vague['overall']}")
    check("vague HR answer < 5.5", vague["overall"] < 5.5, f"got {vague['overall']}")
    check("HR answer not punished for missing STAR",
          not any("STAR" in i for i in good["improvements"]))


def test_empty():
    print("\n[4] Edge cases")
    empty = scoring.score_answer("", IDEAL_JOINS, "sql", "technical", 2,
                                 question="Explain JOINs.")
    check("empty answer scores 0", empty["overall"] == 0.0)
    check("empty answer flagged", "empty" in empty["flags"])
    whitespace = scoring.score_answer("     \n  ", IDEAL_JOINS, "", "technical", 2)
    check("whitespace-only scores 0", whitespace["overall"] == 0.0)


def test_review_mining():
    print("\n[5] Review mining (Loop 1)")
    topics = feedback.extract_topics(
        "They asked SQL joins and then DBMS normalization and indexing. Also a STAR "
        "behavioural question about conflict.")
    check("extracts sql", "sql" in topics, str(sorted(topics)))
    check("extracts dbms", "dbms" in topics)
    check("extracts star", "star" in topics)
    no_false_positive = feedback.extract_topics("The interview was on Tuesday in a nice room.")
    check("no false positive on plain text",
          not ({"sql", "dbms", "index"} & no_false_positive), str(sorted(no_false_positive)))

    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    fresh = feedback._recency_weight(now.isoformat(timespec="seconds"))
    old = feedback._recency_weight((now - dt.timedelta(days=180)).isoformat(timespec="seconds"))
    check("fresh review weight == 1.0", abs(fresh - 1.0) < 0.01, f"got {fresh:.3f}")
    check("180-day-old review halved twice", 0.2 < old < 0.3, f"got {old:.3f}")


def test_ranking_and_adaptivity():
    print("\n[6] Ranking + adaptive difficulty")
    qs = [
        {"id": 1, "tags": "sql,joins", "difficulty": 2, "times_asked": 0, "text": "a"},
        {"id": 2, "tags": "nosuchtag", "difficulty": 2, "times_asked": 0, "text": "b"},
        {"id": 3, "tags": "sql", "difficulty": 5, "times_asked": 9, "text": "c"},
    ]
    ranked = feedback.rank_questions(qs, "TCS", "technical", target_difficulty=2.0,
                                    weak_tags={}, asked_ids=())
    check("ranks all candidates", len(ranked) == 3)
    check("respects asked_ids filter",
          len(feedback.rank_questions(qs, "TCS", "technical", asked_ids={1, 2})) == 1)
    check("difficulty fit favours target", ranked[0][1]["id"] in (1, 2),
          f"top id {ranked[0][1]['id']}")

    check("no history keeps start", feedback.next_target_difficulty([]) == 2.5)
    check("high scores raise difficulty", feedback.next_target_difficulty([8, 9]) > 2.5)
    check("low scores lower difficulty", feedback.next_target_difficulty([3, 4]) < 2.5)
    check("difficulty capped at 5", feedback.next_target_difficulty([10, 10], start=4.5) <= 5.0)
    check("difficulty floored at 1", feedback.next_target_difficulty([1, 1], start=1.5) >= 1.0)


def test_session_summary():
    print("\n[7] Session summary")
    turns = []
    for i, (txt, ideal, tags) in enumerate([
        (STRONG_JOINS, IDEAL_JOINS, "sql,joins,dbms"),
        (VAGUE_JOINS, IDEAL_JOINS, "sql,joins,dbms"),
    ], start=1):
        turns.append({
            "seq": i, "question": f"Q{i}", "answer": txt,
            "score": scoring.score_answer(txt, ideal, tags, "technical", 2, question=f"Q{i}"),
        })
    rep = scoring.summarise_session(turns)
    check("report has an overall score", 0 <= rep["overall"] <= 10)
    check("report counts turns", rep["turns"] == 2)
    check("report has all 5 dimensions", len(rep["dimensions"]) == 5)
    check("report gives next actions", len(rep["next_actions"]) >= 1)
    check("sibling tags deduped in weak_topics", len(rep["weak_topics"]) <= 3,
          str(rep["weak_topics"]))
    check("per-turn breakdown present", len(rep["per_turn"]) == 2)
    check("empty history handled", scoring.summarise_session([])["turns"] == 0)


if __name__ == "__main__":
    print("=" * 62)
    print("InterviewLoop — offline test suite")
    print("=" * 62)
    test_technical_scoring()
    test_behavioural_story()
    test_hr_direct()
    test_empty()
    test_review_mining()
    test_ranking_and_adaptivity()
    test_session_summary()

    print("\n" + "=" * 62)
    print(f"PASSED {PASS} / {PASS + FAIL}")
    if FAILURES:
        print("\nFailures:")
        for f in FAILURES:
            print("  -", f)
        sys.exit(1)
    print("All good.")

```

---

<!-- FILE: .github/workflows/ci.yml -->

<sub>1395 bytes</sub>

```yaml
name: tests

on:
  push:
    branches: [main, master]
  pull_request:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Seed database
        run: python -m app.db

      - name: Run scoring + learning-loop tests
        run: python tests/test_scoring.py

      - name: Smoke-test the API endpoints
        run: |
          python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
          for i in $(seq 1 30); do
            curl -sf http://127.0.0.1:8000/api/health && break
            sleep 1
          done
          curl -sf http://127.0.0.1:8000/api/companies > /dev/null
          curl -sf -X POST http://127.0.0.1:8000/api/sessions \
            -H 'Content-Type: application/json' \
            -d '{"student_name":"CI","company":"TCS","round":"technical","limit":3}' > /dev/null
          echo "API smoke test passed"

      - name: Verify the offline build is self-contained
        run: |
          python standalone/build.py
          if grep -Eq '(src|href)="https?://' standalone.html; then
            echo "ERROR: standalone.html references an external URL"; exit 1
          fi
          echo "standalone.html is self-contained"

```

---

<!-- FILE: README.md -->

<sub>27873 bytes</sub>

````markdown
# InterviewLoop — Company-Specific Mock Interview Bot

A working mock-interview bot for students that **takes company-specific interviews** and
**learns from the reviews and feedback of previous candidates**.

This repo contains two things:

1. **A runnable MVP** (Python + FastAPI + browser voice) you can demo today with no API keys.
2. **A blueprint** (this document) explaining every design decision, so you can extend it
   without reverse-engineering your own code later.

---

## Table of contents

1. [What it does](#1-what-it-does)
2. [Quickstart (2 minutes)](#2-quickstart)
3. [The idea in one diagram](#3-the-idea-in-one-diagram)
4. [The two learning loops (the core differentiator)](#4-the-two-learning-loops)
5. [How scoring works](#5-how-scoring-works)
6. [Voice mode](#6-voice-mode)
7. [Code map](#7-code-map)
8. [Adding companies and questions](#8-adding-companies-and-questions)
9. [Turning on a real LLM](#9-turning-on-a-real-llm)
10. [API reference](#10-api-reference)
11. [Roadmap: what to build next](#11-roadmap)
12. [Cost model](#12-cost-model)
13. [Deployment](#13-deployment)
14. [Legal and ethical guardrails](#14-legal-and-ethical-guardrails)
15. [Known limitations (be honest in your demo)](#15-known-limitations)

---

## Where do I start?

- **Never deployed anything?** → **[GO_LIVE.md](GO_LIVE.md)** walks you through running it on
  your own laptop and then putting it on the internet for free, in plain language, with
  every command and every common error explained.
- **Just want to see it work right now?** → double-click `standalone.html`. No install.
- **Need to upload it to GitHub?** → **[PUSH_TO_GITHUB.md](PUSH_TO_GITHUB.md)** covers the
  token, the commands, and the `master`/`main` trap that makes a successful push look empty.
- **Want the code structure?** → [PROJECT_FILES.md](PROJECT_FILES.md) has the entire repo in
  one copy-pasteable document.

## 1. What it does

A student picks a company (TCS, Infosys, Amazon, Google, Zoho…) and a round
(aptitude, technical, DSA, system design, HR, behavioural). The bot then:

- runs a **spoken or typed interview** with one question at a time,
- **scores each answer** on a 5-dimension rubric and explains what to fix,
- asks a **smart follow-up** on answers that deserve a probe,
- adjusts **difficulty** based on how the student is doing,
- produces an end-of-round **report** with a study plan,
- and **re-weights future questions** using both past candidate reviews and
  this student's own weak areas.

Everything runs locally. Interview content is a **curated JSON question bank**, so the bot
can never hallucinate a wrong question into an interview.

---

## 2. Quickstart

```bash
cd mockinterview
pip install -r requirements.txt        # fastapi + uvicorn
python -m app.db                       # creates mockinterview.db, seeds 65 Qs + 23 reviews
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000> in **Chrome or Edge** (for voice).
Interactive API docs are at <http://localhost:8000/docs>.

No API key is required. The app runs on a deterministic offline engine; adding a key is a
one-line upgrade (see [§9](#9-turning-on-a-real-llm)).

---

## 3. The idea in one diagram

```
                    ┌──────────────────────────────┐
  past students ───►│  reviews (free text)         │
                    └──────────────┬───────────────┘
                                   │  mine topics, advice, felt difficulty
                                   ▼
                    ┌──────────────────────────────┐
                    │  COMPANY PROFILE             │
                    │  hot topics + weights        │
                    └──────────────┬───────────────┘
                                   │ biasing signal (45%)
                                   ▼
 ┌─────────────┐      ┌────────────────────────┐      ┌──────────────────┐
 │ question    │─────►│  QUESTION SELECTOR     │─────►│  INTERVIEWER     │
 │ bank (JSON) │      │  + adaptive difficulty │      │  (voice / text)  │
 └─────────────┘      └───────────┬────────────┘      └────────┬─────────┘
                                  │ weak-area signal (25%)     │ answers
                                  │                            ▼
                    ┌─────────────┴──────────┐      ┌──────────────────────┐
                    │  STUDENT PROFILE       │◄─────│  RUBRIC SCORER       │
                    │  per-topic weakness    │      │  5 dimensions + flags│
                    └────────────────────────┘      └──────────┬───────────┘
                                                               │
                                                               ▼
                                                    ┌──────────────────────┐
                                                    │  REPORT + STUDY PLAN │
                                                    └──────────────────────┘
```

The thing that makes this different from "ChatGPT with a prompt": **the questions are chosen
by a scoring function over data**, not by the model's mood. Every selection is explainable —
the UI literally shows *why* a question was picked.

---

## 4. The two learning loops

### Loop 1 — community → bot (`app/feedback.py`)

Students submit free-text reviews:

> *"SQL heavy. Second highest salary, types of joins, then a question on when to use left join.
> They also asked me to pick one language and go deep."*

The miner turns that into structured signal:

| Step | What happens |
|---|---|
| **Topic extraction** | ~55 canonical topics (`sql`, `joins`, `dbms`, `index`, `star`, `relocation`…) each with synonym phrases. Matched with word boundaries so `join` doesn't match `joint`. |
| **Recency weighting** | Exponential decay, 90-day half-life: `0.5 ** (age_days / 90)`. A review from last week outranks one from last year. |
| **Felt difficulty** | Weighted mean of `difficulty_felt` → tells the bot how hard the real round is, not the syllabus. |
| **Advice extraction** | Sentences containing advice markers ("prepare", "my advice", "be ready", "don't") are surfaced verbatim as peer tips. |
| **Cold-start guard** | Fewer than 3 reviews for a round → blend in company-wide reviews rather than over-fitting to one opinion. |
| **Coverage gaps** | Hot topics the question bank has *no* question for are flagged on screen. This is your to-do list for content. |

That profile becomes a weight vector `{topic: 0..1}`, which the selector multiplies into each
question's score.

### Loop 2 — student → bot

Every answered question is tagged. Average score per tag is stored per student. On the next
session, questions matching **low-scoring tags** get a boost, and the report converts those
tags into a concrete study plan (see `TOPIC_HINTS`).

### The selection formula

```
score = 0.45 · review_topic_match     ← Loop 1
      + 0.25 · weak_area_match        ← Loop 2
      + 0.20 · difficulty_fit         ← adaptive target difficulty
      + 0.10 · freshness              ← 1/(1+times_asked), spreads coverage
```

`difficulty_fit` uses `max(0, 1 - |q.difficulty - target| / 3)`, and the target moves:

| Recent score | Next target difficulty |
|---|---|
| ≥ 7.5 | +1.0 (harder) |
| ≥ 5.5 | unchanged |
| < 5.5 | −0.75 (consolidate) |

This is a tiny version of **item response theory** — the same idea behind adaptive tests.
It's why the interview feels like it's paying attention.

---

## 5. How scoring works

`app/scoring.py` computes a **deterministic rubric**, then (optionally) lets an LLM write the
narrative. This split matters: LLM-only grading is unreproducible — the same answer scores
6/10 today and 8/10 tomorrow, and students stop trusting the product.

**Five dimensions**

| Dimension | Technical weight | Behavioural weight | Measures |
|---|---|---|---|
| coverage | 0.40 | 0.30 | Did the answer hit the key concepts? |
| structure | 0.15 | 0.25 | Logical flow / STAR |
| specificity | 0.20 | 0.20 | Numbers, examples, exact terminology |
| depth | 0.15 | 0.15 | Length fit (too short = unprepared, too long = rambling) |
| confidence | 0.10 | 0.10 | Hedging and filler words |

**Three question kinds, three grading styles** — this is the subtle part:

| Kind | Example | Graded on |
|---|---|---|
| Technical | "Explain JOINs" | Concept coverage + trade-offs + complexity |
| Behavioural **story** | "Tell me about a time you…" | STAR completeness, ownership ("I" not "we"), measurable result |
| HR **direct** | "Are you okay relocating?" | Clear position + a reason + something concrete |

Without that third row, a perfectly good relocation answer scored 4.8/10 "Weak" because it
had no Situation-Task-Action-Result. That was a real bug found by testing, and it's the kind
of thing that kills credibility with students. `question_kind()` classifies by the wording of
the question, not the round name.

One more safeguard: for HR questions the reference answer is *guidance*, not content, so
lexical overlap with it is down-weighted to 14%. Otherwise a student "fails" for not
parroting coach-speak.

**Flags** are emitted for the report: `missing_concepts`, `too_short`, `rambling`, `hedging`,
`no_specifics`, `no_structure`.

---

## 6. Voice mode — it talks *with* you

The screen at `/` is a conversation, not a form. There is **no Send button, no mic button,
no Skip, no End** — nothing to click once the call starts.

```
interviewer speaks the question  ->  mic opens by itself
        -> you answer out loud
        -> you stop talking -> your answer is sent automatically
        -> interviewer reacts ("Strong answer.") and asks the next question
```

The screen shows the exchange as a transcript, the way a call recording reads: the
interviewer's lines on the left, yours on the right, your live words appearing as a caption
while you speak, and a score chip on each answer once it has been marked.

### The only button in the whole app

`Start the interview`. Browsers refuse to play audio or open a microphone without a user
gesture, so exactly one tap is unavoidable. After that everything is speech.

### Everything is a spoken command

| Say | What happens |
|---|---|
| "repeat", "say that again", "pardon" | re-reads the question, mic reopens |
| "skip", "next question", "I don't know" | moves on |
| "hint", "give me a clue" | hints out loud, then lets you answer |
| "send it", "I'm done", "that's my answer" | submits without waiting for the pause |
| "end the interview", "let's stop" | wraps up and produces the report |

Commands are only recognised on **short utterances** (six words or fewer), so an answer that
happens to contain the word "send" or "done" is never mistaken for an instruction.

**Safety nets, so a hiccup never kills the session:** clicking anywhere reopens the mic, and
`R` repeat / `S` skip / `H` hint / `M` mic / `Space` send / `Esc` end work as keys. These are
invisible until needed — there are no buttons for them.

### Why voice-first is harder than it looks

| Mechanism | Why it matters |
|---|---|
| **Echo guard** | The mic is hard-gated against synthesis. Without this, the browser transcribes the interviewer's own voice and you end up answering yourself. A 420ms gap follows every spoken line. |
| **Silence detection** | Every recognised word rearms a timer; when it expires the turn is submitted. The pause length is yours to choose (1.2s / 1.7s / 2.3s). |
| **Auto-restart** | The recognition engine stops itself after ~60s of quiet or on a transient error. `onend` restarts it, so pausing to think doesn't end the interview. |
| **Synthesis timeout** | Some engines never fire `onend`. Without a length-based fallback the conversation deadlocks with no mic and no speech. |
| **Honest capability checks** | Unsupported browser, insecure origin and blocked mic each get a specific message instead of failing silently. |

### Browser support

| Browser | Speaks | Listens |
|---|---|---|
| Chrome / Edge (desktop + Android) | ✅ | ✅ best |
| Safari 16+ | ✅ | ✅ (iOS needs a tap per turn) |
| Firefox | ✅ | ❌ no `SpeechRecognition` |

Recognition also requires a **secure context** — `localhost` or HTTPS. Opening the page over a
raw IP shows an explicit warning.

### Text mode

The old text chat is still served at **`/text`** for keyboards, screen readers and quiet rooms.
It is a separate page, so the voice screen stays free of controls.

## 6b. Legacy voice details

Implemented with the **Web Speech API**, entirely in the browser (`static/index.html`):

- **Speech → text**: `SpeechRecognition` with interim results, `lang = 'en-IN'`, continuous
  mode, appended into the answer box so the student can edit before sending.
- **Text → speech**: `SpeechSynthesisUtterance`, rate 0.97, prefers an `en-IN` voice.
- **Safety valve**: some engines never fire `onend`, so `speak()` also has a character-length
  timeout to avoid the "bot stopped talking and the UI is stuck" bug.

**Why this over server-side STT/TTS:** zero cost, zero latency, no audio leaves the device
(a real privacy win for a student product), and no keys to demo. Chrome and Edge have solid
support; Firefox/Safari are patchy — always keep the text path as the fallback, which this
app does.

When you want production-grade voice (noise robustness, more accents, telephony), swap in a
server-side pipeline — Deepgram/Whisper for STT, ElevenLabs/OpenAI for TTS — behind the same
API. See the roadmap.

---

## 7. Code map

```
mockinterview/
├── app/
│   ├── main.py       FastAPI routes, request models, static mount        (~180 lines)
│   ├── db.py         SQLite schema + migrations + all queries            (~330)
│   ├── engine.py     interview state machine, adaptive selection         (~230)
│   ├── scoring.py    rubric scoring, session summary, study plan         (~330)
│   ├── feedback.py   review mining, ranking, loops                    (~300)
│   └── llm.py        pluggable LLM seam (offline ↔ OpenAI-compatible)    (~200)
├── data/
│   ├── questions.json    65 curated questions + 12 company profiles
│   └── seed_reviews.json 23 realistic student reviews
├── static/index.html     single-file frontend (voice, chat, report)
├── tests/test_scoring.py 24 assertions, runs offline
├── requirements.txt
└── mockinterview.db      generated, gitignore this
```

**Key design decision: one seam for the LLM.** Everything generative goes through
`app/llm.py`. Every function there has an offline implementation, so the product never
depends on a vendor to boot. `llm.status()` is surfaced in the UI so you always know which
mode you're in.

**Second key decision: the question *content* is never LLM-generated.** It comes from
`data/questions.json`, version-controlled and reviewable. The LLM may phrase a follow-up or
write coaching prose, but it cannot invent the SQL question.

---

## 8. Adding companies and questions

**Add a question** — append to `data/questions.json`, then `python -m app.db` (or
`init_db(force_reseed=True)`):

```json
{
  "company": "Infosys",
  "round": "technical",
  "text": "What is the difference between a stack and a queue?",
  "ideal": "Stack is LIFO, queue is FIFO. Stack operations push/pop at one end; queue enqueues at rear and dequeues at front. Give one use each: undo history for a stack, printer/task scheduling for a queue.",
  "tags": ["data-structures", "stack", "queue", "core"],
  "difficulty": 2
}
```

Rules that keep quality high:
- `text` should be what an interviewer actually says, in one sentence.
- `ideal` must contain the **concepts** you want scored (coverage is derived from it) plus
  the trade-off. Add it in plain sentences, not bullet lists.
- `tags` should reuse existing tags where possible — that's what links questions to reviews.
- `difficulty` is 1–5 and must mean the same thing across the bank.
- Use `"company": null` for a shared question any company can use.

**Add a company** — add an entry to `companies` in the same file (name, type, about, rounds).
If it has zero questions for a round, that round is **hidden automatically** rather than
offering a button that errors (another bug we hit).

**Grow the review corpus** — the more reviews, the sharper the questions get. Realistic
sources: a Google Form after each placement drive, a WhatsApp group export you manually
transcribe, or an in-app "add your review" form (already built).

---

## 9. Turning on a real LLM

```bash
export OPENAI_API_KEY=sk-...
# optional — any OpenAI-compatible endpoint:
export LLM_BASE_URL=https://api.openai.com/v1     # or Groq / Together / OpenRouter / Ollama
export LLM_MODEL=gpt-4o-mini
uvicorn app.main:app --reload
```

The UI badge flips from "offline rubric engine" to the model name. What improves:

| Capability | Offline | With LLM |
|---|---|---|
| Question selection | same | same (still data-driven) |
| Rubric score | same | same (still deterministic) |
| Coaching prose | templated, from flags | specific, quotes the student's own words |
| Follow-up probe | 4 templates by weakest signal | genuine depth/edge-case probe |
| Hint | truncates the reference | real nudge without giving it away |
| Opening / closing | templated | in character |

**Deliberate constraint:** the LLM's own numeric score is *not* used. If you later want to
blend it, do it as one weighted signal (e.g. 30% LLM, 70% rubric) and log both so you can
measure drift. Never let it silently become the whole grade.

For Ollama (free, local): `LLM_BASE_URL=http://localhost:11434/v1`,
`LLM_MODEL=llama3.1`, key can be any non-empty string.

---

## 10. API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | engine mode + dataset counts |
| GET | `/api/companies` | catalogue with review stats and available rounds |
| GET | `/api/companies/{c}/profile?round=r` | mined profile: hot topics, advice, gaps |
| GET | `/api/questions` | browse the bank |
| POST | `/api/sessions` | start: `{student_name, company, round, limit}` |
| POST | `/api/sessions/{id}/answer` | `{answer}` → probe \| next \| report |
| POST | `/api/sessions/{id}/hint` | hint + peer advice |
| POST | `/api/sessions/{id}/skip` | skip without scoring |
| POST | `/api/sessions/{id}/finish` | end early → report |
| GET | `/api/sessions/{id}/report` | stored report |
| GET | `/api/students/{name}/history` | sessions + weak areas + focus plan |
| GET/POST | `/api/reviews` | read / add reviews (POST closes Loop 1) |

The `/api/sessions/{id}/answer` response is a discriminated union on `type`:
`"probe"`, `"next"`, or `"report"`. The frontend just switches on it — that's the whole
client state machine.

---

## 11. Roadmap

### Phase 0 — MVP ✅ (this repo)
Interview loop, voice, rubric scoring, both learning loops, report, review form.

### Phase 1 — Make it a real product (2–3 weeks)
1. **Auth + student accounts.** Replace the typed name with login (email OTP or Google).
   Names collide; progress must survive a device change.
2. **Postgres instead of SQLite.** `app/db.py` is the only file to change — every query is
   already parameterised raw SQL with no SQLite-specific syntax.
3. **Company-specific review submission flow** with moderation. Unmoderated free text will
   be gamed ("this company is the best") and will poison the weights.
4. **Admin panel**: approve questions, see coverage gaps, blocklist topics.

### Phase 2 — Better grading (3–4 weeks)
5. **Semantic coverage** via embeddings instead of token overlap. This is the single biggest
   accuracy win: cosine similarity between answer and reference concepts catches paraphrases
   the current prefix matching misses. Cheap: cache question embeddings at seed time.
6. **Calibration study.** Have 2 human interviewers score 50 answers independently; measure
   agreement with the rubric (use quadratic-weighted kappa, target > 0.6). Publish the number.
   Right now the rubric is *plausible*, not *validated* — say so if asked.
7. **Speech metrics**: fillers per minute, pace (WPM), long pauses. You already have the
   transcript; these are the things interviewers actually judge and nobody measures.

### Phase 3 — Real voice + scale (1 month)
8. Server-side STT/TTS for accent robustness and phone support.
9. Live "panel mode": two interviewer personas probing the same answer.
10. Recording + replay so a student can hear themselves — the highest-value feedback channel
    in every real interview-prep product.

### Phase 4 — Distribution
11. College dashboard: cohort-level weak topics across all students (this is what a placement
    cell will actually pay for).
12. Drive-momentum view: "Amazon visits in 3 weeks → 42 students prepared, weakest topic is
    system design."
13. Mobile-friendly PWA; offline mode for low-connectivity campuses.

---

## 12. Cost model

Per 4-question interview, roughly:

| Stack | Cost |
|---|---|
| **This MVP** (browser voice + offline engine) | **₹0** |
| + LLM feedback (GPT-4o-mini: ~4k input, ~1.5k output tokens) | ≈ **$0.002** (~₹0.18) |
| + server-side STT (Whisper $0.006/min × ~8 min) | ≈ $0.05 |
| + server-side TTS (~2,500 chars) | ≈ $0.04 |
| Full production stack | ≈ **₹8–10 per interview** |

So a 1,000-student cohort doing 3 mocks each is ~₹25,000 on the full stack, or almost
nothing if you keep browser voice and use a cheap model for feedback only. The offline-first
architecture is what buys you that choice.

---

## 13. Deployment

**Cheapest path (free tier):**
- Backend → Render / Railway / Fly.io free instance (FastAPI + uvicorn as above)
- Static file is served by the same app, so nothing else needed
- **Caveat:** free instances have ephemeral disks — SQLite resets on redeploy. Use Supabase
  Postgres free tier (change `db.py`) or mount a persistent volume.

**College/internal:** a single Docker container on campus network. Voice needs HTTPS for
mic permission — either a real cert or `localhost` (which is exempt).

**Docker sketch:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m app.db
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 14. Legal and ethical guardrails

Take these seriously — they're also a selling point to a college.

1. **Never scrape confidential interview questions** from NDA-bound candidates or paid
   platforms. Build your bank from public sources, your own mock interviews, and voluntarily
   shared experiences with consent.
2. **Consent for reviews.** The review form must say what will be stored and that it will
   influence generated interviews. Don't display a student's name with a critical review
   without permission — default to first name or anonymous.
3. **India DPDP Act.** Student answers are personal data. Tell them where it's stored, allow
   deletion, and don't ship audio to a third party without explicit consent.
4. **Don't promise outcomes.** Label the report as *practice feedback*, not a prediction of
   selection. Wording like "you will clear TCS" is both untrue and liability.
5. **Bias check.** Fairness in an interview bot means the rubric shouldn't reward a particular
   dialect or English fluency over technical correctness. Test scoring on answers written in
   plain Indian English versus formal English — you'll likely find a specificity gap worth
   correcting. Do this before you deploy to students.

---

## 15. Known limitations

Be upfront about these in a demo or viva — they're the difference between confidence and
overclaiming.

- **The rubric is heuristic.** It approximates an interviewer's judgement. It has not been
  validated against human raters yet (Phase 2, item 6).
- **Coverage is lexical, not semantic.** A correct answer phrased very differently from the
  reference can be under-scored. There's a floor to prevent the worst of it, and embeddings
  are the real fix.
- **The question bank is small** — 65 questions. Fine for a demo, thin for a semester.
- **No auth.** Anyone can type anyone's name and see "their" history.
- **SQLite + ephemeral disk** means data loss on most free hosts.
- **Voice depends on the browser.** Chrome/Edge yes; Safari/Firefox unreliable.
- **Reviews are unmoderated**, so a single angry outlier can skew a company's weights. The
  cold-start blending softens this but doesn't solve it.

---

## Test it

```bash
python tests/test_scoring.py     # 24 assertions, no server, no keys
```

Covers: strong vs weak answers scoring in the right band, HR-direct vs STAR-story grading,
empty-answer handling, sibling-tag deduping, topic extraction from reviews, recency decay,
ranking order, and the adaptive difficulty curve.

---

Built as a starting point, not a finished product. The architecture is deliberately boring —
raw SQL, one file per concern, no framework magic — because the hard part of this project
isn't the code, it's the **quality of the question bank and the honesty of the scoring**.

---

## Appendix A — the single-file offline edition

`standalone.html` is the **entire app in one file**: no server, no API key, no network.
Double-click it and it runs.

Use this when the hosted preview is unavailable, when you're demoing in a lab with no
internet, or when you want to email the demo to a placement officer.

```bash
python3 standalone/build.py      # regenerates standalone.html from the JSON bank + engine.js
```

**What's inside**

| | |
|---|---|
| `standalone/engine.js` | The Python engine ported to plain JS — scoring, review mining, ranking, adaptive difficulty, session summary |
| `standalone/template.html` | The whole UI, same design as the server version |
| `standalone/build.py` | Inlines `data/questions.json` + `seed_reviews.json` + `engine.js` into one file |

**Differences from the server edition**

- State lives in `localStorage`, not SQLite. Reviews you add persist across reloads in that
  browser, and "Reset demo data" restores the seed.
- Follow-ups, hints and coaching come from the offline rule engine only (the server version
  can upgrade to a real LLM via `OPENAI_API_KEY`).
- Voice is identical — Web Speech API in both.

**Keeping the two in sync.** `app/*.py` is the source of truth for the production API;
`standalone/engine.js` is the mirror. `tests/test_scoring.py` guards the Python side and the
JS port was verified to agree within **0.1 points** on every reference case (7 of 8 exact).
If you change a scoring rule, change it in both and re-run that comparison.

Verified end-to-end: the file loads with **all HTTP(S) traffic blocked**, produces zero
console errors, completes a full interview, and both learning loops work (a new review
re-ranked Wipro from `relocation/bond` to `sql/joins/dbms/index`; a weak answer pulled the
next session's top pick onto that topic).

````

---

<!-- FILE: SETUP.md -->

<sub>3538 bytes</sub>

````markdown
# Setup — running InterviewLoop on your machine

Three commands. Pick your operating system below.

---

## The 3 commands (macOS / Linux)

```bash
git clone https://github.com/YOUR-USERNAME/interviewloop.git
cd interviewloop
./run.sh
```

Then open **<http://localhost:8000>** in Chrome or Edge.

`run.sh` creates the database on first run if it's missing, then starts the server.

## The 3 commands (Windows, PowerShell)

```powershell
git clone https://github.com/YOUR-USERNAME/interviewloop.git
cd interviewloop
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.db
python -m uvicorn app.main:app --reload --port 8000
```

Then open **<http://localhost:8000>**.

> If PowerShell blocks the activate script, run once:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

---

## Don't want Python at all?

Just open **`standalone.html`** by double-clicking it. It's the whole app in one file — no
server, no install, no internet. It opens in Chrome and works.

---

## What "localhost" means here

`localhost` = *your* computer. This is why the app must be started **on your machine** — a
server running anywhere else is not your localhost.

| Address | Who can reach it |
|---|---|
| `http://localhost:8000` | you, on your own machine |
| `http://127.0.0.1:8000` | same thing, written as an IP |
| `http://0.0.0.0:8000` | **not a browsable address** — it's what the server binds to. `ERR_ADDRESS_INVALID` is expected. |
| `http://<laptop-ip>:8000` | your phone on the same Wi-Fi, if the firewall allows |

---

## Verify it's working

```bash
curl http://localhost:8000/api/health
```

You should see `{"ok": true, "llm": {"mode": "offline", ...}}`.
Interactive API docs: <http://localhost:8000/docs>

## Useful commands

```bash
python tests/test_scoring.py            # 42 offline tests, no server needed
python -m app.db                        # (re)seed the database
python standalone/build.py              # rebuild the single-file offline edition
./run.sh                                # start the server
```

Reset everything back to the seeded demo state:

```bash
rm mockinterview.db && python -m app.db
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ERR_ADDRESS_INVALID` | You typed `0.0.0.0:8000`. Use `localhost:8000`. |
| `Address already in use` | Something else has port 8000. Use `--port 8001` and open `localhost:8001`. |
| `ModuleNotFoundError: fastapi` | The virtualenv isn't active, or `pip install -r requirements.txt` didn't run. |
| `command not found: python` | Try `python3` (macOS/Linux). |
| Voice button does nothing | Use Chrome or Edge. Mic needs `localhost` or HTTPS — both work here. |
| Voice blocked / no permission prompt | Check the site permissions in the browser's address bar. |
| Page loads but no companies appear | The API isn't up. Check the terminal for a traceback. |
| Mic works, bot doesn't speak | Click "Voice mode: off" so it reads **on**, then start the session. |

---

## Sharing it with classmates (same Wi-Fi)

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Now `0.0.0.0` *is* useful: it means "listen on all network interfaces". Others open
`http://<your-laptop-ip>:8000` — find your IP with `ipconfig` (Windows) or `ifconfig` /
`ip addr` (macOS/Linux), and allow Python through the firewall.

Note that mic access over plain `http://` on an IP address will be blocked by browsers.
For shared voice use, put it behind HTTPS (see the deployment section of `README.md`).

````

---

<!-- FILE: PUSH_TO_GITHUB.md -->

<sub>9623 bytes</sub>

````markdown
# PUSH_TO_GITHUB.md — uploading this project to your GitHub

Everything here is copy-paste. Two routes: **Route 1** uses the ready-to-push zip I gave
you (recommended — it keeps all 19 commits and the history), **Route 2** uses plain
upload of files (no git needed, but you lose the history).

Before you start, confirm the destination repo exists: **https://github.com/suresh-y17/mock_interview_bot**

---

## What you were given

| File | What it is | Use it how |
|---|---|---|
| **`interviewloop-github-ready.zip`** | The whole project **including its git history** (19 commits, broker `main` branch, remote already set) | Route 1. Unzip → `git push`. That's it. |
| `mock_interview_bot.zip` | Same code without `.git` | Copy files manually, or drag-drop into GitHub |
| `standalone.html` | The entire app as one file | Double-click. Needs no install, no server |
| `GO_LIVE.md` | Beginner guide to running it locally and deploying | Read this after the push |
| `PROJECT_FILES.md` | Every file in one copy-pasteable document | For rebuilding the repo by hand |

The zip contains **no database, no virtual environment, no secrets** — I checked. The
database is created automatically on first run, so shipping it would be wrong.

---

# Route 1 — The ready-to-push zip (recommended)

## Step 1 — Unzip it

Unzip `interviewloop-github-ready.zip`. You get a folder named `mock_interview_bot`.

Open a terminal and go into it:

```
cd path/to/mock_interview_bot
```

> **Trick for beginners:** type `cd ` (with a space), then drag the folder from your file
> manager into the terminal window, then press Enter. It fills in the path for you.

## Step 2 — Confirm the history came with it

```
git log --oneline
```

You should see 19 lines, newest first. The top one mentions `docs: add GO_LIVE.md`.
**If you see "not a git repository",** stop and use Route 2 instead — your unzip tool may
have dropped the hidden `.git` folder. (On macOS, press **Cmd + Shift + .** to reveal
hidden folders; on Windows, File Explorer → View → tick "Hidden items".)

## Step 3 — Point it at your repo

The zip's remote is already `https://github.com/suresh-y17/mock_interview_bot.git`. If
your username is different, correct it now:

```
git remote set-url origin https://github.com/YOUR-USERNAME/mock_interview_bot.git
```

Check what it says:

```
git remote -v
```

## Step 4 — Push

```
git push -u origin main
```

You'll be asked for a **Username** and **Password**:

- **Username:** your GitHub username
- **Password:** **NOT your GitHub password.** GitHub has refused account passwords for
  git operations since 2021. You must paste a Personal Access Token.

### Making the token (2 minutes)

1. GitHub → click your avatar (top right) → **Settings**
2. Left menu, scroll to the bottom → **Developer settings**
3. **Personal access tokens** → **Tokens (classic)**
4. **Generate new token** → **Generate new token (classic)**
5. Fill in:
   - **Note:** `interviewloop-push`
   - **Expiration:** `30 days`
   - **Scopes:** tick **`repo`** (the whole group). Nothing else is needed.
6. **Generate token** at the bottom
7. Copy the `ghp_…` string **immediately** — GitHub never shows it again

Paste it as the password. A terminal shows nothing while you paste — that's normal, just
press Enter.

> **This token is a password.** Don't commit it, screenshot it, or paste it into a chat.
> Revoke it when you're done: same page → the token → **Delete**.

### Optional: stop typing the token every time

```
git config --global credential.helper store
```

This saves it in plain text on **your** machine only (`~/.git-credentials`). Convenient on a
personal laptop; don't do it on a shared computer.

## Step 5 — Confirm it worked

```
git status
```

You want: `Your branch is up to date with 'origin/main'.`

Then open **https://github.com/suresh-y17/mock_interview_bot** in your browser. You
should see `README.md` rendered on the page, the folder list, and "19 commits" in the
top bar.

## Step 6 — The master/main trap (if the repo looks empty on GitHub)

**Symptom:** the push reported success, the terminal is happy, but the GitHub page shows
an empty repo with only a README you didn't write.

**Cause:** GitHub expects a branch called `master`, your work is on `main` (or the
reverse). The code is *there*, GitHub is just looking at the wrong branch.

**Fix, in order of preference:**

1. On GitHub go to **Settings** → **Branches** → change **Default branch** to `main`
2. If `main` isn't offered, push it explicitly:
   ```
   git push -u origin main:master
   ```
3. Or rename locally and push again:
   ```
   git branch -M main
   git push -u origin main
   ```

I hit exactly this while testing your package against a stand-in remote — the code
uploaded fine and the clone came back empty. It is the single most common "my push
worked but GitHub is blank" cause.

## Step 7 — Making changes later

```
git add .
git commit -m "describe what changed"
git push
```

If Render is connected (see `GO_LIVE.md`, Part B), that push automatically redeploys your
live site about a minute later.

---

# Route 2 — No git at all (drag and drop)

Use this if git isn't installed or Route 1 failed.

## Option 2a — GitHub's web uploader

1. Unzip `mock_interview_bot.zip` (the one **without** `.git`)
2. Go to your repo → **Add file** → **Upload files**
3. Open the unzipped folder, select everything, drag it into the browser
4. **Important exclusions:** skip `.venv`, `venv`, `__pycache__`, and `mockinterview.db`
   if they appear. `.gitignore` already covers them, but the uploader ignores that file.
5. Scroll down → **Commit changes**

Repeat for subfolders if the uploader refuses a large batch. This is tedious but works.

## Option 2b — Turn a plain folder into a repo and push it

If you have the code as a normal folder (no `.git`) and git installed:

```
cd path/to/mock_interview_bot
git init
git branch -M main
git remote add origin https://github.com/suresh-y17/mock_interview_bot.git
git add .
git commit -m "Initial commit: InterviewLoop mock interview bot"
git push -u origin main
```

`git add .` respects `.gitignore`, so the database and virtual environment are skipped
automatically.

> **If the push is rejected** with `updates were rejected because the remote contains work
> that you do not have locally`, the repo already has commits. Either clone it fresh and
> copy your files in, or force your version with:
> ```
> git push -u origin main --force
> ```
> Only force-push a repo **you** own and **only** when you don't mind replacing what's
> there. Never on a shared repo.

---

# Verifying the upload is complete

After pushing, check these six files exist on GitHub. If any is missing, the deploy will
fail later:

| File | Why it matters |
|---|---|
| `requirements.txt` | The host installs dependencies from this |
| `run.sh` | The host's start command |
| `Procfile` | Tells Render/Railway how to start the app |
| `render.yaml` | Lets Render configure everything in one click |
| `app/main.py` | The FastAPI application |
| `static/voice.html` + `static/voice.js` | The voice interview UI |

I tested exactly this: pushed the package to a stand-in remote, cloned it back into an
empty folder, created a fresh virtual environment, ran `bash run.sh`, and got
`200` on `/`, `/text`, `/api/health` and `/api/companies` with 65 questions seeded.

**What should NOT be on GitHub:**

- `mockinterview.db` — a database of test data; it regenerates on first run
- `.venv/` — thousands of files, specific to your machine
- `.env` — **secrets.** If you ever commit this, treat the key inside as compromised and
  rotate it.

`.gitignore` already handles all three. You only need to worry if you used Route 2a.

---

# Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `fatal: could not read Username for 'https://github.com'` | No token, or you pressed Enter at the prompt | Step 4 — make a token, paste it as the password |
| `Authentication failed` | Pasted your account password, or the token lacks the `repo` scope | New token with `repo` ticked |
| `remote: Repository not found` | Typo in the URL, or the repo doesn't exist yet | Check `git remote -v`; create the repo on GitHub first |
| `Updates were rejected... remote contains work` | The repo already has commits (e.g. a README made at creation) | Clone it and copy files in, or `--force` **only** on your own repo |
| Push works but GitHub shows an empty repo | The `master` / `main` mismatch | Step 6 |
| `git: command not found` | Git isn't installed | Windows: https://git-scm.com/download/win · Mac: `brew install git` · Linux: `sudo apt install git` |
| `error: src refspec main does not match any` | You have no commits yet | `git add . && git commit -m "Initial commit"` first |
| `Permission denied (publickey)` | You're using an SSH URL without SSH keys set up | Use the `https://` URL instead, with a token |

---

# After the push: make it live

You now have code on GitHub but nothing running publicly yet. Two choices, both in
**`GO_LIVE.md`**:

- **Part A** — run it on your own laptop at `http://localhost:8000` (do this first; errors
  are easier to read locally)
- **Part B** — deploy to Render for free, giving you a public `https://` link anyone can
  open. Since `render.yaml` is in the repo, this is: Render dashboard → **New +** →
  **Blueprint** → pick the repo → **Apply**. Nothing to type.

Remember that the live link is `https://`, which is required anyway — browsers only allow
microphone access on `localhost` or HTTPS.

````

---

<!-- FILE: tools/file_bundle.py -->

<sub>9786 bytes</sub>

````python
#!/usr/bin/env python3
"""
file_bundle.py — generate PROJECT_FILES.md: the whole repo as one copy-pasteable doc.

Usage:
    python3 tools/file_bundle.py            # writes PROJECT_FILES.md at repo root

Why a script instead of hand-writing the doc: the output must stay in lockstep with
the source. If a file changes, re-run this rather than editing the markdown.

Fence safety: any file containing ``` would break a normal markdown code fence, so
each fence is sized one backtick longer than the longest backtick run inside that
file. Reconstructing from the doc is therefore lossless (verified by --verify).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "PROJECT_FILES.md"

# Files we deliberately leave out: generated at runtime, or binary and therefore
# not copy-pasteable. Each has a documented regeneration command.
EXCLUDE = {
    "standalone.html",          # python3 standalone/build.py
    "mockinterview.db",         # python3 -m app.db
    "screenshot-setup.png",     # binary image
    "screenshot-report.png",    # binary image
    "PROJECT_FILES.md",         # this output
    ".git",
}

# Display order: config -> backend -> data -> frontend -> offline -> tests -> docs
ORDER = [
    "requirements.txt", "run.sh", ".gitignore", ".env.example",
    "app/__init__.py", "app/db.py", "app/scoring.py", "app/feedback.py",
    "app/llm.py", "app/engine.py", "app/main.py",
    "data/questions.json", "data/seed_reviews.json",
    "static/index.html",
    "standalone/engine.js", "standalone/template.html", "standalone/build.py",
    "tests/test_scoring.py",
    ".github/workflows/ci.yml",
    "README.md", "SETUP.md", "PUSH_TO_GITHUB.md",
    "tools/file_bundle.py",
]

LANG = {
    ".py": "python", ".js": "javascript", ".html": "html", ".json": "json",
    ".yml": "yaml", ".yaml": "yaml", ".md": "markdown", ".sh": "bash",
    ".txt": "", ".example": "bash",
}


def tracked_files():
    """Prefer git's file list, fall back to a walk for non-git copies."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
        files = [f for f in out.splitlines() if f.strip()]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE and not d.startswith(".git")]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            found.append(rel.replace(os.sep, "/"))
    return found


def included_files():
    files = [f for f in tracked_files() if f not in EXCLUDE]
    # Keep the authored order, then append anything unexpected alphabetically.
    ordered = [f for f in ORDER if f in files]
    extra = sorted(f for f in files if f not in ordered)
    return ordered + extra


def fence_for(content, minimum=3):
    """One backtick longer than the longest run inside the file."""
    runs = [len(m) for m in re.findall(r"`+", content)]
    return "`" * max(minimum, (max(runs) + 1) if runs else minimum)


def tree_lines(files):
    """Render a directory tree from a flat path list."""
    tree = {}
    for f in files:
        node = tree
        for part in f.split("/"):
            node = node.setdefault(part, {})
    lines = []

    def walk(node, prefix=""):
        entries = sorted(node.items(), key=lambda kv: (not kv[1], kv[0]))
        for i, (name, child) in enumerate(entries):
            last = i == len(entries) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}{'/' if child else ''}")
            if child:
                walk(child, prefix + ("    " if last else "│   "))

    walk(tree)
    return lines


def build():
    files = included_files()
    total = sum((ROOT / f).stat().st_size for f in files)

    parts = [
        "# InterviewLoop — complete source, one file",
        "",
        "Every source file in the project, in copy-paste order. Reconstruction is "
        "**lossless**: the generator verifies a rebuild matches the original "
        "byte-for-byte.",
        "",
        "## How to use this",
        "",
        "**Option A — rebuild the server app (recommended)**",
        "",
        "1. Create the folders shown in the tree below.",
        "2. Create each file and paste the matching block.",
        "3. Then run:",
        "",
        "```bash",
        "pip install -r requirements.txt",
        "python -m app.db                       # creates the database, seeds 65 questions",
        "python -m uvicorn app.main:app --reload --port 8000",
        "```",
        "",
        "Open <http://localhost:8000> in Chrome or Edge.",
        "",
        "**Option B — just want the demo, no Python**",
        "",
        "You only need `standalone/` plus `data/`, then:",
        "",
        "```bash",
        "python standalone/build.py     # produces standalone.html",
        "```",
        "",
        "Double-click the resulting `standalone.html`. Whole app, one file, no server.",
        "",
        "## Not included (generated, not hand-written)",
        "",
        "| File | How to generate |",
        "|---|---|",
        "| `standalone.html` | `python standalone/build.py` |",
        "| `mockinterview.db` | `python -m app.db` |",
        "| `screenshot-*.png` | binary images — download from the project workspace |",
        "",
        f"**{len(files)} files · {total/1024:.0f} KB of text.**",
        "",
        "## Directory structure",
        "",
        "```text",
        "mockinterview/",
        *tree_lines(files),
        "```",
        "",
        "---",
        "",
        "## Files",
        "",
    ]

    for f in files:
        with open(ROOT / f, "r", encoding="utf-8", newline="") as fh:
            content = fh.read()
        lang = LANG.get(Path(f).suffix, "")
        fence = fence_for(content)
        size = len(content.encode())

        parts.append(f"<!-- FILE: {f} -->")
        parts.append("")
        parts.append(f"<sub>{size} bytes</sub>")
        parts.append("")
        parts.append(f"{fence}{lang}")
        # Split on newlines and rejoin on parse: byte-exact, including trailing
        # newlines and empty files (an empty file contributes one empty line).
        parts.extend(content.split("\n"))
        parts.append(fence)
        parts.append("")
        parts.append("---")
        parts.append("")

    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(files)} files, {OUT.stat().st_size/1024:.0f} KB")
    return files


def verify():
    """Reconstruct from PROJECT_FILES.md and diff against the source tree."""
    import tempfile

    lines = OUT.read_text(encoding="utf-8").split("\n")
    files = included_files()

    # Scan for:  <!-- FILE: path -->  ...  <fence>  body lines  <fence>
    parsed = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^<!-- FILE: (.+?) -->$", lines[i])
        if not m:
            i += 1
            continue
        path = m.group(1)
        # Advance to the opening fence (first line that is only backticks,
        # optionally followed by a language tag).
        j = i + 1
        while j < len(lines) and not re.match(r"^(`{3,})[a-z]*$", lines[j]):
            j += 1
        if j >= len(lines):
            print(f"FAIL: no opening fence for {path}")
            return False
        fence = re.match(r"^(`{3,})[a-z]*$", lines[j]).group(1)
        j += 1
        body = []
        while j < len(lines) and lines[j] != fence:
            body.append(lines[j])
            j += 1
        parsed[path] = "\n".join(body)
        i = j + 1

    print(f"parsed {len(parsed)} blocks, expected {len(files)}")
    ok = set(parsed) == set(files)
    missing = set(files) - set(parsed)
    extra = set(parsed) - set(files)
    if missing:
        print("  MISSING:", sorted(missing))
    if extra:
        print("  EXTRA:", sorted(extra))

    tmp = Path(tempfile.mkdtemp())
    for path, content in parsed.items():
        p = tmp / path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)

    mismatches = []
    for f in files:
        orig = (ROOT / f).read_bytes()
        target = tmp / f
        rebuilt = target.read_bytes() if target.exists() else b""
        if orig != rebuilt:
            mismatches.append((f, len(orig), len(rebuilt)))

    if mismatches:
        ok = False
        print("BYTE MISMATCHES:")
        for f, a, b in mismatches:
            print(f"  {f}: original {a} bytes, rebuilt {b} bytes")
    else:
        print(f"all {len(files)} files rebuilt byte-for-byte \u2713")

    # Prove the reconstruction actually runs.
    r = subprocess.run([sys.executable, "-m", "app.db"], cwd=tmp, capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    print("seed:", out.splitlines()[0] if out else "?")
    r = subprocess.run([sys.executable, "tests/test_scoring.py"], cwd=tmp, capture_output=True, text=True)
    tail = [ln for ln in r.stdout.strip().splitlines() if ln.startswith(("PASSED", "All good"))]
    print("tests:", " | ".join(tail) or r.stdout[-200:])
    if r.returncode != 0:
        ok = False

    print("\nVERIFY:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="rebuild and diff against the source")
    args = ap.parse_args()
    if args.verify:
        sys.exit(0 if verify() else 1)
    build()

````

---

<!-- FILE: .dockerignore -->

<sub>83 bytes</sub>

```
.git
__pycache__
*.pyc
.venv
venv
*.db
.env
.env.*
screenshot-*.png
*.zip
*.bundle

```

---

<!-- FILE: Dockerfile -->

<sub>450 bytes</sub>

```
# Optional container build. Render/Railway do not need this (they read run.sh),
# but Fly.io, Google Cloud Run and plain `docker run` do.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The database is created and seeded on first boot, so no build-time DB is needed.
EXPOSE 8000
CMD ["bash", "run.sh"]

```

---

<!-- FILE: GO_LIVE.md -->

<sub>17674 bytes</sub>

````markdown
# GO_LIVE.md — putting InterviewLoop on the internet, step by step

Written for someone who has never deployed anything. Nothing here assumes you know
what a server, a port, or a build command is. Every command is copy-paste.

There are **two paths**. Read this table, pick one, and skip the other.

| | Path A — Local | Path B — Live on the internet |
|---|---|---|
| **What it means** | Runs on *your* laptop, at `http://localhost:8000` | Runs on a computer owned by a hosting company, at a real `https://` link |
| **Who can open it** | Only you | Anyone you send the link to |
| **Cost** | Free | Free |
| **Time** | ~10 minutes | ~15 minutes |
| **Needs** | Python installed | A GitHub account + a Render account |
| **Link works when your laptop is off?** | No | Yes |

> **Path A first.** If the app does not run on your own laptop, it will not run on a
> server either, and every error is easier to read locally. Do Path A, confirm the
> voice interview works, then do Path B.

---

# PART 0 — Words you'll see, in plain English

You do not need to memorise these. Skim them so the steps below don't feel alien.

| Word | What it actually means |
|---|---|
| **Terminal** (or *command line*, *shell*, *console*) | A window where you type commands instead of clicking. On Windows it's "PowerShell" or "Command Prompt". On Mac it's "Terminal". |
| **Repository / repo** | A folder of code that git keeps track of, with its full history. |
| **Git** | The tool that records changes to your folder. |
| **GitHub** | A website that stores repos online so other computers (like a host) can download them. |
| **Commit** | A saved snapshot of your files. |
| **Push** | Upload your commits to GitHub. |
| **Localhost** | "This computer, right here." `localhost:8000` = port 8000 on your own machine. |
| **Port** | A numbered door on a computer. A web server sits behind one. Ours is `8000`. |
| **Deploy** | Copy your code to someone else's computer and start it running there. |
| **Build command** | The command a host runs to install your dependencies. |
| **Start command** | The command a host runs to actually launch your app. |
| **Dependency** | A library your code needs. Ours are listed in `requirements.txt`. |
| **Environment variable** | A setting passed to a program from outside the code, like an API key. |
| **Cold start** | On a free host, your app goes to sleep when nobody uses it. The next visit takes ~30–60s to wake up. Normal. |

---

# PART A — Run it on your own laptop

## Step A1 — Check whether Python is installed

Open your terminal and type this exact line, then press Enter:

```
python3 --version
```

You should see something like `Python 3.12.7`.

- **If you see a version:** good, continue to A2.
- **If you see "command not found" or the Microsoft Store opens:** try `python --version` instead. If that also fails, install Python:
  - **Windows:** go to https://www.python.org/downloads/ and run the installer. **On the very first screen, tick the box that says "Add python.exe to PATH"** — this is the single most common beginner mistake. Then close and reopen the terminal.
  - **Mac:** run `brew install python` (or download from python.org).
  - **Linux:** `sudo apt install python3 python3-venv python3-pip`

## Step A2 — Get the code onto your laptop

Pick **one** of these three, whichever matches what you have.

**Option 1 — If you already pushed to GitHub** (do Path B step B1 first, then come back):

```
git clone https://github.com/suresh-y17/mock_interview_bot.git
cd mock_interview_bot
```

**Option 2 — If you downloaded `mock_interview_bot.zip`:**

Unzip it. You get a folder called `mock_interview_bot`. Then:

```
cd path/to/mock_interview_bot
```

(drag the folder into the terminal window after typing `cd ` and it fills the path for you)

**Option 3 — If someone sent you the single file `standalone.html`:**

You can **double-click it** and it opens in your browser. No Python at all. Skip to
Part C to learn the limitations of that mode.

## Step A3 — Create a virtual environment

A "virtual environment" is a private box for this project's libraries so they can't
break anything else on your laptop. Create it:

```
python3 -m venv .venv
```

Now **activate** it. This is the part people forget — it must be done **every time you
open a new terminal** to work on this project.

- **Mac / Linux:**
  ```
  source .venv/bin/activate
  ```
- **Windows (PowerShell):**
  ```
  .venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt):**
  ```
  .venv\Scripts\activate.bat
  ```

Your prompt should now start with `(.venv)`. That is how you know it worked.

> **Windows error: "running scripts is disabled on this system"?** Run this once, then retry:
> ```
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

## Step A4 — Install the dependencies

```
pip install -r requirements.txt
```

Three small libraries. Takes under a minute. If `pip` is not found, use `python3 -m pip install -r requirements.txt`.

## Step A5 — Start it

```
bash run.sh
```

On Windows, if `bash` is not recognised, use these three lines instead:

```
python -m app.db
python -m uvicorn app.main:app --reload --port 8000
```

The first time, you will see the database being created and filled with questions:

```
Seeded database at .../mockinterview.db
  questions: 65
  reviews  : 23
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**That last line means it is running. Leave this terminal window open.** Closing it
stops the server.

## Step A6 — Open it and run one interview

In **Chrome** or **Edge**, go to:

```
http://localhost:8000
```

Checklist:

1. The page shows a glowing circle and a **Start the interview** button.
2. Open "Who are you interviewing with?" and enter your name.
3. Click **Start** → the browser asks for microphone permission → click **Allow**.
4. The interviewer speaks a question. When it stops, the bar says *Listening to you*.
5. **Answer out loud.** When you stop talking for ~1.7 seconds, your answer sends itself.
6. It replies, asks the next question, and gives you a report at the end.

To stop the server: go back to the terminal and press **Ctrl + C**.

> **Everything is a spoken command.** Say "repeat", "skip", "hint", "send it", or
> "end the interview". There are no buttons during the interview — that is the point.

### Must-know: Voice only works in the right place

| Situation | Speaks? | Listens? |
|---|---|---|
| Chrome/Edge at `http://localhost:8000` | ✅ | ✅ |
| Chrome/Edge at `https://…` (Path B) | ✅ | ✅ |
| Safari 16+ | ✅ | ✅ (iPhone may need a tap per turn) |
| **Firefox** | ✅ | ❌ — no speech recognition at all |
| Chrome at `http://192.168.x.x` (a raw IP) | ✅ | ❌ |

Browsers only allow the microphone on **`localhost`** or **`https://`**. That rule is
theirs, not the app's. If you open the app via a LAN IP, the page will show a warning
explaining exactly this.

---

# PART B — Put it live on the internet (free)

## How this works, in one picture

```
your laptop  --git push-->  GitHub  --Render reads it-->  a server runs your app  -->  https://your-app.onrender.com
```

You never touch the server. You push code; Render notices and updates the live site.

## Step B1 — Put the code on GitHub

You need a free GitHub account: https://github.com/signup

**If you already have the code running locally (Part A), the repo is already a git
repository.** Check:

```
git status
```

Then push it:

```
git remote add origin https://github.com/YOUR-USERNAME/mock_interview_bot.git
git branch -M main
git push -u origin main
```

Replace `YOUR-USERNAME`. When asked for a password, paste a **Personal Access Token**,
not your GitHub password (GitHub stopped accepting passwords in 2021):

1. GitHub → your avatar → **Settings** → **Developer settings** (bottom of left menu)
2. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
3. Note: `interviewloop`, Expiration: `30 days`, tick the **`repo`** checkbox
4. **Generate token**, then copy the `ghp_…` string immediately — it is shown once
5. Paste it when git asks for a password

> The token is a password. Never paste it into a file, a screenshot, or a chat. Revoke
> it when you're done (same page → Delete).

**No git installed?** Alternative with zero commands: on GitHub click **New repository**,
name it `mock_interview_bot`, don't add a README, click **Create**. On the empty repo page
click **"uploading an existing file"**, then drag in everything **except** the `.venv`
folder and `mockinterview.db`. The database is created automatically on the server.

## Step B2 — Create the Render account

1. Go to https://render.com and click **Get Started** / **Sign Up**
2. Choose **Sign up with GitHub** (one less password to manage)
3. Authorise Render to see your repositories. If asked to pick repos, you can grant
   "All repositories" or just `mock_interview_bot`
4. **No credit card is required for the free plan**

## Step B3 — Deploy using the blueprint (recommended — nothing to type)

This project includes a file called `render.yaml` that already describes the whole
service. Render reads it and fills in every field for you.

1. In the Render dashboard, click **+ New** (top right)
2. Click **Blueprint**
3. Find `mock_interview_bot` in the list and click **Connect**
4. Render shows a service named **interviewloop** with the plan **Free** already chosen
5. Click **Apply** / **Create**
6. Watch the log. You'll see `pip install -r requirements.txt`, then the seeding lines
   (`questions: 65`), then `Uvicorn running on http://0.0.0.0:10000`
7. When the status badge turns **Live**, your URL appears at the top:
   `https://interviewloop-xxxx.onrender.com`

That's it. Open the link and you are on the internet.

### If Blueprint is not offered — create a Web Service by hand

Same result, four fields to fill:

| Field | What to enter |
|---|---|
| **Source** | your `mock_interview_bot` repo |
| **Language / Runtime** | **Python 3** |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `bash run.sh` |
| **Instance Type** | **Free** |
| **Health Check Path** (under Advanced) | `/api/health` |

Click **Create Web Service**. Nothing else is required — no database to add, no
environment variables, no API keys. The app seeds its own database on first boot.

## Step B4 — Check it actually works

Open your live URL and run the A6 checklist. Two things specific to the live site:

**1. The first visit will be slow.** On the free plan, Render puts your app to sleep
after 15 minutes with no visitors. The next visit takes 30–60 seconds to wake it. You
will see a blank page or a spinner — **wait, don't refresh in a panic.** The second
visit is instant.

**2. Microphone permission.** The link is `https://`, so the mic works. Click **Allow**
when Chrome asks. If you accidentally clicked Block: click the padlock icon in the
address bar → Microphone → Allow → reload.

## Step B5 — Making changes later

This is the whole loop:

```
git add .
git commit -m "describe what you changed"
git push
```

Render notices the push and redeploys automatically in about a minute. No clicking.

## Optional — turn on the smarter AI interviewer

By default the interviewer uses a built-in rule engine. It works offline, costs nothing,
and needs no signup. It scores answers, reacts, and asks follow-up questions — but its
wording is template-based.

If you want it to generate its own follow-up questions in natural language, plug in an
OpenAI-compatible API key. **This is optional; do not do it on your first deploy.**

1. Get a key from https://platform.openai.com/api-keys (or Groq / OpenRouter — any
   OpenAI-compatible endpoint, including a local Ollama)
2. Render dashboard → your service → **Environment** → **Add Environment Variable**
3. Add `OPENAI_API_KEY` = your key. Optionally `LLM_BASE_URL` and `LLM_MODEL`.
4. Save. Render restarts the service by itself.

Never put the key in code, in `render.yaml`, or on GitHub. Environment variables exist
precisely so secrets stay out of the repository.

---

# PART C — The zero-install option: one HTML file

There is a file called `standalone.html` in the project. **Double-click it.** It opens
in your browser and the whole app runs — no Python, no terminal, no internet.

Useful when: you want to demo on a friend's laptop, your college machine blocks
installs, or you're offline.

| Works | Doesn't work |
|---|---|
| Voice interview, all 65 questions, both learning loops | Any data survives a browser-cache wipe |
| Scoring, follow-ups, the full report | Sharing a link with someone else (it's a file) |
| Saves progress in the browser automatically | Anything needing the Python server |

You **cannot** upload this file to GitHub Pages and call it live — see the next section
for why.

---

# PART D — When it doesn't work

Find your symptom. Each one is a real failure with a real cause.

### "python3: command not found"
Python isn't installed, or isn't on your PATH. Part A1. On Windows, reinstall and tick
**"Add python.exe to PATH"**.

### "No module named uvicorn" / "No module named fastapi"
The virtual environment isn't active, or dependencies aren't installed. Part A3 then A4.
Your prompt must show `(.venv)`.

### "Address already in use" / port 8000 is busy
Something else is using port 8000. Either stop it, or use another port:
```
PORT=8000 python3 -m uvicorn app.main:app --port 8001
```
then open `http://localhost:8001`.

### The page loads but every action shows an error, or `/api/health` says `ok: false`
The database didn't get created. Fix it:
```
rm mockinterview.db
python3 -m app.db
```
(Windows: `del mockinterview.db`). Then restart.

### The interviewer is silent
1. Is it Chrome or Edge? Firefox cannot listen (it can still speak).
2. Is the URL `localhost` or `https://`? A raw IP will not get the microphone.
3. Click the padlock in the address bar → Microphone → **Allow** → reload.
4. Is the tab muted? Right-click the tab and check.
5. Your system volume / output device.

### The page says "microphone blocked"
Same as above — browser site permissions. Allow, then reload.

### It hears me but never sends my answer
It sends after a pause. The lobby has a **"How long a pause means I'm done"** setting —
choose *Quick — 1.2 seconds* if you speak in short bursts. Say **"send it"** to send
immediately.

### It keeps hearing itself / answers its own question
That would be an echo-guard failure. Check that you're on the latest code (`git pull`).
Also: use headphones, or lower your speaker volume — a loud speaker can leak into the mic.

### Render build fails with "No open ports detected"
The start command must bind to the port Render provides. Use exactly `bash run.sh` — it
already handles `${PORT}`. If you typed a start command by hand, make sure it ends with
`--port $PORT`, not `--port 8000`.

### Render says "Live" but the page is blank
Wait 60 seconds — it's the cold start (Part B4). If it persists, open
`https://your-url.onrender.com/api/health`. If that returns `"ok": true`, the server is
fine and it's a browser cache issue: hard-reload with **Ctrl + Shift + R**.

### I pushed to GitHub but Render shows the old version
Check the **Events** tab in Render — the deploy may still be running, or it failed.
Failed builds do not replace a working site; the old one keeps serving.

### "fatal: could not read Username" when pushing
GitHub needs a Personal Access Token, not your password. Part B1.

---

# PART E — Cheat sheet

```
# first-time setup on a new laptop
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
bash run.sh                        # -> http://localhost:8000

# everyday: come back later  (cd into the project folder and activate first)
source .venv/bin/activate
bash run.sh

# stop the server
Ctrl + C

# reset the database to a clean seed
rm mockinterview.db && python3 -m app.db

# rebuild the offline single-file app
python3 standalone/build.py

# run the tests
python3 tests/test_scoring.py

# deploy a change
git add . && git commit -m "my change" && git push
```

| URL | What it is |
|---|---|
| `http://localhost:8000` | The voice interview (the main app) |
| `http://localhost:8000/text` | Text chat version, for keyboards |
| `http://localhost:8000/api/health` | Server health, as JSON |
| `http://localhost:8000/docs` | Auto-generated API reference |
| `standalone.html` | The whole app in one file — double-click it |

---

# Two honest warnings

**1. The free database is temporary.** The app stores data in a single SQLite file on the
server. On Render's free plan, that file is wiped whenever the service rebuilds or
redeploys. Questions and reviews are re-seeded automatically, so nothing breaks — but
past session history will vanish. For a portfolio project that is completely fine. If you
ever need persistence, that means moving to Render Postgres, which is a real (if
moderate) project of its own.

**2. Chrome's speech recognition is not private.** It sends your recorded audio to
Google's servers to transcribe it. The app itself stores nothing — audio never touches
the server or the database — but the transcription is a cloud service. If you need
genuinely offline speech, that requires a different engine (Whisper or Vosk running
locally), which is a significant change. For a mock-interview practice tool, the
tradeoff is reasonable; just know it, and don't record anything sensitive.

````

---

<!-- FILE: Procfile -->

<sub>17 bytes</sub>

```
web: bash run.sh

```

---

<!-- FILE: render.yaml -->

<sub>377 bytes</sub>

```yaml
# Render blueprint — lets Render configure the whole service from the repo.
# In the Render dashboard: New + -> Blueprint -> pick this repo. Nothing to type.
services:
  - type: web
    name: interviewloop
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: bash run.sh
    healthCheckPath: /api/health
    autoDeploy: true

```

---

<!-- FILE: standalone/local_api.js -->

<sub>8203 bytes</sub>

```javascript
/**
 * local_api.js — serves the server's REST shape from local state, in-browser.
 *
 * static/voice.html talks to `/api/...`. In the single-file offline edition there
 * is no server, so this shim implements exactly the routes that page calls, on
 * top of engine.js + localStorage. Same request paths, same response shapes, so
 * the UI code is identical in both builds.
 *
 * Keep the response shapes in sync with app/main.py + app/engine.py.
 */
(function () {
  'use strict';

  const QUESTIONS_PER_ROUND = { aptitude: 3, technical: 4, dsa: 3, system_design: 3, hr: 4, behavioral: 3 };

  const current = (state, id) => state.sessions.find(s => s.id === Number(id));
  const questionById = (state, qid) => state.questions.find(q => q.id === qid);

  function ask(q, index, total) {
    return {
      seq: index, of: total, question_id: q.id, text: q.text,
      round: q.round, difficulty: q.difficulty, tags: q.tags,
      speak: `Question ${index}. ${q.text}`,
    };
  }

  function finish(state, s) {
    const report = summariseSession(s.turns.map(t => ({
      seq: t.seq, question: t.question, answer: t.answer, score: t.score,
    })));
    report.student_name = s.student_name;
    report.company = s.company;
    report.round = s.round;
    report.focus_plan = focusPlan(state, s.student_name);
    report.closing = Offline.closing(report.overall);
    report.company_profile = companyProfile(state, s.company, s.round);
    s.finished = true;
    s.report = report;
    return { type: 'report', report, speak: report.closing };
  }

  function advance(state, s, answeredId) {
    const limit = s.total_questions;
    if (s.turns.length >= limit) return finish(state, s);

    const asked = new Set(s.turns.map(t => t.question_id));
    if (answeredId) asked.add(answeredId);
    const history = s.turns.map(t => t.score.overall);
    const pool = questionsFor(state, s.company, s.round);
    const ranked = rankQuestions(state, pool, s.company, s.round,
      nextTargetDifficulty(history), studentWeakTags(state, s.student_name), asked);
    if (!ranked.length) return finish(state, s);

    const nxt = ranked[0];
    s.current_qid = nxt.q.id;
    return {
      type: 'next',
      next: ask(nxt.q, s.turns.length + 1, limit),
      why_selected: nxt.why,
    };
  }

  const routes = {
    'GET /api/health'() {
      return {
        ok: true,
        llm: { mode: 'offline', model: 'rule-based rubric engine (in-browser)',
               note: 'Single-file edition: no server, no API key.' },
        insights: {
          questions: state.questions.length,
          reviews: state.reviews.length,
          sessions: state.sessions.length,
          answers_scored: state.sessions.reduce((n, s) => n + s.turns.length, 0),
        },
      };
    },

    'GET /api/companies'() {
      return {
        companies: SEED_COMPANIES.map(c => {
          const rv = state.reviews.filter(r => r.company === c.name);
          const available = (c.rounds || []).filter(r =>
            state.questions.some(q => q.company === c.name && q.round === r));
          return {
            name: c.name, type: c.type, about: c.about,
            rounds: available.length ? available : c.rounds,
            question_count: state.questions.filter(q => q.company === c.name).length,
            review_count: rv.length,
            avg_difficulty_felt: rv.length
              ? Math.round(rv.reduce((a, r) => a + r.difficulty_felt, 0) / rv.length * 100) / 100
              : null,
            avg_rating: rv.length
              ? Math.round(rv.reduce((a, r) => a + r.rating, 0) / rv.length * 100) / 100
              : null,
          };
        }),
      };
    },

    'POST /api/sessions'(body) {
      const limit = body.limit || QUESTIONS_PER_ROUND[body.round] || 4;
      const pool = questionsFor(state, body.company, body.round);
      if (!pool.length) throw new Error(`No questions for ${body.company} / ${body.round}.`);

      const weak = studentWeakTags(state, body.student_name);
      const ranked = rankQuestions(state, pool, body.company, body.round,
        2.5, weak, new Set());

      state.sessionSeq = (state.sessionSeq || 0) + 1;
      const sid = state.sessionSeq;
      const s = {
        id: sid, student_name: body.student_name, company: body.company,
        round: body.round, created_at: new Date().toISOString(),
        total_questions: limit, current_qid: ranked[0].q.id,
        turns: [], finished: false, report: null,
      };
      state.sessions.push(s);
      save();

      return {
        session_id: sid,
        student_name: body.student_name,
        company: body.company,
        round: body.round,
        total_questions: limit,
        pool_size: pool.length,
        profile: companyProfile(state, body.company, body.round),
        weak_areas: weak,
        intro: Offline.intro(body.company, body.round, body.student_name, limit),
        llm: { mode: 'offline', model: 'in-browser rubric' },
        first: ask(ranked[0].q, 1, limit),
      };
    },

    'POST /api/sessions/:id/answer'(body, id) {
      const s = current(state, id);
      if (!s) throw new Error('Session not found');
      const q = questionById(state, s.current_qid);
      if (!q) throw new Error('Question not found');

      const isFollowup = !!body.followup_answer;
      const sc = scoreAnswer(body.answer || '', q.ideal, q.tags, s.round, q.difficulty, q.text);
      sc.coaching = Offline.coaching(sc);
      sc.is_followup = isFollowup;

      if (isFollowup && s.turns.length) {
        const prev = s.turns[s.turns.length - 1];
        prev.score.probe_answer = body.answer;
        prev.score.probe_score = sc.overall;
        prev.score.probe_coaching = sc.coaching;
      } else {
        const probe = Offline.probe(sc);
        s.turns.push({
          seq: s.turns.length + 1, question_id: q.id, question: q.text,
          answer: body.answer || '', score: sc,
        });
        q.times_asked = (q.times_asked || 0) + 1;
        if (probe) {
          save();
          return { type: 'probe', seq: s.turns.length, of: s.total_questions, score: sc, probe };
        }
      }

      const out = advance(state, s, q.id);
      save();
      return Object.assign({ score: sc }, out);
    },

    'POST /api/sessions/:id/skip'(body, id) {
      const s = current(state, id);
      if (!s) throw new Error('Session not found');
      if (s.turns.length + 1 >= s.total_questions) { const r = finish(state, s); save(); return r; }
      const out = advance(state, s, s.current_qid);
      save();
      return out;
    },

    'POST /api/sessions/:id/hint'(body, id) {
      const s = current(state, id);
      const q = questionById(state, s.current_qid);
      return {
        hint: Offline.hint(q.ideal),
        peer_advice: companyProfile(state, s.company, s.round).advice,
      };
    },

    'POST /api/sessions/:id/finish'(body, id) {
      const s = current(state, id);
      const out = finish(state, s);
      save();
      return out;
    },

    'GET /api/sessions/:id/report'(body, id) {
      const s = current(state, id);
      return s && s.report ? s.report : summariseSession(s ? s.turns : []);
    },
  };

  /**
   * Drop-in replacement for the fetch-based api() in voice.html.
   * Signature matches: api(path, {method, body}) -> parsed JSON.
   */
  window.localApi = function (path, opts) {
    opts = opts || {};
    const method = (opts.method || 'GET').toUpperCase();
    const body = typeof opts.body === 'string' ? JSON.parse(opts.body) : (opts.body || {});
    const clean = String(path).split('?')[0];

    for (const key of Object.keys(routes)) {
      const [m, pattern] = key.split(' ');
      if (m !== method) continue;
      const paramNames = [];
      const rx = new RegExp('^' + pattern.replace(/:(\w+)/g, (_, n) => {
        paramNames.push(n); return '([^/]+)';
      }) + '$');
      const match = clean.match(rx);
      if (match) {
        const args = paramNames.map(n => decodeURIComponent(match[paramNames.indexOf(n) + 1]));
        return Promise.resolve(routes[key](body, ...args));
      }
    }
    return Promise.reject(new Error('No local route for ' + method + ' ' + clean));
  };
})();

```

---

<!-- FILE: static/voice.html -->

<sub>35736 bytes</sub>

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>InterviewLoop — Voice Mock Interviews</title>
<style>
  :root{
    --bg:#080c17; --panel:#101728; --panel2:#0c1322; --line:#1d2842;
    --text:#e8ecf8; --muted:#8494b8;
    --good:#3ddc97; --warn:#ffb454; --bad:#ff6b81;
    --accent:#5b8cff; --accent2:#8b5cf6;
    --bot:#9db4ff; --you:#3ddc97;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; background:radial-gradient(1200px 700px at 50% -10%, #131d36 0%, var(--bg) 62%);
    color:var(--text); font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    min-height:100vh; -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:780px; margin:0 auto; padding:20px 18px 40px; min-height:100vh; display:flex; flex-direction:column}
  .hide{display:none !important}

  /* ---------- brand ---------- */
  .brand{display:flex; align-items:center; gap:10px; margin-bottom:18px}
  .logo{width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,var(--accent),var(--accent2));
    display:grid;place-items:center;font-weight:800;font-size:12px;color:#0a1020}
  .brand h1{font-size:15px;margin:0;font-weight:700;letter-spacing:-.2px}
  .brand p{margin:0;font-size:11px;color:var(--muted)}

  /* ---------- lobby ---------- */
  #lobby{flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; padding:10px 0}
  .callstate{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-top:26px;font-weight:700}
  .blurb{color:var(--muted);font-size:13.5px;max-width:430px;margin:10px auto 0;line-height:1.65}

  .callbtn{
    margin-top:26px; padding:16px 30px; border-radius:999px; border:0; cursor:pointer;
    background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#fff;
    font:600 15px/1 inherit; letter-spacing:.01em;
    box-shadow:0 10px 30px rgba(91,140,255,.35), inset 0 1px 0 rgba(255,255,255,.2);
    transition:transform .16s ease, box-shadow .16s ease;
  }
  .callbtn:hover{transform:translateY(-1px); box-shadow:0 14px 38px rgba(91,140,255,.45)}
  .callbtn:active{transform:translateY(0) scale(.985)}

  details{margin-top:30px; width:100%; max-width:420px; text-align:left;
    background:var(--panel); border:1px solid var(--line); border-radius:13px; padding:0 15px}
  details[open]{padding-bottom:15px}
  summary{cursor:pointer; padding:13px 0; font-size:12.5px; color:var(--muted); font-weight:600;
    list-style:none; display:flex; justify-content:space-between; align-items:center}
  summary::-webkit-details-marker{display:none}
  summary::after{content:"⌄"; font-size:15px; transform:translateY(-2px); transition:transform .2s}
  details[open] summary::after{transform:rotate(180deg) translateY(2px)}
  .field{margin-bottom:11px}
  .field label{display:block; font-size:11px; text-transform:uppercase; letter-spacing:.08em;
    color:var(--muted); margin-bottom:5px; font-weight:700}
  select,input{width:100%; background:var(--panel2); border:1px solid var(--line); color:var(--text);
    border-radius:9px; padding:9px 11px; font:inherit; font-size:13.5px}
  select:focus,input:focus{outline:2px solid rgba(91,140,255,.45); outline-offset:1px}
  .two{display:flex; gap:10px}
  .two > *{flex:1; min-width:0}

  /* ---------- orb ---------- */
  .orb{position:relative; width:190px; height:190px; display:grid; place-items:center}
  .orb.sm{width:74px; height:74px}
  .orb canvas{position:absolute; inset:0; width:100%; height:100%; display:block}
  .core{
    width:104px;height:104px;border-radius:50%;
    background:radial-gradient(circle at 34% 28%, #ffffff 0%, #cfd8ee 26%, #6d7ea8 62%, #2b3550 100%);
    box-shadow:0 0 44px rgba(157,180,255,.35), inset 0 -10px 24px rgba(0,0,0,.45);
    transition:background .4s ease, box-shadow .4s ease, transform .4s ease;
  }
  .orb.sm .core{width:40px;height:40px}
  .orb[data-state="speaking"] .core{
    background:radial-gradient(circle at 34% 28%, #ffffff 0%, #b9f5d8 22%, #3ddc97 60%, #106b47 100%);
    box-shadow:0 0 60px rgba(61,220,151,.5), inset 0 -10px 24px rgba(0,0,0,.4);
    animation:breathe 1.5s ease-in-out infinite;
  }
  .orb[data-state="listening"] .core{
    background:radial-gradient(circle at 34% 28%, #ffffff 0%, #ffd3da 22%, #ff6b81 60%, #8a1f30 100%);
    box-shadow:0 0 60px rgba(255,107,129,.5), inset 0 -10px 24px rgba(0,0,0,.4);
    animation:breathe 2.6s ease-in-out infinite;
  }
  .orb[data-state="thinking"] .core{
    background:radial-gradient(circle at 34% 28%, #ffffff 0%, #ffe3b8 22%, #ffb454 60%, #8a5410 100%);
    box-shadow:0 0 52px rgba(255,180,84,.45), inset 0 -10px 24px rgba(0,0,0,.4);
    animation:spinpulse 1.1s ease-in-out infinite;
  }
  .orb[data-state="idle"] .core{animation:breathe 5s ease-in-out infinite}
  @keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
  @keyframes spinpulse{0%,100%{transform:scale(.95);opacity:.85}50%{transform:scale(1.06);opacity:1}}

  /* ---------- interview: the conversation ---------- */
  #stage{flex:1; display:flex; flex-direction:column; min-height:0}
  .topline{display:flex; align-items:center; gap:8px; font-size:11.5px; color:var(--muted);
    padding-bottom:11px; border-bottom:1px solid var(--line); margin-bottom:4px}
  .topline b{color:var(--text); font-weight:600}
  .dots{display:flex; gap:3px; margin-left:auto}
  .dots i{width:6px;height:6px;border-radius:50%;background:var(--line);display:block}
  .dots i.on{background:var(--accent)}
  .dots i.now{background:var(--good)}

  .thread{
    flex:1; overflow-y:auto; padding:18px 2px 8px; display:flex; flex-direction:column; gap:11px;
    scroll-behavior:smooth; min-height:0;
  }
  .thread::-webkit-scrollbar{width:6px}
  .thread::-webkit-scrollbar-thumb{background:#1c2740; border-radius:3px}

  .b{max-width:86%; padding:11px 14px; border-radius:15px; font-size:14.5px; line-height:1.62;
     animation:rise .32s cubic-bezier(.2,.8,.3,1)}
  @keyframes rise{from{opacity:0; transform:translateY(9px)} to{opacity:1; transform:none}}

  .b.bot{
    align-self:flex-start; background:linear-gradient(180deg,#141d33,#111a2c);
    border:1px solid var(--line); border-left:2px solid var(--bot);
    border-bottom-left-radius:5px; color:#eef2ff;
  }
  .b.you{
    align-self:flex-end; background:linear-gradient(180deg,#0f2a22,#0d231d);
    border:1px solid #1c4436; border-right:2px solid var(--you);
    border-bottom-right-radius:5px; color:#e4fff3;
  }
  /* the in-progress utterance, styled as a live caption */
  .b.live{
    align-self:flex-end; background:rgba(61,220,151,.06); border:1px dashed #2a6b52;
    border-radius:15px; color:#a9e8cc; font-style:italic; min-height:0;
  }
  .b.live:empty{display:none}
  .b.sys{align-self:center; background:transparent; border:0; color:var(--muted);
    font-size:11.5px; letter-spacing:.06em; text-transform:uppercase; font-weight:700; padding:2px}

  .who{font-size:10px; letter-spacing:.13em; text-transform:uppercase; font-weight:800;
    margin-bottom:5px; opacity:.62}
  .b.bot .who{color:var(--bot)}
  .b.you .who{color:var(--you)}

  .score{display:block; text-align:right; margin-top:7px; font-size:11px;
    font-weight:800; letter-spacing:.04em; opacity:.9}

  /* docked status — ambient, not a control */
  .dock{
    display:flex; align-items:center; gap:13px; padding:12px 4px 2px;
    border-top:1px solid var(--line); margin-top:6px;
  }
  .dock .orb{width:52px;height:52px;flex:0 0 52px}
  .dock .orb .core{width:26px;height:26px;box-shadow:none;animation-duration:2.6s}
  .docktxt{min-width:0}
  .dockstate{font-size:11px; letter-spacing:.15em; text-transform:uppercase; font-weight:800; color:var(--muted)}
  .dockhint{font-size:12px; color:var(--muted); margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
  .bars{display:flex; gap:2px; align-items:flex-end; height:22px; margin-left:auto; flex:0 0 auto}
  .bars i{width:3px; border-radius:2px; background:var(--line); height:5px; transition:height .12s ease, background .2s}
  .bars.act i{background:var(--good)}

  /* ---------- report ---------- */
  .card{background:var(--panel); border:1px solid var(--line); border-radius:15px; padding:20px}
  .report h2{margin:0 0 3px; font-size:19px; letter-spacing:-.3px}
  .report h3{font-size:11px; letter-spacing:.13em; text-transform:uppercase; color:var(--muted);
    margin:22px 0 9px; font-weight:800}
  .report .sub{color:var(--muted); font-size:12.5px; margin:0}
  .ringrow{display:flex; align-items:center; gap:16px; margin-top:14px}
  .list{margin:6px 0 0; padding-left:17px; color:#c3cde4; font-size:13px; line-height:1.75}
  .advice{background:var(--panel2); border-left:2px solid var(--accent); border-radius:0 9px 9px 0;
    padding:9px 12px; margin-bottom:8px; font-size:12.6px; color:#c3cde4}
  .turn{border-top:1px solid var(--line); padding-top:12px; margin-top:12px}
  .banner{background:linear-gradient(135deg,rgba(91,140,255,.12),rgba(139,92,246,.1));
    border:1px solid #2c3c66; border-radius:11px; padding:12px 14px; font-size:13.5px; margin-top:16px}
  .again{display:inline-block; margin-top:16px; color:var(--accent); text-decoration:none;
    font-size:13px; font-weight:600; border-bottom:1px solid rgba(91,140,255,.35); padding-bottom:1px}
  .muted{color:var(--muted)}
  .row{display:flex; gap:9px; align-items:center}
  .foot{text-align:center; color:#4e5d80; font-size:10.5px; margin-top:22px; line-height:1.7}

  .toast{position:fixed; left:50%; bottom:26px; transform:translateX(-50%) translateY(20px);
    background:#17213a; border:1px solid #2b3a5e; color:var(--text); padding:11px 16px;
    border-radius:11px; font-size:13px; opacity:0; pointer-events:none; transition:.28s; z-index:99;
    max-width:88vw; box-shadow:0 12px 34px rgba(0,0,0,.5)}
  .toast.on{opacity:1; transform:translateX(-50%)}
  .cap{border-radius:10px; padding:10px 13px; font-size:12.5px; margin-bottom:12px; line-height:1.6}
  .cap.warn{background:rgba(255,180,84,.09); border:1px solid #4a3a1c; color:#f3d3a1}
  .cap.bad{background:rgba(255,107,129,.09); border:1px solid #4c2230; color:#ffb3bf}

  @media (max-width:620px){
    .wrap{padding:14px 13px 30px}
    .orb{width:150px;height:150px}
    .core{width:84px;height:84px}
    .b{max-width:92%; font-size:14px}
    .callbtn{width:100%; padding:17px 22px}
  }
</style>
</head>
<body>
<div class="wrap">

  <div class="brand">
    <div class="logo">IL</div>
    <div>
      <h1>InterviewLoop</h1>
      <p>A voice interviewer that talks with you</p>
    </div>
  </div>

  <!-- ================= LOBBY ================= -->
  <section id="lobby">
    <div class="orb" id="lobbyOrb" data-state="idle"><canvas id="lobbyViz"></canvas><div class="core"></div></div>
    <div class="callstate" id="callState">Ready when you are</div>
    <p class="blurb" id="blurb">
      Your interviewer will greet you, ask questions out loud, listen to your answers,
      and reply — like a real conversation. Nothing to type. No buttons to press once you begin.
    </p>

    <button class="callbtn" id="startBtn">🎧 Start the interview</button>

    <details id="opts">
      <summary>Who are you interviewing with?</summary>
      <div class="field">
        <label for="studentName">Your name</label>
        <input id="studentName" placeholder="e.g. Ananya" autocomplete="off" spellcheck="false" />
      </div>
      <div class="field">
        <label for="companySel">Company</label>
        <select id="companySel"></select>
      </div>
      <div class="two">
        <div class="field">
          <label for="roundSel">Round</label>
          <select id="roundSel"></select>
        </div>
        <div class="field">
          <label for="lenSel">Questions</label>
          <select id="lenSel">
            <option value="3">3</option>
            <option value="4" selected>4</option>
            <option value="5">5</option>
          </select>
        </div>
      </div>
      <div class="field" style="margin-bottom:0">
        <label for="paceSel">How long a pause means "I'm done"</label>
        <select id="paceSel">
          <option value="2300">Relaxed — 2.3 seconds</option>
          <option value="1700" selected>Normal — 1.7 seconds</option>
          <option value="1200">Quick — 1.2 seconds</option>
        </select>
      </div>
    </details>

    <div id="capBanner" style="width:100%;max-width:420px"></div>
    <p class="foot" id="lobbyFoot">Chrome or Edge recommended · your microphone is used only while you speak</p>
  </section>

  <!-- ================= INTERVIEW ================= -->
  <section id="stage" class="hide">
    <div class="topline">
      <span id="ivMeta"></span>
      <span class="dots" id="dots"></span>
    </div>

    <div class="thread" id="thread" aria-live="polite"></div>

    <div class="dock">
      <div class="orb sm" id="dockOrb" data-state="idle"><div class="core"></div></div>
      <div class="docktxt">
        <div class="dockstate" id="dockState">connecting</div>
        <div class="dockhint" id="dockHint">Getting ready…</div>
      </div>
      <div class="bars" id="bars"></div>
    </div>
  </section>

  <!-- ================= REPORT ================= -->
  <section id="report" class="hide"></section>

</div>

<script src="/static/voice.js"></script>
<script>
/* =====================================================================
   InterviewLoop — a conversation, not a form.
   The interview screen has no buttons at all. Turn-taking is driven by
   speech: the interviewer speaks, the mic opens, you talk, silence sends
   your answer, it replies. Spoken commands (repeat / skip / hint / stop)
   replace every control that used to live here.
   ===================================================================== */

const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const prettyRound = r => ({ aptitude:'Aptitude', technical:'Technical', hr:'HR / Behavioural',
  behavioral:'Behavioural', dsa:'DSA', system_design:'System Design' }[r] || r);
const BAND_COLOR = s => s >= 7 ? 'var(--good)' : s >= 5.5 ? 'var(--warn)' : 'var(--bad)';

async function api(path, opts = {}) {
  if (window.localApi) {
    try { return await window.localApi(path, opts); }
    catch (e) { throw new Error(e.message || 'local call failed'); }
  }
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.reason || `Request failed (${res.status})`);
  return data;
}

let toastTimer = null;
function toast(msg, ms = 3400) {
  let el = document.querySelector('.toast');
  if (!el) { el = document.createElement('div'); el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg;
  requestAnimationFrame(() => el.classList.add('on'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('on'), ms);
}

const S = {
  sessionId: null, seq: 1, of: 4,
  answeringProbe: false, probeText: null,
  currentQuestion: '', lastSpeak: '', lastAnswer: '',
  botName: 'Interviewer', studentName: 'there',
};

/* ------------------------------------------------------------------ viz */
function makeViz(canvas) {
  let ctx = null, raf = null, mode = 'idle', levels = [];
  const N = 24;

  function size() {
    if (!canvas) return;
    const r = canvas.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(1, Math.round((r.width || 190) * dpr));
    const h = Math.max(1, Math.round((r.height || 190) * dpr));
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    ctx = canvas.getContext('2d');
  }

  function color() {
    return mode === 'speaking' ? '61,220,151' : mode === 'listening' ? '255,107,129'
         : mode === 'thinking' ? '255,180,84' : '157,180,255';
  }

  function draw() {
    if (!ctx) size();
    if (!ctx) return;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    ctx.clearRect(0, 0, w, h);
    if (mode === 'idle') { levels = levels.map(() => 0); }

    const base = Math.min(w, h) * 0.30;
    const c = color();
    for (let i = 0; i < N; i++) {
      const target = mode === 'idle' ? 0
        : (mode === 'listening' ? 0.35 + Math.random() * 0.9
        : mode === 'speaking' ? 0.3 + Math.abs(Math.sin(i * 0.7 + performance.now() / 260)) * 0.8
        : 0.2 + Math.random() * 0.35);
      levels[i] = (levels[i] == null ? target : levels[i] * 0.72 + target * 0.28);
      const len = base * 0.18 + base * 0.62 * levels[i];
      const a = (i / N) * Math.PI * 2 - Math.PI / 2;
      const x1 = cx + Math.cos(a) * base, y1 = cy + Math.sin(a) * base;
      const x2 = cx + Math.cos(a) * (base + len), y2 = cy + Math.sin(a) * (base + len);
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${c},${0.28 + levels[i] * 0.55})`;
      ctx.lineWidth = Math.max(2, (w / 190) * 2.4);
      ctx.lineCap = 'round';
      ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
    raf = requestAnimationFrame(draw);
  }

  return {
    set(m) { mode = m; if (!raf) draw(); },
    start() { size(); if (!raf) draw(); },
    stop() { if (raf) { cancelAnimationFrame(raf); raf = null; } },
    resize: size,
  };
}

const lobbyViz = makeViz($('lobbyViz'));
const dockViz = makeViz(document.querySelector('#stage #viz') || null);
const bars = (() => {
  const host = $('bars');
  const els = [];
  for (let i = 0; i < 14; i++) { const b = document.createElement('i'); host.appendChild(b); els.push(b); }
  return els;
})();
let barsTimer = null;
function animateBars(active) {
  $('bars').classList.toggle('act', active);
  if (barsTimer) { clearInterval(barsTimer); barsTimer = null; }
  if (!active) { bars.forEach(b => { b.style.height = '5px'; }); return; }
  barsTimer = setInterval(() => {
    bars.forEach(b => { b.style.height = (5 + Math.random() * 17) + 'px'; });
  }, 110);
}

/* --------------------------------------------------------------- thread */
function addBubble(kind, text, opts) {
  const thread = $('thread');
  const el = document.createElement('div');
  el.className = 'b ' + kind;
  const who = kind === 'bot' ? (opts && opts.who || S.botName)
            : kind === 'you' ? 'You' : '';
  el.innerHTML = (who ? `<div class="who">${esc(who)}</div>` : '') + esc(text);
  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
  return el;
}

function sysNote(text) {
  const el = addBubble('sys', text);
  setTimeout(() => { el.style.opacity = '0.45'; }, 2600);
}

let liveEl = null;
function setLive(text) {
  const thread = $('thread');
  if (!liveEl) {
    liveEl = document.createElement('div');
    liveEl.className = 'b live';
    thread.appendChild(liveEl);
  }
  liveEl.textContent = text || '';
  thread.scrollTop = thread.scrollHeight;
}
function clearLive() { if (liveEl) { liveEl.remove(); liveEl = null; } }

/* ----------------------------------------------------------- voice state */
function setUIState(s) {
  const orb = $('dockOrb');
  if (orb) orb.dataset.state = s;
  const label = { speaking: 'Interviewer is speaking', listening: 'Listening to you',
    thinking: 'Thinking', idle: 'Waiting' }[s] || s;
  const ds = $('dockState'); if (ds) ds.textContent = label;

  const hint = {
    speaking: 'Listen — you can answer as soon as the microphone opens.',
    listening: 'Answer normally. Stop talking and your answer is sent.',
    thinking: 'Scoring your answer…',
    idle: 'Speak any time, or say “repeat”.',
  }[s] || '';
  const dh = $('dockHint'); if (dh) dh.textContent = hint;

  animateBars(s === 'listening');
  dockViz.set(s);
  if (s === 'listening') dockViz.start(); 
}

function capBanner(html, kind) {
  $('capBanner').innerHTML = `<div class="cap ${kind || 'warn'}">${html}</div>`;
}

/* ------------------------------------------------------- voice readiness */
function checkVoice() {
  const c = window.VoiceEngine ? VoiceEngine.capabilities() : { works: false };
  if (!c.stt && !c.tts) {
    capBanner('This browser has no speech support. Use <b>Chrome</b>, <b>Edge</b>, or <b>Safari 16+</b>.', 'bad');
    return false;
  }
  if (!c.stt) {
    capBanner('Your browser can <b>speak</b> but cannot listen. Chrome or Edge can do both.', 'bad');
    return false;
  }
  if (!c.secure) {
    capBanner('Speech recognition needs a <b>secure page</b> — open <code>http://localhost:8000</code> or an HTTPS link. An IP address will not work.', 'bad');
    return false;
  }
  if (!c.tts) capBanner('Speech output is unavailable, so questions will appear as text.', 'warn');
  return true;
}

/* --------------------------------------------------------------- lobby */
let COMPANIES = [];

async function loadCompanies() {
  try {
    const data = await api('/api/companies');
    COMPANIES = data.companies || [];
    const sel = $('companySel');
    sel.innerHTML = COMPANIES.map(c =>
      `<option value="${esc(c.name)}">${esc(c.name)} — ${esc(c.type)}</option>`).join('');
    const pref = COMPANIES.find(c => c.name === 'TCS') || COMPANIES[0];
    if (pref) { sel.value = pref.name; await loadRounds(); }
  } catch (e) {
    capBanner('Could not load the question bank: ' + esc(e.message), 'bad');
  }
}

async function loadRounds() {
  const co = COMPANIES.find(c => c.name === $('companySel').value);
  const sel = $('roundSel');
  const rounds = (co && co.rounds && co.rounds.length) ? co.rounds : ['technical', 'hr'];
  sel.innerHTML = rounds.map(r => `<option value="${esc(r)}">${esc(prettyRound(r))}</option>`).join('');
  if (co) {
    const bits = [];
    if (co.review_count) bits.push(`${co.review_count} reviews mined`);
    if (co.question_count) bits.push(`${co.question_count} questions`);
    if (co.avg_rating) bits.push(`rated ${co.avg_rating}/5 by past candidates`);
    $('blurb').innerHTML = `${esc(prettyRound(sel.value))} round for <b>${esc(co.name)}</b>. ` +
      (bits.length ? `<span class="muted">${bits.join(' · ')}</span>` : '');
  }
}

/* ---------------------------------------------------------- start a call */
let started = false;

async function startInterview() {
  if (started) return;
  const name = ($('studentName').value || '').trim() || 'there';
  if (!$('studentName').value.trim()) {
    $('studentName').value = '';
    $('opts').open = true;
    toast('Add your name so the interviewer can greet you.');
    $('studentName').focus();
    return;
  }
  if (!checkVoice()) { $('opts').open = true; return; }

  started = true;
  S.studentName = name.slice(0, 40);
  savePrefs();

  try {
    const data = await api('/api/sessions', {
      method: 'POST',
      body: JSON.stringify({
        student_name: S.studentName,
        company: $('companySel').value,
        round: $('roundSel').value,
        limit: Number($('lenSel').value),
      }),
    });

    S.sessionId = data.session_id;
    S.seq = 1; S.of = data.total_questions;
    S.answeringProbe = false; S.probeText = null;

    VoiceEngine.setAutoSubmitDelay(Number($('paceSel').value));
    VoiceEngine.enable(true);

    $('lobby').classList.add('hide');
    $('stage').classList.remove('hide');
    $('thread').innerHTML = '';
    $('ivMeta').innerHTML = `<b>${esc(data.company)}</b> · ${esc(prettyRound(data.round))} round`;
    $('dots').innerHTML = Array.from({ length: S.of }, (_, i) =>
      `<i class="${i === 0 ? 'now' : ''}"></i>`).join('');
    dockViz.resize();
    requestAnimationFrame(() => dockViz.resize());
    setUIState('speaking');

    // The greeting, personalised by the two learning loops: previous reviews
    // for this company/round and this student's own weak areas.
    let greet = data.intro;
    const weak = Object.keys(data.weak_areas || {});
    if (weak.length) {
      const w = weak.sort((a, b) => data.weak_areas[a] - data.weak_areas[b]).slice(0, 2);
      greet += ` I'll also focus on ${w.join(' and ')}, which you scored low on last time.`;
      setTimeout(() => sysNote(`focusing on your weak areas: ${w.join(', ')}`), 2600);
    }

    S.currentQuestion = data.first.text;
    S.lastSpeak = `${greet} ${data.first.text}`;

    // Two bubbles so it reads like speech, but one spoken turn so the mic
    // opens exactly once, after the question has been read out.
    addBubble('bot', greet);
    setTimeout(() => addBubble('bot', data.first.text), 500);
    VoiceEngine.turn(S.lastSpeak);
  } catch (e) {
    started = false;
    toast('Could not start: ' + e.message);
  }
}

/* ===================== spoken commands =====================
   Every control that used to be a button is now something you can say.
   Matched only on short utterances, so a real answer that happens to
   contain the word "send" is never mistaken for an instruction. */
const RULES = [
  ['end',    /\b(end (the )?(interview|round)|stop (the )?interview|finish (the )?interview|i want to stop|let'?s stop)\b/i],
  ['repeat', /\b(repeat( that)?|say (that )?again|what was the question|come again|pardon)\b/i],
  ['skip',   /\b(skip( this| it)?|next question|move on|pass( on)?( this)?|don'?t know|no idea)\b/i],
  ['hint',   /\b(hint|give me a clue|clue|help me with this)\b/i],
  ['send',   /\b(send( it| my answer)?|submit|i'?m done|that'?s (my|all)|that'?s it|done|go ahead)\b/i],
];

function matchCommand(text) {
  const t = String(text).trim().replace(/\s+/g, ' ').toLowerCase();
  if (!t) return null;
  const words = t.split(' ').length;
  if (words > 6) return null;          // a long answer is never a command
  for (const [act, re] of RULES) if (re.test(t)) return act;
  return null;
}

async function runCommand(act) {
  if (act === 'send') {
    const t = VoiceEngine.finishTurn();
    if (!t) VoiceEngine.listen();     // nothing captured: never strand the student
    return;
  }
  if (act === 'repeat') {
    sysNote('repeating the question');
    VoiceEngine.turn(S.lastSpeak || S.currentQuestion);
    return;
  }
  if (act === 'skip') { await doSkip(); return; }
  if (act === 'hint') { await doHint(); return; }
  if (act === 'end') { await doEnd(); return; }
}

/* ===================== answering ===================== */
async function submitAnswer(text) {
  if (!text || !S.sessionId) return;

  const cmd = matchCommand(text);
  if (cmd) { clearLive(); VoiceEngine.reset(); await runCommand(cmd); return; }

  S.lastAnswer = text;
  clearLive();
  addBubble('you', text);

  try {
    const body = S.answeringProbe
      ? { answer: text, followup_answer: S.probeText }
      : { answer: text };
    const data = await api(`/api/sessions/${S.sessionId}/answer`, {
      method: 'POST', body: JSON.stringify(body),
    });

    const last = $('thread').querySelector('.b.you:last-of-type');
    if (data.score && last) {
      const chip = document.createElement('div');
      chip.className = 'score';
      chip.style.color = BAND_COLOR(data.score.overall);
      chip.textContent = `${data.score.overall}/10 · ${data.score.band}`;
      last.appendChild(chip);
    }

    if (data.type === 'probe') {
      S.answeringProbe = true; S.probeText = data.probe;
      const line = `${Math.round(data.score.overall)} out of 10. ${data.probe}`;
      S.lastSpeak = line;
      addBubble('bot', data.probe);
      VoiceEngine.turn(line);
      return;
    }

    if (data.type === 'next') {
      S.answeringProbe = false; S.probeText = null;
      S.seq = data.next.seq;
      document.querySelectorAll('#dots i').forEach((d, i) => {
        d.className = i < S.seq - 1 ? 'on' : i === S.seq - 1 ? 'now' : '';
      });
      const bridge = reaction(data.score);
      const line = `${bridge} ${data.next.text}`;
      S.lastSpeak = line;
      S.currentQuestion = data.next.text;
      addBubble('bot', data.next.text);
      VoiceEngine.turn(line);
      return;
    }

    if (data.type === 'report') {
      addBubble('bot', data.report.closing || 'That wraps up the round.');
      VoiceEngine.say(`That's the end of the round. ${data.report.closing || ''}`);
      setTimeout(() => renderReport(data.report), 2200);
    }
  } catch (e) {
    toast(e.message);
    VoiceEngine.listen();
  } finally {
    VoiceEngine.reset();
  }
}

// A short spoken reaction, so scoring is heard rather than read.
function reaction(sc) {
  if (!sc) return 'Okay.';
  const s = sc.overall;
  if (s >= 8) return 'Strong answer.';
  if (s >= 7) return 'Good answer.';
  if (s >= 5.5) return 'Alright, though that could be sharper.';
  if (s >= 3.5) return 'That was a bit thin.';
  return 'Okay. Let us move on.';
}

/* ===================== spoken actions ===================== */
async function doSkip() {
  VoiceEngine.stopListening();
  sysNote('skipped');
  try {
    const data = await api(`/api/sessions/${S.sessionId}/skip`, { method: 'POST' });
    if (data.type === 'report') return renderReport(data.report);
    S.answeringProbe = false; S.probeText = null;
    S.seq = data.next.seq;
    S.currentQuestion = data.next.text;
    S.lastSpeak = `Sure. ${data.next.text}`;
    addBubble('bot', data.next.text);
    VoiceEngine.turn(S.lastSpeak);
  } catch (e) { toast(e.message); VoiceEngine.listen(); }
}

async function doHint() {
  try {
    const data = await api(`/api/sessions/${S.sessionId}/hint`, { method: 'POST' });
    sysNote('hint');
    addBubble('bot', data.hint, { who: 'Hint' });
    VoiceEngine.turn(`Here is a hint. ${data.hint}`);
  } catch (e) { toast(e.message); VoiceEngine.listen(); }
}

async function doEnd() {
  VoiceEngine.stopListening();
  sysNote('ending the interview');
  try {
    const data = await api(`/api/sessions/${S.sessionId}/finish`, { method: 'POST' });
    if (window.speechSynthesis) speechSynthesis.cancel();
    VoiceEngine.say(`Alright, let's stop there. ${data.report.closing || ''}`);
    setTimeout(() => renderReport(data.report), 1800);
  } catch (e) { toast(e.message); }
}

/* ===================== report ===================== */
function renderReport(r) {
  VoiceEngine.stopListening();
  VoiceEngine.enable(false);
  $('stage').classList.add('hide');
  $('report').classList.remove('hide');
  $('report').innerHTML = `
    <div class="card report">
      <h2>${esc(r.company)} · ${esc(prettyRound(r.round))}</h2>
      <p class="sub">${esc(r.student_name)} · ${r.turns} scored answer${r.turns === 1 ? '' : 's'}</p>
      <div class="ringrow">
        <svg width="70" height="70" viewBox="0 0 36 36" aria-hidden="true">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="#212c4d" stroke-width="3.4"/>
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="${BAND_COLOR(r.overall)}" stroke-width="3.4"
            stroke-linecap="round" stroke-dasharray="${r.overall / 10 * 97.4} 97.4" transform="rotate(-90 18 18)"/>
          <text x="18" y="20.8" text-anchor="middle" font-size="9.5" font-weight="800" fill="#e8ecf8"
            font-family="sans-serif">${r.overall}</text>
        </svg>
        <div>
          <b style="font-size:15px">${esc(r.band)}</b>
          <div class="muted" style="font-size:12.5px">${esc(r.verdict)}</div>
          <div class="muted" style="font-size:12px;margin-top:4px">
            strongest <b>${esc(r.strongest_dimension || '—')}</b> ·
            weakest <b>${esc(r.weakest_dimension || '—')}</b></div>
        </div>
      </div>
      <h3>What to fix next</h3>
      <ul class="list">${(r.next_actions || []).map(a => `<li>${esc(a)}</li>`).join('')}</ul>
      ${(r.focus_plan || []).length ? `<h3>Your focus plan</h3>
        ${r.focus_plan.map(f => `<div class="advice"><b>${esc(f.topic)}</b> (${f.avg_score}/10)<br>${esc(f.why)}</div>`).join('')}` : ''}
      <h3>Answer by answer</h3>
      ${(r.per_turn || []).map(t => `<div class="turn">
        <div class="row" style="justify-content:space-between;align-items:flex-start">
          <b style="font-size:13px;flex:1">Q${t.seq}. ${esc(t.question)}</b>
          <b style="color:${BAND_COLOR(t.overall)};white-space:nowrap">${t.overall}/10</b></div>
        <div class="muted" style="font-size:12.4px;margin:6px 0">You said: ${esc(t.answer)}</div>
        <ul class="list">${(t.improvements || []).map(i => `<li>${esc(i)}</li>`).join('')}</ul></div>`).join('')}
      <div class="banner">${esc(r.closing || '')}</div>
      <a class="again" href="./">Talk to the interviewer again ↻</a>
    </div>`;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ===================== voice engine wiring ===================== */
VoiceEngine.init({
  onState: setUIState,
  onTranscript: (text) => setLive(text),
  onAutoSubmit: (text) => submitAnswer(text),
  onError: (msg) => { if (msg) toast(msg); },
});

/* ===================== the only gesture in the whole app =====================
   Browsers refuse to play audio until the user has interacted with the page
   (autoplay policy) and need an explicit gesture to open the microphone.
   One tap starts the call; after that it is entirely speech-driven. */
$('startBtn').addEventListener('click', startInterview);

/* Clicking anywhere on the interview reopens the mic if it ever goes quiet.
   Not a control — just a safety net so a hiccup never ends the session. */
$('stage').addEventListener('click', () => {
  if (VoiceEngine.speaking || VoiceEngine.listening) return;
  VoiceEngine.enable(true);
  VoiceEngine.listen();
});

/* Keyboard equivalents stay for accessibility and quiet rooms. */
document.addEventListener('keydown', (e) => {
  if ($('stage').classList.contains('hide')) return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  const k = e.key.toLowerCase();
  if (e.code === 'Space') { e.preventDefault(); const t = VoiceEngine.finishTurn(); if (!t) VoiceEngine.listen(); }
  else if (k === 'r') { e.preventDefault(); VoiceEngine.turn(S.lastSpeak || S.currentQuestion); }
  else if (k === 's') { e.preventDefault(); doSkip(); }
  else if (k === 'h') { e.preventDefault(); doHint(); }
  else if (k === 'm') { e.preventDefault(); VoiceEngine.enable(true); VoiceEngine.listen(); }
  else if (e.key === 'Escape') { e.preventDefault(); doEnd(); }
});

/* ===================== boot ===================== */
const PREF_KEY = 'interviewloop_prefs_v1';

function loadPrefs() {
  let p = {};
  try { p = JSON.parse(localStorage.getItem(PREF_KEY) || '{}') || {}; } catch (e) { p = {}; }
  if (p.name) $('studentName').value = p.name;
  if (p.company) pendingCompany = p.company;
  if (p.round) pendingRound = p.round;
  if (p.limit) $('lenSel').value = p.limit;
  if (p.pace) $('paceSel').value = p.pace;
  return p;
}

function savePrefs() {
  try {
    localStorage.setItem(PREF_KEY, JSON.stringify({
      name: $('studentName').value.trim(),
      company: $('companySel').value,
      round: $('roundSel').value,
      limit: $('lenSel').value,
      pace: $('paceSel').value,
    }));
  } catch (e) {}
}

let pendingCompany = null, pendingRound = null;

$('companySel').addEventListener('change', loadRounds);
lobbyViz.start();
lobbyViz.set('idle');

const prefs = loadPrefs();
// A first-time visitor needs to see who they're interviewing with, so the
// panel starts open and closes itself once they start talking.
$('opts').open = !prefs.name;

loadCompanies().then(() => {
  if (pendingCompany) {
    $('companySel').value = pendingCompany;
    loadRounds().then(() => { if (pendingRound) $('roundSel').value = pendingRound; });
  }
  if (!checkVoice()) { $('opts').open = true; return; }
  $('callState').textContent = prefs.name ? `Ready when you are, ${prefs.name}` : 'Ready when you are';
});
</script>
</body>
</html>

```

---

<!-- FILE: static/voice.js -->

<sub>9565 bytes</sub>

```javascript
/**
 * voice.js — voice-first conversation engine.
 *
 * Goal: a hands-free interview. The bot SPEAKS the question, then automatically
 * starts listening; when you stop talking, it submits your answer by itself and
 * speaks the next question. You never touch the keyboard.
 *
 * Core problem this solves: echo. If the mic is open while the bot is talking,
 * the browser transcribes the bot's own voice and you end up answering yourself.
 * So the mic is hard-gated against synthesis (see the `speaking` flag).
 *
 * Dependency-free. Used by the server UI and inlined into standalone.html.
 */
(function () {
  'use strict';

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  const state = {
    enabled: false,
    speaking: false,
    listening: false,
    thinking: false,
    wantListening: false,   // desired state — survives the engine's onend
    finalText: '',
    noSpeechRetries: 0,
    autoSubmitDelay: 1700,  // ms of silence before auto-submitting
  };

  let rec = null;
  let silenceTimer = null;
  let restartTimer = null;
  let voices = [];
  let handlers = {
    onState: function () {},
    onTranscript: function () {},
    onAutoSubmit: function () {},
    onError: function () {},
  };

  /* ---------------------------------------------------------------- utils */

  const emit = (s, detail) => { handlers.onState(s, detail); };

  function loadVoices() {
    try { voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : []; }
    catch (e) { voices = []; }
  }

  function pickVoice() {
    if (!voices.length) loadVoices();
    if (!voices.length) return null;
    const en = voices.filter(v => /^en(-|$)/i.test(v.lang));
    const pool = en.length ? en : voices;
    // Prefer an Indian English voice, then a named female voice, then anything.
    return pool.find(v => /en[-_]in/i.test(v.lang))
        || pool.find(v => /female|woman|zira|heera|neerja|samantha/i.test(v.name))
        || pool[0];
  }

  function clearSilence() {
    if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
  }

  function armSilence() {
    clearSilence();
    silenceTimer = setTimeout(() => {
      const text = state.finalText.trim();
      if (text && !state.thinking) {
        state.thinking = true;
        stopListening();
        emit('thinking');
        handlers.onAutoSubmit(text);
      }
    }, state.autoSubmitDelay);
  }

  /* ---------------------------------------------------------------- speech */

  function speak(text, done) {
    const finish = () => {
      state.speaking = false;
      if (done) done();
    };

    if (!state.enabled || !window.speechSynthesis || !text) { finish(); return; }

    // Echo guard: never have the mic open while the bot is talking.
    stopListening();
    state.speaking = true;
    emit('speaking', text);

    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text).replace(/[*#`_]/g, ''));
      const v = pickVoice();
      if (v) u.voice = v;
      u.lang = (v && v.lang) || 'en-IN';
      u.rate = 0.97;
      u.pitch = 1.02;
      u.volume = 1;

      let ended = false;
      const once = () => { if (!ended) { ended = true; finish(); } };
      u.onend = once;
      u.onerror = once;

      speechSynthesis.speak(u);

      // Safety valve: some engines never fire onend (or fire it instantly when
      // cancelled). Without this the conversation deadlocks with no mic and no
      // speech. Estimate generously from text length.
      const estimate = Math.min(30000, 2200 + String(text).length * 72);
      setTimeout(once, estimate);
    } catch (e) {
      finish();
    }
  }

  function buildRecognizer() {
    if (!SR) return null;
    const r = new SR();
    r.continuous = true;
    r.interimResults = true;
    r.lang = 'en-IN';
    r.maxAlternatives = 1;

    r.onstart = () => {
      state.listening = true;
      emit('listening');
    };

    r.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          state.finalText += (state.finalText ? ' ' : '') + t.trim();
          state.noSpeechRetries = 0;
        } else {
          interim += t;
        }
      }
      const shown = (state.finalText + ' ' + interim).replace(/\s+/g, ' ').trim();
      handlers.onTranscript(shown, !!interim);
      // Every new word pushes the auto-submit timer back — that IS the
      // "you stopped talking" detector.
      armSilence();
    };

    r.onerror = (e) => {
      const err = e.error;
      if (err === 'no-speech' || err === 'aborted') {
        // Harmless: the engine timed out, or we stopped it ourselves.
        return;
      }
      if (err === 'not-allowed' || err === 'service-not-allowed') {
        state.wantListening = false;
        state.listening = false;
        emit('idle');
        handlers.onError({
          code: 'mic-blocked',
          message: 'Microphone blocked. Allow mic access for this site, then reload.',
        });
        return;
      }
      if (err === 'network') {
        state.wantListening = false;
        state.listening = false;
        emit('idle');
        handlers.onError({
          code: 'network',
          message: 'Speech recognition needs an internet connection (Chrome sends audio to its speech service).',
        });
        return;
      }
      handlers.onError({ code: err, message: 'Voice error: ' + err });
    };

    r.onend = () => {
      state.listening = false;
      if (state.speaking) { emit('speaking'); return; }   // echo guard
      if (state.thinking) { emit('thinking'); return; }
      if (state.wantListening) {
        // The engine stops itself after ~60s of silence or on transient
        // errors. Restart so a long think doesn't kill the session.
        clearTimeout(restartTimer);
        restartTimer = setTimeout(() => {
          if (state.wantListening && !state.speaking) startListening();
        }, 300);
      } else {
        emit('idle');
      }
    };

    return r;
  }

  function startListening() {
    if (!state.enabled) return;
    if (!rec) rec = buildRecognizer();
    if (!rec) {
      handlers.onError({ code: 'unsupported', message: 'This browser has no speech recognition.' });
      return;
    }
    if (state.speaking) return;                   // never listen over the bot
    state.wantListening = true;
    state.thinking = false;
    try {
      rec.start();
    } catch (e) {
      // start() throws if already running — that is fine, just re-emit state.
      if (String(e && e.name) === 'InvalidStateError') emit('listening');
    }
  }

  function stopListening() {
    state.wantListening = false;
    clearSilence();
    clearTimeout(restartTimer);
    if (rec) {
      try { rec.stop(); } catch (e) { /* not running */ }
    }
    state.listening = false;
  }

  function stopSpeaking() {
    if (window.speechSynthesis) {
      try { speechSynthesis.cancel(); } catch (e) {}
    }
    state.speaking = false;
    emit('idle');
  }

  /* ------------------------------------------------------------ public API */

  const VoiceEngine = {
    /** What this browser can actually do, for honest UI messaging. */
    capabilities() {
      return {
        tts: 'speechSynthesis' in window,
        stt: !!SR,
        secure: !!window.isSecureContext,
        fileProtocol: String(location.protocol) === 'file:',
        works: !!(SR && 'speechSynthesis' in window),
      };
    },

    init(h) {
      Object.assign(handlers, h || {});
      loadVoices();
      if (window.speechSynthesis) speechSynthesis.onvoiceschanged = loadVoices;
      return this;
    },

    get enabled() { return state.enabled; },
    get speaking() { return state.speaking; },
    get listening() { return state.listening; },
    get thinking() { return state.thinking; },
    get transcript() { return state.finalText; },

    setAutoSubmitDelay(ms) { state.autoSubmitDelay = Math.max(600, ms | 0); },

    enable(on) {
      state.enabled = !!on;
      if (!state.enabled) {
        stopListening();
        stopSpeaking();
      }
      return state.enabled;
    },

    /**
     * The whole turn: speak the line, then open the mic automatically.
     * This is what makes the conversation hands-free.
     */
    turn(text, opts) {
      const listenAfter = !opts || opts.listenAfter !== false;
      state.finalText = '';
      state.thinking = false;
      handlers.onTranscript('', false);
      speak(text, () => {
        if (!state.enabled) { emit('idle'); return; }
        if (listenAfter) {
          // Small gap so the tail of the bot's own voice can't leak into the mic.
          setTimeout(() => startListening(), 420);
        } else {
          emit('idle');
        }
      });
    },

    /** Speak without opening the mic (used for sign-off). */
    say(text) { this.turn(text, { listenAfter: false }); },

    listen() { startListening(); },
    stopListening,
    stopSpeaking,

    /** Manual "send now" — also cancels the silence timer. */
    finishTurn() {
      const text = state.finalText.trim();
      clearSilence();
      stopListening();
      if (text) {
        state.thinking = true;
        emit('thinking');
        handlers.onAutoSubmit(text);
      }
      return text;
    },

    reset() {
      state.finalText = '';
      state.thinking = false;
      clearSilence();
      handlers.onTranscript('', false);
    },
  };

  window.VoiceEngine = VoiceEngine;
})();

```

---
