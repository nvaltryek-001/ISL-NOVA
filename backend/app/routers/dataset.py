"""Dataset Intelligence Lab: signers, consent, sessions, recordings, annotation
review, validation, statistics and versioned manifest export."""

from __future__ import annotations

import json
import re
from collections import Counter

from pydantic import BaseModel, Field
from starlette.responses import Response

from ..api import ApiError, Ctx, Router, not_found
from ..db import jdump, jload, utcnow
from ..services import VIDEO_TYPES, audit, new_code, notify, probe_video, quality_check, sha256, sniff_video
from .signs import MIN_APPROVED_SAMPLES, MIN_SIGNERS, READINESS, recompute_readiness, sign_row

router = Router("dataset")

CONSENT_SCOPES = {"recording_storage", "model_training", "research_display", "public_reference_media"}
CONSENT_TEXT_VERSIONS = {"isl-nova-consent-v1"}


class SignerIn(BaseModel):
    dominant_hand: str | None = Field(default=None, pattern="^(left|right|both)$")
    age_band: str | None = Field(default=None, pattern="^(18-25|26-35|36-50|51-65|65\\+)$")
    region: str | None = Field(default=None, max_length=80)
    deaf_status: str | None = Field(default=None, pattern="^(deaf|hard_of_hearing|hearing|coda|prefer_not_to_say)$")


class ConsentIn(BaseModel):
    consent_text_version: str = "isl-nova-consent-v1"
    scopes: list[str] = Field(min_length=1)
    retention_until: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}")
    confirmed_by_signer: bool


class RevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SessionIn(BaseModel):
    signer_id: int
    lighting: str | None = Field(default=None, max_length=60)
    background: str | None = Field(default=None, max_length=60)
    camera_distance: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=1000)


class RecQuery(BaseModel):
    sign_id: str | None = None
    status: str | None = None
    signer_id: int | None = None
    limit: int = Field(default=100, ge=1, le=500)


class AnnotationIn(BaseModel):
    recording_id: int
    label_sign_id: str
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class AnnotationReview(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|needs_changes)$")
    notes: str | None = Field(default=None, max_length=2000)


class AnnQuery(BaseModel):
    recording_id: int | None = None
    decision: str | None = None


class VersionIn(BaseModel):
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(min_length=3, max_length=1000)
    seed: int = 13


# --------------------------------------------------------------------------- stats

@router.get("/dataset/stats", summary="Truthful dataset readiness statistics", auth="none")
def stats(ctx: Ctx):
    c = ctx.db
    sl = c.one("SELECT COUNT(*) AS slots, "
               "SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END) AS verified, "
               "SUM(CASE WHEN verification_status = 'reference_found' THEN 1 ELSE 0 END) AS reference_found, "
               "SUM(CASE WHEN verification_status = 'review_pending' THEN 1 ELSE 0 END) AS review_pending, "
               "SUM(CASE WHEN verification_status = 'rejected' THEN 1 ELSE 0 END) AS rejected, "
               "SUM(external_train_videos + external_val_videos + external_test_videos) AS external_videos "
               "FROM signs WHERE retired = ?", (False,))
    readiness = {r: 0 for r in READINESS}
    for r in c.all("SELECT data_readiness, COUNT(*) AS n FROM signs WHERE retired = ? GROUP BY data_readiness", (False,)):
        readiness[r["data_readiness"]] = r["n"]
    rec = {r["status"]: r["n"] for r in c.all("SELECT status, COUNT(*) AS n FROM recordings GROUP BY status")}
    with_rec = c.scalar("SELECT COUNT(DISTINCT sign_id) FROM recordings WHERE status NOT IN ('deleted','quarantined')")
    per_class = c.all("SELECT sign_id, COUNT(*) AS n FROM recordings WHERE status = 'approved' GROUP BY sign_id")
    counts = [r["n"] for r in per_class]
    tr = {r["language"]: r["n"] for r in c.all(
        "SELECT language, COUNT(*) AS n FROM translations WHERE status = 'verified' GROUP BY language")}
    return {
        "class_slots": int(sl["slots"] or 0),
        "verified_classes": int(sl["verified"] or 0),
        "reference_found_classes": int(sl["reference_found"] or 0),
        "review_pending_classes": int(sl["review_pending"] or 0),
        "rejected_classes": int(sl["rejected"] or 0),
        "classes_with_recordings": int(with_rec or 0),
        "classes_approved_for_training": readiness["approved_for_training"],
        "readiness": readiness,
        "recordings": {"total": sum(rec.values()), **rec},
        "approved_samples": rec.get("approved", 0),
        "signers": c.scalar("SELECT COUNT(*) FROM pseudonymous_signers"),
        "sessions": c.scalar("SELECT COUNT(*) FROM recording_sessions"),
        "active_consents": c.scalar("SELECT COUNT(*) FROM consent_records WHERE revoked_at IS NULL"),
        "imbalance": {"min": min(counts) if counts else 0, "max": max(counts) if counts else 0,
                      "classes_with_approved": len(counts)},
        "verified_translations": {lang: tr.get(lang, 0) for lang in ("en", "hi", "kn")},
        "external_source": {"name": "INCLUDE (CC BY 4.0)", "videos_listed": int(sl["external_videos"] or 0),
                            "downloaded": False},
        "thresholds": {"min_approved_samples": MIN_APPROVED_SAMPLES, "min_signers": MIN_SIGNERS},
        "categories": c.all("SELECT category, COUNT(*) AS slots, "
                            "SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END) AS verified "
                            "FROM signs WHERE retired = ? GROUP BY category ORDER BY MIN(sign_id)", (False,)),
    }


