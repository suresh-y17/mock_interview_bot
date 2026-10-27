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
