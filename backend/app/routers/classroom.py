"""Teacher classes.

A teacher (role ``teacher`` or ``admin``) creates a class and shares its join code.
A learner who joins agrees that the teacher sees a progress SUMMARY for the
learner: attempts, accuracy, streak, signs practised and the signs they find
hard. Recognition history, recordings and settings are never shared. Learners
can leave at any time, and the teacher then sees nothing more.
"""

from __future__ import annotations

import secrets
from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from ..api import ApiError, Ctx, Router, not_found
from ..db import utcnow
from ..services import audit

router = Router("classroom")

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


def _code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(8))


def _own_class(ctx: Ctx, cid: int) -> dict:
    c = ctx.db.one("SELECT * FROM classes WHERE id = ?", (cid,))
    if not c or (c["teacher_id"] != ctx.uid and "admin" not in ctx.roles):
        raise not_found("class")
    return c


@router.post("/classes", summary="Create a class (teacher)", perm="classes:manage", body=ClassIn, status=201)
def create_class(ctx: Ctx):
    for _ in range(5):
        code = _code()
        if not ctx.db.one("SELECT id FROM classes WHERE join_code = ?", (code,)):
            break
    cid = ctx.db.insert("classes", {"name": ctx.body.name.strip(), "teacher_id": ctx.uid, "join_code": code,
                                    "created_at": utcnow()})
    audit(ctx.db, ctx.uid, "class.create", f"class:{cid}", ip=ctx.ip)
    return ctx.db.one("SELECT * FROM classes WHERE id = ?", (cid,))


@router.get("/classes", summary="My classes: the ones I teach and the ones I joined")
def my_classes(ctx: Ctx):
    teaching = ctx.db.all("SELECT c.*, (SELECT COUNT(*) FROM class_members m WHERE m.class_id = c.id) AS members "
                          "FROM classes c WHERE c.teacher_id = ? ORDER BY c.id", (ctx.uid,))
    joined = ctx.db.all("SELECT c.id, c.name, u.display_name AS teacher, m.joined_at FROM class_members m "
                        "JOIN classes c ON c.id = m.class_id JOIN users u ON u.id = c.teacher_id "
                        "WHERE m.user_id = ? ORDER BY m.joined_at", (ctx.uid,))
    return {"teaching": teaching, "joined": joined, "can_teach": bool({"teacher", "admin"} & ctx.roles)}


@router.post("/classes/join", summary="Join a class with its code (shares a progress summary with the teacher)",
             body=JoinIn, rate="auth")
def join_class(ctx: Ctx):
    c = ctx.db.one("SELECT * FROM classes WHERE join_code = ?", (ctx.body.code.strip().upper(),))
    if not c:
        raise ApiError(404, "not_found", "no class with this code")
    if c["teacher_id"] == ctx.uid:
        raise ApiError(400, "own_class", "you teach this class")
    if not ctx.db.one("SELECT 1 AS x FROM class_members WHERE class_id = ? AND user_id = ?", (c["id"], ctx.uid)):
        ctx.db.insert("class_members", {"class_id": c["id"], "user_id": ctx.uid, "joined_at": utcnow()}, pk=None)
        audit(ctx.db, ctx.uid, "class.join", f"class:{c['id']}", ip=ctx.ip)
    return {"id": c["id"], "name": c["name"]}


@router.delete("/classes/{cid}/membership", summary="Leave a class (the teacher stops seeing my progress)")
def leave_class(ctx: Ctx):
    cid = int(ctx.params["cid"])
    ctx.db.execute("DELETE FROM class_members WHERE class_id = ? AND user_id = ?", (cid, ctx.uid))
    audit(ctx.db, ctx.uid, "class.leave", f"class:{cid}", ip=ctx.ip)
    return {"ok": True}


@router.delete("/classes/{cid}/members/{uid}", summary="Remove a learner from my class", perm="classes:manage")
def remove_member(ctx: Ctx):
    c = _own_class(ctx, int(ctx.params["cid"]))
    ctx.db.execute("DELETE FROM class_members WHERE class_id = ? AND user_id = ?", (c["id"], int(ctx.params["uid"])))
    return {"ok": True}


@router.delete("/classes/{cid}", summary="Delete a class", perm="classes:manage")
def delete_class(ctx: Ctx):
    c = _own_class(ctx, int(ctx.params["cid"]))
    ctx.db.execute("DELETE FROM classes WHERE id = ?", (c["id"],))
    audit(ctx.db, ctx.uid, "class.delete", f"class:{c['id']}", ip=ctx.ip)
    return {"ok": True}


@router.get("/classes/{cid}/progress", summary="Teacher dashboard: progress summary per learner and hard signs",
            perm="classes:manage")
def class_progress(ctx: Ctx):
    from .personal import _streaks

    c = _own_class(ctx, int(ctx.params["cid"]))
    members = ctx.db.all("SELECT u.id, u.display_name, m.joined_at FROM class_members m JOIN users u ON u.id = m.user_id "
                         "WHERE m.class_id = ? ORDER BY u.display_name", (c["id"],))
    today = utcnow()[:10]
    learners, per_sign = [], defaultdict(lambda: [0, 0])
    for m in members:
        rows = ctx.db.all("SELECT sign_id, correct, created_at FROM learning_attempts WHERE user_id = ?", (m["id"],))
        n = len(rows)
        ok = sum(1 for r in rows if r["correct"])
        cur, best = _streaks([str(r["created_at"])[:10] for r in rows], today)
        wrong = Counter(r["sign_id"] for r in rows if not r["correct"])
        for r in rows:
            per_sign[r["sign_id"]][0] += 1
            per_sign[r["sign_id"]][1] += bool(r["correct"])
        learners.append({"user_id": m["id"], "name": m["display_name"], "joined_at": m["joined_at"],
                         "attempts": n, "accuracy": round(ok / n, 3) if n else None,
                         "signs_practised": len({r["sign_id"] for r in rows}), "current_streak": cur,
                         "last_active": max((str(r["created_at"]) for r in rows), default=None),
                         "hardest": [s for s, _ in wrong.most_common(3)]})
    names = {s["sign_id"]: s["canonical_sign_name"] for s in ctx.db.all("SELECT sign_id, canonical_sign_name FROM signs")}
    hard = sorted(({"sign_id": s, "name": names.get(s, s), "attempts": a, "accuracy": round(k / a, 3)}
                   for s, (a, k) in per_sign.items() if a >= 3), key=lambda d: (d["accuracy"], -d["attempts"]))[:10]
    return {"class": c, "learners": learners, "hard_signs": hard,
            "note": "Summary of quiz and Practice Coach attempts only; recognition history and recordings are never shared."}
