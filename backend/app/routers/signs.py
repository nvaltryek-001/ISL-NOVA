"""Vocabulary: sign CRUD, verification workflow, translations, references, bookmarks."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..api import ApiError, Ctx, Router, not_found
from ..db import Conn, utcnow
from ..services import audit

router = Router("signs")

LANGS = ("en", "hi", "kn")
TRANSITIONS = {
    "proposed": {"reference_found", "review_pending", "rejected"},
    "reference_found": {"review_pending", "rejected"},
    "review_pending": {"verified", "rejected", "reference_found"},
    "verified": {"review_pending"},
    "rejected": {"review_pending"},
}
READINESS = ("no_data", "collecting", "insufficient_data", "ready_for_review", "approved_for_training", "excluded")
MIN_APPROVED_SAMPLES = 10
MIN_SIGNERS = 3
SIGN_ID_RE = re.compile(r"^ISL\d{3,4}$")

EDITABLE = ("canonical_sign_name", "category", "category_label", "linguistic_description", "dominant_hand",
            "hands_required", "movement_type", "body_movement", "non_manual_cue", "regional_variation",
            "annotation_notes")


class SignsQuery(BaseModel):
    q: str | None = Field(default=None, max_length=100)
    category: str | None = None
    status: str | None = None
    readiness: str | None = None
    include_retired: bool = False
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=200)


class SignIn(BaseModel):
    sign_id: str = Field(pattern=r"^ISL\d{3,4}$")
    canonical_sign_name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=60)
    category_label: str | None = Field(default=None, max_length=120)
    english_meaning: str | None = Field(default=None, max_length=200)
    linguistic_description: str | None = Field(default=None, max_length=4000)
    dominant_hand: str | None = Field(default=None, pattern="^(left|right|either)$")
    hands_required: str | None = Field(default=None, pattern="^(one|two)$")
    movement_type: str | None = Field(default=None, pattern="^(static|dynamic)$")
    body_movement: str | None = Field(default=None, max_length=1000)
    non_manual_cue: str | None = Field(default=None, max_length=1000)
    regional_variation: str | None = Field(default=None, max_length=2000)
    annotation_notes: str | None = Field(default=None, max_length=4000)


class SignPatch(BaseModel):
    canonical_sign_name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    category_label: str | None = Field(default=None, max_length=120)
    linguistic_description: str | None = Field(default=None, max_length=4000)
    dominant_hand: str | None = Field(default=None, pattern="^(left|right|either)$")
    hands_required: str | None = Field(default=None, pattern="^(one|two)$")
    movement_type: str | None = Field(default=None, pattern="^(static|dynamic)$")
    body_movement: str | None = Field(default=None, max_length=1000)
    non_manual_cue: str | None = Field(default=None, max_length=1000)
    regional_variation: str | None = Field(default=None, max_length=2000)
    annotation_notes: str | None = Field(default=None, max_length=4000)
    data_readiness: str | None = Field(default=None, pattern="^(excluded|auto)$")


class VerifyChecklist(BaseModel):
    reference_reviewed: bool = False   # watched the licensed reference recording(s)
    form_matches_reference: bool = False  # handshape, location, movement, orientation agree
    meaning_confirmed: bool = False    # the English meaning is an accurate gloss for this ISL sign


class ReviewIn(BaseModel):
    to_status: str = Field(pattern="^(proposed|reference_found|review_pending|verified|rejected)$")
    note: str = Field(min_length=3, max_length=2000)
    checklist: VerifyChecklist | None = None

VERIFY_REQUIRED_FIELDS = ("linguistic_description", "hands_required", "movement_type")


class TranslationIn(BaseModel):
    text: str = Field(max_length=300)
    status: str = Field(pattern="^(draft|verified|rejected)$")
    transliteration: str | None = Field(default=None, max_length=300)


class ReferenceIn(BaseModel):
    source_name: str = Field(min_length=1, max_length=120)
    source_url: str | None = Field(default=None, max_length=500, pattern=r"^https://")
    license: str = Field(min_length=1, max_length=120)
    media_type: str | None = Field(default=None, max_length=60)
    media_url: str | None = Field(default=None, max_length=500, pattern=r"^https://")
    training_permitted: str | None = Field(default=None, max_length=200)
    attribution: str | None = Field(default=None, max_length=500)


def translations_for(conn: Conn, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    out: dict[str, dict] = {i: {} for i in ids}
    for t in conn.all(f"SELECT sign_id, language, text, status, transliteration, source, reviewer FROM translations "
                      f"WHERE sign_id IN ({marks})", ids):
        out[t["sign_id"]][t["language"]] = {"text": t["text"], "status": t["status"],
                                            "transliteration": t["transliteration"], "source": t["source"],
                                            "reviewer": t["reviewer"]}
    return out


def sign_row(conn: Conn, sign_id: str) -> dict:
    s = conn.one("SELECT * FROM signs WHERE sign_id = ?", (sign_id,))
    if not s:
        raise not_found(f"sign {sign_id}")
    s["retired"] = bool(s["retired"])
    return s


def recompute_readiness(conn: Conn, sign_id: str) -> str:
    s = sign_row(conn, sign_id)
    if s["data_readiness"] == "excluded":
        return "excluded"
    c = conn.one(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN r.status = 'approved' THEN 1 ELSE 0 END) AS approved, "
        "SUM(CASE WHEN r.status = 'pending_review' THEN 1 ELSE 0 END) AS pending, "
        "COUNT(DISTINCT CASE WHEN r.status = 'approved' THEN rs.signer_id END) AS signers "
        "FROM recordings r JOIN recording_sessions rs ON rs.id = r.session_id "
        "WHERE r.sign_id = ? AND r.status NOT IN ('deleted', 'quarantined')", (sign_id,))
    total, approved, pending, signers = (int(c[k] or 0) for k in ("total", "approved", "pending", "signers"))
    if total == 0:
        state = "no_data"
    elif approved == 0:
        state = "ready_for_review" if pending else "collecting"
    elif approved < MIN_APPROVED_SAMPLES or signers < MIN_SIGNERS:
        state = "insufficient_data"
    elif s["verification_status"] == "verified":
        state = "approved_for_training"
    else:
        state = "ready_for_review"
    conn.update("signs", {"data_readiness": state, "updated_at": utcnow()}, "sign_id = ?", (sign_id,))
    return state


@router.get("/signs", summary="Search and filter the vocabulary", auth="optional", query=SignsQuery)
def list_signs(ctx: Ctx):
    q: SignsQuery = ctx.query
    where, params = [], []
    if not q.include_retired:
        where.append("s.retired = ?")
        params.append(False)
    if q.category:
        where.append("s.category = ?")
        params.append(q.category)
    if q.status:
        where.append("s.verification_status = ?")
        params.append(q.status)
    if q.readiness:
        where.append("s.data_readiness = ?")
        params.append(q.readiness)
    if q.q:
        like = f"%{q.q.strip().lower()}%"
        where.append("(LOWER(s.canonical_sign_name) LIKE ? OR LOWER(s.source_gloss) LIKE ? OR LOWER(s.sign_id) LIKE ? "
                     "OR s.sign_id IN (SELECT sign_id FROM translations WHERE LOWER(text) LIKE ?))")
        params += [like, like, like, like]
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = ctx.db.scalar(f"SELECT COUNT(*) FROM signs s{w}", params)
    rows = ctx.db.all(
        f"SELECT s.sign_id, s.canonical_sign_name, s.source_gloss, s.category, s.category_label, "
        f"s.verification_status, s.data_readiness, s.hands_required, s.movement_type, s.retired, "
        f"s.external_train_videos + s.external_val_videos + s.external_test_videos AS external_videos "
        f"FROM signs s{w} ORDER BY s.sign_id LIMIT ? OFFSET ?", (*params, q.size, (q.page - 1) * q.size))
    tr = translations_for(ctx.db, [r["sign_id"] for r in rows])
    marks = set()
    if ctx.user and rows:
        marks = {b["sign_id"] for b in ctx.db.all("SELECT sign_id FROM bookmarks WHERE user_id = ?", (ctx.uid,))}
    for r in rows:
        r["retired"] = bool(r["retired"])
        r["translations"] = tr[r["sign_id"]]
        r["bookmarked"] = r["sign_id"] in marks
    return {"items": rows, "total": total, "page": q.page, "size": q.size}


@router.get("/signs/review-sheet.csv", summary="CSV review sheet of all signs for offline linguistic review",
            perm="signs:review")
def review_sheet(ctx: Ctx):
    import csv
    import io

    from starlette.responses import Response

    rows = ctx.db.all("SELECT s.sign_id, s.canonical_sign_name, s.category_label, s.verification_status, s.data_readiness, "
                      "s.linguistic_description, s.hands_required, s.movement_type, s.non_manual_cue, s.regional_variation, "
                      "s.reviewer, s.approval_date FROM signs s WHERE s.retired = ? ORDER BY s.sign_id", (False,))
    tr = translations_for(ctx.db, [r["sign_id"] for r in rows])
    refs = {r["sign_id"]: r for r in ctx.db.all("SELECT sign_id, source_url, doi FROM sign_references")}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sign_id", "name", "category", "status", "readiness", "english", "hindi", "kannada", "description", "hands",
                "movement", "non_manual", "regional_variation", "reference", "reviewer", "approval_date",
                "reviewer_decision (verify/reject/needs_changes)", "reviewer_notes"])
    for r in rows:
        t = tr[r["sign_id"]]
        ref = refs.get(r["sign_id"], {})
        w.writerow([r["sign_id"], r["canonical_sign_name"], r["category_label"], r["verification_status"], r["data_readiness"],
                    t.get("en", {}).get("text", ""), t.get("hi", {}).get("text", ""), t.get("kn", {}).get("text", ""),
                    r["linguistic_description"] or "", r["hands_required"] or "", r["movement_type"] or "",
                    r["non_manual_cue"] or "", r["regional_variation"] or "", ref.get("source_url") or "",
                    r["reviewer"] or "", r["approval_date"] or "", "", ""])
    audit(ctx.db, ctx.uid, "sign.review_sheet_export", None, {"rows": len(rows)}, ctx.ip)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="isl-nova-review-sheet.csv"'})


@router.get("/signs/categories", summary="Categories with slot counts", auth="none")
def categories(ctx: Ctx):
    return ctx.db.all(
        "SELECT category, MAX(category_label) AS label, COUNT(*) AS slots, "
        "SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END) AS verified "
        "FROM signs WHERE retired = ? GROUP BY category ORDER BY MIN(sign_id)", (False,))


@router.get("/signs/{sign_id}", summary="Sign detail with references, translations and history", auth="optional")
def get_sign(ctx: Ctx):
    sid = ctx.params["sign_id"]
    s = sign_row(ctx.db, sid)
    s["translations"] = translations_for(ctx.db, [sid])[sid]
    s["references"] = ctx.db.all("SELECT * FROM sign_references WHERE sign_id = ? ORDER BY id", (sid,))
    s["verification_events"] = ctx.db.all(
        "SELECT v.from_status, v.to_status, v.note, v.created_at, u.display_name AS actor FROM verification_events v "
        "LEFT JOIN users u ON u.id = v.actor_id WHERE v.sign_id = ? ORDER BY v.id DESC LIMIT 50", (sid,))
    s["recordings"] = {r["status"]: r["n"] for r in ctx.db.all(
        "SELECT status, COUNT(*) AS n FROM recordings WHERE sign_id = ? GROUP BY status", (sid,))}
    s["related"] = ctx.db.all(
        "SELECT sign_id, canonical_sign_name, verification_status FROM signs WHERE category = ? AND sign_id <> ? "
        "AND retired = ? ORDER BY sign_id LIMIT 8", (s["category"], sid, False))
    s["bookmarked"] = bool(ctx.user and ctx.db.one(
        "SELECT 1 AS x FROM bookmarks WHERE user_id = ? AND sign_id = ?", (ctx.uid, sid)))
    return s


@router.post("/signs", summary="Create a vocabulary entry", perm="signs:write", body=SignIn, status=201)
def create_sign(ctx: Ctx):
    b: SignIn = ctx.body
    if ctx.db.one("SELECT sign_id FROM signs WHERE sign_id = ?", (b.sign_id,)):
        raise ApiError(409, "exists", f"{b.sign_id} already exists; sign ids are stable and never reused")
    from .proposals import key
    dup = next((s["sign_id"] for s in ctx.db.all("SELECT sign_id, canonical_sign_name FROM signs")
                if key(s["canonical_sign_name"]) == key(b.canonical_sign_name)), None)
    if dup:
        raise ApiError(409, "duplicate", f"a sign named '{b.canonical_sign_name}' already exists as {dup}")
    now = utcnow()
    with ctx.db.transaction():
        vals = {k: getattr(b, k) for k in EDITABLE}
        ctx.db.insert("signs", {"sign_id": b.sign_id, **vals, "verification_status": "proposed",
                                "data_readiness": "no_data", "created_at": now, "updated_at": now}, pk=None)
        for lang in LANGS:
            text = (b.english_meaning or "") if lang == "en" else ""
            ctx.db.insert("translations", {"sign_id": b.sign_id, "language": lang, "text": text,
                                           "status": "draft" if text else "pending", "updated_at": now})
        ctx.db.insert("verification_events", {"sign_id": b.sign_id, "from_status": None, "to_status": "proposed",
                                              "actor_id": ctx.uid, "note": "created", "created_at": now})
        audit(ctx.db, ctx.uid, "sign.create", b.sign_id, ip=ctx.ip)
    return get_sign(_with_param(ctx, b.sign_id))


@router.patch("/signs/{sign_id}", summary="Update descriptive fields of a sign", perm="signs:write", body=SignPatch)
def update_sign(ctx: Ctx):
    sid = ctx.params["sign_id"]
    s = sign_row(ctx.db, sid)
    b: SignPatch = ctx.body
    vals = {k: v for k, v in b.model_dump(exclude_unset=True).items() if k in EDITABLE}
    with ctx.db.transaction():
        if b.data_readiness == "excluded":
            vals["data_readiness"] = "excluded"
        vals["updated_at"] = utcnow()
        ctx.db.update("signs", vals, "sign_id = ?", (sid,))
        if b.data_readiness == "auto" and s["data_readiness"] == "excluded":
            ctx.db.update("signs", {"data_readiness": "no_data"}, "sign_id = ?", (sid,))
            recompute_readiness(ctx.db, sid)
        # a substantive change to a verified sign sends it back for review
        substantive = {"canonical_sign_name", "linguistic_description", "hands_required", "movement_type"}
        if s["verification_status"] == "verified" and substantive & set(vals):
            ctx.db.update("signs", {"verification_status": "review_pending"}, "sign_id = ?", (sid,))
            ctx.db.insert("verification_events", {"sign_id": sid, "from_status": "verified",
                                                  "to_status": "review_pending", "actor_id": ctx.uid,
                                                  "note": "edited after verification", "created_at": utcnow()})
        audit(ctx.db, ctx.uid, "sign.update", sid, {"fields": sorted(vals)}, ctx.ip)
    return get_sign(ctx)


@router.delete("/signs/{sign_id}", summary="Retire a sign (soft delete; ids are never reused)", perm="signs:write")
def retire_sign(ctx: Ctx):
    sid = ctx.params["sign_id"]
    sign_row(ctx.db, sid)
    n = ctx.db.scalar("SELECT COUNT(*) FROM recordings WHERE sign_id = ? AND status = 'approved'", (sid,))
    if n:
        raise ApiError(409, "has_approved_recordings", f"{sid} has {n} approved recordings; exclude it instead")
    ctx.db.update("signs", {"retired": True, "updated_at": utcnow()}, "sign_id = ?", (sid,))
    audit(ctx.db, ctx.uid, "sign.retire", sid, ip=ctx.ip)
    return {"sign_id": sid, "retired": True}


@router.post("/signs/{sign_id}/restore", summary="Restore a retired sign", perm="signs:write")
def restore_sign(ctx: Ctx):
    sid = ctx.params["sign_id"]
    sign_row(ctx.db, sid)
    ctx.db.update("signs", {"retired": False, "updated_at": utcnow()}, "sign_id = ?", (sid,))
    audit(ctx.db, ctx.uid, "sign.restore", sid, ip=ctx.ip)
    return {"sign_id": sid, "retired": False}


@router.post("/signs/{sign_id}/review", summary="Move a sign through the verification workflow",
             perm="signs:review", body=ReviewIn)
def review_sign(ctx: Ctx):
    sid = ctx.params["sign_id"]
    s = sign_row(ctx.db, sid)
    b: ReviewIn = ctx.body
    cur = s["verification_status"]
    if b.to_status not in TRANSITIONS.get(cur, set()):
        raise ApiError(409, "invalid_transition", f"cannot move from {cur} to {b.to_status}",
                       {"allowed": sorted(TRANSITIONS.get(cur, set()))})
    if b.to_status == "verified" and "linguist" not in ctx.roles:
        raise ApiError(403, "linguist_required", "only a qualified ISL reviewer (linguist role) can verify a sign")
    if b.to_status == "verified":
        missing = [f for f in VERIFY_REQUIRED_FIELDS if not s.get(f)]
        if missing:
            raise ApiError(422, "incomplete_entry", "document the sign before verifying it", {"missing_fields": missing})
        ck = b.checklist
        if not ck or not (ck.reference_reviewed and ck.form_matches_reference and ck.meaning_confirmed):
            raise ApiError(422, "checklist_incomplete", "all three verification checklist items must be confirmed")
    now = utcnow()
    vals: dict = {"verification_status": b.to_status, "updated_at": now}
    if b.to_status == "verified":
        vals.update(reviewer=ctx.user["display_name"], approval_date=now)
    with ctx.db.transaction():
        ctx.db.update("signs", vals, "sign_id = ?", (sid,))
        note = b.note if b.to_status != "verified" else f"{b.note} [checklist: reference reviewed, form matches, meaning confirmed]"
        ctx.db.insert("verification_events", {"sign_id": sid, "from_status": cur, "to_status": b.to_status,
                                              "actor_id": ctx.uid, "note": note, "created_at": now})
        recompute_readiness(ctx.db, sid)
        audit(ctx.db, ctx.uid, "sign.review", sid, {"from": cur, "to": b.to_status}, ctx.ip)
    return get_sign(ctx)


@router.put("/signs/{sign_id}/translations/{lang}", summary="Set a meaning in en/hi/kn",
            perm="translations:write", body=TranslationIn)
def set_translation(ctx: Ctx):
    sid, lang = ctx.params["sign_id"], ctx.params["lang"]
    if lang not in LANGS:
        raise ApiError(422, "validation_error", "language must be en, hi or kn")
    sign_row(ctx.db, sid)
    b: TranslationIn = ctx.body
    if b.status == "verified" and "linguist" not in ctx.roles:
        raise ApiError(403, "linguist_required", "only a linguist can mark a translation verified")
    if b.status == "verified" and not b.text.strip():
        raise ApiError(422, "validation_error", "a verified translation needs text")
    now = utcnow()
    vals = {"text": b.text.strip(), "status": b.status, "updated_at": now, "source": "human (app)",
            "reviewer": ctx.user["display_name"] if b.status in ("verified", "rejected") else None,
            "reviewed_at": now if b.status in ("verified", "rejected") else None}
    if b.transliteration is not None:
        vals["transliteration"] = b.transliteration.strip() or None
    if ctx.db.one("SELECT id FROM translations WHERE sign_id = ? AND language = ?", (sid, lang)):
        ctx.db.update("translations", vals, "sign_id = ? AND language = ?", (sid, lang))
    else:
        ctx.db.insert("translations", {"sign_id": sid, "language": lang, **vals})
    audit(ctx.db, ctx.uid, "translation.set", f"{sid}:{lang}", {"status": b.status}, ctx.ip)
    return translations_for(ctx.db, [sid])[sid]


@router.post("/signs/{sign_id}/references", summary="Attach a licensed reference source", perm="signs:write",
             body=ReferenceIn, status=201)
def add_reference(ctx: Ctx):
    sid = ctx.params["sign_id"]
    sign_row(ctx.db, sid)
    rid = ctx.db.insert("sign_references", {"sign_id": sid, **ctx.body.model_dump()})
    audit(ctx.db, ctx.uid, "sign.reference_add", sid, {"reference_id": rid}, ctx.ip)
    return ctx.db.one("SELECT * FROM sign_references WHERE id = ?", (rid,))


@router.delete("/signs/{sign_id}/references/{rid}", summary="Remove a reference", perm="signs:write")
def delete_reference(ctx: Ctx):
    n = ctx.db.execute("DELETE FROM sign_references WHERE id = ? AND sign_id = ?",
                       (int(ctx.params["rid"]), ctx.params["sign_id"])).rowcount
    if not n:
        raise not_found("reference")
    audit(ctx.db, ctx.uid, "sign.reference_delete", ctx.params["sign_id"], ip=ctx.ip)
    return {"ok": True}


@router.get("/bookmarks", summary="My bookmarked signs")
def bookmarks(ctx: Ctx):
    return ctx.db.all("SELECT s.sign_id, s.canonical_sign_name, s.category, s.verification_status, b.created_at "
                      "FROM bookmarks b JOIN signs s ON s.sign_id = b.sign_id WHERE b.user_id = ? "
                      "ORDER BY b.created_at DESC", (ctx.uid,))


@router.put("/bookmarks/{sign_id}", summary="Bookmark a sign")
def add_bookmark(ctx: Ctx):
    sid = ctx.params["sign_id"]
    sign_row(ctx.db, sid)
    if not ctx.db.one("SELECT 1 AS x FROM bookmarks WHERE user_id = ? AND sign_id = ?", (ctx.uid, sid)):
        ctx.db.insert("bookmarks", {"user_id": ctx.uid, "sign_id": sid, "created_at": utcnow()}, pk=None)
    return {"sign_id": sid, "bookmarked": True}


@router.delete("/bookmarks/{sign_id}", summary="Remove a bookmark")
def remove_bookmark(ctx: Ctx):
    ctx.db.execute("DELETE FROM bookmarks WHERE user_id = ? AND sign_id = ?", (ctx.uid, ctx.params["sign_id"]))
    return {"sign_id": ctx.params["sign_id"], "bookmarked": False}


def _with_param(ctx: Ctx, sign_id: str) -> Ctx:
    ctx.params = {**ctx.params, "sign_id": sign_id}
    return ctx
