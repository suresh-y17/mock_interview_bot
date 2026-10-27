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
