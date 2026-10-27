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
