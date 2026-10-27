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
