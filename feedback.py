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
