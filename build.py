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
