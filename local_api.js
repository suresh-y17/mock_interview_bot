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
