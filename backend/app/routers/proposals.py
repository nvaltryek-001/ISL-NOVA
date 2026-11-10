"""Vocabulary growth: anyone signed in can propose a new sign; linguists accept or reject.

Accepting creates the next free stable ID (ISL201, ISL202, ...) with status
`proposed`; Hindi/Kannada meanings from the proposal are stored as drafts.
Duplicates (same normalised gloss as an existing sign or a pending proposal)
are refused.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..api import ApiError, Ctx, Router
from ..db import utcnow
from ..services import audit, notify

router = Router("proposals")


def key(s: str) -> str:
    return re.sub(r"[^a-z0-9ऀ-ॿಀ-೿]+", " ", s.casefold()).strip()


class ProposalIn(BaseModel):
    gloss: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=60, pattern=r"^[a-z_]+$")
    english_meaning: str | None = Field(default=None, max_length=200)
    hindi_meaning: str | None = Field(default=None, max_length=200)
    kannada_meaning: str | None = Field(default=None, max_length=200)
    reference_url: str | None = Field(default=None, max_length=500, pattern=r"^https://")
    notes: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(accept|reject)$")
    note: str | None = Field(default=None, max_length=2000)


def duplicate_of(db, gloss_key: str) -> str | None:
    for s in db.all("SELECT sign_id, canonical_sign_name FROM signs"):
        if key(s["canonical_sign_name"]) == gloss_key:
            return s["sign_id"]
    p = db.one("SELECT id FROM sign_proposals WHERE gloss_key = ? AND status = 'pending'", (gloss_key,))
    return f"proposal #{p['id']}" if p else None


@router.post("/vocabulary/proposals", summary="Propose a new vocabulary sign", body=ProposalIn, status=201, rate="default")
def propose(ctx: Ctx):
    b: ProposalIn = ctx.body
    k = key(b.gloss)
    if not k:
        raise ApiError(422, "validation_error", "gloss must contain letters")
    dup = duplicate_of(ctx.db, k)
    if dup:
        raise ApiError(409, "duplicate", f"'{b.gloss}' already exists as {dup}")
    pid = ctx.db.insert("sign_proposals", {**b.model_dump(), "gloss_key": k, "proposer_id": ctx.uid,
                                           "status": "pending", "created_at": utcnow()})
    audit(ctx.db, ctx.uid, "proposal.create", str(pid), {"gloss": b.gloss}, ctx.ip)
    return ctx.db.one("SELECT * FROM sign_proposals WHERE id = ?", (pid,))


@router.get("/vocabulary/proposals", summary="List proposals (reviewers see all, others their own)")
def list_proposals(ctx: Ctx):
    if "linguist" in ctx.roles or "admin" in ctx.roles:
        rows = ctx.db.all("SELECT * FROM sign_proposals ORDER BY id DESC LIMIT 500")
    else:
        rows = ctx.db.all("SELECT * FROM sign_proposals WHERE proposer_id = ? ORDER BY id DESC", (ctx.uid,))
    total = ctx.db.scalar("SELECT COUNT(*) FROM signs") or 0
    return {"items": rows, "vocabulary_size": int(total), "target": 500}


def next_sign_id(db) -> str:
    n = max(int(r["sign_id"][3:]) for r in db.all("SELECT sign_id FROM signs")) + 1
    return f"ISL{n:03d}"


@router.post("/vocabulary/proposals/{pid}/decide", summary="Accept or reject a proposal", perm="signs:write", body=DecisionIn)
def decide(ctx: Ctx):
    pid = int(ctx.params["pid"])
    p = ctx.db.one("SELECT * FROM sign_proposals WHERE id = ?", (pid,))
    if not p:
        raise ApiError(404, "not_found", "no such proposal")
    if p["status"] != "pending":
        raise ApiError(409, "already_decided", f"proposal is already {p['status']}")
    b: DecisionIn = ctx.body
    now = utcnow()
    if b.decision == "reject":
        if not (b.note or "").strip():
            raise ApiError(422, "validation_error", "a rejection needs a note for the proposer")
        ctx.db.update("sign_proposals", {"status": "rejected", "reviewer_id": ctx.uid, "decision_note": b.note,
                                         "decided_at": now}, "id = ?", (pid,))
        audit(ctx.db, ctx.uid, "proposal.reject", str(pid), None, ctx.ip)
    else:
        dup = next((s["sign_id"] for s in ctx.db.all("SELECT sign_id, canonical_sign_name FROM signs")
                    if key(s["canonical_sign_name"]) == p["gloss_key"]), None)
        if dup:
            raise ApiError(409, "duplicate", f"already exists as {dup}")
        with ctx.db.transaction():
            sid = next_sign_id(ctx.db)
            ctx.db.insert("signs", {"sign_id": sid, "canonical_sign_name": p["gloss"], "category": p["category"],
                                    "category_label": p["category"].replace("_", " ").title(),
                                    "verification_status": "proposed",
                                    "data_readiness": "no_data", "created_at": now, "updated_at": now}, pk=None)
            for lang, text in (("en", p["english_meaning"] or p["gloss"]), ("hi", p["hindi_meaning"]), ("kn", p["kannada_meaning"])):
                ctx.db.insert("translations", {"sign_id": sid, "language": lang, "text": text or "",
                                               "status": "draft" if text else "pending", "source": "proposal",
                                               "updated_at": now})
            ctx.db.insert("verification_events", {"sign_id": sid, "from_status": None, "to_status": "proposed",
                                                  "actor_id": ctx.uid, "note": f"accepted from proposal #{pid}", "created_at": now})
            ctx.db.update("sign_proposals", {"status": "accepted", "reviewer_id": ctx.uid, "decision_note": b.note,
                                             "created_sign_id": sid, "decided_at": now}, "id = ?", (pid,))
            audit(ctx.db, ctx.uid, "proposal.accept", str(pid), {"sign_id": sid}, ctx.ip)
    if p["proposer_id"]:
        notify(ctx.db, p["proposer_id"], f"Sign proposal {b.decision}ed", f"Your proposal '{p['gloss']}' was {b.decision}ed. {b.note or ''}".strip())
    return ctx.db.one("SELECT * FROM sign_proposals WHERE id = ?", (pid,))
