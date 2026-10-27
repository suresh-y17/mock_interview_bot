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
