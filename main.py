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