@router.get("/dataset/signs", summary="Per-class readiness table", perm="dataset:read")
def dataset_signs(ctx: Ctx):
    return ctx.db.all(
        "SELECT s.sign_id, s.canonical_sign_name, s.category, s.verification_status, s.data_readiness, "
        "s.external_train_videos + s.external_val_videos + s.external_test_videos AS external_videos, "
        "COUNT(CASE WHEN r.status = 'approved' THEN 1 END) AS approved, "
        "COUNT(CASE WHEN r.status = 'pending_review' THEN 1 END) AS pending, "
        "COUNT(DISTINCT CASE WHEN r.status = 'approved' THEN rs.signer_id END) AS signers, "
        "COUNT(DISTINCT CASE WHEN r.status = 'approved' THEN r.session_id END) AS sessions "
        "FROM signs s LEFT JOIN recordings r ON r.sign_id = s.sign_id "
        "LEFT JOIN recording_sessions rs ON rs.id = r.session_id "
        "WHERE s.retired = ? GROUP BY s.sign_id, s.canonical_sign_name, s.category, s.verification_status, "
        "s.data_readiness, s.external_train_videos, s.external_val_videos, s.external_test_videos "
        "ORDER BY s.sign_id", (False,))


# --------------------------------------------------------------------------- signers + consent

def _consent_state(ctx: Ctx, signer_id: int) -> dict | None:
    c = ctx.db.one("SELECT * FROM consent_records WHERE signer_id = ? AND revoked_at IS NULL ORDER BY id DESC",
                   (signer_id,))
    if c:
        c["scopes"] = jload(c["scopes"])
        if c["retention_until"] and c["retention_until"][:10] < utcnow()[:10]:
            c["expired"] = True
    return c


@router.get("/dataset/signers", summary="Pseudonymous signers", perm="dataset:read")
def list_signers(ctx: Ctx):
    rows = ctx.db.all("SELECT s.*, (SELECT COUNT(*) FROM recording_sessions r WHERE r.signer_id = s.id) AS sessions, "
                      "(SELECT COUNT(*) FROM recordings x JOIN recording_sessions y ON y.id = x.session_id "
                      "WHERE y.signer_id = s.id AND x.status <> 'deleted') AS recordings "
                      "FROM pseudonymous_signers s ORDER BY s.id DESC")
    for r in rows:
        r["consent"] = _consent_state(ctx, r["id"])
    return rows


@router.post("/dataset/signers", summary="Register a pseudonymous signer (no names or contact data)",
             perm="dataset:write", body=SignerIn, status=201)
def create_signer(ctx: Ctx):
    code = new_code("SGN")
    sid = ctx.db.insert("pseudonymous_signers", {"signer_code": code, **ctx.body.model_dump(),
                                                 "created_by": ctx.uid, "created_at": utcnow()})
    audit(ctx.db, ctx.uid, "signer.create", code, ip=ctx.ip)
    return {**ctx.db.one("SELECT * FROM pseudonymous_signers WHERE id = ?", (sid,)), "consent": None}


