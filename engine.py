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
