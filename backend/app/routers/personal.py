"""Learner-facing features: history, feedback, learning, phrases, video analysis, dashboard."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from ..api import ApiError, Ctx, Router, not_found
from ..db import jdump, jload, utcnow
from ..services import VIDEO_TYPES, audit, probe_video, sniff_video
from .signs import translations_for

router = Router("personal")


class HistoryIn(BaseModel):
    state: str = Field(pattern="^(recognized|uncertain|unknown|insufficient_input|model_unavailable|camera_unavailable)$")
    model_id: str | None = Field(default=None, max_length=120)
    top: list[dict] = Field(default_factory=list, max_length=10)
    chosen_sign: str | None = None
    corrected_sign: str | None = None


class FeedbackIn(BaseModel):
    kind: str = Field(pattern="^(prediction|correction|bug|content|accessibility|other)$")
    message: str = Field(min_length=3, max_length=4000)
    sign_id: str | None = None


class FeedbackPatch(BaseModel):
    status: str = Field(pattern="^(open|resolved|dismissed)$")
    resolution: str | None = Field(default=None, max_length=2000)


class AttemptIn(BaseModel):
    sign_id: str
    mode: str = Field(pattern="^(quiz|practice|review|coach)$")
    correct: bool
    answer: str | None = Field(default=None, max_length=120)


class LessonsQuery(BaseModel):
    include_unverified: bool = False


class QuizQuery(BaseModel):
    category: str | None = None
    n: int = Field(default=5, ge=1, le=20)


class PhraseIn(BaseModel):
    sign_ids: list[str] = Field(min_length=1, max_length=30)
    text: str = Field(min_length=1, max_length=1000)
    language: str = Field(default="en", pattern="^(en|hi|kn)$")
    is_quick: bool = False


def _check_sign(ctx: Ctx, sid: str | None) -> None:
    if sid and not ctx.db.one("SELECT sign_id FROM signs WHERE sign_id = ?", (sid,)):
        raise ApiError(422, "validation_error", f"unknown sign {sid}")


# --------------------------------------------------------------------------- history

@router.get("/history", summary="My recognition history")
def history(ctx: Ctx):
    rows = ctx.db.all("SELECT * FROM recognition_history WHERE user_id = ? ORDER BY id DESC LIMIT 200", (ctx.uid,))
    for r in rows:
        r["top"] = jload(r["top"]) or []
    return rows


@router.post("/history", summary="Save a recognition result", body=HistoryIn, status=201)
def add_history(ctx: Ctx):
    b: HistoryIn = ctx.body
    _check_sign(ctx, b.chosen_sign)
    _check_sign(ctx, b.corrected_sign)
    hid = ctx.db.insert("recognition_history", {"user_id": ctx.uid, "model_id": b.model_id, "state": b.state,
                                                "top": jdump(b.top), "chosen_sign": b.chosen_sign,
                                                "corrected_sign": b.corrected_sign, "created_at": utcnow()})
    return {"id": hid}


@router.patch("/history/{hid}", summary="Correct a saved result", body=HistoryIn)
def correct_history(ctx: Ctx):
    b: HistoryIn = ctx.body
    _check_sign(ctx, b.corrected_sign)
    n = ctx.db.update("recognition_history", {"corrected_sign": b.corrected_sign}, "id = ? AND user_id = ?",
                      (int(ctx.params["hid"]), ctx.uid))
    if not n:
        raise not_found("history item")
    return {"ok": True}


@router.delete("/history/{hid}", summary="Delete one history item")
def delete_history(ctx: Ctx):
    n = ctx.db.execute("DELETE FROM recognition_history WHERE id = ? AND user_id = ?",
                       (int(ctx.params["hid"]), ctx.uid)).rowcount
    if not n:
        raise not_found("history item")
    return {"ok": True}


@router.delete("/history", summary="Clear my history")
def clear_history(ctx: Ctx):
    n = ctx.db.execute("DELETE FROM recognition_history WHERE user_id = ?", (ctx.uid,)).rowcount
    return {"deleted": n}


# --------------------------------------------------------------------------- feedback

@router.post("/feedback", summary="Send feedback or a correction report", auth="optional", body=FeedbackIn,
             status=201)
def feedback(ctx: Ctx):
    b: FeedbackIn = ctx.body
    _check_sign(ctx, b.sign_id)
    fid = ctx.db.insert("feedback", {"user_id": ctx.user["id"] if ctx.user else None, "kind": b.kind,
                                     "sign_id": b.sign_id, "message": b.message.strip(), "created_at": utcnow()})
    return {"id": fid, "status": "open"}


@router.get("/feedback", summary="Feedback inbox", perm="feedback:read")
def list_feedback(ctx: Ctx):
    return ctx.db.all("SELECT f.*, u.display_name AS author FROM feedback f LEFT JOIN users u ON u.id = f.user_id "
                      "ORDER BY f.id DESC LIMIT 300")


@router.patch("/feedback/{fid}", summary="Resolve feedback", perm="feedback:read", body=FeedbackPatch)
def resolve_feedback(ctx: Ctx):
    n = ctx.db.update("feedback", ctx.body.model_dump(exclude_none=True), "id = ?", (int(ctx.params["fid"]),))
    if not n:
        raise not_found("feedback")
    audit(ctx.db, ctx.uid, "feedback.update", ctx.params["fid"], ctx.body.model_dump(), ctx.ip)
    return ctx.db.one("SELECT * FROM feedback WHERE id = ?", (int(ctx.params["fid"]),))


# --------------------------------------------------------------------------- learning

@router.get("/learning/lessons", summary="Lessons by category (verified content by default)", auth="optional",
            query=LessonsQuery)
def lessons(ctx: Ctx):
    statuses = ("verified", "reference_found", "review_pending") if ctx.query.include_unverified else ("verified",)
    marks = ",".join("?" for _ in statuses)
    rows = ctx.db.all(f"SELECT sign_id, canonical_sign_name, category, category_label, verification_status "
                      f"FROM signs WHERE retired = ? AND verification_status IN ({marks}) ORDER BY sign_id",
                      (False, *statuses))
    prog = {}
    if ctx.user:
        prog = {p["sign_id"]: p for p in ctx.db.all("SELECT * FROM learning_progress WHERE user_id = ?", (ctx.uid,))}
    out: dict[str, dict] = {}
    for r in rows:
        les = out.setdefault(r["category"], {"category": r["category"], "label": r["category_label"], "signs": []})
        p = prog.get(r["sign_id"])
        les["signs"].append({**r, "attempts": p["attempts"] if p else 0, "correct": p["correct"] if p else 0})
    total_verified = ctx.db.scalar("SELECT COUNT(*) FROM signs WHERE verification_status = 'verified' AND retired = ?",
                                   (False,))
    return {"verified_signs": total_verified, "include_unverified": ctx.query.include_unverified,
            "lessons": list(out.values())}


@router.get("/learning/quiz", summary="Quiz built only from verified signs and verified meanings",
            auth="optional", query=QuizQuery)
def quiz(ctx: Ctx):
    q: QuizQuery = ctx.query
    params: list = [False]
    sql = ("SELECT s.sign_id, s.canonical_sign_name, s.category, s.linguistic_description FROM signs s "
           "JOIN translations t ON t.sign_id = s.sign_id AND t.language = 'en' AND t.status = 'verified' "
           "WHERE s.verification_status = 'verified' AND s.retired = ?")
    if q.category:
        sql += " AND s.category = ?"
        params.append(q.category)
    pool = ctx.db.all(sql, params)
    if len(pool) < 2:
        return {"available": False, "reason": "a quiz needs at least 2 verified signs with verified English meanings",
                "questions": []}
    rng = random.Random()
    refs = {r["sign_id"]: r for r in ctx.db.all("SELECT sign_id, source_name, source_url, media_url FROM sign_references")}
    tr = translations_for(ctx.db, [p["sign_id"] for p in pool])
    qs = []
    for s in rng.sample(pool, min(q.n, len(pool))):
        others = [o for o in pool if o["sign_id"] != s["sign_id"]]
        opts = [s, *rng.sample(others, min(3, len(others)))]
        rng.shuffle(opts)
        qs.append({"sign_id": s["sign_id"], "prompt": s["linguistic_description"] or "Identify the meaning of this sign",
                   "reference": refs.get(s["sign_id"]),
                   "options": [{"sign_id": o["sign_id"], "text": tr[o["sign_id"]]["en"]["text"]} for o in opts]})
    return {"available": True, "questions": qs}


@router.get("/learning/progress", summary="My learning progress")
def progress(ctx: Ctx):
    rows = ctx.db.all("SELECT p.*, s.canonical_sign_name, s.category FROM learning_progress p JOIN signs s "
                      "ON s.sign_id = p.sign_id WHERE p.user_id = ? ORDER BY p.last_seen_at DESC", (ctx.uid,))
    attempts = sum(r["attempts"] for r in rows)
    correct = sum(r["correct"] for r in rows)
    difficult = [r for r in rows if r["attempts"] >= 2 and r["correct"] / r["attempts"] < 0.6]
    return {"signs_practised": len(rows), "attempts": attempts, "correct": correct,
            "accuracy": round(correct / attempts, 3) if attempts else None, "difficult": difficult, "items": rows}


BADGES = [
    # (id, title, description, test on the stats dict)
    ("first_step", "First step", "Record your first attempt", lambda s: s["attempts"] >= 1),
    ("ten_signs", "Ten signs", "Practise 10 different signs", lambda s: s["signs_practised"] >= 10),
    ("fifty_signs", "Fifty signs", "Practise 50 different signs", lambda s: s["signs_practised"] >= 50),
    ("sharp_eye", "Sharp eye", "At least 80 % correct over 20 or more attempts",
     lambda s: s["attempts"] >= 20 and s["correct"] / s["attempts"] >= 0.8),
    ("streak_3", "Three-day streak", "Practise on 3 days in a row", lambda s: s["best_streak"] >= 3),
    ("streak_7", "Week streak", "Practise on 7 days in a row", lambda s: s["best_streak"] >= 7),
    ("coached", "Coached", "Pass 5 Practice Coach attempts (score 70 or more)", lambda s: s["coach_passed"] >= 5),
]
WEEKLY_GOAL = 20
DAILY_GOAL = 10


def _streaks(days: list[str], today: str) -> tuple[int, int]:
    """Current and best run of consecutive UTC days with at least one attempt."""
    from datetime import date, timedelta
    ds = sorted({date.fromisoformat(d) for d in days})
    best = run = 0
    prev = None
    for d in ds:
        run = run + 1 if prev is not None and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    t = date.fromisoformat(today)
    current = run if ds and (t - ds[-1]).days <= 1 else 0
    return current, best


@router.get("/learning/achievements", summary="My streaks, points, weekly goal and badges (from my own attempts)")
def achievements(ctx: Ctx):
    from datetime import UTC, datetime, timedelta
    rows = ctx.db.all("SELECT sign_id, mode, correct, created_at FROM learning_attempts WHERE user_id = ?", (ctx.uid,))
    now = datetime.now(UTC)
    today = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    current, best = _streaks([str(r["created_at"])[:10] for r in rows], today)
    correct = sum(1 for r in rows if r["correct"])
    stats = {"attempts": len(rows), "correct": correct, "signs_practised": len({r["sign_id"] for r in rows}),
             "current_streak": current, "best_streak": best,
             "coach_passed": sum(1 for r in rows if r["mode"] == "coach" and r["correct"]),
             "points": 10 * correct + 2 * (len(rows) - correct),
             "this_week": sum(1 for r in rows if str(r["created_at"])[:10] >= week_start),
             "today": sum(1 for r in rows if str(r["created_at"])[:10] == today)}
    try:
        goal = min(200, max(1, int((jload(ctx.user.get("settings")) or {}).get("daily_goal") or DAILY_GOAL)))
    except (TypeError, ValueError):
        goal = DAILY_GOAL
    return {**stats, "weekly_goal": WEEKLY_GOAL, "daily_goal": goal,
            "badges": [{"id": b, "title": t, "description": d, "earned": bool(f(stats))} for b, t, d, f in BADGES]}


REVIEW_INTERVAL_DAYS = [0, 1, 2, 4, 8, 16]  # Leitner boxes 0..5


def _due(now_iso: str, box: int) -> str:
    from datetime import datetime, timedelta
    t = datetime.strptime(now_iso, "%Y-%m-%dT%H:%M:%SZ") + timedelta(days=REVIEW_INTERVAL_DAYS[box])
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


@router.post("/learning/attempts", summary="Record a practice or quiz attempt", body=AttemptIn, status=201)
def attempt(ctx: Ctx):
    b: AttemptIn = ctx.body
    _check_sign(ctx, b.sign_id)
    now = utcnow()
    with ctx.db.transaction():
        ctx.db.insert("learning_attempts", {"user_id": ctx.uid, "sign_id": b.sign_id, "mode": b.mode,
                                            "correct": b.correct, "answer": b.answer, "created_at": now})
        row = ctx.db.one("SELECT review_box FROM learning_progress WHERE user_id = ? AND sign_id = ?", (ctx.uid, b.sign_id))
        # spaced repetition: a correct answer moves the sign up one box (longer interval), a wrong one back to box 0
        box = min(int(row["review_box"] or 0) + 1, 5) if (row and b.correct) else (1 if b.correct else 0)
        if row:
            ctx.db.execute("UPDATE learning_progress SET attempts = attempts + 1, correct = correct + ?, "
                           "last_seen_at = ?, review_box = ?, due_at = ? WHERE user_id = ? AND sign_id = ?",
                           (int(b.correct), now, box, _due(now, box), ctx.uid, b.sign_id))
        else:
            ctx.db.insert("learning_progress", {"user_id": ctx.uid, "sign_id": b.sign_id, "attempts": 1,
                                                "correct": int(b.correct), "last_seen_at": now,
                                                "review_box": box, "due_at": _due(now, box)}, pk=None)
    return {"ok": True, "review_box": box, "next_review": _due(now, box)}


@router.get("/learning/review", summary="Signs due for review today (spaced repetition)")
def review_queue(ctx: Ctx):
    now = utcnow()
    rows = ctx.db.all("SELECT p.sign_id, p.attempts, p.correct, p.review_box, p.due_at, s.canonical_sign_name, s.category "
                      "FROM learning_progress p JOIN signs s ON s.sign_id = p.sign_id "
                      "WHERE p.user_id = ? AND p.due_at IS NOT NULL AND p.due_at <= ? ORDER BY p.due_at, p.sign_id",
                      (ctx.uid, now))
    upcoming = ctx.db.scalar("SELECT COUNT(*) FROM learning_progress WHERE user_id = ? AND due_at > ?", (ctx.uid, now)) or 0
    return {"due": rows, "due_count": len(rows), "upcoming": int(upcoming), "intervals_days": REVIEW_INTERVAL_DAYS}


# --------------------------------------------------------------------------- phrases

@router.get("/phrases", summary="My saved phrases and the curated quick phrases", auth="optional")
def phrases(ctx: Ctx):
    rows = ctx.db.all("SELECT * FROM phrases WHERE is_quick = ? OR user_id = ? ORDER BY is_quick DESC, id DESC LIMIT 200",
                      (True, ctx.user["id"] if ctx.user else -1))
    for r in rows:
        r["sign_ids"] = jload(r["sign_ids"])
        r["is_quick"] = bool(r["is_quick"])
    return rows


@router.post("/phrases", summary="Save a composed phrase", body=PhraseIn, status=201)
def add_phrase(ctx: Ctx):
    b: PhraseIn = ctx.body
    for s in b.sign_ids:
        _check_sign(ctx, s)
    if b.is_quick:
        ctx.require("phrases:quick")
        marks = ",".join("?" for _ in b.sign_ids)
        nv = ctx.db.scalar(f"SELECT COUNT(*) FROM signs WHERE sign_id IN ({marks}) AND verification_status = 'verified'",
                           b.sign_ids)
        if nv != len(set(b.sign_ids)):
            raise ApiError(422, "unverified_signs", "kiosk quick phrases may only use verified signs")
    pid = ctx.db.insert("phrases", {"user_id": ctx.uid, "sign_ids": jdump(b.sign_ids), "text": b.text.strip(),
                                    "language": b.language, "is_quick": b.is_quick, "created_at": utcnow()})
    return {"id": pid}


@router.delete("/phrases/{pid}", summary="Delete a phrase")
def delete_phrase(ctx: Ctx):
    p = ctx.db.one("SELECT * FROM phrases WHERE id = ?", (int(ctx.params["pid"]),))
    if not p:
        raise not_found("phrase")
    if p["user_id"] != ctx.uid and not (p["is_quick"] and ctx.can("phrases:quick")):
        raise ApiError(403, "forbidden", "not your phrase")
    ctx.db.execute("DELETE FROM phrases WHERE id = ?", (p["id"],))
    return {"ok": True}


# --------------------------------------------------------------------------- video analysis

def _purge_expired(ctx: Ctx) -> None:
    for j in ctx.db.all("SELECT id, storage_key FROM analysis_jobs WHERE expires_at < ? AND storage_key IS NOT NULL",
                        (utcnow(),)):
        try:
            ctx.app.storage.delete(j["storage_key"])
        except ValueError:
            pass
        ctx.db.update("analysis_jobs", {"storage_key": None, "status": "expired"}, "id = ?", (j["id"],))


@router.post("/analysis/videos", summary="Upload a video for analysis (auto-deleted after retention window)",
             multipart=True, status=201)
def upload_analysis(ctx: Ctx):
    f = ctx.form.get("file")
    if f is None or isinstance(f, str):
        raise ApiError(422, "validation_error", "file is required")
    limit = ctx.app.settings.max_upload_mb * 1024 * 1024
    data = f.file.read(limit + 1)
    if len(data) > limit:
        raise ApiError(413, "too_large", f"video exceeds {ctx.app.settings.max_upload_mb} MB")
    mime = sniff_video(data[:64])
    if mime is None:
        raise ApiError(415, "unsupported_media_type", "only MP4, WebM or MOV video is accepted")
    now = datetime.now(UTC)
    expires = (now + timedelta(hours=ctx.app.settings.analysis_retention_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    jid = ctx.db.insert("analysis_jobs", {"user_id": ctx.uid, "filename": (f.filename or "video")[:200],
                                          "mime_type": mime, "size_bytes": len(data), "status": "queued",
                                          "expires_at": expires, "created_at": utcnow()})
    key = f"analysis/{ctx.uid}/{jid}{VIDEO_TYPES[mime]}"
    ctx.app.storage.put(key, data)
    ctx.db.update("analysis_jobs", {"storage_key": key}, "id = ?", (jid,))
    ctx.app.jobs.submit(_analyse, ctx.app, jid)
    return _job(ctx, jid)


def _job(ctx: Ctx, jid: int) -> dict:
    j = ctx.db.one("SELECT * FROM analysis_jobs WHERE id = ? AND user_id = ?", (jid, ctx.uid))
    if not j:
        raise not_found("analysis job")
    j["result"] = jload(j["result"])
    return j


def _analyse(state, jid: int) -> None:
    with state.db.connect() as conn:
        j = conn.one("SELECT * FROM analysis_jobs WHERE id = ?", (jid,))
        conn.update("analysis_jobs", {"status": "processing"}, "id = ?", (jid,))
        path = state.storage.local_path(j["storage_key"])
        probe = probe_video(path.read_bytes(), path.suffix)
        result: dict = {"video": probe, "timeline": [], "predictions": []}
        status = "completed"
        try:
            from isl_nova_ml.extract import ExtractorUnavailable, LandmarkExtractor

            ex = LandmarkExtractor()
        except ExtractorUnavailable as exc:
            result["extractor"] = {"available": False, "reason": str(exc)}
            status = "extractor_unavailable"
        else:
            try:
                frames, aspect, meta = ex.video(path)
            finally:
                ex.close()
            result["extractor"] = {"available": True, **meta}
            result["timeline"] = [{"frame": i, "left": f["left"] is not None, "right": f["right"] is not None,
                                   "pose": f["pose"] is not None} for i, f in enumerate(frames)]
            p = state.models.predictor
            if p is None:
                result["predictions"] = []
                result["model"] = {"available": False, "reason": state.models.error}
            else:
                win, step = 45, 15
                for s in range(0, max(1, len(frames) - win + 1), step):
                    out = p.predict(frames[s:s + win], aspect, 3)
                    result["predictions"].append({"start_frame": s, "end_frame": s + win, **out})
        conn.update("analysis_jobs", {"status": status, "result": jdump(result), "finished_at": utcnow()},
                    "id = ?", (jid,))


@router.get("/analysis/videos", summary="My analysis jobs")
def list_jobs(ctx: Ctx):
    _purge_expired(ctx)
    rows = ctx.db.all("SELECT id, filename, mime_type, size_bytes, status, expires_at, created_at, finished_at "
                      "FROM analysis_jobs WHERE user_id = ? ORDER BY id DESC LIMIT 50", (ctx.uid,))
    return rows


@router.get("/analysis/videos/{jid}", summary="Analysis result")
def get_job(ctx: Ctx):
    _purge_expired(ctx)
    return _job(ctx, int(ctx.params["jid"]))


@router.delete("/analysis/videos/{jid}", summary="Delete an analysis job and its video now")
def delete_job(ctx: Ctx):
    j = _job(ctx, int(ctx.params["jid"]))
    if j["storage_key"]:
        ctx.app.storage.delete(j["storage_key"])
    ctx.db.execute("DELETE FROM analysis_jobs WHERE id = ?", (j["id"],))
    return {"ok": True}


# --------------------------------------------------------------------------- dashboard

@router.get("/dashboard", summary="Aggregated dashboard data (real counts only)", auth="optional")
def dashboard(ctx: Ctx):
    from .dataset import stats
    from .ml import _info

    ds = stats(ctx)
    mi = _info(ctx)
    me = None
    if ctx.user:
        me = {
            "history": ctx.db.scalar("SELECT COUNT(*) FROM recognition_history WHERE user_id = ?", (ctx.uid,)),
            "recognized": ctx.db.scalar("SELECT COUNT(*) FROM recognition_history WHERE user_id = ? AND state = 'recognized'", (ctx.uid,)),
            "bookmarks": ctx.db.scalar("SELECT COUNT(*) FROM bookmarks WHERE user_id = ?", (ctx.uid,)),
            "attempts": ctx.db.scalar("SELECT COALESCE(SUM(attempts), 0) FROM learning_progress WHERE user_id = ?", (ctx.uid,)),
            "unread_notifications": ctx.db.scalar("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL", (ctx.uid,)),
        }
    exps = {r["status"]: r["n"] for r in ctx.db.all("SELECT status, COUNT(*) AS n FROM experiments GROUP BY status")}
    return {"dataset": ds, "model": {k: mi.get(k) for k in ("available", "state", "reason", "model_id", "synthetic",
                                                            "n_classes", "metrics_summary")},
            "experiments": exps, "me": me, "time": utcnow()}