@router.delete("/dataset/signers/{sid}", summary="Erase a signer and all their media", perm="dataset:write")
def delete_signer(ctx: Ctx):
    sid = int(ctx.params["sid"])
    s = ctx.db.one("SELECT * FROM pseudonymous_signers WHERE id = ?", (sid,))
    if not s:
        raise not_found("signer")
    in_versions = ctx.db.scalar("SELECT COUNT(*) FROM manifest_entries m JOIN recordings r ON r.id = m.recording_id "
                                "JOIN recording_sessions rs ON rs.id = r.session_id WHERE rs.signer_id = ?", (sid,))
    recs = ctx.db.all("SELECT r.id, r.sign_id, r.storage_key, r.landmarks_key FROM recordings r "
                      "JOIN recording_sessions rs ON rs.id = r.session_id WHERE rs.signer_id = ?", (sid,))
    for r in recs:
        _erase_media(ctx, r)
    with ctx.db.transaction():
        if in_versions:
            # published dataset versions keep their row ids for lineage; media are erased and rows tombstoned
            for r in recs:
                ctx.db.update("recordings", {"status": "deleted", "deleted_at": utcnow(), "storage_key": None,
                                             "landmarks_key": None}, "id = ?", (r["id"],))
            ctx.db.update("consent_records", {"revoked_at": utcnow(), "revocation_reason": "signer erased"},
                          "signer_id = ? AND revoked_at IS NULL", (sid,))
        else:
            # explicit dependency order: recordings reference consent records, which
            # PostgreSQL checks before cascading from the signer
            ctx.db.execute("DELETE FROM recordings WHERE session_id IN "
                           "(SELECT id FROM recording_sessions WHERE signer_id = ?)", (sid,))
            ctx.db.execute("DELETE FROM recording_sessions WHERE signer_id = ?", (sid,))
            ctx.db.execute("DELETE FROM consent_records WHERE signer_id = ?", (sid,))
            ctx.db.execute("DELETE FROM pseudonymous_signers WHERE id = ?", (sid,))
        for sign in {r["sign_id"] for r in recs}:
            recompute_readiness(ctx.db, sign)
        audit(ctx.db, ctx.uid, "signer.erase", s["signer_code"], {"recordings": len(recs)}, ctx.ip)
    return {"erased": s["signer_code"], "recordings_erased": len(recs), "tombstoned": bool(in_versions)}


@router.post("/dataset/signers/{sid}/consents", summary="Record informed consent", perm="dataset:write",
             body=ConsentIn, status=201)
def add_consent(ctx: Ctx):
    sid = int(ctx.params["sid"])
    if not ctx.db.one("SELECT id FROM pseudonymous_signers WHERE id = ?", (sid,)):
        raise not_found("signer")
    b: ConsentIn = ctx.body
    if not b.confirmed_by_signer:
        raise ApiError(422, "consent_not_confirmed", "the signer must explicitly confirm the consent text")
    if b.consent_text_version not in CONSENT_TEXT_VERSIONS:
        raise ApiError(422, "validation_error", "unknown consent text version")
    bad = set(b.scopes) - CONSENT_SCOPES
    if bad:
        raise ApiError(422, "validation_error", f"unknown scopes {sorted(bad)}")
    if "recording_storage" not in b.scopes:
        raise ApiError(422, "validation_error", "recording_storage scope is required to record")
    cid = ctx.db.insert("consent_records", {"signer_id": sid, "consent_text_version": b.consent_text_version,
                                            "scopes": jdump(sorted(set(b.scopes))), "retention_until": b.retention_until,
                                            "recorded_by": ctx.uid, "granted_at": utcnow()})
    audit(ctx.db, ctx.uid, "consent.grant", f"signer:{sid}", {"scopes": sorted(set(b.scopes))}, ctx.ip)
    c = ctx.db.one("SELECT * FROM consent_records WHERE id = ?", (cid,))
    c["scopes"] = jload(c["scopes"])
    return c


@router.post("/dataset/consents/{cid}/revoke", summary="Withdraw consent (erases that signer's media)",
             perm="dataset:write", body=RevokeIn)
def revoke_consent(ctx: Ctx):
    cid = int(ctx.params["cid"])
    c = ctx.db.one("SELECT * FROM consent_records WHERE id = ? AND revoked_at IS NULL", (cid,))
    if not c:
        raise not_found("active consent")
    recs = ctx.db.all("SELECT id, sign_id, storage_key, landmarks_key FROM recordings WHERE consent_id = ? "
                      "AND status <> 'deleted'", (cid,))
    for r in recs:
        _erase_media(ctx, r)
    with ctx.db.transaction():
        ctx.db.update("consent_records", {"revoked_at": utcnow(), "revocation_reason": ctx.body.reason}, "id = ?", (cid,))
        for r in recs:
            ctx.db.update("recordings", {"status": "deleted", "deleted_at": utcnow(), "storage_key": None,
                                         "landmarks_key": None}, "id = ?", (r["id"],))
        for sign in {r["sign_id"] for r in recs}:
            recompute_readiness(ctx.db, sign)
        audit(ctx.db, ctx.uid, "consent.revoke", f"consent:{cid}", {"recordings_erased": len(recs)}, ctx.ip)
    return {"revoked": cid, "recordings_erased": len(recs)}


# --------------------------------------------------------------------------- sessions

@router.get("/dataset/sessions", summary="Recording sessions", perm="dataset:read")
def list_sessions(ctx: Ctx):
    rows = ctx.db.all("SELECT rs.*, s.signer_code FROM recording_sessions rs JOIN pseudonymous_signers s "
                      "ON s.id = rs.signer_id ORDER BY rs.id DESC LIMIT 200")
    for r in rows:
        r["environment"] = jload(r["environment"])
    return rows


@router.post("/dataset/sessions", summary="Open a recording session", perm="dataset:write", body=SessionIn, status=201)
def create_session(ctx: Ctx):
    b: SessionIn = ctx.body
    if not ctx.db.one("SELECT id FROM pseudonymous_signers WHERE id = ?", (b.signer_id,)):
        raise not_found("signer")
    if not _consent_state(ctx, b.signer_id):
        raise ApiError(409, "no_consent", "signer has no active consent")
    env = {k: v for k, v in b.model_dump().items() if k in ("lighting", "background", "camera_distance") and v}
    sid = ctx.db.insert("recording_sessions", {"session_code": new_code("SES"), "signer_id": b.signer_id,
                                               "environment": jdump(env), "notes": b.notes, "created_by": ctx.uid,
                                               "created_at": utcnow()})
    r = ctx.db.one("SELECT * FROM recording_sessions WHERE id = ?", (sid,))
    r["environment"] = jload(r["environment"])
    return r


# --------------------------------------------------------------------------- recordings

def _erase_media(ctx: Ctx, r: dict) -> None:
    for k in ("storage_key", "landmarks_key"):
        if r.get(k):
            try:
                ctx.app.storage.delete(r[k])
            except ValueError:
                pass


@router.post("/dataset/recordings", summary="Upload a consented recording (video + optional landmarks)",
             perm="dataset:write", multipart=True, status=201)
def upload_recording(ctx: Ctx):
    f = ctx.form
    sign_id = str(f.get("sign_id") or "")
    try:
        session_id = int(f.get("session_id") or 0)
    except ValueError as exc:
        raise ApiError(422, "validation_error", "session_id must be an integer") from exc
    upload = f.get("file")
    if not sign_id or not session_id or upload is None or isinstance(upload, str):
        raise ApiError(422, "validation_error", "sign_id, session_id and file are required")
    sign = sign_row(ctx.db, sign_id)
    if sign["retired"]:
        raise ApiError(409, "retired", "cannot record a retired sign")
    sess = ctx.db.one("SELECT * FROM recording_sessions WHERE id = ?", (session_id,))
    if not sess:
        raise not_found("session")
    consent = _consent_state(ctx, sess["signer_id"])
    if not consent or consent.get("expired") or "recording_storage" not in consent["scopes"]:
        raise ApiError(409, "no_consent", "signer has no active consent covering recording storage")
    data = upload.file.read(ctx.app.settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > ctx.app.settings.max_upload_mb * 1024 * 1024:
        raise ApiError(413, "too_large", f"video exceeds {ctx.app.settings.max_upload_mb} MB")
    mime = sniff_video(data[:64])
    if mime is None:
        raise ApiError(415, "unsupported_media_type", "only MP4, WebM or MOV video is accepted")
    digest = sha256(data)
    dup = ctx.db.one("SELECT recording_code FROM recordings WHERE sha256 = ? AND status <> 'deleted'", (digest,))
    if dup:
        raise ApiError(409, "duplicate", f"identical file already stored as {dup['recording_code']}")
    probe = quality_check(probe_video(data, VIDEO_TYPES[mime]))
    if not probe.get("decodable"):
        raise ApiError(422, "undecodable", "the video could not be decoded")

    landmarks_key, lm_quality = None, None
    lm_raw = f.get("landmarks")
    code = new_code("REC")
    if lm_raw:
        lm_text = lm_raw if isinstance(lm_raw, str) else lm_raw.file.read(8 * 1024 * 1024).decode()
        landmarks_key, lm_quality = _store_landmarks(ctx, code, sign_id, lm_text)
    key = f"recordings/{sign_id}/{code}{VIDEO_TYPES[mime]}"
    ctx.app.storage.put(key, data)
    quality = {**probe, "landmarks": lm_quality}
    with ctx.db.transaction():
        rid = ctx.db.insert("recordings", {
            "recording_code": code, "sign_id": sign_id, "session_id": session_id, "consent_id": consent["id"],
            "source": "local", "storage_key": key, "landmarks_key": landmarks_key, "mime_type": mime,
            "size_bytes": len(data), "sha256": digest, "duration_s": probe.get("duration_s"), "fps": probe.get("fps"),
            "width": probe.get("width"), "height": probe.get("height"), "quality": jdump(quality),
            "status": "pending_review", "uploaded_by": ctx.uid, "created_at": utcnow()})
        recompute_readiness(ctx.db, sign_id)
        audit(ctx.db, ctx.uid, "recording.upload", code, {"sign_id": sign_id, "bytes": len(data)}, ctx.ip)
    return _rec(ctx, rid)


def _store_landmarks(ctx: Ctx, code: str, sign_id: str, text: str) -> tuple[str, dict]:
    from isl_nova_ml.data import save_landmarks
    from isl_nova_ml.features import extract_features

    try:
        payload = json.loads(text)
        frames, aspect = payload["frames"], float(payload.get("aspect", 1.0))
        if not isinstance(frames, list) or len(frames) > 900:
            raise ValueError("frames must be a list of at most 900 frames")
        fr = extract_features(frames, aspect)
    except (ValueError, KeyError, TypeError) as exc:
        raise ApiError(422, "invalid_landmarks", f"landmarks JSON rejected: {exc}") from exc
    key = f"landmarks/{sign_id}/{code}.npz"
    save_landmarks(ctx.app.storage.local_path(key), frames, aspect)
    return key, {"status": fr.status, "reasons": fr.reasons, "hand_frame_ratio": round(fr.hand_frame_ratio, 3),
                 "raw_frames": fr.raw_frames}


def _rec(ctx: Ctx, rid: int) -> dict:
    r = ctx.db.one("SELECT r.*, rs.session_code, s.signer_code, rs.signer_id FROM recordings r "
                   "JOIN recording_sessions rs ON rs.id = r.session_id "
                   "JOIN pseudonymous_signers s ON s.id = rs.signer_id WHERE r.id = ?", (rid,))
    if not r:
        raise not_found("recording")
    r["quality"] = jload(r["quality"])
    return r


@router.get("/dataset/recordings", summary="List recordings", perm="dataset:read", query=RecQuery)
def list_recordings(ctx: Ctx):
    q: RecQuery = ctx.query
    where, params = ["1 = 1"], []
    if q.sign_id:
        where.append("r.sign_id = ?")
        params.append(q.sign_id)
    if q.status:
        where.append("r.status = ?")
        params.append(q.status)
    if q.signer_id:
        where.append("rs.signer_id = ?")
        params.append(q.signer_id)
    rows = ctx.db.all(
        "SELECT r.id, r.recording_code, r.sign_id, r.status, r.duration_s, r.fps, r.width, r.height, r.size_bytes, "
        "r.quality, r.created_at, rs.session_code, s.signer_code, r.landmarks_key IS NOT NULL AS has_landmarks "
        "FROM recordings r JOIN recording_sessions rs ON rs.id = r.session_id "
        "JOIN pseudonymous_signers s ON s.id = rs.signer_id WHERE " + " AND ".join(where) +
        " ORDER BY r.id DESC LIMIT ?", (*params, q.limit))
    for r in rows:
        r["quality"] = jload(r["quality"])
        r["has_landmarks"] = bool(r["has_landmarks"])
    return rows


@router.get("/dataset/recordings/{rid}", summary="Recording detail", perm="dataset:read")
def get_recording(ctx: Ctx):
    r = _rec(ctx, int(ctx.params["rid"]))
    r["annotations"] = ctx.db.all("SELECT * FROM annotations WHERE recording_id = ? ORDER BY id", (r["id"],))
    return r


@router.get("/dataset/recordings/{rid}/media", summary="Stream recording media to authorised reviewers",
            perm="dataset:review")
def recording_media(ctx: Ctx):
    r = _rec(ctx, int(ctx.params["rid"]))
    if not r["storage_key"] or not ctx.app.storage.exists(r["storage_key"]):
        raise not_found("media")
    audit(ctx.db, ctx.uid, "recording.view_media", r["recording_code"], ip=ctx.ip)
    return Response(ctx.app.storage.get(r["storage_key"]), media_type=r["mime_type"],
                    headers={"Cache-Control": "no-store", "Content-Disposition": "inline"})


@router.delete("/dataset/recordings/{rid}", summary="Delete a recording and its media", perm="dataset:write")
def delete_recording(ctx: Ctx):
    r = _rec(ctx, int(ctx.params["rid"]))
    _erase_media(ctx, r)
    with ctx.db.transaction():
        ctx.db.update("recordings", {"status": "deleted", "deleted_at": utcnow(), "storage_key": None,
                                     "landmarks_key": None}, "id = ?", (r["id"],))
        recompute_readiness(ctx.db, r["sign_id"])
        audit(ctx.db, ctx.uid, "recording.delete", r["recording_code"], ip=ctx.ip)
    return {"deleted": r["recording_code"]}


# --------------------------------------------------------------------------- annotations

@router.get("/annotations", summary="Annotation review queue", perm="dataset:read", query=AnnQuery)
def list_annotations(ctx: Ctx):
    q: AnnQuery = ctx.query
    where, params = ["1 = 1"], []
    if q.recording_id:
        where.append("a.recording_id = ?")
        params.append(q.recording_id)
    if q.decision:
        where.append("a.decision = ?")
        params.append(q.decision)
    return ctx.db.all("SELECT a.*, r.recording_code, r.sign_id AS recording_sign_id, u.display_name AS annotator "
                      "FROM annotations a JOIN recordings r ON r.id = a.recording_id "
                      "LEFT JOIN users u ON u.id = a.annotator_id WHERE " + " AND ".join(where) +
                      " ORDER BY a.id DESC LIMIT 300", params)


@router.post("/annotations", summary="Annotate a recording", perm="dataset:write", body=AnnotationIn, status=201)
def create_annotation(ctx: Ctx):
    b: AnnotationIn = ctx.body
    r = _rec(ctx, b.recording_id)
    sign_row(ctx.db, b.label_sign_id)
    if r["status"] == "deleted":
        raise ApiError(409, "deleted", "recording was deleted")
    if b.start_ms is not None and b.end_ms is not None and b.end_ms <= b.start_ms:
        raise ApiError(422, "validation_error", "end_ms must be greater than start_ms")
    aid = ctx.db.insert("annotations", {**b.model_dump(), "annotator_id": ctx.uid, "created_at": utcnow()})
    audit(ctx.db, ctx.uid, "annotation.create", r["recording_code"], ip=ctx.ip)
    return ctx.db.one("SELECT * FROM annotations WHERE id = ?", (aid,))


@router.patch("/annotations/{aid}", summary="Review an annotation (four-eyes: not your own)",
              perm="dataset:review", body=AnnotationReview)
def review_annotation(ctx: Ctx):
    aid = int(ctx.params["aid"])
    a = ctx.db.one("SELECT * FROM annotations WHERE id = ?", (aid,))
    if not a:
        raise not_found("annotation")
    if a["annotator_id"] == ctx.uid:
        raise ApiError(403, "self_review", "annotations must be reviewed by someone other than the annotator")
    b: AnnotationReview = ctx.body
    r = _rec(ctx, a["recording_id"])
    with ctx.db.transaction():
        ctx.db.update("annotations", {"decision": b.decision, "reviewer_id": ctx.uid, "reviewed_at": utcnow(),
                                      "notes": b.notes or a["notes"]}, "id = ?", (aid,))
        if r["status"] in ("pending_review", "approved", "rejected"):
            if b.decision == "approved" and a["label_sign_id"] == r["sign_id"]:
                status = "approved"
            elif b.decision == "approved":
                status = "rejected"  # label disagrees with the requested sign
            else:
                status = "rejected" if b.decision == "rejected" else "pending_review"
            ctx.db.update("recordings", {"status": status}, "id = ?", (r["id"],))
        recompute_readiness(ctx.db, r["sign_id"])
        if a["annotator_id"]:
            notify(ctx.db, a["annotator_id"], f"Annotation {b.decision}", f"{r['recording_code']} ({r['sign_id']})")
        audit(ctx.db, ctx.uid, "annotation.review", r["recording_code"], {"decision": b.decision}, ctx.ip)
    return ctx.db.one("SELECT * FROM annotations WHERE id = ?", (aid,))


# --------------------------------------------------------------------------- validation + versions

@router.post("/dataset/validate", summary="Run dataset integrity, consent and leakage checks", perm="dataset:read")
def validate(ctx: Ctx):
    c = ctx.db
    issues: list[dict] = []
    ids = [r["sign_id"] for r in c.all("SELECT sign_id FROM signs WHERE retired = ? ORDER BY sign_id", (False,))]
    slot_ids = [i for i in ids if re.fullmatch(r"ISL\d{3}", i) and 1 <= int(i[3:]) <= 200]
    if len(slot_ids) != 200:
        issues.append({"level": "error", "check": "class_slots", "message": f"{len(slot_ids)} of 200 slots active"})
    checked = 0
    for r in c.all("SELECT id, recording_code, storage_key, landmarks_key, sha256, status FROM recordings "
                   "WHERE status NOT IN ('deleted')"):
        checked += 1
        if not r["storage_key"] or not ctx.app.storage.exists(r["storage_key"]):
            issues.append({"level": "error", "check": "media_missing", "message": r["recording_code"]})
            continue
        if sha256(ctx.app.storage.get(r["storage_key"])) != r["sha256"]:
            issues.append({"level": "error", "check": "checksum", "message": r["recording_code"]})
        if not r["landmarks_key"]:
            issues.append({"level": "warning", "check": "landmarks_missing", "message": r["recording_code"]})
    for d in c.all("SELECT sha256, COUNT(*) AS n FROM recordings WHERE status <> 'deleted' GROUP BY sha256 HAVING COUNT(*) > 1"):
        issues.append({"level": "error", "check": "duplicate", "message": f"{d['n']} files share sha {d['sha256'][:12]}"})
    for r in c.all("SELECT r.recording_code FROM recordings r JOIN consent_records cr ON cr.id = r.consent_id "
                   "WHERE cr.revoked_at IS NOT NULL AND r.status <> 'deleted'"):
        issues.append({"level": "error", "check": "revoked_consent", "message": r["recording_code"]})
    today = utcnow()[:10]
    for r in c.all("SELECT r.recording_code, cr.retention_until FROM recordings r JOIN consent_records cr "
                   "ON cr.id = r.consent_id WHERE cr.retention_until IS NOT NULL AND r.status <> 'deleted'"):
        if str(r["retention_until"])[:10] < today:
            issues.append({"level": "error", "check": "retention_expired",
                           "message": f"{r['recording_code']} retained past {str(r['retention_until'])[:10]}"})
    approved = c.all("SELECT r.sign_id, rs.signer_id FROM recordings r JOIN recording_sessions rs ON rs.id = r.session_id "
                     "WHERE r.status = 'approved'")
    signers = {a["signer_id"] for a in approved}
    if approved and len(signers) < 3:
        issues.append({"level": "warning", "check": "signer_independence",
                       "message": f"only {len(signers)} signer(s); a signer-independent split needs at least 3"})
    per = Counter(a["sign_id"] for a in approved)
    if per and max(per.values()) > 5 * max(1, min(per.values())):
        issues.append({"level": "warning", "check": "imbalance", "message": f"class sizes range {min(per.values())}-{max(per.values())}"})
    audit(ctx.db, ctx.uid, "dataset.validate", None, {"issues": len(issues)}, ctx.ip)
    return {"ok": not any(i["level"] == "error" for i in issues), "recordings_checked": checked,
            "issues": issues, "checked_at": utcnow()}


def _manifest_for_version(ctx: Ctx, vid: int) -> dict:
    v = ctx.db.one("SELECT * FROM dataset_versions WHERE id = ?", (vid,))
    if not v:
        raise not_found("dataset version")
    entries = ctx.db.all(
        "SELECT r.recording_code AS recording_id, m.sign_id, m.signer_code AS signer_id, m.session_code AS session_id, "
        "r.landmarks_key AS landmarks_path, r.sha256, m.split, cr.scopes FROM manifest_entries m "
        "JOIN recordings r ON r.id = m.recording_id JOIN consent_records cr ON cr.id = r.consent_id "
        "WHERE m.dataset_version_id = ? ORDER BY m.id", (vid,))
    for e in entries:
        e.update(source="local", license="project-consent", approved=True, consent_scope=jload(e.pop("scopes")))
    return {"dataset_version": v["version"], "feature_contract": v["contract_name"], "created_at": v["created_at"],
            "summary": jload(v["summary"]), "entries": entries}


@router.get("/dataset/versions", summary="Dataset versions", perm="dataset:read")
def list_versions(ctx: Ctx):
    rows = ctx.db.all("SELECT * FROM dataset_versions ORDER BY id DESC")
    for r in rows:
        r["summary"] = jload(r["summary"])
    return rows


@router.post("/dataset/versions", summary="Freeze approved, consented recordings into a versioned manifest",
             perm="dataset:version", body=VersionIn, status=201)
def create_version(ctx: Ctx):
    from isl_nova_ml.contract import CONTRACT_NAME, as_dict
    from isl_nova_ml.data import assign_splits, leakage_report

    b: VersionIn = ctx.body
    if ctx.db.one("SELECT id FROM dataset_versions WHERE version = ?", (b.version,)):
        raise ApiError(409, "exists", "version already exists; versions are immutable")
    rows = ctx.db.all(
        "SELECT r.id, r.recording_code, r.sign_id, r.landmarks_key, r.sha256, s.signer_code, rs.session_code, cr.scopes "
        "FROM recordings r JOIN recording_sessions rs ON rs.id = r.session_id "
        "JOIN pseudonymous_signers s ON s.id = rs.signer_id JOIN consent_records cr ON cr.id = r.consent_id "
        "WHERE r.status = 'approved' AND cr.revoked_at IS NULL AND r.landmarks_key IS NOT NULL ORDER BY r.id")
    eligible = [r for r in rows if "model_training" in (jload(r["scopes"]) or [])]
    if not eligible:
        raise ApiError(409, "no_eligible_recordings",
                       "no approved recordings with landmarks and model_training consent exist yet")
    split = assign_splits([{"recording_id": r["recording_code"], "signer_id": r["signer_code"],
                            "session_id": r["session_code"], "sha256": r["sha256"]} for r in eligible], seed=b.seed)
    leak = leakage_report(split)
    by_code = {s["recording_id"]: s["split"] for s in split}
    summary = {"recordings": len(eligible), "classes": len({r["sign_id"] for r in eligible}),
               "signers": len({r["signer_code"] for r in eligible}),
               "splits": dict(Counter(by_code.values())), "leakage": leak, "seed": b.seed,
               "excluded_without_training_consent": len(rows) - len(eligible)}
    with ctx.db.transaction():
        if not ctx.db.one("SELECT name FROM feature_contracts WHERE name = ?", (CONTRACT_NAME,)):
            fc = as_dict()
            ctx.db.insert("feature_contracts", {"name": CONTRACT_NAME, "version": fc["version"],
                                                "definition": jdump(fc), "created_at": utcnow()}, pk=None)
        vid = ctx.db.insert("dataset_versions", {"version": b.version, "description": b.description,
                                                 "contract_name": CONTRACT_NAME, "summary": jdump(summary),
                                                 "created_by": ctx.uid, "created_at": utcnow()})
        for r in eligible:
            ctx.db.insert("manifest_entries", {"dataset_version_id": vid, "recording_id": r["id"],
                                               "sign_id": r["sign_id"], "split": by_code[r["recording_code"]],
                                               "signer_code": r["signer_code"], "session_code": r["session_code"]})
        manifest = _manifest_for_version(ctx, vid)
        blob = json.dumps(manifest, indent=1).encode()
        ctx.app.storage.put(f"manifests/{b.version}.json", blob)
        ctx.db.update("dataset_versions", {"manifest_sha256": sha256(blob)}, "id = ?", (vid,))
        audit(ctx.db, ctx.uid, "dataset.version_create", b.version, summary, ctx.ip)
    v = ctx.db.one("SELECT * FROM dataset_versions WHERE id = ?", (vid,))
    v["summary"] = jload(v["summary"])
    return v


@router.get("/dataset/versions/{vid}/manifest", summary="Export a version's training manifest", perm="dataset:read")
def export_manifest(ctx: Ctx):
    return _manifest_for_version(ctx, int(ctx.params["vid"]))


@router.get("/dataset/feature-contract", summary="Active feature contract definition", auth="none")
def feature_contract(ctx: Ctx):
    from isl_nova_ml.contract import as_dict

    return as_dict()
